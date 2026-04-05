"""
My AI Agent v2
Run:  python main.py
      python main.py --cli   (headless CLI fallback)
"""
import sys


def run_gui():
    from PyQt6.QtWidgets import QApplication
    from gui.app import MainWindow, STYLE
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def run_cli():
    """Original CLI REPL — kept as --cli fallback for headless environments."""
    import os, logging
    logging.basicConfig(level=logging.WARNING)

    import config
    from crawler.agent      import CrawlerAgent
    from crawler.seed_urls  import get_seed_urls
    from pipeline.chunker   import chunk_text
    from pipeline.embedder  import embed_chunks
    from storage.vector_store import VectorStore
    from query.rag          import RAGEngine

    HELP = """
╔══════════════════════════════════════════════════════════╗
║           Local AI Learning Agent v2 — CLI Mode          ║
╠══════════════════════════════════════════════════════════╣
║  learn <topic>               Start learning a topic      ║
║  ask <topic> <question>      Ask about a learned topic   ║
║  topics                      List all learned topics     ║
║  stats <topic>               Show storage stats          ║
║  help                        Show this message           ║
║  exit                        Quit                        ║
╚══════════════════════════════════════════════════════════╝
"""

    for d in [config.DATA_DIR, config.RAW_TEXT_DIR, config.VECTOR_DB_DIR]:
        os.makedirs(d, exist_ok=True)

    vector_store = VectorStore()
    print(HELP)

    while True:
        try:
            raw = input("agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not raw:
            continue
        parts = raw.split(maxsplit=1)
        cmd   = parts[0].lower()
        args  = parts[1] if len(parts) > 1 else ""

        if cmd in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        elif cmd == "help":
            print(HELP)

        elif cmd == "topics":
            topics = vector_store.list_topics()
            if topics:
                print("\n📚 Learned topics:")
                for t in topics:
                    s = vector_store.get_topic_stats(t)
                    print(f"   • {t} — {s['chunks']} chunks (~{s['estimated_pages']} pages)")
            else:
                print("  No topics yet. Use: learn <topic>")
            print()

        elif cmd == "stats":
            if not args:
                print("Usage: stats <topic>")
                continue
            s = vector_store.get_topic_stats(args)
            print(f"\n📊 {args}: {s['chunks']} chunks, ~{s['estimated_pages']} pages\n")

        elif cmd == "learn":
            if not args:
                print("Usage: learn <topic>")
                continue
            topic     = args
            seed_urls = get_seed_urls(topic)
            if not seed_urls:
                print(f"No pre-configured URLs for '{topic}'. Enter URLs (empty line to finish):")
                while True:
                    url = input("  URL: ").strip()
                    if not url:
                        break
                    seed_urls.append(url)
            if not seed_urls:
                print("No URLs provided.")
                continue
            print(f"\n🌐 Learning: '{topic}'")
            crawler = CrawlerAgent(topic=topic, seed_urls=seed_urls)
            total_chunks, total_pages = 0, 0
            for page in crawler.crawl():
                total_pages += 1
                print(f"  ✓ [{total_pages}] {page['title'][:55]} ({page['word_count']} words)")
                chunks = chunk_text(page["text"], page["url"], page["title"], topic)
                chunks = embed_chunks(chunks)
                total_chunks += vector_store.save_chunks(chunks, topic)
            print(f"\n✅ Done! {total_pages} pages, {total_chunks} chunks saved.\n")

        elif cmd == "ask":
            if not args:
                print("Usage: ask <topic> <question>")
                continue
            known   = vector_store.list_topics()
            matched, question = None, args
            for t in sorted(known, key=len, reverse=True):
                if args.lower().startswith(t.lower()):
                    matched  = t
                    question = args[len(t):].strip()
                    break
            if not matched:
                sub     = args.split(maxsplit=1)
                matched = sub[0]
                question = sub[1] if len(sub) > 1 else ""
            if not question:
                print("Please include a question.")
                continue
            rag    = RAGEngine()
            check  = rag.check_ollama()
            if not check["ok"]:
                print(f"\n❌ {check['reason']}\n   {check['suggestion']}\n")
                continue
            print("\n🔍 Searching knowledge base...")
            result = rag.ask(question, matched)
            print(f"\n{'─'*60}")
            print(f"💬 Answer:\n\n{result['answer']}")
            if result["sources"]:
                print(f"\n📚 Sources:")
                for s in result["sources"]:
                    print(f"   [{s['num']}] {s['title']} — {s['url']}")
            print(f"{'─'*60}\n")

        else:
            print(f"Unknown command: '{cmd}'. Type 'help'.")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        run_gui()
