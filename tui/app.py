"""
My AI Agent v2 — Textual TUI
Run with:  python main.py
"""
from __future__ import annotations

import os, sys, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core.nlp_parser     import extract_topic
from core.storage_monitor import get_folder_size, format_size, usage_bar, within_limit
from core.scheduler      import TopicScheduler
from crawler.agent       import CrawlerAgent
from crawler.seed_urls   import get_seed_urls
from pipeline.chunker    import chunk_text
from pipeline.embedder   import embed_chunks, embed_query
from storage.vector_store import VectorStore
from query.rag           import RAGEngine

from textual            import on, work
from textual.app        import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets    import (
    Button, DataTable, Footer, Header, Input,
    Label, ProgressBar, RichLog, Select, Static,
    TabbedContent, TabPane, Rule,
)
from textual.worker import get_current_worker


# ─────────────────────────────────────────────────────────────────────────────
class AIAgentApp(App):

    TITLE = "My AI Agent v2"
    BINDINGS = [
        ("ctrl+q", "quit",     "Quit"),
        ("f5",     "refresh",  "Refresh"),
    ]

    DEFAULT_CSS = """
    Screen { background: $surface; }

    #sidebar {
        width: 24;
        background: $panel;
        border-right: solid $primary-darken-2;
        padding: 1 1;
    }
    .sb-head { color: $primary; text-style: bold; margin-bottom: 1; }
    #sb-topics  { color: $text; margin-bottom: 1; }
    #sb-storage { color: $text-muted; }

    #main { width: 1fr; padding: 0 1; }

    TabbedContent { height: 1fr; }

    .tab-head { color: $primary; text-style: bold; margin-bottom: 1; }
    .lbl { color: $text-muted; margin: 0; }

    Input  { margin-bottom: 1; }
    Select { margin-bottom: 1; }
    Button { margin: 0 1 1 0; }

    #activity-log { height: 12; border: solid $primary-darken-2; margin-top: 1; }
    #answer-log   { height: 16; border: solid $primary-darken-2; margin-top: 1; padding: 1; }
    #sources-log  { height: 6;  border: solid $primary-darken-3; margin-top: 0;  color: $text-muted; }

    ProgressBar { margin: 0 0 1 0; }

    #status-lbl { color: $warning;    margin-bottom: 0; }
    #eta-lbl    { color: $text-muted; margin-bottom: 1; }
    #ask-status { color: $warning;    margin-bottom: 0; }

    DataTable { height: 14; margin-top: 1; }
    #sched-table { height: 10; margin-top: 1; }

    .ok    { color: $success; }
    .err   { color: $error;   }
    .warn  { color: $warning; }
    """

    # ── Init ─────────────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self._cfg         = config.load_all()
        self._stop_event  = threading.Event()
        self._topic_rows: list[str] = []   # topic names in DataTable order
        self._scheduler   = TopicScheduler(on_trigger=self._on_schedule_fire)
        self._scheduler.load_from_config(self._cfg.get("SCHEDULES", {}))
        self._scheduler.start()

    # ── Layout ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            # ── Sidebar ──────────────────────────────────────────────────────
            with Vertical(id="sidebar"):
                yield Label("📚 Topics", classes="sb-head")
                yield Static("(none)", id="sb-topics")
                yield Rule()
                yield Label("💾 Storage", classes="sb-head")
                yield Static("...", id="sb-storage")

            # ── Main tabs ────────────────────────────────────────────────────
            with Vertical(id="main"):
                with TabbedContent():

                    # ── LEARN ────────────────────────────────────────────────
                    with TabPane("🌐 Learn", id="t-learn"):
                        yield Label("What do you want to learn?", classes="tab-head")
                        yield Input(
                            placeholder='"Learn everything about React JS and its framework"',
                            id="learn-input",
                        )
                        with Horizontal():
                            with Vertical():
                                yield Label("Storage Limit", classes="lbl")
                                yield Select(
                                    [("2 GB","2"),("5 GB","5"),("10 GB","10"),("20 GB","20")],
                                    value=str(int(self._cfg.get("STORAGE_LIMIT_GB", 5))),
                                    allow_blank=False,
                                    id="limit-sel",
                                )
                            with Vertical():
                                yield Label("Storage Path", classes="lbl")
                                yield Input(
                                    value=self._cfg.get("DATA_DIR", ""),
                                    placeholder=r"e.g. E:\my_data",
                                    id="path-input",
                                )
                            with Vertical():
                                yield Label("Max Pages", classes="lbl")
                                yield Input(
                                    value=str(self._cfg.get("CRAWLER_MAX_PAGES", 150)),
                                    placeholder="150",
                                    id="maxpages-input",
                                )
                        with Horizontal():
                            yield Button("▶  Start Learning", id="btn-start", variant="primary")
                            yield Button("⏹  Stop",          id="btn-stop",  variant="error", disabled=True)
                        yield Label("",        id="status-lbl")
                        yield ProgressBar(total=150, show_eta=False, id="crawl-bar")
                        yield Label("Ready.", id="eta-lbl")
                        yield Label("Activity Log", classes="lbl")
                        yield RichLog(id="activity-log", highlight=True, markup=True)

                    # ── ASK ──────────────────────────────────────────────────
                    with TabPane("💬 Ask", id="t-ask"):
                        yield Label("Ask Your AI", classes="tab-head")
                        with Horizontal():
                            with Vertical():
                                yield Label("Topic (type name)", classes="lbl")
                                yield Input(placeholder="e.g. React JS", id="ask-topic")
                            with Vertical():
                                yield Label("Question", classes="lbl")
                                yield Input(
                                    placeholder="What is useState and how do I use it?",
                                    id="ask-question",
                                )
                        yield Label("", id="ask-available")
                        yield Button("🔍  Ask", id="btn-ask", variant="primary")
                        yield Label("", id="ask-status")
                        yield Label("Answer", classes="lbl")
                        yield RichLog(id="answer-log", highlight=True, markup=True)
                        yield Label("Sources", classes="lbl")
                        yield RichLog(id="sources-log", markup=True)

                    # ── TOPICS ───────────────────────────────────────────────
                    with TabPane("📋 Topics", id="t-topics"):
                        yield Label("Learned Topics", classes="tab-head")
                        with Horizontal():
                            yield Button("🔄 Refresh",       id="btn-refresh-topics")
                            yield Button("🗑  Delete Selected", id="btn-delete-topic",
                                         variant="error", disabled=True)
                        yield DataTable(id="topics-table", cursor_type="row")
                        yield Label("", id="topics-footer")

                    # ── SCHEDULE ─────────────────────────────────────────────
                    with TabPane("⏰ Schedule", id="t-sched"):
                        yield Label("Scheduled Re-Learning", classes="tab-head")
                        with Horizontal():
                            with Vertical():
                                yield Label("Topic (type name)", classes="lbl")
                                yield Input(placeholder="React JS", id="sched-topic")
                            with Vertical():
                                yield Label("Re-learn every", classes="lbl")
                                yield Select(
                                    [("1 day","1"),("3 days","3"),("7 days","7"),
                                     ("14 days","14"),("30 days","30")],
                                    value="7", allow_blank=False, id="sched-freq",
                                )
                        yield Button("+ Add Schedule", id="btn-add-sched", variant="primary")
                        yield Label("Active Schedules", classes="lbl")
                        yield DataTable(id="sched-table", cursor_type="row")
                        yield Button("🗑  Remove Selected", id="btn-rm-sched",
                                     variant="error", disabled=True)

                    # ── SETTINGS ─────────────────────────────────────────────
                    with TabPane("⚙️  Settings", id="t-settings"):
                        yield Label("Settings", classes="tab-head")
                        yield Label("Storage Path", classes="lbl")
                        yield Input(
                            value=self._cfg.get("DATA_DIR",""),
                            placeholder=r"E:\my_data or /mnt/storage/ai",
                            id="set-path",
                        )
                        yield Label("Default Storage Limit", classes="lbl")
                        yield Select(
                            [("2 GB","2"),("5 GB","5"),("10 GB","10"),("20 GB","20")],
                            value=str(int(self._cfg.get("STORAGE_LIMIT_GB",5))),
                            allow_blank=False, id="set-limit",
                        )
                        yield Rule()
                        yield Label("LLM Model (Ollama)", classes="lbl")
                        yield Input(value=self._cfg.get("LLM_MODEL","llama3.2"), id="set-llm")
                        yield Label("Ollama URL", classes="lbl")
                        yield Input(value=self._cfg.get("OLLAMA_BASE_URL","http://localhost:11434"),
                                    id="set-ollama")
                        yield Rule()
                        yield Label("Crawler Max Pages", classes="lbl")
                        yield Input(value=str(self._cfg.get("CRAWLER_MAX_PAGES",150)), id="set-maxpages")
                        yield Label("Crawler Max Depth", classes="lbl")
                        yield Input(value=str(self._cfg.get("CRAWLER_MAX_DEPTH",3)), id="set-maxdepth")
                        yield Label("Crawler Delay (seconds)", classes="lbl")
                        yield Input(value=str(self._cfg.get("CRAWLER_DELAY_SECONDS",1.5)), id="set-delay")
                        yield Rule()
                        yield Button("💾  Save Settings", id="btn-save-settings", variant="primary")
                        yield Label("", id="set-status")

        yield Footer()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_mount(self):
        # Set up DataTable columns
        topics_t = self.query_one("#topics-table", DataTable)
        topics_t.add_columns("Topic", "Chunks", "Est. Pages", "Last Scraped")

        sched_t = self.query_one("#sched-table", DataTable)
        sched_t.add_columns("Topic", "Interval", "Next Run")

        self._refresh_all()

    def action_refresh(self):
        self._refresh_all()

    def _refresh_all(self):
        self._refresh_sidebar()
        self._refresh_topics_table()
        self._refresh_sched_table()
        self._refresh_ask_available()

    # ── Sidebar ──────────────────────────────────────────────────────────────

    def _refresh_sidebar(self):
        storage_path = self._cfg.get("DATA_DIR", config.DATA_DIR)
        limit_gb     = float(self._cfg.get("STORAGE_LIMIT_GB", 5))

        try:
            vs     = VectorStore(storage_path=storage_path)
            topics = vs.list_topics()
            self.query_one("#sb-topics", Static).update(
                "\n".join(f"• {t}" for t in topics) if topics else "(none)"
            )
        except Exception:
            self.query_one("#sb-topics", Static).update("(error)")

        try:
            used       = get_folder_size(storage_path)
            limit_b    = int(limit_gb * 1024 ** 3)
            bar        = usage_bar(used, limit_b, width=12)
            pct        = min(100, int(used / limit_b * 100)) if limit_b else 0
            self.query_one("#sb-storage", Static).update(
                f"{format_size(used)} / {limit_gb:.0f} GB\n[{bar}] {pct}%"
            )
        except Exception:
            self.query_one("#sb-storage", Static).update("(error)")

    # ── Topics table ─────────────────────────────────────────────────────────

    def _refresh_topics_table(self):
        table = self.query_one("#topics-table", DataTable)
        table.clear()
        self._topic_rows = []
        storage_path = self._cfg.get("DATA_DIR", config.DATA_DIR)
        try:
            vs     = VectorStore(storage_path=storage_path)
            topics = vs.list_topics()
            total  = 0
            for t in topics:
                s = vs.get_topic_stats(t)
                table.add_row(t, str(s["chunks"]), f"~{s['estimated_pages']}", s["last_scraped"])
                self._topic_rows.append(t)
                total += s["chunks"]
            self.query_one("#topics-footer", Label).update(
                f"Total: {len(topics)} topic(s), {total:,} chunks"
            )
        except Exception as e:
            self.query_one("#topics-footer", Label).update(f"Error: {e}")

    # ── Schedule table ───────────────────────────────────────────────────────

    def _refresh_sched_table(self):
        table = self.query_one("#sched-table", DataTable)
        table.clear()
        for job in self._scheduler.get_jobs():
            table.add_row(job["topic"], f"Every {job['interval_days']} day(s)", job["next_run"])

    # ── Ask tab available topics ─────────────────────────────────────────────

    def _refresh_ask_available(self):
        storage_path = self._cfg.get("DATA_DIR", config.DATA_DIR)
        try:
            vs     = VectorStore(storage_path=storage_path)
            topics = vs.list_topics()
            lbl    = ", ".join(topics) if topics else "(none yet — run Learn first)"
            self.query_one("#ask-available", Label).update(f"Available topics: {lbl}")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # LEARN TAB
    # ═══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-start")
    def handle_start(self):
        raw_input    = self.query_one("#learn-input",   Input).value.strip()
        storage_path = self.query_one("#path-input",    Input).value.strip()
        limit_str    = self.query_one("#limit-sel",     Select).value
        maxpages_str = self.query_one("#maxpages-input",Input).value.strip()

        if not raw_input:
            self._set_status("[warn]Please enter a topic.[/warn]")
            return

        topic        = extract_topic(raw_input)
        storage_path = os.path.normpath(storage_path or self._cfg.get("DATA_DIR", config.DATA_DIR))

        try:
            limit_gb = float(limit_str)
        except (TypeError, ValueError):
            limit_gb = 5.0

        try:
            max_pages = int(maxpages_str)
        except ValueError:
            max_pages = 150

        # Pre-flight: storage limit
        ok, used, limit_b = within_limit(storage_path, limit_gb)
        if not ok:
            self._set_status(
                f"[err]Storage full: {format_size(used)} / {format_size(limit_b)}."
                f"  Increase limit or change path.[/err]"
            )
            return

        os.makedirs(storage_path, exist_ok=True)

        # Reset UI
        self._stop_event.clear()
        self.query_one("#btn-start", Button).disabled = True
        self.query_one("#btn-stop",  Button).disabled = False
        log = self.query_one("#activity-log", RichLog)
        log.clear()
        log.write(f"[bold cyan]Topic:[/bold cyan]   {topic}")
        log.write(f"[bold cyan]Path:[/bold cyan]    {storage_path}  (limit {limit_gb:.0f} GB)")
        log.write(f"[bold cyan]Max pages:[/bold cyan] {max_pages}")
        log.write("─" * 55)

        bar = self.query_one("#crawl-bar", ProgressBar)
        bar.update(total=max_pages, progress=0)
        self._set_status(f"[cyan]Starting crawl for: {topic}[/cyan]")
        self._set_eta("Initializing...")

        self._crawl_worker(topic, storage_path, limit_gb, max_pages)

    @on(Button.Pressed, "#btn-stop")
    def handle_stop(self):
        self._stop_event.set()
        self._set_status("[warn]Stopping after current page...[/warn]")

    # ── Background crawl worker ───────────────────────────────────────────────

    @work(thread=True)
    def _crawl_worker(self, topic: str, storage_path: str, limit_gb: float, max_pages: int):
        worker     = get_current_worker()
        start_time = time.monotonic()
        page_times: list[float] = []
        pages_done = 0
        chunks_saved = 0

        def log(msg):    self.call_from_thread(self._log_activity, msg)
        def status(msg): self.call_from_thread(self._set_status,   msg)
        def eta(msg):    self.call_from_thread(self._set_eta,      msg)
        def progress(n): self.call_from_thread(self._set_progress, n)

        try:
            seed_urls = get_seed_urls(topic)
            if not seed_urls:
                log(f"[yellow]No pre-configured seed URLs for '{topic}'.[/yellow]")
                log("[yellow]Add URLs to crawler/seed_urls.py, or enter them in Settings.[/yellow]")
                self.call_from_thread(self._finish_crawl, 0, 0)
                return

            log(f"[green]Seeds ({len(seed_urls)}):[/green]")
            for u in seed_urls:
                log(f"  [dim]→ {u}[/dim]")

            vs = VectorStore(storage_path=storage_path)
            crawler = CrawlerAgent(
                topic=topic, seed_urls=seed_urls,
                max_pages=max_pages, stop_event=self._stop_event,
            )
            raw_dir = os.path.join(storage_path, "raw_text", topic.replace(" ", "_"))
            os.makedirs(raw_dir, exist_ok=True)

            for page in crawler.crawl():
                if worker.is_cancelled or self._stop_event.is_set():
                    break

                # Storage limit check
                ok, used, lim = within_limit(storage_path, limit_gb)
                if not ok:
                    log(f"[red]⚠ Storage limit reached ({format_size(used)} / {format_size(lim)}). Stopping.[/red]")
                    break

                page_start = time.monotonic()
                pages_done += 1

                # ETA
                page_times.append(time.monotonic() - page_start)
                if len(page_times) > 10:
                    page_times.pop(0)
                avg_sec = sum(page_times) / len(page_times) if page_times else 1
                remaining = max(0, max_pages - pages_done)
                eta_sec = remaining * avg_sec
                eta_str = f"~{int(eta_sec//60)}m {int(eta_sec%60)}s remaining" if eta_sec > 1 else "Almost done"

                log(
                    f"[green]✓[/green] [{pages_done:03d}] "
                    f"{page['title'][:52]}  [dim]({page['word_count']:,} words)[/dim]"
                )
                status(f"[cyan]Crawling... {pages_done} pages | "
                       f"{format_size(get_folder_size(storage_path))} used[/cyan]")
                eta(f"⏱  {eta_str}")
                progress(pages_done)

                # Save raw text
                fname = page["url"].replace("https://","").replace("http://","").replace("/","_")[:80] + ".txt"
                with open(os.path.join(raw_dir, fname), "w", encoding="utf-8") as f:
                    f.write(f"URL: {page['url']}\nTITLE: {page['title']}\n\n{page['text']}")

                # Embed + store
                chunks = chunk_text(page["text"], page["url"], page["title"], topic)
                chunks = embed_chunks(chunks, on_status=lambda m: log(f"  [dim]{m}[/dim]"))
                saved  = vs.save_chunks(chunks, topic)
                chunks_saved += saved
                log(f"  [dim]↳ {saved} new chunks stored[/dim]")

        except Exception as e:
            log(f"[red]Crawl error: {e}[/red]")

        self.call_from_thread(self._finish_crawl, pages_done, chunks_saved)

    # Thread-safe UI helpers (called via call_from_thread)
    def _log_activity(self, msg: str):
        self.query_one("#activity-log", RichLog).write(msg)

    def _set_status(self, msg: str):
        self.query_one("#status-lbl", Label).update(msg)

    def _set_eta(self, msg: str):
        self.query_one("#eta-lbl", Label).update(msg)

    def _set_progress(self, n: int):
        self.query_one("#crawl-bar", ProgressBar).update(progress=n)

    def _finish_crawl(self, pages: int, chunks: int):
        self.query_one("#btn-start", Button).disabled = False
        self.query_one("#btn-stop",  Button).disabled = True
        self._log_activity("─" * 55)
        self._log_activity(
            f"[bold green]✅ Done — {pages} pages, {chunks:,} chunks saved.[/bold green]"
        )
        self._set_status(f"[ok]Complete: {pages} pages, {chunks:,} chunks.[/ok]")
        self._set_eta("")
        self._refresh_all()

    # ═══════════════════════════════════════════════════════════════════════
    # ASK TAB
    # ═══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-ask")
    def handle_ask(self):
        topic    = self.query_one("#ask-topic",    Input).value.strip()
        question = self.query_one("#ask-question", Input).value.strip()

        if not topic:
            self.query_one("#ask-status", Label).update("[warn]Enter a topic name.[/warn]")
            return
        if not question:
            self.query_one("#ask-status", Label).update("[warn]Enter a question.[/warn]")
            return

        self.query_one("#btn-ask",    Button).disabled = True
        self.query_one("#ask-status", Label).update("[cyan]Searching knowledge base...[/cyan]")
        self.query_one("#answer-log",  RichLog).clear()
        self.query_one("#sources-log", RichLog).clear()
        self._ask_worker(topic, question)

    @work(thread=True)
    def _ask_worker(self, topic: str, question: str):
        storage_path = self._cfg.get("DATA_DIR", config.DATA_DIR)
        try:
            rag    = RAGEngine(storage_path=storage_path)
            check  = rag.check_ollama()
            if not check["ok"]:
                msg = f"[red]{check['reason']}[/red]\n[yellow]{check['suggestion']}[/yellow]"
                self.call_from_thread(self._show_answer, msg, [])
                self.call_from_thread(
                    self.query_one("#ask-status", Label).update,
                    f"[err]Ollama unavailable.[/err]",
                )
                return

            result = rag.ask(question, topic)
            self.call_from_thread(self._show_answer, result["answer"], result["sources"])
            self.call_from_thread(
                self.query_one("#ask-status", Label).update,
                f"[ok]Found {result['chunks_found']} relevant chunks.[/ok]",
            )
        except Exception as e:
            self.call_from_thread(self._show_answer, f"[red]Error: {e}[/red]", [])
        finally:
            self.call_from_thread(self._enable_ask_btn)

    def _show_answer(self, answer: str, sources: list):
        self.query_one("#answer-log", RichLog).write(answer)
        log = self.query_one("#sources-log", RichLog)
        if sources:
            for s in sources:
                log.write(f"[{s['num']}] {s['title']} — {s['url']}")
        else:
            log.write("[dim]No sources found.[/dim]")

    def _enable_ask_btn(self):
        self.query_one("#btn-ask", Button).disabled = False

    # ═══════════════════════════════════════════════════════════════════════
    # TOPICS TAB
    # ═══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-refresh-topics")
    def handle_refresh_topics(self):
        self._refresh_all()

    @on(DataTable.RowSelected, "#topics-table")
    def topics_row_selected(self):
        self.query_one("#btn-delete-topic", Button).disabled = False

    @on(Button.Pressed, "#btn-delete-topic")
    def handle_delete_topic(self):
        table = self.query_one("#topics-table", DataTable)
        idx   = table.cursor_row
        if idx < 0 or idx >= len(self._topic_rows):
            return
        topic = self._topic_rows[idx]
        vs = VectorStore(storage_path=self._cfg.get("DATA_DIR", config.DATA_DIR))
        vs.delete_topic(topic)
        self.query_one("#btn-delete-topic", Button).disabled = True
        self._refresh_all()

    # ═══════════════════════════════════════════════════════════════════════
    # SCHEDULE TAB
    # ═══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-add-sched")
    def handle_add_schedule(self):
        topic    = self.query_one("#sched-topic", Input).value.strip()
        freq_str = self.query_one("#sched-freq",  Select).value
        if not topic:
            return
        try:
            days = int(freq_str)
        except (TypeError, ValueError):
            days = 7
        self._scheduler.set_schedule(topic, days)

        # Persist to settings
        schedules = self._cfg.get("SCHEDULES", {})
        schedules[topic] = days
        self._cfg["SCHEDULES"] = schedules
        config.save_all(self._cfg)

        self._refresh_sched_table()

    @on(DataTable.RowSelected, "#sched-table")
    def sched_row_selected(self):
        self.query_one("#btn-rm-sched", Button).disabled = False

    @on(Button.Pressed, "#btn-rm-sched")
    def handle_remove_schedule(self):
        table = self.query_one("#sched-table", DataTable)
        idx   = table.cursor_row
        jobs  = self._scheduler.get_jobs()
        if idx < 0 or idx >= len(jobs):
            return
        topic = jobs[idx]["topic"]
        self._scheduler.remove_schedule(topic)

        schedules = self._cfg.get("SCHEDULES", {})
        schedules.pop(topic, None)
        self._cfg["SCHEDULES"] = schedules
        config.save_all(self._cfg)

        self.query_one("#btn-rm-sched", Button).disabled = True
        self._refresh_sched_table()

    def _on_schedule_fire(self, topic: str):
        """Called from scheduler thread when a topic is due."""
        self.call_from_thread(self._notify_scheduled, topic)

    def _notify_scheduled(self, topic: str):
        # Show in Learn tab log if it's open; otherwise just notify
        try:
            log = self.query_one("#activity-log", RichLog)
            log.write(f"[yellow]⏰ Scheduled re-learn triggered: {topic}[/yellow]")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # SETTINGS TAB
    # ═══════════════════════════════════════════════════════════════════════

    @on(Button.Pressed, "#btn-save-settings")
    def handle_save_settings(self):
        new_cfg = dict(self._cfg)
        new_cfg["DATA_DIR"]               = os.path.normpath(
            self.query_one("#set-path",     Input).value.strip()
            or config.DATA_DIR
        )
        new_cfg["STORAGE_LIMIT_GB"]       = float(
            self.query_one("#set-limit",    Select).value or 5
        )
        new_cfg["LLM_MODEL"]              = self.query_one("#set-llm",       Input).value.strip()
        new_cfg["OLLAMA_BASE_URL"]        = self.query_one("#set-ollama",    Input).value.strip()
        try:
            new_cfg["CRAWLER_MAX_PAGES"]  = int(self.query_one("#set-maxpages", Input).value)
        except ValueError:
            pass
        try:
            new_cfg["CRAWLER_MAX_DEPTH"]  = int(self.query_one("#set-maxdepth", Input).value)
        except ValueError:
            pass
        try:
            new_cfg["CRAWLER_DELAY_SECONDS"] = float(self.query_one("#set-delay", Input).value)
        except ValueError:
            pass

        config.save_all(new_cfg)
        self._cfg = new_cfg

        # Sync Learn-tab path input
        self.query_one("#path-input", Input).value = new_cfg["DATA_DIR"]

        self.query_one("#set-status", Label).update(
            "[ok]✓ Settings saved.  Storage path changes take effect on next crawl.[/ok]"
        )
        self._refresh_sidebar()
