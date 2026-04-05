import logging, requests, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.embedder import embed_query
from storage.vector_store import VectorStore

log = logging.getLogger(__name__)


class RAGEngine:
    def __init__(self, storage_path: str | None = None):
        self.vector_store = VectorStore(storage_path=storage_path)

    # ── Ollama ─────────────────────────────────────────────────────────────

    def check_ollama(self) -> dict:
        try:
            r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                if any(config.LLM_MODEL in m for m in models):
                    return {"ok": True, "reason": "", "suggestion": ""}
                return {
                    "ok": False,
                    "reason": f"Model '{config.LLM_MODEL}' not found in Ollama.",
                    "suggestion": f"Run:  ollama pull {config.LLM_MODEL}",
                }
        except requests.ConnectionError:
            return {
                "ok": False,
                "reason": "Ollama is not running.",
                "suggestion": f"Start Ollama, then run:  ollama pull {config.LLM_MODEL}",
            }
        except Exception as e:
            return {"ok": False, "reason": str(e), "suggestion": "Check your Ollama installation."}
        return {"ok": False, "reason": "Unknown error.", "suggestion": ""}

    def list_ollama_models(self) -> list[str]:
        """Return all model names currently available in Ollama."""
        try:
            r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            if r.status_code == 200:
                return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            pass
        return []

    def _call_ollama(self, prompt: str, model: str | None = None) -> str:
        model = model or config.LLM_MODEL
        try:
            r = requests.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model":   model,
                    "prompt":  prompt,
                    "stream":  False,
                    "options": {
                        "temperature": config.LLM_TEMPERATURE,
                        "num_predict": config.LLM_MAX_TOKENS,
                    },
                },
                timeout=300,
            )
            if r.status_code == 200:
                return r.json().get("response", "").strip()
            return f"[LLM Error: HTTP {r.status_code}]"
        except requests.ConnectionError:
            return "[Error] Cannot connect to Ollama. Make sure it is running: ollama serve"

    def _call_ollama_stream(self, prompt: str, model: str | None = None, on_token=None) -> str:
        """
        Stream response token by token.
        on_token(str) is called for each chunk so the UI can update live.
        Returns the full completed response string.
        """
        model = model or config.LLM_MODEL
        full  = ""
        try:
            with requests.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model":   model,
                    "prompt":  prompt,
                    "stream":  True,
                    "options": {
                        "temperature": config.LLM_TEMPERATURE,
                        "num_predict": config.LLM_MAX_TOKENS,
                    },
                },
                stream=True,
                timeout=300,
            ) as r:
                import json as _json
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data  = _json.loads(line)
                        token = data.get("response", "")
                        full += token
                        if on_token and token:
                            on_token(token)
                        if data.get("done"):
                            break
                    except Exception:
                        continue
        except requests.ConnectionError:
            err = "[Error] Cannot connect to Ollama."
            if on_token:
                on_token(err)
            return err
        return full

    # ── Prompt builders ────────────────────────────────────────────────────

    def _build_chat_prompt(
        self,
        question:     str,
        chunks:       list,
        history:      list[dict],
        file_context: str = "",
    ) -> str:
        """
        Build a full conversational prompt with:
          - RAG context from ChromaDB
          - Attached file content (if any)
          - Full chat history (alternating user/assistant)
          - Current question
        """
        parts = [
            "You are a highly capable AI coding assistant with access to a private knowledge base.\n"
            "You can answer questions, explain concepts, generate complete working code (any length),\n"
            "debug issues, and reason step-by-step. Always be thorough and precise.\n"
        ]

        # RAG knowledge base context
        if chunks:
            ctx_parts = []
            for i, c in enumerate(chunks, 1):
                snippet = c["text"][:600].replace("\n", " ")
                ctx_parts.append(f"[{i}] {c['title']}\n{snippet}...")
            parts.append("=== KNOWLEDGE BASE ===\n" + "\n\n".join(ctx_parts) + "\n=== END KNOWLEDGE BASE ===\n")

        # Attached file context
        if file_context.strip():
            parts.append(
                "=== ATTACHED FILE ===\n" + file_context.strip() + "\n=== END ATTACHED FILE ===\n\n"
                "FILE OPERATION RULES: When your response requires creating or modifying a file, "
                "output the COMPLETE file content wrapped in exactly this format:\n"
                "<file_write path=\"relative/path/to/file.ext\">\n"
                "... complete file content ...\n"
                "</file_write>\n"
                "Rules: (1) path must be relative to the workspace root, "
                "(2) always include the FULL file content — never partial, "
                "(3) you may include multiple <file_write> blocks if several files need changes, "
                "(4) only use this format when actually writing or creating a file."
            )

        # Conversation history
        if history:
            hist_lines = []
            for msg in history[-20:]:   # keep last 20 exchanges to stay within token limit
                role    = "User" if msg["role"] == "user" else "Assistant"
                hist_lines.append(f"{role}: {msg['content']}")
            parts.append("=== CONVERSATION HISTORY ===\n" + "\n\n".join(hist_lines) + "\n=== END HISTORY ===\n")

        parts.append(f"User: {question}\n\nAssistant:")
        return "\n\n".join(parts)

    def _build_simple_prompt(self, question: str, chunks: list, file_context: str = "") -> str:
        """Single-turn prompt (no history) — used by the Ask tab."""
        if not chunks and not file_context:
            return (
                "You are a helpful technical assistant.\n"
                f"Answer the following question:\n\nQuestion: {question}\n\nAnswer:"
            )
        parts = ["You are a helpful technical assistant. Answer using the context below. "
                 "Cite sources inline as [1], [2], etc.\n"]
        if chunks:
            ctx = "\n\n---\n\n".join(
                f"[{i}] Source: {c['title']}\nURL: {c['url']}\n{c['text'][:400]}..."
                for i, c in enumerate(chunks, 1)
            )
            parts.append(f"=== CONTEXT ===\n{ctx}\n=== END CONTEXT ===\n")
        if file_context.strip():
            parts.append(f"=== ATTACHED FILE ===\n{file_context.strip()}\n=== END ATTACHED FILE ===\n")
        parts.append(f"Question: {question}\n\nAnswer (cite facts with [N]):")
        return "\n\n".join(parts)

    # ── Public API ─────────────────────────────────────────────────────────

    def ask(self, question: str, topic: str, offline_only: bool = False) -> dict:
        """Single-turn ask (Ask tab). Returns answer + numbered sources."""
        query_vec = embed_query(question)
        chunks    = self.vector_store.search(query_vec, topic)

        if not chunks and offline_only:
            return {
                "answer":       f"No stored knowledge found for '{topic}'. Run 'learn {topic}' first.",
                "sources":      [],
                "chunks_found": 0,
            }

        answer  = self._call_ollama(self._build_simple_prompt(question, chunks))
        sources, seen = [], set()
        for i, c in enumerate(chunks, 1):
            if c["url"] not in seen:
                sources.append({"num": i, "title": c["title"], "url": c["url"]})
                seen.add(c["url"])

        return {"answer": answer, "sources": sources, "chunks_found": len(chunks)}

    def chat(
        self,
        question:     str,
        topic:        str,
        history:      list[dict],
        file_context: str = "",
        model:        str | None = None,
        on_token=None,
    ) -> dict:
        """
        Multi-turn conversational ask (Chat tab).
        Streams tokens if on_token callback provided.
        Returns {"answer": str, "sources": list, "chunks_found": int}
        """
        query_vec = embed_query(question)
        chunks    = self.vector_store.search(query_vec, topic) if topic else []

        prompt = self._build_chat_prompt(question, chunks, history, file_context)

        if on_token:
            answer = self._call_ollama_stream(prompt, model=model, on_token=on_token)
        else:
            answer = self._call_ollama(prompt, model=model)

        sources, seen = [], set()
        for i, c in enumerate(chunks, 1):
            if c["url"] not in seen:
                sources.append({"num": i, "title": c["title"], "url": c["url"]})
                seen.add(c["url"])

        return {"answer": answer, "sources": sources, "chunks_found": len(chunks)}
