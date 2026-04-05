"""
Background QThread workers — crawl and ask run here so the GUI stays responsive.
"""
from __future__ import annotations
import os, sys, time, threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core.storage_monitor import get_folder_size, format_size, within_limit
from crawler.agent        import CrawlerAgent
from crawler.seed_urls    import get_seed_urls
from pipeline.chunker     import chunk_text
from pipeline.embedder    import embed_chunks
from storage.vector_store import VectorStore
from query.rag            import RAGEngine

from PyQt6.QtCore import QThread, pyqtSignal


class CrawlWorker(QThread):
    log_sig      = pyqtSignal(str, str)   # (message, level)  level: info/ok/warn/err
    status_sig   = pyqtSignal(str)
    eta_sig      = pyqtSignal(str)
    progress_sig = pyqtSignal(int, int)   # (current, total)
    storage_sig  = pyqtSignal(int, int)   # (used_bytes, limit_bytes)
    done_sig     = pyqtSignal(int, int)   # (pages, chunks)

    def __init__(self, topic: str, storage_path: str, limit_gb: float, max_pages: int):
        super().__init__()
        self.topic        = topic
        self.storage_path = storage_path
        self.limit_gb     = limit_gb
        self.max_pages    = max_pages
        self._stop        = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        pages_done   = 0
        chunks_saved = 0
        page_times: list[float] = []

        def log(msg, level="info"):
            self.log_sig.emit(str(msg), level)

        try:
            seed_urls = get_seed_urls(self.topic)
            if not seed_urls:
                log(f"No pre-configured seed URLs for '{self.topic}'.", "warn")
                log("Add entries to crawler/seed_urls.py, then re-run.", "warn")
                self.done_sig.emit(0, 0)
                return

            log(f"Seeds found: {len(seed_urls)}", "info")
            for u in seed_urls:
                log(f"  -> {u}", "info")

            vs      = VectorStore(storage_path=self.storage_path)
            crawler = CrawlerAgent(
                topic=self.topic,
                seed_urls=seed_urls,
                max_pages=self.max_pages,
                stop_event=self._stop,
            )
            raw_dir = os.path.join(self.storage_path, "raw_text", self.topic.replace(" ", "_"))
            os.makedirs(raw_dir, exist_ok=True)

            limit_bytes = int(self.limit_gb * 1024 ** 3)

            for page in crawler.crawl():
                if self._stop.is_set():
                    break

                ok, used, lim = within_limit(self.storage_path, self.limit_gb)
                self.storage_sig.emit(used, lim)
                if not ok:
                    log(f"Storage limit reached ({format_size(used)} / {format_size(lim)}). Stopping.", "warn")
                    break

                t0 = time.monotonic()
                pages_done += 1

                # ETA
                page_times.append(time.monotonic() - t0 + config.CRAWLER_DELAY_SECONDS)
                if len(page_times) > 10:
                    page_times.pop(0)
                avg      = sum(page_times) / len(page_times)
                remaining = max(0, self.max_pages - pages_done)
                eta_s    = remaining * avg
                eta_str  = f"~{int(eta_s // 60)}m {int(eta_s % 60)}s remaining" if eta_s > 1 else "Almost done"

                log(f"[{pages_done:03d}] {page['title'][:58]}  ({page['word_count']:,} words)", "ok")
                self.status_sig.emit(
                    f"Crawling...  {pages_done} pages  |  "
                    f"{format_size(get_folder_size(self.storage_path))} used"
                )
                self.eta_sig.emit(eta_str)
                self.progress_sig.emit(pages_done, self.max_pages)

                # Save raw
                fname = (
                    page["url"]
                    .replace("https://", "").replace("http://", "")
                    .replace("/", "_")[:80] + ".txt"
                )
                with open(os.path.join(raw_dir, fname), "w", encoding="utf-8") as f:
                    f.write(f"URL: {page['url']}\nTITLE: {page['title']}\n\n{page['text']}")

                # Embed + store
                chunks = chunk_text(page["text"], page["url"], page["title"], self.topic)
                chunks = embed_chunks(chunks)
                saved  = vs.save_chunks(chunks, self.topic)
                chunks_saved += saved
                log(f"    -> {saved} new chunks stored", "info")

        except Exception as e:
            import traceback
            log(f"Crawl error: {e}", "err")
            log(traceback.format_exc(), "err")

        self.done_sig.emit(pages_done, chunks_saved)


class AskWorker(QThread):
    answer_sig = pyqtSignal(str, list)   # (answer_text, sources_list)
    status_sig = pyqtSignal(str)
    error_sig  = pyqtSignal(str)

    def __init__(self, topic: str, question: str, storage_path: str):
        super().__init__()
        self.topic        = topic
        self.question     = question
        self.storage_path = storage_path

    def run(self):
        try:
            rag   = RAGEngine(storage_path=self.storage_path)
            check = rag.check_ollama()
            if not check["ok"]:
                self.error_sig.emit(f"{check['reason']}\n\nFix: {check['suggestion']}")
                return

            result = rag.ask(self.question, self.topic)
            self.answer_sig.emit(result["answer"], result["sources"])
            self.status_sig.emit(f"Done — {result['chunks_found']} relevant chunks found.")
        except Exception as e:
            self.error_sig.emit(str(e))
