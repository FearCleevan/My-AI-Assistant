"""
My AI Agent — local REST API server.
Used by the VS Code extension (and any other client) to talk to the AI backend.

Start with:
    myai serve           (port 8765 by default)
    myai serve --port 9000

Endpoints
---------
GET  /health             — server + Ollama liveness
POST /chat/stream        — SSE streaming multi-turn chat
POST /ask                — single-turn RAG ask (no streaming)
GET  /topics             — list all learned topics
GET  /projects           — list all indexed projects
GET  /models             — list available Ollama models
"""
from __future__ import annotations
import asyncio
import json
import os
import queue as std_queue
import sys
import threading
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="My AI Agent API", version="2.0.0")

# Allow the VS Code extension (running in a webview on a different origin) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question:     str
    topic:        str  = ""
    history:      list[dict[str, str]] = []
    file_context: str  = ""
    model:        str | None = None


class AskRequest(BaseModel):
    question:     str
    topic:        str = ""
    file_context: str = ""


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    from query.rag import RAGEngine
    rag   = RAGEngine()
    check = rag.check_ollama()
    return {
        "ok":     check["ok"],
        "ollama": check["ok"],
        "model":  config.LLM_MODEL,
        "reason": check.get("reason", ""),
    }


# ── SSE chat streaming ────────────────────────────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Server-Sent Events endpoint.
    Each event is a JSON object on a 'data:' line:
      data: {"token": "..."}
      data: {"done": true, "sources": [...]}
    """
    sync_q: std_queue.Queue = std_queue.Queue()

    def _run_chat():
        try:
            from query.rag import RAGEngine
            rag = RAGEngine(storage_path=config.DATA_DIR)

            def on_token(tok: str):
                sync_q.put(("token", tok))

            result = rag.chat(
                question     = req.question,
                topic        = req.topic,
                history      = req.history,
                file_context = req.file_context,
                model        = req.model or None,
                on_token     = on_token,
            )
            sync_q.put(("done", result))
        except Exception as exc:
            sync_q.put(("error", str(exc)))

    thread = threading.Thread(target=_run_chat, daemon=True)
    thread.start()

    async def generate():
        loop = asyncio.get_event_loop()
        while True:
            try:
                item: tuple = await loop.run_in_executor(
                    None, lambda: sync_q.get(timeout=120)
                )
            except std_queue.Empty:
                yield "data: " + json.dumps({"error": "timeout"}) + "\n\n"
                break

            kind, data = item

            if kind == "token":
                yield "data: " + json.dumps({"token": data}) + "\n\n"
            elif kind == "done":
                yield "data: " + json.dumps({
                    "done":    True,
                    "sources": data.get("sources", []),
                }) + "\n\n"
                break
            elif kind == "error":
                yield "data: " + json.dumps({"error": data}) + "\n\n"
                break

    return StreamingResponse(
        generate(),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


# ── Single-turn ask ───────────────────────────────────────────────────────────

@app.post("/ask")
async def ask(req: AskRequest):
    loop = asyncio.get_event_loop()

    def _run():
        from query.rag import RAGEngine
        rag = RAGEngine(storage_path=config.DATA_DIR)
        return rag.ask(question=req.question, topic=req.topic)

    result = await loop.run_in_executor(None, _run)
    return result


# ── Topics ────────────────────────────────────────────────────────────────────

@app.get("/topics")
async def topics():
    from storage.vector_store import VectorStore
    loop = asyncio.get_event_loop()

    def _run():
        vs     = VectorStore(storage_path=config.DATA_DIR)
        names  = vs.list_topics()
        return [vs.get_topic_stats(t) for t in names]

    return {"topics": await loop.run_in_executor(None, _run)}


# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/projects")
async def projects():
    from indexer.project_indexer import load_all_projects
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: load_all_projects(config.DATA_DIR)
    )
    return {"projects": result}


# ── Ollama models ─────────────────────────────────────────────────────────────

@app.get("/models")
async def models():
    from query.rag import RAGEngine
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: RAGEngine().list_ollama_models())
    return {"models": result, "default": config.LLM_MODEL}
