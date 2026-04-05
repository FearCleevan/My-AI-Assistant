"""
ChatWorker — background QThread for Phase 1 Chat tab.

Handles:
  - Multi-turn conversation with history
  - File parsing (PDF, TXT, code files, JSON, Markdown)
  - Token streaming back to UI
  - RAG search against ChromaDB
  - Model selection
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from query.rag import RAGEngine

from PyQt6.QtCore import QThread, pyqtSignal


# ── File parsers ──────────────────────────────────────────────────────────────

def parse_file(path: str) -> tuple[str, str]:
    """
    Parse a file and return (content: str, label: str).
    Raises ValueError for unsupported types or parse failures.
    """
    ext  = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)

    # PDF
    if ext == ".pdf":
        return _parse_pdf(path), f"📄 {name}"

    # Plain text / code / config
    text_exts = {
        ".txt", ".md", ".markdown", ".rst",
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".html", ".css", ".scss", ".sass",
        ".json", ".yaml", ".yml", ".toml", ".env",
        ".sh", ".bash", ".zsh", ".fish",
        ".cpp", ".c", ".h", ".java", ".go",
        ".rs", ".rb", ".php", ".cs", ".swift",
        ".kt", ".dart", ".sql", ".graphql",
        ".xml", ".csv", ".ini", ".cfg",
    }
    if ext in text_exts or ext == "":
        return _parse_text(path), f"📝 {name}"

    raise ValueError(
        f"Unsupported file type: '{ext}'\n"
        "Supported: PDF, TXT, MD, PY, JS, TS, TSX, JSX, JSON, YAML, SQL, and most code files."
    )


def _parse_text(path: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                content = f.read()
            # Truncate very large files to 20k chars to stay within token limits
            if len(content) > 20_000:
                content = content[:20_000] + f"\n\n... [truncated — file is {len(content):,} chars total]"
            return content
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode file: {os.path.basename(path)}")


def _parse_pdf(path: str) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        pages  = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i+1}]\n{text.strip()}")
        content = "\n\n".join(pages)
        if len(content) > 20_000:
            content = content[:20_000] + "\n\n... [truncated]"
        return content
    except ImportError:
        raise ValueError(
            "PDF support requires pypdf.\n"
            "Install it with:  pip install pypdf"
        )
    except Exception as e:
        raise ValueError(f"Could not read PDF: {e}")


# ── Worker ────────────────────────────────────────────────────────────────────

class ChatWorker(QThread):
    token_sig  = pyqtSignal(str)         # each streamed token
    done_sig   = pyqtSignal(str, list)   # (full_answer, sources)
    error_sig  = pyqtSignal(str)

    def __init__(
        self,
        question:     str,
        topic:        str,
        history:      list[dict],
        storage_path: str,
        file_context: str = "",
        model:        str | None = None,
    ):
        super().__init__()
        self.question     = question
        self.topic        = topic
        self.history      = history
        self.storage_path = storage_path
        self.file_context = file_context
        self.model        = model
        self._tokens:     list[str] = []

    def run(self):
        try:
            rag   = RAGEngine(storage_path=self.storage_path)
            check = rag.check_ollama()
            if not check["ok"]:
                self.error_sig.emit(
                    f"{check['reason']}\n\nFix: {check['suggestion']}"
                )
                return

            def on_token(tok: str):
                self._tokens.append(tok)
                self.token_sig.emit(tok)

            result = rag.chat(
                question     = self.question,
                topic        = self.topic,
                history      = self.history,
                file_context = self.file_context,
                model        = self.model,
                on_token     = on_token,
            )
            self.done_sig.emit(result["answer"], result["sources"])

        except Exception as e:
            import traceback
            self.error_sig.emit(f"{e}\n\n{traceback.format_exc()}")
