"""
My AI Agent v2 — PyQt6 GUI
Opens a standalone desktop window (no terminal needed).
"""
from __future__ import annotations
import html
import os
import queue
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core.nlp_parser       import extract_topic
from core.storage_monitor  import get_folder_size, format_size, within_limit
from core.scheduler        import TopicScheduler
from storage.vector_store  import VectorStore
from gui.workers           import CrawlWorker, AskWorker
from gui.chat_worker       import ChatWorker, parse_file
from gui.project_worker    import ProjectWorker

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QApplication,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QProgressBar, QTextEdit, QPlainTextEdit, QTextBrowser,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFrame, QScrollArea,
    QFileDialog, QAbstractItemView,
    QTabWidget, QMessageBox, QSizePolicy,
    QSplitter,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui  import QFont, QTextCursor, QColor, QTextCharFormat


# ─── Stylesheet ───────────────────────────────────────────────────────────────
STYLE = """
QMainWindow { background-color: #1e1e2e; }

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 9px 20px;
    border: 1px solid #313244;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    min-width: 110px;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #313244;
    color: #cdd6f4;
}

QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 6px 6px 6px;
    font-size: 13px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #89b4fa;
}

QLabel { font-size: 13px; color: #cdd6f4; }
QLabel#hint        { color: #6c7086; font-size: 11px; }
QLabel#status-ok   { color: #a6e3a1; font-size: 13px; }
QLabel#status-warn { color: #f9e2af; font-size: 13px; }
QLabel#status-err  { color: #f38ba8; font-size: 13px; }
QLabel#sidebar-section { color: #89b4fa; font-weight: bold; font-size: 13px; }
QLabel#sidebar-value   { color: #a6adc8; font-size: 12px; }

QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 6px 8px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
    font-size: 13px;
    min-height: 28px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #89b4fa;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #45475a;
    border: none;
    width: 18px;
}

QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 6px 8px;
    color: #cdd6f4;
    min-width: 100px;
    min-height: 28px;
    font-size: 13px;
}
QComboBox:focus { border: 1px solid #89b4fa; }
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    border: 1px solid #45475a;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
    font-size: 13px;
}

QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 5px;
    padding: 8px 18px;
    font-weight: bold;
    min-width: 120px;
    font-size: 13px;
}
QPushButton:hover    { background-color: #b4d0f7; }
QPushButton:pressed  { background-color: #6c98d4; }
QPushButton:disabled { background-color: #45475a; color: #6c7086; }
QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
}
QPushButton#danger:hover    { background-color: #f5a3bb; }
QPushButton#danger:disabled { background-color: #45475a; color: #6c7086; }
QPushButton#secondary {
    background-color: #45475a;
    color: #cdd6f4;
}
QPushButton#secondary:hover { background-color: #585b70; }

QProgressBar {
    border: 1px solid #45475a;
    border-radius: 5px;
    background-color: #313244;
    text-align: center;
    color: #cdd6f4;
    min-height: 20px;
    font-size: 12px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}

QTextEdit {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 5px;
    color: #cdd6f4;
    padding: 4px;
}

QTableWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 5px;
    gridline-color: #313244;
    selection-background-color: #3d59a1;
    selection-color: #cdd6f4;
    alternate-background-color: #1e1e2e;
    font-size: 13px;
}
QTableWidget::item { padding: 5px 8px; }
QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    padding: 7px 8px;
    border: none;
    border-bottom: 1px solid #45475a;
    font-weight: bold;
    font-size: 13px;
}

QScrollBar:vertical {
    background: #181825;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #585b70; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #181825;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background: #585b70; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QStatusBar {
    background-color: #181825;
    color: #6c7086;
    border-top: 1px solid #313244;
    font-size: 12px;
}
QFrame#sidebar {
    background-color: #181825;
    border-right: 1px solid #313244;
}
QMessageBox { background-color: #1e1e2e; }
QMessageBox QLabel { color: #cdd6f4; font-size: 13px; }
"""

_LOG_COLOR = {
    "ok":   "#a6e3a1",
    "warn": "#f9e2af",
    "err":  "#f38ba8",
    "info": "#cdd6f4",
}

_MONO = QFont("Consolas", 11)


# ── Syntax highlighting + code-block renderer ──────────────────────────────────

def _highlight_code_blocks(
    text: str,
    start_id: int = 0,
) -> tuple[str, dict[str, str], int]:
    """
    Convert markdown ``` code blocks into styled HTML with a 'Copy code' anchor.

    Returns:
        html        — full HTML string for insertion into QTextBrowser
        code_blocks — {block_id: raw_code_string}  (for clipboard copy)
        next_id     — next available block counter value
    """
    import re
    import html as _html

    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, TextLexer
        from pygments.formatters import HtmlFormatter
        _HAS_PYGMENTS = True
    except ImportError:
        _HAS_PYGMENTS = False

    CODE_BLOCK  = re.compile(r'```(\w*)\n?(.*?)```', re.DOTALL)
    parts:       list[str]       = []
    code_blocks: dict[str, str]  = {}
    block_id = start_id
    last     = 0

    def _plain(s: str) -> str:
        """Escape plain text for HTML, preserve newlines as <br>."""
        return (
            '<span style="color:#cdd6f4;font-family:\'Segoe UI\',Arial,sans-serif;">'
            + _html.escape(s).replace("\n", "<br>")
            + "</span>"
        )

    for m in CODE_BLOCK.finditer(text):
        before = text[last:m.start()]
        if before:
            parts.append(_plain(before))

        lang = m.group(1).strip() or "text"
        code = m.group(2)
        bid  = f"block_{block_id}"
        code_blocks[bid] = code            # raw code stored for clipboard

        # ── Syntax-highlight (or plain fallback) ─────────────────────────────
        if _HAS_PYGMENTS:
            try:
                lexer = get_lexer_by_name(lang, stripall=True)
            except Exception:
                lexer = TextLexer()
            formatter = HtmlFormatter(style="monokai", noclasses=True, nowrap=True)
            code_html = highlight(code, lexer, formatter)
        else:
            code_html = (
                '<span style="color:#f8f8f2;">'
                + _html.escape(code)
                + "</span>"
            )

        lang_label = _html.escape(lang) if lang not in ("text", "") else ""

        # ── Code block table ─────────────────────────────────────────────────
        #   Row 1: language label  |  Copy code link
        #   Row 2: syntax-highlighted code body
        parts.append(
            # Outer container table
            '<table width="100%" cellpadding="0" cellspacing="0" '
            'style="background-color:#12121f;border:1px solid #45475a;margin:10px 0;">'

            # Header row ─────────────────────────────────────────────────────
            '<tr style="background-color:#1e1e38;">'

            # Language label (left)
            f'<td style="padding:5px 14px;color:#6c7086;font-size:11px;'
            f'font-family:Consolas,monospace;">{lang_label}</td>'

            # Copy link (right) — uses copy://bid URL scheme
            f'<td style="padding:5px 14px;text-align:right;">'
            f'<a href="copy://{bid}" '
            f'style="color:#89b4fa;font-size:11px;text-decoration:none;'
            f'font-family:\'Segoe UI\',Arial,sans-serif;">'
            f'&#128203; Copy code'
            f'</a></td>'
            '</tr>'

            # Thin separator
            '<tr><td colspan="2" '
            'style="background-color:#45475a;padding:0;height:1px;"></td></tr>'

            # Code body row ──────────────────────────────────────────────────
            '<tr><td colspan="2" '
            'style="padding:14px 16px;font-family:Consolas,monospace;font-size:11px;'
            'line-height:1.6;">'
            f'<pre style="margin:0;white-space:pre-wrap;word-break:break-word;">'
            f'{code_html}'
            f'</pre>'
            '</td></tr>'

            '</table>'
        )

        block_id += 1
        last = m.end()

    tail = text[last:]
    if tail:
        parts.append(_plain(tail))

    return "".join(parts), code_blocks, block_id


def _err_dialog(parent, title: str, msg: str):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(msg)
    box.setIcon(QMessageBox.Icon.Critical)
    box.exec()


def _info_dialog(parent, title: str, msg: str):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(msg)
    box.setIcon(QMessageBox.Icon.Information)
    box.exec()


def _group(title: str, layout) -> QGroupBox:
    box = QGroupBox(title)
    box.setLayout(layout)
    return box


def _btn(text: str, style_id: str = "") -> QPushButton:
    b = QPushButton(text)
    if style_id:
        b.setObjectName(style_id)
    return b


def _lbl(text: str = "", obj: str = "") -> QLabel:
    lbl = QLabel(text)
    if obj:
        lbl.setObjectName(obj)
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("background-color: #313244; max-height: 1px;")
    return f


# ─── Main Window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My AI Agent v2")
        self.setMinimumSize(1000, 680)
        self.resize(1200, 800)

        self._cfg: dict       = config.load_all()
        self._crawl_worker:   CrawlWorker   | None = None
        self._ask_worker:     AskWorker    | None = None
        self._chat_worker:    ChatWorker   | None = None
        self._project_worker: ProjectWorker| None = None
        self._topic_rows:     list[str]    = []
        self._sched_jobs:     list[dict]   = []
        self._project_rows:   list[dict]   = []   # cached project metadata list

        # Phase 1 Chat state
        self._chat_history:      list[dict]      = []   # [{role, content}, ...]
        self._attached_file:     str             = ""   # parsed file content
        self._attached_label:    str             = ""   # display name
        self._stream_start_pos:  int             = 0    # cursor pos where assistant text starts
        self._code_blocks:       dict[str, str]  = {}   # {block_id: raw_code}
        self._code_block_counter: int            = 0    # increments per code block added

        # Thread-safe queue for scheduler → UI notifications
        self._sched_queue: queue.Queue = queue.Queue()
        self._sched_timer  = QTimer(self)
        self._sched_timer.timeout.connect(self._poll_sched_queue)
        self._sched_timer.start(1000)  # check every second

        self._scheduler = TopicScheduler(on_trigger=self._on_schedule_fire)
        self._scheduler.load_from_config(self._cfg.get("SCHEDULES", {}))
        self._scheduler.start()

        self._build_ui()
        self._refresh_all()

    # ═════════════════════════════════════════════════════════════════════════
    # BUILD UI
    # ═════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_sidebar())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_learn_tab(),    "🌐   Learn")
        self._tabs.addTab(self._build_chat_tab(),     "🤖   Chat")
        self._tabs.addTab(self._build_ask_tab(),      "💬   Ask")
        self._tabs.addTab(self._build_projects_tab(), "📁   Projects")
        self._tabs.addTab(self._build_topics_tab(),   "📋   Topics")
        self._tabs.addTab(self._build_sched_tab(),    "⏰   Schedule")
        self._tabs.addTab(self._build_settings_tab(), "⚙️   Settings")
        root.addWidget(self._tabs, stretch=1)

        self.statusBar().showMessage("Ready — My AI Agent v2")

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(210)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 14, 10, 14)
        lay.setSpacing(6)

        lay.addWidget(_lbl("📚  Topics", "sidebar-section"))
        self._sb_topics = QLabel("(none)")
        self._sb_topics.setObjectName("sidebar-value")
        self._sb_topics.setWordWrap(True)
        self._sb_topics.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self._sb_topics)

        lay.addWidget(_sep())
        lay.addWidget(_lbl("💾  Storage", "sidebar-section"))

        self._sb_storage_lbl = QLabel("...")
        self._sb_storage_lbl.setObjectName("sidebar-value")
        self._sb_storage_lbl.setWordWrap(True)
        lay.addWidget(self._sb_storage_lbl)

        self._sb_storage_bar = QProgressBar()
        self._sb_storage_bar.setTextVisible(False)
        self._sb_storage_bar.setFixedHeight(8)
        self._sb_storage_bar.setMaximum(100)
        self._sb_storage_bar.setStyleSheet(
            "QProgressBar { border-radius: 4px; background: #313244; border: none; }"
            "QProgressBar::chunk { background: #89b4fa; border-radius: 4px; }"
        )
        lay.addWidget(self._sb_storage_bar)
        lay.addStretch()
        return frame

    # ── Learn Tab ─────────────────────────────────────────────────────────────

    def _build_learn_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # Topic input
        inp_lay = QVBoxLayout()
        inp_lay.addWidget(_lbl("What do you want to learn?"))
        self._learn_input = QLineEdit()
        self._learn_input.setPlaceholderText(
            '"Learn everything about React JS and its framework"'
        )
        self._learn_input.setMinimumHeight(36)
        self._learn_input.returnPressed.connect(self._start_crawl)
        inp_lay.addWidget(self._learn_input)
        lay.addWidget(_group("Topic", inp_lay))

        # Options row
        opts = QHBoxLayout()

        lim_lay = QVBoxLayout()
        lim_lay.addWidget(_lbl("Storage Limit"))
        self._limit_combo = QComboBox()
        for label, val in [("2 GB", "2"), ("5 GB", "5"), ("10 GB", "10"), ("20 GB", "20")]:
            self._limit_combo.addItem(label, val)
        saved = str(int(self._cfg.get("STORAGE_LIMIT_GB", 5)))
        idx = self._limit_combo.findData(saved)
        if idx >= 0:
            self._limit_combo.setCurrentIndex(idx)
        lim_lay.addWidget(self._limit_combo)
        opts.addWidget(_group("Limit", lim_lay))

        path_lay = QHBoxLayout()
        self._path_input = QLineEdit(self._cfg.get("DATA_DIR", ""))
        self._path_input.setPlaceholderText(r"e.g. E:\my_data")
        browse_btn = _btn("Browse", "secondary")
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(self._browse_learn_path)
        path_lay.addWidget(self._path_input, stretch=1)
        path_lay.addWidget(browse_btn)
        opts.addWidget(_group("Storage Path", path_lay), stretch=1)

        pages_lay = QVBoxLayout()
        pages_lay.addWidget(_lbl("Max Pages"))
        self._maxpages_spin = QSpinBox()
        self._maxpages_spin.setRange(1, 10000)
        self._maxpages_spin.setValue(int(self._cfg.get("CRAWLER_MAX_PAGES", 150)))
        pages_lay.addWidget(self._maxpages_spin)
        opts.addWidget(_group("Pages", pages_lay))

        lay.addLayout(opts)

        # Buttons
        btn_row = QHBoxLayout()
        self._start_btn = _btn("▶   Start Learning")
        self._start_btn.clicked.connect(self._start_crawl)
        self._stop_btn = _btn("⏹   Stop", "danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_crawl)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # Status + progress
        self._crawl_status = QLabel("Ready.")
        self._crawl_status.setObjectName("status-ok")
        lay.addWidget(self._crawl_status)

        self._crawl_bar = QProgressBar()
        self._crawl_bar.setMinimum(0)
        self._crawl_bar.setMaximum(150)
        self._crawl_bar.setValue(0)
        self._crawl_bar.setFormat(" %v / %m pages")
        lay.addWidget(self._crawl_bar)

        prog_row = QHBoxLayout()
        self._eta_lbl      = _lbl("", "hint")
        self._storage_stat = _lbl("", "hint")
        prog_row.addWidget(self._eta_lbl)
        prog_row.addStretch()
        prog_row.addWidget(self._storage_stat)
        lay.addLayout(prog_row)

        self._learn_storage_bar = QProgressBar()
        self._learn_storage_bar.setTextVisible(False)
        self._learn_storage_bar.setFixedHeight(6)
        self._learn_storage_bar.setMaximum(100)
        self._learn_storage_bar.setValue(0)
        self._learn_storage_bar.setStyleSheet(
            "QProgressBar { border-radius: 3px; background: #313244; border: none; }"
            "QProgressBar::chunk { background: #a6e3a1; border-radius: 3px; }"
        )
        lay.addWidget(self._learn_storage_bar)

        # Activity log
        log_inner = QVBoxLayout()
        self._activity_log = QTextEdit()
        self._activity_log.setReadOnly(True)
        self._activity_log.setFont(_MONO)
        self._activity_log.setMinimumHeight(200)
        log_inner.addWidget(self._activity_log)
        lay.addWidget(_group("Activity Log", log_inner), stretch=1)

        return tab

    # ── Chat Tab ──────────────────────────────────────────────────────────────

    def _build_chat_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # ── Top toolbar row ───────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        # Topic (optional — leave blank to skip RAG search)
        topic_grp_lay = QVBoxLayout()
        topic_grp_lay.addWidget(_lbl("Topic (optional)"))
        self._chat_topic = QLineEdit()
        self._chat_topic.setPlaceholderText("react, firebase, python …  (blank = general chat)")
        self._chat_topic.setMinimumHeight(32)
        topic_grp_lay.addWidget(self._chat_topic)
        toolbar.addWidget(_group("Knowledge Base Topic", topic_grp_lay), stretch=2)

        # Model selector
        model_grp_lay = QVBoxLayout()
        model_grp_lay.addWidget(_lbl("Model"))
        self._chat_model_combo = QComboBox()
        self._chat_model_combo.addItem(f"Default ({config.LLM_MODEL})", "")
        self._chat_model_combo.setMinimumHeight(32)
        model_grp_lay.addWidget(self._chat_model_combo)
        toolbar.addWidget(_group("Ollama Model", model_grp_lay))

        # Refresh models button
        refresh_model_btn = _btn("↻ Refresh Models", "secondary")
        refresh_model_btn.setMinimumWidth(140)
        refresh_model_btn.clicked.connect(self._refresh_chat_models)
        toolbar.addWidget(refresh_model_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        # Clear conversation button
        clear_btn = _btn("🗑  Clear Chat", "secondary")
        clear_btn.setMinimumWidth(120)
        clear_btn.clicked.connect(self._clear_chat)
        toolbar.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        lay.addLayout(toolbar)

        # ── Chat display ──────────────────────────────────────────────────────
        self._chat_display = QTextBrowser()
        self._chat_display.setFont(QFont("Segoe UI", 12))
        self._chat_display.setMinimumHeight(300)
        self._chat_display.setOpenLinks(False)           # intercept anchor clicks
        self._chat_display.anchorClicked.connect(self._on_copy_clicked)
        self._chat_display.setStyleSheet(
            "QTextBrowser { background-color: #181825; border: 1px solid #313244; "
            "border-radius: 6px; padding: 8px; }"
        )
        lay.addWidget(self._chat_display, stretch=1)

        # ── Attachment bar ────────────────────────────────────────────────────
        attach_bar = QHBoxLayout()
        self._attach_btn = _btn("📎  Attach File", "secondary")
        self._attach_btn.setMinimumWidth(130)
        self._attach_btn.clicked.connect(self._attach_file)
        self._attach_label = _lbl("No file attached", "hint")
        self._attach_label.setWordWrap(False)
        self._remove_attach_btn = _btn("✕", "danger")
        self._remove_attach_btn.setMinimumWidth(36)
        self._remove_attach_btn.setMaximumWidth(36)
        self._remove_attach_btn.setEnabled(False)
        self._remove_attach_btn.clicked.connect(self._remove_attachment)
        attach_bar.addWidget(self._attach_btn)
        attach_bar.addWidget(self._attach_label, stretch=1)
        attach_bar.addWidget(self._remove_attach_btn)
        lay.addLayout(attach_bar)

        # ── Input row ─────────────────────────────────────────────────────────
        input_row = QHBoxLayout()
        self._chat_input = QPlainTextEdit()
        self._chat_input.setPlaceholderText(
            "Ask anything… type your question or request code generation here.\n"
            "Press Ctrl+Enter to send."
        )
        self._chat_input.setMaximumHeight(100)
        self._chat_input.setFont(QFont("Segoe UI", 12))
        self._chat_input.setStyleSheet(
            "QPlainTextEdit { background-color: #313244; border: 1px solid #45475a; "
            "border-radius: 6px; padding: 6px; color: #cdd6f4; }"
            "QPlainTextEdit:focus { border: 1px solid #89b4fa; }"
        )
        # Ctrl+Enter to send
        self._chat_input.keyPressEvent = self._chat_input_key_press

        self._chat_send_btn = _btn("Send  ↵")
        self._chat_send_btn.setMinimumWidth(100)
        self._chat_send_btn.setMinimumHeight(100)
        self._chat_send_btn.clicked.connect(self._send_chat)

        input_row.addWidget(self._chat_input, stretch=1)
        input_row.addWidget(self._chat_send_btn)
        lay.addLayout(input_row)

        # Status bar
        self._chat_status = _lbl("Ready — start a conversation.", "hint")
        lay.addWidget(self._chat_status)

        return tab

    # ── Chat Tab: logic ───────────────────────────────────────────────────────

    def _chat_input_key_press(self, event):
        """Send on Ctrl+Enter, newline on plain Enter."""
        from PyQt6.QtCore import Qt as _Qt
        from PyQt6.QtGui  import QKeyEvent
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._send_chat()
        else:
            QPlainTextEdit.keyPressEvent(self._chat_input, event)

    def _refresh_chat_models(self):
        try:
            from query.rag import RAGEngine
            models = RAGEngine().list_ollama_models()
            self._chat_model_combo.clear()
            self._chat_model_combo.addItem(f"Default ({config.LLM_MODEL})", "")
            for m in models:
                self._chat_model_combo.addItem(m, m)
            self._chat_status.setText(f"Found {len(models)} Ollama model(s).")
        except Exception as e:
            _err_dialog(self, "Model Refresh Error", str(e))

    def _clear_chat(self):
        self._chat_history       = []
        self._code_blocks        = {}
        self._code_block_counter = 0
        self._chat_display.clear()
        self._chat_status.setText("Conversation cleared.")

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach File", "",
            "All Supported Files (*.pdf *.txt *.md *.py *.js *.ts *.tsx *.jsx "
            "*.json *.yaml *.yml *.html *.css *.sh *.sql *.go *.rs *.cpp *.c *.java *.kt);;"
            "PDF Files (*.pdf);;Text Files (*.txt *.md);;Code Files (*.py *.js *.ts *.tsx *.jsx);;"
            "All Files (*)"
        )
        if not path:
            return
        try:
            content, label = parse_file(path)
            self._attached_file  = content
            self._attached_label = label
            self._attach_label.setText(label)
            self._remove_attach_btn.setEnabled(True)
            self._append_chat_system(f"File attached: {label}")
        except ValueError as e:
            _err_dialog(self, "File Error", str(e))

    def _remove_attachment(self):
        self._attached_file  = ""
        self._attached_label = ""
        self._attach_label.setText("No file attached")
        self._remove_attach_btn.setEnabled(False)
        self._append_chat_system("File attachment removed.")

    def _send_chat(self):
        question = self._chat_input.toPlainText().strip()
        if not question:
            return
        if self._chat_worker and self._chat_worker.isRunning():
            _err_dialog(self, "Busy", "Still generating a response. Please wait.")
            return

        # Display user message
        self._append_chat_message("user", question)
        self._chat_input.clear()
        self._chat_send_btn.setEnabled(False)
        self._chat_status.setText("Thinking…")

        topic        = self._chat_topic.text().strip()
        storage_path = self._cfg.get("DATA_DIR", "")
        model        = self._chat_model_combo.currentData() or None

        # Add to history before sending
        self._chat_history.append({"role": "user", "content": question})

        # Placeholder for streaming assistant response
        self._append_chat_message("assistant", "")   # empty — will be filled by tokens
        self._streaming_buffer = ""

        # Mark where streaming text begins so we can replace it with highlighted HTML
        _cur = self._chat_display.textCursor()
        _cur.movePosition(QTextCursor.MoveOperation.End)
        self._stream_start_pos = _cur.position()

        self._chat_worker = ChatWorker(
            question     = question,
            topic        = topic,
            history      = self._chat_history[:-1],  # history before current message
            storage_path = storage_path,
            file_context = self._attached_file,
            model        = model,
        )
        self._chat_worker.token_sig.connect(self._on_chat_token)
        self._chat_worker.done_sig.connect(self._on_chat_done)
        self._chat_worker.error_sig.connect(self._on_chat_error)
        self._chat_worker.start()

    @pyqtSlot(str)
    def _on_chat_token(self, token: str):
        """Append each streamed token to the last assistant bubble."""
        self._streaming_buffer += token
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _rerender_last_assistant_message(self, answer: str):
        """
        Replace the plain-text streamed content with syntax-highlighted HTML.
        Selects from the saved stream-start position to the current end,
        deletes it, then inserts the fully rendered HTML (code blocks + copy links).
        """
        try:
            html_body, new_blocks, next_id = _highlight_code_blocks(
                answer, start_id=self._code_block_counter
            )
            # Persist code blocks so copy handler can retrieve raw code
            self._code_blocks.update(new_blocks)
            self._code_block_counter = next_id

            cursor = self._chat_display.textCursor()
            cursor.setPosition(self._stream_start_pos)
            cursor.movePosition(
                QTextCursor.MoveOperation.End,
                QTextCursor.MoveMode.KeepAnchor,
            )
            cursor.removeSelectedText()
            cursor.insertHtml(html_body)
            self._chat_display.setTextCursor(cursor)
            self._chat_display.ensureCursorVisible()
        except Exception:
            pass  # leave streamed plain text as-is if anything fails

    @pyqtSlot(str, list)
    def _on_chat_done(self, answer: str, sources: list):
        self._chat_send_btn.setEnabled(True)

        # Save full answer to history
        self._chat_history.append({"role": "assistant", "content": answer})

        # Replace streamed plain text with syntax-highlighted version
        self._rerender_last_assistant_message(answer)

        # Show sources if any
        if sources:
            src_text = "\n".join(f"  [{s['num']}] {s['title']}  {s['url']}" for s in sources)
            self._append_chat_system(f"Sources:\n{src_text}")

        chunks_note = ""
        if sources:
            chunks_note = f" | {len(sources)} source(s) cited"
        self._chat_status.setText(
            f"Done — {len(self._chat_history)//2} exchange(s) in session{chunks_note}"
        )

        # Append visual separator
        self._append_chat_system("─" * 60)

    def _on_copy_clicked(self, url):
        """Handle 'Copy code' anchor clicks from inside the chat display."""
        from PyQt6.QtCore import QUrl as _QUrl
        if url.scheme() == "copy":
            block_id = url.host()          # e.g. "block_0"
            code = self._code_blocks.get(block_id, "")
            if code:
                QApplication.clipboard().setText(code)
                self._chat_status.setText("Code copied to clipboard!")
                # Reset status after 3 s
                QTimer.singleShot(3000, lambda: self._chat_status.setText(
                    f"Done — {len(self._chat_history)//2} exchange(s) in session"
                    if self._chat_history else "Ready — start a conversation."
                ))

    @pyqtSlot(str)
    def _on_chat_error(self, msg: str):
        self._chat_send_btn.setEnabled(True)
        self._append_chat_system(f"ERROR: {msg}", color="#f38ba8")
        self._chat_status.setText("Error — see chat.")

    def _append_chat_message(self, role: str, content: str):
        """
        Append a styled message bubble to the chat display.

        User messages: blue left-border card.
        Assistant messages: green label, then a plain-text insertion point
          (tokens stream in here, replaced by highlighted HTML when done).
        """
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if role == "user":
            # ── User bubble ──────────────────────────────────────────────────
            safe_content = html.escape(content).replace("\n", "<br>")
            bubble = (
                '<table width="100%" cellpadding="0" cellspacing="0" '
                'style="margin:10px 0 4px 0;">'
                # Label row
                '<tr><td style="padding:0 0 4px 0;">'
                '<span style="color:#89b4fa;font-weight:bold;font-size:13px;'
                'font-family:\'Segoe UI\',Arial,sans-serif;">You</span>'
                '</td></tr>'
                # Message bubble row
                '<tr><td style="'
                'background-color:#1e2a3a;'
                'border-left:3px solid #89b4fa;'
                'padding:10px 14px;'
                'color:#cdd6f4;'
                'font-family:\'Segoe UI\',Arial,sans-serif;'
                'font-size:11px;'
                'line-height:1.6;">'
                f'{safe_content}'
                '</td></tr>'
                '</table>'
            )
            cursor.insertHtml(bubble)

        else:
            # ── Assistant label (the streamed text goes after this) ───────────
            label = (
                '<p style="margin:12px 0 4px 0;">'
                '<span style="color:#a6e3a1;font-weight:bold;font-size:13px;'
                'font-family:\'Segoe UI\',Arial,sans-serif;">AI</span>'
                '</p>'
            )
            cursor.insertHtml(label)
            # Insert a plain paragraph so streaming text has a home
            if content:
                # Used when re-populating (not streaming path)
                cursor.insertText(content, QTextCharFormat())

        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _append_chat_system(self, msg: str, color: str = "#6c7086"):
        """Append a dimmed italic system / meta note."""
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        safe = html.escape(msg).replace("\n", "<br>")
        cursor.insertHtml(
            f'<p style="color:{color};font-style:italic;font-size:11px;'
            f'font-family:\'Segoe UI\',Arial,sans-serif;margin:2px 0;">'
            f'{safe}</p>'
        )
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    # ── Ask Tab ───────────────────────────────────────────────────────────────

    def _build_ask_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        inp_row = QHBoxLayout()

        topic_lay = QVBoxLayout()
        topic_lay.addWidget(_lbl("Topic"))
        self._ask_topic = QLineEdit()
        self._ask_topic.setPlaceholderText("e.g.  React Js")
        self._ask_topic.setMinimumHeight(34)
        topic_lay.addWidget(self._ask_topic)
        inp_row.addWidget(_group("Topic", topic_lay))

        q_lay = QVBoxLayout()
        q_lay.addWidget(_lbl("Question"))
        self._ask_question = QLineEdit()
        self._ask_question.setPlaceholderText("What is useState and how do I use it?")
        self._ask_question.setMinimumHeight(34)
        self._ask_question.returnPressed.connect(self._run_ask)
        q_lay.addWidget(self._ask_question)
        inp_row.addWidget(_group("Question", q_lay), stretch=2)

        lay.addLayout(inp_row)

        self._ask_available_lbl = _lbl("", "hint")
        lay.addWidget(self._ask_available_lbl)

        btn_row = QHBoxLayout()
        self._ask_btn = _btn("🔍   Ask")
        self._ask_btn.clicked.connect(self._run_ask)
        self._ask_status = _lbl("", "hint")
        btn_row.addWidget(self._ask_btn)
        btn_row.addWidget(self._ask_status, stretch=1)
        lay.addLayout(btn_row)

        ans_inner = QVBoxLayout()
        self._answer_edit = QTextEdit()
        self._answer_edit.setReadOnly(True)
        self._answer_edit.setFont(QFont("Segoe UI", 12))
        self._answer_edit.setMinimumHeight(200)
        ans_inner.addWidget(self._answer_edit)
        lay.addWidget(_group("Answer", ans_inner), stretch=1)

        src_inner = QVBoxLayout()
        self._sources_edit = QTextEdit()
        self._sources_edit.setReadOnly(True)
        self._sources_edit.setFont(_MONO)
        self._sources_edit.setMaximumHeight(120)
        src_inner.addWidget(self._sources_edit)
        lay.addWidget(_group("Sources", src_inner))

        return tab

    # ── Projects Tab ──────────────────────────────────────────────────────────

    def _build_projects_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # ── Index a project ───────────────────────────────────────────────
        idx_inner = QVBoxLayout()

        path_row = QHBoxLayout()
        self._proj_path_input = QLineEdit()
        self._proj_path_input.setPlaceholderText(
            r"Folder path  (e.g.  C:\Users\FearCleevan\my-react-app)"
        )
        self._proj_path_input.setMinimumHeight(34)
        browse_btn = _btn("Browse", "secondary")
        browse_btn.setMinimumWidth(90)
        browse_btn.clicked.connect(self._browse_project_path)
        path_row.addWidget(self._proj_path_input, stretch=1)
        path_row.addWidget(browse_btn)
        idx_inner.addLayout(path_row)

        btn_row = QHBoxLayout()
        self._proj_index_btn = _btn("▶   Index Project")
        self._proj_index_btn.clicked.connect(self._start_index_project)
        self._proj_stop_btn  = _btn("⏹   Stop", "danger")
        self._proj_stop_btn.setEnabled(False)
        self._proj_stop_btn.clicked.connect(self._stop_index_project)
        btn_row.addWidget(self._proj_index_btn)
        btn_row.addWidget(self._proj_stop_btn)
        btn_row.addStretch()
        idx_inner.addLayout(btn_row)

        lay.addWidget(_group("Index a Project", idx_inner))

        # ── Progress ──────────────────────────────────────────────────────
        prog_inner = QVBoxLayout()

        self._proj_bar = QProgressBar()
        self._proj_bar.setMinimum(0)
        self._proj_bar.setMaximum(100)
        self._proj_bar.setValue(0)
        self._proj_bar.setFormat(" %v / %m files")
        prog_inner.addWidget(self._proj_bar)

        stat_row = QHBoxLayout()
        self._proj_stat_lbl   = _lbl("", "hint")
        self._proj_chunks_lbl = _lbl("", "hint")
        stat_row.addWidget(self._proj_stat_lbl, stretch=1)
        stat_row.addWidget(self._proj_chunks_lbl)
        prog_inner.addLayout(stat_row)

        self._proj_current_lbl = _lbl("", "hint")
        self._proj_current_lbl.setWordWrap(True)
        prog_inner.addWidget(self._proj_current_lbl)

        lay.addWidget(_group("Progress", prog_inner))

        # ── Indexed projects table ────────────────────────────────────────
        tbl_inner = QVBoxLayout()

        self._proj_table = QTableWidget(0, 6)
        self._proj_table.setHorizontalHeaderLabels(
            ["Project", "Framework", "Language", "Files", "Chunks", "Indexed"]
        )
        self._proj_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._proj_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._proj_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._proj_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._proj_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._proj_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._proj_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._proj_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._proj_table.setAlternatingRowColors(True)
        self._proj_table.selectionModel().selectionChanged.connect(self._on_proj_select)
        tbl_inner.addWidget(self._proj_table)

        tbl_btn_row = QHBoxLayout()
        self._proj_ask_btn    = _btn("💬   Ask about this project")
        self._proj_ask_btn.setEnabled(False)
        self._proj_ask_btn.clicked.connect(self._ask_about_project)
        self._proj_reindex_btn = _btn("↺   Re-index", "secondary")
        self._proj_reindex_btn.setEnabled(False)
        self._proj_reindex_btn.clicked.connect(self._reindex_project)
        self._proj_delete_btn = _btn("🗑   Delete", "danger")
        self._proj_delete_btn.setEnabled(False)
        self._proj_delete_btn.clicked.connect(self._delete_project)
        tbl_btn_row.addWidget(self._proj_ask_btn)
        tbl_btn_row.addWidget(self._proj_reindex_btn)
        tbl_btn_row.addWidget(self._proj_delete_btn)
        tbl_btn_row.addStretch()
        tbl_inner.addLayout(tbl_btn_row)

        lay.addWidget(_group("Indexed Projects", tbl_inner), stretch=1)

        # ── Activity log ──────────────────────────────────────────────────
        log_inner = QVBoxLayout()
        self._proj_log = QTextEdit()
        self._proj_log.setReadOnly(True)
        self._proj_log.setFont(_MONO)
        self._proj_log.setMaximumHeight(160)
        log_inner.addWidget(self._proj_log)
        lay.addWidget(_group("Activity Log", log_inner))

        return tab

    # ── Projects Tab: logic ───────────────────────────────────────────────────

    def _browse_project_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder", "")
        if folder:
            self._proj_path_input.setText(folder)

    def _start_index_project(self):
        root = self._proj_path_input.text().strip()
        if not root:
            _err_dialog(self, "No folder selected", "Please enter or browse to a project folder.")
            return
        if not os.path.isdir(root):
            _err_dialog(self, "Invalid folder", f"Folder not found:\n{root}")
            return
        if self._project_worker and self._project_worker.isRunning():
            _err_dialog(self, "Busy", "An indexing job is already running.")
            return

        self._proj_log.clear()
        self._proj_bar.setValue(0)
        self._proj_bar.setMaximum(100)
        self._proj_stat_lbl.setText("Scanning…")
        self._proj_chunks_lbl.setText("")
        self._proj_current_lbl.setText("")
        self._proj_index_btn.setEnabled(False)
        self._proj_stop_btn.setEnabled(True)
        self.statusBar().showMessage(f"Indexing project: {root}")

        storage_path = self._cfg.get("DATA_DIR", "")
        self._project_worker = ProjectWorker(root=root, storage_path=storage_path)
        self._project_worker.log_sig.connect(self._on_proj_log)
        self._project_worker.progress_sig.connect(self._on_proj_progress)
        self._project_worker.done_sig.connect(self._on_proj_done)
        self._project_worker.error_sig.connect(self._on_proj_error)
        self._project_worker.start()

    def _stop_index_project(self):
        if self._project_worker and self._project_worker.isRunning():
            self._project_worker.stop()
            self._proj_stop_btn.setEnabled(False)
            self._proj_stat_lbl.setText("Stopping…")

    def _proj_log_line(self, msg: str, level: str = "info"):
        color = _LOG_COLOR.get(level, _LOG_COLOR["info"])
        self._proj_log.append(
            f'<span style="color:{color};">{html.escape(str(msg))}</span>'
        )

    @pyqtSlot(str, str)
    def _on_proj_log(self, msg: str, level: str):
        self._proj_log_line(msg, level)

    @pyqtSlot(int, int, str)
    def _on_proj_progress(self, done: int, total: int, rel_path: str):
        self._proj_bar.setMaximum(total)
        self._proj_bar.setValue(done)
        pct = int(done / total * 100) if total else 0
        self._proj_stat_lbl.setText(f"{done} / {total} files  ({pct}%)")
        self._proj_current_lbl.setText(f"→  {rel_path}")

    @pyqtSlot(dict)
    def _on_proj_done(self, summary: dict):
        self._proj_index_btn.setEnabled(True)
        self._proj_stop_btn.setEnabled(False)
        name   = summary.get("name", "")
        files  = summary.get("files", 0)
        chunks = summary.get("chunks", 0)
        self._proj_stat_lbl.setText(f"Done — {files} files, {chunks} chunks")
        self._proj_current_lbl.setText("")
        self.statusBar().showMessage(
            f"Project '{name}' indexed — {files} files, {chunks} chunks stored."
        )
        self._refresh_projects_list()

    @pyqtSlot(str)
    def _on_proj_error(self, msg: str):
        self._proj_index_btn.setEnabled(True)
        self._proj_stop_btn.setEnabled(False)
        self._proj_log_line(f"ERROR: {msg}", "err")
        self._proj_stat_lbl.setText("Error — see log.")
        self.statusBar().showMessage("Project indexing failed.")

    def _refresh_projects_list(self):
        from indexer.project_indexer import load_all_projects
        storage_path = self._cfg.get("DATA_DIR", "")
        self._project_rows = load_all_projects(storage_path)

        self._proj_table.setRowCount(0)
        for meta in self._project_rows:
            row = self._proj_table.rowCount()
            self._proj_table.insertRow(row)
            indexed_at = meta.get("indexed_at", "")[:10]
            for col, val in enumerate([
                meta.get("name",      ""),
                meta.get("framework", "—"),
                meta.get("language",  "—"),
                str(meta.get("files",  0)),
                str(meta.get("chunks", 0)),
                indexed_at,
            ]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._proj_table.setItem(row, col, item)

        self._on_proj_select()

    def _on_proj_select(self):
        has = bool(self._proj_table.selectedItems())
        self._proj_ask_btn.setEnabled(has)
        self._proj_reindex_btn.setEnabled(has)
        self._proj_delete_btn.setEnabled(has)

    def _selected_project_meta(self) -> dict | None:
        rows = self._proj_table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if idx < len(self._project_rows):
            return self._project_rows[idx]
        return None

    def _ask_about_project(self):
        meta = self._selected_project_meta()
        if not meta:
            return
        topic = meta.get("topic", "")
        name  = meta.get("name",  "")
        # Switch to Chat tab and pre-fill topic
        self._tabs.setCurrentIndex(1)        # Chat is tab 1
        self._chat_topic.setText(topic)
        self._append_chat_system(
            f"Switched context to project: {name}  (topic: {topic})\n"
            f"Ask anything about this codebase — architecture, bugs, refactoring, etc."
        )

    def _reindex_project(self):
        meta = self._selected_project_meta()
        if not meta:
            return
        root = meta.get("root", "")
        if root and os.path.isdir(root):
            self._proj_path_input.setText(root)
            self._start_index_project()
        else:
            _err_dialog(self, "Folder not found",
                        f"Original project folder is no longer accessible:\n{root}")

    def _delete_project(self):
        meta = self._selected_project_meta()
        if not meta:
            return
        name  = meta.get("name",  "")
        topic = meta.get("topic", "")
        box = QMessageBox(self)
        box.setWindowTitle("Delete project?")
        box.setText(
            f"Delete all indexed data for project:\n\n  {name}\n\n"
            f"This removes {meta.get('chunks', 0)} chunk(s) from ChromaDB.\n"
            f"Your original source files are NOT deleted."
        )
        box.setIcon(QMessageBox.Icon.Warning)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        from indexer.project_indexer import delete_project_meta
        storage_path = self._cfg.get("DATA_DIR", "")
        self._vs().delete_topic(topic)
        delete_project_meta(storage_path, name)
        self._refresh_projects_list()
        self.statusBar().showMessage(f"Project '{name}' deleted.")

    # ── Topics Tab ────────────────────────────────────────────────────────────

    def _build_topics_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        btn_row = QHBoxLayout()
        self._refresh_btn = _btn("🔄  Refresh", "secondary")
        self._refresh_btn.clicked.connect(self._refresh_all)
        self._delete_btn = _btn("🗑  Delete Selected", "danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_topic)
        btn_row.addWidget(self._refresh_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._topics_table = QTableWidget(0, 4)
        self._topics_table.setHorizontalHeaderLabels(
            ["Topic", "Chunks", "Est. Pages", "Last Scraped"]
        )
        hdr = self._topics_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._topics_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._topics_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._topics_table.setAlternatingRowColors(True)
        self._topics_table.itemSelectionChanged.connect(
            lambda: self._delete_btn.setEnabled(
                len(self._topics_table.selectedItems()) > 0
            )
        )
        lay.addWidget(self._topics_table, stretch=1)

        self._topics_footer = _lbl("", "hint")
        lay.addWidget(self._topics_footer)
        return tab

    # ── Schedule Tab ──────────────────────────────────────────────────────────

    def _build_sched_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        add_inner = QHBoxLayout()

        st_lay = QVBoxLayout()
        st_lay.addWidget(_lbl("Topic name"))
        self._sched_topic = QLineEdit()
        self._sched_topic.setPlaceholderText("React Js")
        st_lay.addWidget(self._sched_topic)
        add_inner.addWidget(_group("Topic", st_lay))

        sf_lay = QVBoxLayout()
        sf_lay.addWidget(_lbl("Frequency"))
        self._sched_freq = QComboBox()
        for label, val in [("1 day","1"),("3 days","3"),("7 days","7"),
                            ("14 days","14"),("30 days","30")]:
            self._sched_freq.addItem(label, val)
        self._sched_freq.setCurrentIndex(2)
        sf_lay.addWidget(self._sched_freq)
        add_inner.addWidget(_group("Re-learn every", sf_lay))

        add_btn = _btn("+ Add Schedule")
        add_btn.clicked.connect(self._add_schedule)
        add_inner.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        add_inner.addStretch()
        lay.addWidget(_group("New Schedule", add_inner))

        self._sched_table = QTableWidget(0, 3)
        self._sched_table.setHorizontalHeaderLabels(["Topic", "Interval", "Next Run"])
        hdr = self._sched_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._sched_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sched_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sched_table.setAlternatingRowColors(True)
        lay.addWidget(self._sched_table, stretch=1)

        rm_btn = _btn("🗑  Remove Selected", "danger")
        rm_btn.clicked.connect(self._remove_schedule)
        lay.addWidget(rm_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return tab

    # ── Settings Tab ──────────────────────────────────────────────────────────

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)

        # Storage
        stor_lay = QGridLayout()
        stor_lay.setSpacing(8)
        stor_lay.addWidget(QLabel("Storage Path"), 0, 0)
        self._set_path = QLineEdit(self._cfg.get("DATA_DIR", ""))
        stor_lay.addWidget(self._set_path, 0, 1)
        browse2 = _btn("Browse", "secondary")
        browse2.setMinimumWidth(80)
        browse2.clicked.connect(self._browse_settings_path)
        stor_lay.addWidget(browse2, 0, 2)
        stor_lay.addWidget(QLabel("Default Storage Limit"), 1, 0)
        self._set_limit = QComboBox()
        for label, val in [("2 GB","2"),("5 GB","5"),("10 GB","10"),("20 GB","20")]:
            self._set_limit.addItem(label, val)
        idx = self._set_limit.findData(str(int(self._cfg.get("STORAGE_LIMIT_GB", 5))))
        if idx >= 0:
            self._set_limit.setCurrentIndex(idx)
        stor_lay.addWidget(self._set_limit, 1, 1)
        lay.addWidget(_group("Storage", stor_lay))

        # LLM
        llm_lay = QGridLayout()
        llm_lay.setSpacing(8)
        llm_lay.addWidget(QLabel("Model"), 0, 0)
        self._set_llm = QLineEdit(self._cfg.get("LLM_MODEL", "llama3.2"))
        llm_lay.addWidget(self._set_llm, 0, 1)
        llm_lay.addWidget(QLabel("Ollama URL"), 1, 0)
        self._set_ollama = QLineEdit(
            self._cfg.get("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        llm_lay.addWidget(self._set_ollama, 1, 1)
        lay.addWidget(_group("LLM (Ollama)", llm_lay))

        # Crawler
        craw_lay = QGridLayout()
        craw_lay.setSpacing(8)
        craw_lay.addWidget(QLabel("Max Pages"), 0, 0)
        self._set_maxpages = QSpinBox()
        self._set_maxpages.setRange(1, 10000)
        self._set_maxpages.setValue(int(self._cfg.get("CRAWLER_MAX_PAGES", 150)))
        craw_lay.addWidget(self._set_maxpages, 0, 1)
        craw_lay.addWidget(QLabel("Max Depth"), 1, 0)
        self._set_maxdepth = QSpinBox()
        self._set_maxdepth.setRange(1, 20)
        self._set_maxdepth.setValue(int(self._cfg.get("CRAWLER_MAX_DEPTH", 3)))
        craw_lay.addWidget(self._set_maxdepth, 1, 1)
        craw_lay.addWidget(QLabel("Delay (seconds)"), 2, 0)
        self._set_delay = QDoubleSpinBox()
        self._set_delay.setRange(0.0, 30.0)
        self._set_delay.setSingleStep(0.5)
        self._set_delay.setValue(float(self._cfg.get("CRAWLER_DELAY_SECONDS", 1.5)))
        craw_lay.addWidget(self._set_delay, 2, 1)
        lay.addWidget(_group("Crawler", craw_lay))

        save_row = QHBoxLayout()
        save_btn = _btn("💾   Save Settings")
        save_btn.clicked.connect(self._save_settings)
        self._set_status_lbl = _lbl("", "hint")
        save_row.addWidget(save_btn)
        save_row.addWidget(self._set_status_lbl, stretch=1)
        save_row.addStretch()
        lay.addLayout(save_row)
        lay.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return tab

    # ═════════════════════════════════════════════════════════════════════════
    # DATA REFRESH
    # ═════════════════════════════════════════════════════════════════════════

    def _refresh_all(self):
        try:
            self._refresh_sidebar()
        except Exception as e:
            print(f"[sidebar refresh error] {e}")
        try:
            self._refresh_topics_table()
        except Exception as e:
            print(f"[topics refresh error] {e}")
        try:
            self._refresh_projects_list()
        except Exception as e:
            print(f"[projects refresh error] {e}")
        try:
            self._refresh_sched_table()
        except Exception as e:
            print(f"[schedule refresh error] {e}")
        try:
            self._refresh_ask_available()
        except Exception as e:
            print(f"[ask refresh error] {e}")

    def _vs(self) -> VectorStore:
        return VectorStore(storage_path=self._cfg.get("DATA_DIR"))

    def _refresh_sidebar(self):
        try:
            topics = self._vs().list_topics()
            self._sb_topics.setText(
                "\n".join(f"• {t}" for t in topics) if topics else "(none)"
            )
        except Exception:
            self._sb_topics.setText("(error reading topics)")

        try:
            path    = self._cfg.get("DATA_DIR", "")
            lim_gb  = float(self._cfg.get("STORAGE_LIMIT_GB", 5))
            used    = get_folder_size(path)
            lim_b   = int(lim_gb * 1024 ** 3)
            pct     = min(100, int(used / lim_b * 100)) if lim_b else 0
            self._sb_storage_lbl.setText(f"{format_size(used)} / {lim_gb:.0f} GB  ({pct}%)")
            self._sb_storage_bar.setValue(pct)
        except Exception:
            self._sb_storage_lbl.setText("(error)")

    def _refresh_topics_table(self):
        self._topics_table.setRowCount(0)
        self._topic_rows = []
        try:
            vs     = self._vs()
            topics = vs.list_topics()
            total  = 0
            for row, t in enumerate(topics):
                s = vs.get_topic_stats(t)
                self._topics_table.insertRow(row)
                for col, val in enumerate(
                    [t, f"{s['chunks']:,}", f"~{s['estimated_pages']}", s["last_scraped"]]
                ):
                    self._topics_table.setItem(row, col, QTableWidgetItem(val))
                self._topic_rows.append(t)
                total += s["chunks"]
            self._topics_footer.setText(
                f"Total: {len(topics)} topic(s),  {total:,} chunks"
            )
        except Exception as e:
            self._topics_footer.setText(f"Error: {e}")

    def _refresh_sched_table(self):
        self._sched_table.setRowCount(0)
        self._sched_jobs = self._scheduler.get_jobs()
        for row, job in enumerate(self._sched_jobs):
            self._sched_table.insertRow(row)
            self._sched_table.setItem(row, 0, QTableWidgetItem(job["topic"]))
            self._sched_table.setItem(row, 1, QTableWidgetItem(f"Every {job['interval_days']} day(s)"))
            self._sched_table.setItem(row, 2, QTableWidgetItem(job["next_run"]))

    def _refresh_ask_available(self):
        try:
            topics = self._vs().list_topics()
            lbl = ", ".join(topics) if topics else "(none yet — run Learn first)"
            self._ask_available_lbl.setText(f"Available topics:  {lbl}")
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════════════════════
    # LEARN TAB
    # ═════════════════════════════════════════════════════════════════════════

    def _browse_learn_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Storage Folder")
        if folder:
            self._path_input.setText(os.path.normpath(folder))

    def _start_crawl(self):
        try:
            self._do_start_crawl()
        except Exception as e:
            _err_dialog(self, "Start Error", f"Could not start crawl:\n\n{e}")
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)

    def _do_start_crawl(self):
        raw_input    = self._learn_input.text().strip()
        storage_path = self._path_input.text().strip()
        limit_gb     = float(self._limit_combo.currentData() or "5")
        max_pages    = self._maxpages_spin.value()

        if not raw_input:
            _err_dialog(self, "Missing Input", "Please enter a topic or learning instruction.")
            return

        if not storage_path:
            storage_path = self._cfg.get("DATA_DIR", "")
        if not storage_path:
            _err_dialog(self, "Missing Path", "Storage path is not set. Check Settings.")
            return

        storage_path = os.path.normpath(storage_path)
        topic = extract_topic(raw_input)

        # Storage limit preflight
        ok, used, lim = within_limit(storage_path, limit_gb)
        if not ok:
            _err_dialog(
                self, "Storage Full",
                f"Storage is full:\n{format_size(used)} used / {format_size(lim)} limit.\n\n"
                "Increase the limit or choose a different storage path."
            )
            return

        # Create dirs
        os.makedirs(storage_path, exist_ok=True)

        # Check seed URLs exist for this topic
        from crawler.seed_urls import get_seed_urls
        seeds = get_seed_urls(topic)
        if not seeds:
            _err_dialog(
                self, "No Seed URLs",
                f"No pre-configured URLs found for topic: '{topic}'\n\n"
                "Add an entry to crawler/seed_urls.py, or the topic name must match "
                "one of: react, python, typescript, nodejs, docker, nextjs, fastapi"
            )
            return

        # Reset UI
        self._activity_log.clear()
        self._crawl_bar.setMaximum(max_pages)
        self._crawl_bar.setValue(0)
        self._eta_lbl.setText("")
        self._storage_stat.setText("")
        self._learn_storage_bar.setValue(0)
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._set_status(f"Starting crawl: {topic}", "ok")

        self._append_log(f"Topic:     {topic}", "info")
        self._append_log(f"Path:      {storage_path}  (limit {limit_gb:.0f} GB)", "info")
        self._append_log(f"Max pages: {max_pages}", "info")
        self._append_log(f"Seeds:     {len(seeds)} URL(s)", "info")
        self._append_log("─" * 60, "info")
        self.statusBar().showMessage(f"Crawling: {topic}")

        # Start background worker
        self._crawl_worker = CrawlWorker(topic, storage_path, limit_gb, max_pages)
        self._crawl_worker.log_sig.connect(self._on_crawl_log)
        self._crawl_worker.status_sig.connect(self._on_crawl_status)
        self._crawl_worker.eta_sig.connect(self._eta_lbl.setText)
        self._crawl_worker.progress_sig.connect(self._on_crawl_progress)
        self._crawl_worker.storage_sig.connect(self._on_storage_update)
        self._crawl_worker.done_sig.connect(self._on_crawl_done)
        self._crawl_worker.start()

    def _stop_crawl(self):
        if self._crawl_worker:
            self._crawl_worker.stop()
        self._set_status("Stopping after current page…", "warn")

    # ── Worker slots ──────────────────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_crawl_log(self, msg: str, level: str):
        self._append_log(msg, level)

    @pyqtSlot(str)
    def _on_crawl_status(self, msg: str):
        self._crawl_status.setText(msg)

    @pyqtSlot(int, int)
    def _on_crawl_progress(self, current: int, total: int):
        self._crawl_bar.setMaximum(total)
        self._crawl_bar.setValue(current)

    @pyqtSlot(int, int)
    def _on_storage_update(self, used: int, limit: int):
        pct = min(100, int(used / limit * 100)) if limit else 0
        self._learn_storage_bar.setValue(pct)
        self._storage_stat.setText(
            f"Storage: {format_size(used)} / {format_size(limit)}"
        )

    @pyqtSlot(int, int)
    def _on_crawl_done(self, pages: int, chunks: int):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._append_log("─" * 60, "info")
        if pages == 0:
            self._append_log("No pages were crawled. Check the activity log for details.", "warn")
            self._set_status("No pages crawled.", "warn")
        else:
            self._append_log(f"Done — {pages} pages,  {chunks:,} chunks saved.", "ok")
            self._set_status(f"Complete: {pages} pages, {chunks:,} chunks.", "ok")
        self._eta_lbl.setText("")
        self.statusBar().showMessage(
            f"Done — {pages} pages, {chunks:,} chunks saved."
        )
        self._refresh_all()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, level: str = "ok"):
        obj_map = {"ok": "status-ok", "warn": "status-warn", "err": "status-err"}
        self._crawl_status.setText(msg)
        self._crawl_status.setObjectName(obj_map.get(level, "status-ok"))
        # Force style refresh
        self._crawl_status.style().unpolish(self._crawl_status)
        self._crawl_status.style().polish(self._crawl_status)

    def _append_log(self, msg: str, level: str = "info"):
        color   = _LOG_COLOR.get(level, "#cdd6f4")
        safe    = html.escape(msg)          # prevent HTML injection from page titles
        self._activity_log.append(
            f'<span style="color:{color};">{safe}</span>'
        )
        sb = self._activity_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ═════════════════════════════════════════════════════════════════════════
    # ASK TAB
    # ═════════════════════════════════════════════════════════════════════════

    def _run_ask(self):
        try:
            self._do_run_ask()
        except Exception as e:
            _err_dialog(self, "Ask Error", f"Could not run query:\n\n{e}")
            self._ask_btn.setEnabled(True)

    def _do_run_ask(self):
        topic    = self._ask_topic.text().strip()
        question = self._ask_question.text().strip()

        if not topic:
            _err_dialog(self, "Missing Topic", "Enter a topic name (e.g. React Js).")
            return
        if not question:
            _err_dialog(self, "Missing Question", "Enter a question.")
            return

        self._ask_btn.setEnabled(False)
        self._ask_status.setText("Searching knowledge base…")
        self._answer_edit.clear()
        self._sources_edit.clear()

        storage_path = self._cfg.get("DATA_DIR", "")
        self._ask_worker = AskWorker(topic, question, storage_path)
        self._ask_worker.answer_sig.connect(self._on_answer)
        self._ask_worker.status_sig.connect(self._ask_status.setText)
        self._ask_worker.error_sig.connect(self._on_ask_error)
        self._ask_worker.finished.connect(lambda: self._ask_btn.setEnabled(True))
        self._ask_worker.start()

    @pyqtSlot(str, list)
    def _on_answer(self, answer: str, sources: list):
        self._answer_edit.setPlainText(answer)
        if sources:
            lines = "\n".join(
                f"[{s['num']}] {s['title']}\n    {s['url']}" for s in sources
            )
        else:
            lines = "(No sources found — try running Learn first)"
        self._sources_edit.setPlainText(lines)

    @pyqtSlot(str)
    def _on_ask_error(self, msg: str):
        self._answer_edit.setPlainText(f"Error:\n\n{msg}")
        self._ask_status.setText("Failed — see answer panel.")

    # ═════════════════════════════════════════════════════════════════════════
    # TOPICS TAB
    # ═════════════════════════════════════════════════════════════════════════

    def _delete_topic(self):
        try:
            rows = sorted(
                {idx.row() for idx in self._topics_table.selectedIndexes()},
                reverse=True,
            )
            if not rows:
                return
            vs = self._vs()
            for row in rows:
                if row < len(self._topic_rows):
                    vs.delete_topic(self._topic_rows[row])
            self._delete_btn.setEnabled(False)
            self._refresh_all()
        except Exception as e:
            _err_dialog(self, "Delete Error", str(e))

    # ═════════════════════════════════════════════════════════════════════════
    # SCHEDULE TAB
    # ═════════════════════════════════════════════════════════════════════════

    def _add_schedule(self):
        try:
            topic = self._sched_topic.text().strip()
            days  = int(self._sched_freq.currentData() or "7")
            if not topic:
                _err_dialog(self, "Missing Topic", "Enter a topic name.")
                return
            self._scheduler.set_schedule(topic, days)
            schedules       = self._cfg.get("SCHEDULES", {})
            schedules[topic] = days
            self._cfg["SCHEDULES"] = schedules
            config.save_all(self._cfg)
            self._refresh_sched_table()
        except Exception as e:
            _err_dialog(self, "Schedule Error", str(e))

    def _remove_schedule(self):
        try:
            rows = sorted(
                {idx.row() for idx in self._sched_table.selectedIndexes()},
                reverse=True,
            )
            for row in rows:
                if row < len(self._sched_jobs):
                    topic = self._sched_jobs[row]["topic"]
                    self._scheduler.remove_schedule(topic)
                    sched = self._cfg.get("SCHEDULES", {})
                    sched.pop(topic, None)
                    self._cfg["SCHEDULES"] = sched
                    config.save_all(self._cfg)
            self._refresh_sched_table()
        except Exception as e:
            _err_dialog(self, "Remove Error", str(e))

    # Scheduler fires from background thread → queue → QTimer polls on main thread
    def _on_schedule_fire(self, topic: str):
        self._sched_queue.put(topic)

    def _poll_sched_queue(self):
        try:
            while True:
                topic = self._sched_queue.get_nowait()
                self._append_log(f"Scheduled re-learn triggered: {topic}", "warn")
                self.statusBar().showMessage(f"Scheduled re-learn: {topic}")
        except queue.Empty:
            pass

    # ═════════════════════════════════════════════════════════════════════════
    # SETTINGS TAB
    # ═════════════════════════════════════════════════════════════════════════

    def _browse_settings_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Storage Folder")
        if folder:
            self._set_path.setText(os.path.normpath(folder))

    def _save_settings(self):
        try:
            new_cfg = dict(self._cfg)
            path = self._set_path.text().strip()
            if not path:
                _err_dialog(self, "Missing Path", "Storage path cannot be empty.")
                return
            new_cfg["DATA_DIR"]               = os.path.normpath(path)
            new_cfg["STORAGE_LIMIT_GB"]       = float(self._set_limit.currentData() or "5")
            new_cfg["LLM_MODEL"]              = self._set_llm.text().strip()
            new_cfg["OLLAMA_BASE_URL"]        = self._set_ollama.text().strip()
            new_cfg["CRAWLER_MAX_PAGES"]      = self._set_maxpages.value()
            new_cfg["CRAWLER_MAX_DEPTH"]      = self._set_maxdepth.value()
            new_cfg["CRAWLER_DELAY_SECONDS"]  = self._set_delay.value()

            config.save_all(new_cfg)
            self._cfg = new_cfg

            # Sync Learn tab fields
            self._path_input.setText(new_cfg["DATA_DIR"])
            idx = self._limit_combo.findData(str(int(new_cfg["STORAGE_LIMIT_GB"])))
            if idx >= 0:
                self._limit_combo.setCurrentIndex(idx)

            self._set_status_lbl.setText(
                "✓  Settings saved.  Changes take effect on next crawl/ask."
            )
            self._refresh_sidebar()
        except Exception as e:
            _err_dialog(self, "Save Error", f"Could not save settings:\n\n{e}")
