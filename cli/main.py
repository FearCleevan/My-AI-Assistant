"""
myai — Personal AI CLI
Run from any terminal, any folder on your PC.

Commands:
  myai ask "how does useState work?"
  myai ask --topic react "how does useState work?"
  myai ask --file src/App.tsx "what is wrong here?"
  myai learn react
  myai learn "firebase authentication" --pages 200
  myai topics
  myai chat
  myai chat --topic python
  myai models
"""
from __future__ import annotations
import argparse
import os
import sys
import threading

# Force UTF-8 output on Windows so Unicode box/emoji chars render correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path so all internal imports work
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import config  # noqa: E402  must come after sys.path patch


# ── ANSI colour helpers ───────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_BLUE   = "\033[94m"
_WHITE  = "\033[97m"
_GREY   = "\033[90m"


def _c(*parts) -> str:
    """Concatenate ANSI codes + text and append reset."""
    return "".join(str(p) for p in parts) + _RESET


def _hr(char: str = "─", width: int = 60) -> str:
    return _c(_GREY, char * width)


def _banner():
    print(_c(_CYAN, _BOLD, "╔" + "═" * 48 + "╗"))
    print(_c(_CYAN, _BOLD, "║") + _c(_WHITE, _BOLD, "   My AI Agent v2  —  myai CLI".center(48)) + _c(_CYAN, _BOLD, "║"))
    print(_c(_CYAN, _BOLD, "╚" + "═" * 48 + "╝"))
    print()


# ── Ollama check ──────────────────────────────────────────────────────────────

def _get_rag(storage_path: str | None = None) -> "RAGEngine":
    """Return a ready RAGEngine or exit with a helpful error."""
    from query.rag import RAGEngine
    rag   = RAGEngine(storage_path=storage_path or config.DATA_DIR)
    check = rag.check_ollama()
    if not check["ok"]:
        print(_c(_RED, f"\n✗  {check['reason']}"))
        print(_c(_YELLOW, f"   Fix: {check['suggestion']}"))
        sys.exit(1)
    return rag


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_ask(args):
    """Single-turn ask with optional file context and topic RAG search."""
    question = " ".join(args.question).strip()
    if not question:
        print(_c(_RED, "✗  Please provide a question."))
        sys.exit(1)

    topic        = args.topic or ""
    file_context = ""

    if args.file:
        from gui.chat_worker import parse_file
        try:
            file_context, label = parse_file(args.file)
            print(_c(_GREY, f"📎  Attached: {label}"))
        except ValueError as e:
            print(_c(_RED, f"✗  File error: {e}"))
            sys.exit(1)

    rag = _get_rag()

    print()
    print(_c(_BLUE, _BOLD, "You: ") + _c(_WHITE, question))
    print(_c(_GREEN, _BOLD, "AI:  "), end="", flush=True)

    def on_token(tok: str):
        print(tok, end="", flush=True)

    result = rag.chat(
        question     = question,
        topic        = topic,
        history      = [],
        file_context = file_context,
        on_token     = on_token,
    )
    print("\n")

    if result["sources"]:
        print(_c(_GREY, "Sources:"))
        for s in result["sources"]:
            print(_c(_GREY, f"  [{s['num']}] {s['title']}"))
            print(_c(_GREY, f"       {s['url']}"))
        print()


def cmd_learn(args):
    """Crawl and index a topic into ChromaDB."""
    from core.nlp_parser       import extract_topic
    from crawler.seed_urls     import get_seed_urls
    from crawler.agent         import CrawlerAgent
    from pipeline.chunker      import chunk_text
    from pipeline.embedder     import embed_chunks
    from storage.vector_store  import VectorStore
    from core.storage_monitor  import format_size, within_limit
    import signal

    raw_topic = " ".join(args.topic).strip()
    # Try NLP extraction, fall back to raw string
    topic = extract_topic(f"learn {raw_topic}") or raw_topic.lower().strip()

    print()
    print(_c(_CYAN, _BOLD, f"🌐  Learning: {topic}"))

    seed_urls = get_seed_urls(topic)
    if not seed_urls:
        print(_c(_RED, f"✗  No seed URLs configured for '{topic}'."))
        print(_c(_YELLOW, "   Edit crawler/seed_urls.py to add seeds, then retry."))
        sys.exit(1)

    max_pages    = args.pages or config.CRAWLER_MAX_PAGES
    storage_path = config.DATA_DIR
    limit_gb     = config.STORAGE_LIMIT_GB

    print(_c(_GREY, f"   Seeds  : {len(seed_urls)}  |  Max pages: {max_pages}  |  "
                    f"Storage limit: {limit_gb} GB"))
    for u in seed_urls:
        print(_c(_GREY, f"   → {u}"))
    print()

    stop_event = threading.Event()

    def _sigint(sig, frame):
        print(_c(_YELLOW, "\n\n⏹  Stopping crawl (Ctrl+C)…"))
        stop_event.set()

    signal.signal(signal.SIGINT, _sigint)

    vs = VectorStore(storage_path=storage_path)
    crawler = CrawlerAgent(
        topic      = topic,
        seed_urls  = seed_urls,
        max_pages  = max_pages,
        stop_event = stop_event,
    )

    raw_dir = os.path.join(storage_path, "raw_text", topic.replace(" ", "_"))
    os.makedirs(raw_dir, exist_ok=True)

    pages_done   = 0
    chunks_saved = 0

    for page in crawler.crawl():
        if stop_event.is_set():
            break

        ok, used, lim = within_limit(storage_path, limit_gb)
        if not ok:
            print(f"\n{_c(_YELLOW, f'⚠  Storage limit reached ({format_size(used)} / {format_size(lim)}). Stopping.')}")
            break

        pages_done += 1
        title = page.get("title", f"page_{pages_done}")[:70]

        # Progress line (overwrite same terminal line)
        pct = int(pages_done / max_pages * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(
            f"\r  {_c(_CYAN, f'[{pages_done:>4}/{max_pages}]')}  "
            f"{_c(_GREY, bar)}  {pct:>3}%  {_c(_WHITE, title[:45]):<55}",
            end="",
            flush=True,
        )

        # Save raw text
        fname = (
            page["url"]
            .replace("https://", "").replace("http://", "")
            .replace("/", "_")[:80] + ".txt"
        )
        raw_path = os.path.join(raw_dir, fname)
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(f"URL: {page['url']}\nTITLE: {page['title']}\n\n{page['text']}")

        # Chunk → embed → store
        chunks = chunk_text(page["text"], page["url"], page["title"], topic)
        chunks = embed_chunks(chunks)
        saved  = vs.save_chunks(chunks, topic)
        chunks_saved += saved

    print()  # end progress line
    print()

    if stop_event.is_set():
        print(_c(_YELLOW, f"⏹  Crawl stopped early — {pages_done} page(s), {chunks_saved} chunk(s) stored."))
    else:
        print(_c(_GREEN, _BOLD, f"✔  Done — {pages_done} page(s) crawled, {chunks_saved} chunk(s) stored in '{topic}'."))

    print()


def cmd_topics(args):
    """List all topics that have been learned."""
    from storage.vector_store import VectorStore

    vs     = VectorStore(storage_path=config.DATA_DIR)
    topics = vs.list_topics()

    if not topics:
        print(_c(_YELLOW, "\n  No topics learned yet."))
        print(_c(_GREY,   "  Run:  myai learn <topic>"))
        print()
        return

    print()
    print(_c(_BOLD, f"  {'Topic':<32}  {'Chunks':>8}  {'Pages (est)':>12}  {'Last scraped':>12}"))
    print(_c(_GREY, "  " + "─" * 70))

    topics_sorted = sorted(topics)
    for t in topics_sorted:
        stats = vs.get_topic_stats(t)
        print(
            f"  {_c(_CYAN, t):<41}  "
            f"{_c(_WHITE, stats['chunks']):>8}  "
            f"{_c(_GREY, stats['estimated_pages']):>12}  "
            f"{_c(_GREY, stats['last_scraped'] or '—'):>12}"
        )

    print()
    print(_c(_GREY, f"  {len(topics)} topic(s) total  |  Data: {config.DATA_DIR}"))
    print()


def cmd_chat(args):
    """Interactive multi-turn conversation REPL."""
    topic = args.topic or ""
    rag   = _get_rag()

    history: list[dict] = []

    _banner()
    if topic:
        print(_c(_GREY, f"  Knowledge base topic: {_c(_CYAN, topic)}"))
    print(_c(_GREY, "  Type your message and press Enter to send."))
    print(_c(_GREY, "  Commands:  /clear  /topic <name>  /exit"))
    print(_hr())
    print()

    while True:
        try:
            user_input = input(_c(_BLUE, _BOLD, "You: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print(_c(_GREY, "\n\nGoodbye!"))
            break

        if not user_input:
            continue

        # Slash commands
        if user_input.lower() in ("/exit", "/quit"):
            print(_c(_GREY, "Goodbye!"))
            break

        if user_input.lower() == "/clear":
            history.clear()
            print(_c(_GREY, "  [Conversation cleared]"))
            print()
            continue

        if user_input.lower().startswith("/topic "):
            topic = user_input[7:].strip()
            print(_c(_GREY, f"  [Topic set to: {_c(_CYAN, topic)}]"))
            print()
            continue

        if user_input.lower() in ("exit", "quit", "bye"):
            print(_c(_GREY, "Goodbye!"))
            break

        # Build history slice (current message excluded — passed as `question`)
        history.append({"role": "user", "content": user_input})

        print(_c(_GREEN, _BOLD, "AI:  "), end="", flush=True)

        full_answer = ""

        def on_token(tok: str):
            nonlocal full_answer
            full_answer += tok
            print(tok, end="", flush=True)

        result = rag.chat(
            question = user_input,
            topic    = topic,
            history  = history[:-1],   # history before this message
            on_token = on_token,
        )

        print("\n")
        history.append({"role": "assistant", "content": result["answer"]})

        if result["sources"]:
            print(_c(_GREY, f"  [{len(result['sources'])} source(s) from knowledge base]"))
            print()

        exchanges = len(history) // 2
        print(_c(_GREY, f"  [{exchanges} exchange(s) in session]"))
        print(_hr())
        print()


def cmd_serve(args):
    """Start the local API server for the VS Code extension."""
    port = args.port or 8765
    print(_c(_CYAN, _BOLD, f"\n  My AI Agent — API Server"))
    print(_c(_GREY, f"  Listening on  http://127.0.0.1:{port}"))
    print(_c(_GREY, f"  Docs at       http://127.0.0.1:{port}/docs"))
    print(_c(_GREY,  "  Press Ctrl+C to stop.\n"))

    try:
        import uvicorn
        from api.server import app
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except ImportError:
        print(_c(_RED, "✗  uvicorn not installed.  Run:  pip install uvicorn fastapi"))
        sys.exit(1)
    except KeyboardInterrupt:
        print(_c(_GREY, "\nServer stopped."))


def cmd_models(args):
    """List all Ollama models currently available."""
    from query.rag import RAGEngine

    rag    = RAGEngine()
    models = rag.list_ollama_models()

    if not models:
        print(_c(_YELLOW, "\n  No Ollama models found (is Ollama running?)."))
        print(_c(_GREY,   f"  Start with:  ollama serve"))
        print()
        return

    print()
    print(_c(_BOLD, f"  {'Model':<45}  Status"))
    print(_c(_GREY, "  " + "─" * 58))

    for m in models:
        is_default = config.LLM_MODEL in m
        status = _c(_GREEN, "● active (default)") if is_default else _c(_GREY, "○ available")
        print(f"  {_c(_CYAN, m):<54}  {status}")

    print()
    print(_c(_GREY, f"  Default model: {config.LLM_MODEL}  |  Change in GUI → Settings"))
    print()


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog    = "myai",
        description = "Your personal local AI assistant",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = """\
Examples:
  myai ask "How does useState work?"
  myai ask --topic react "What is useEffect?"
  myai ask --file src/App.tsx "What is wrong with this component?"
  myai learn react
  myai learn "firebase authentication" --pages 200
  myai topics
  myai chat
  myai chat --topic python
  myai models
  myai serve                   (start API server for VS Code extension)
  myai serve --port 9000
""",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── ask ──────────────────────────────────────────────────────────────────
    p_ask = sub.add_parser(
        "ask",
        help    = "Ask a single question (with optional file context)",
        description = "Query your AI with an optional knowledge base topic and/or attached file.",
    )
    p_ask.add_argument(
        "question", nargs="+",
        help = "The question to ask (quote multi-word questions)",
    )
    p_ask.add_argument(
        "--file", "-f", metavar="FILE",
        help = "Path to a file to attach as context (.py, .ts, .pdf, .json, .md, …)",
    )
    p_ask.add_argument(
        "--topic", "-t", metavar="TOPIC",
        help = "Knowledge base topic to search (e.g. react, firebase)",
    )
    p_ask.set_defaults(func=cmd_ask)

    # ── learn ─────────────────────────────────────────────────────────────────
    p_learn = sub.add_parser(
        "learn",
        help    = "Crawl and store a topic into your knowledge base",
        description = "Scrape documentation sites for a topic and embed them in ChromaDB.",
    )
    p_learn.add_argument(
        "topic", nargs="+",
        help = "Topic to learn (e.g. react, firebase, 'react native')",
    )
    p_learn.add_argument(
        "--pages", "-p", type=int, metavar="N",
        help = f"Max pages to crawl (default: {config.CRAWLER_MAX_PAGES})",
    )
    p_learn.set_defaults(func=cmd_learn)

    # ── topics ────────────────────────────────────────────────────────────────
    p_topics = sub.add_parser(
        "topics",
        help = "List all topics stored in your knowledge base",
    )
    p_topics.set_defaults(func=cmd_topics)

    # ── chat ──────────────────────────────────────────────────────────────────
    p_chat = sub.add_parser(
        "chat",
        help        = "Start an interactive multi-turn conversation",
        description = "REPL chat session. /clear resets history, /topic <name> changes scope.",
    )
    p_chat.add_argument(
        "--topic", "-t", metavar="TOPIC",
        help = "Knowledge base topic to include as context",
    )
    p_chat.set_defaults(func=cmd_chat)

    # ── models ────────────────────────────────────────────────────────────────
    p_models = sub.add_parser(
        "models",
        help = "List all Ollama models currently available",
    )
    p_models.set_defaults(func=cmd_models)

    # ── serve ─────────────────────────────────────────────────────────────────
    p_serve = sub.add_parser(
        "serve",
        help        = "Start the local API server (used by VS Code extension)",
        description = "Exposes a FastAPI REST server that the VS Code extension connects to.",
    )
    p_serve.add_argument(
        "--port", "-p", type=int, metavar="PORT", default=8765,
        help = "Port to listen on (default: 8765)",
    )
    p_serve.set_defaults(func=cmd_serve)

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = _build_parser()
    args   = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
