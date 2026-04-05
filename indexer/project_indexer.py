"""
Project indexer — orchestrates scan → chunk → embed → store for a local folder.
Metadata (framework, file count, etc.) is saved alongside the ChromaDB data so
the Projects tab can display rich info without re-querying the vector DB.
"""
from __future__ import annotations
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from indexer.project_scanner import scan_project, detect_project_type
from pipeline.chunker        import chunk_text
from pipeline.embedder       import embed_chunks
from storage.vector_store    import VectorStore

# ── Tuning ────────────────────────────────────────────────────────────────────
# Code is denser than prose — use smaller chunks so each one stays coherent
_CODE_CHUNK_SIZE    = 150   # words per chunk
_CODE_CHUNK_OVERLAP = 25

# Directory where per-project JSON metadata is stored
_META_DIR = "projects"


def project_topic(name: str) -> str:
    """Canonical ChromaDB topic name for a project."""
    return "project:" + name.lower().replace(" ", "_").replace("-", "_")


def _meta_dir(storage_path: str) -> Path:
    d = Path(storage_path) / _META_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_project_meta(storage_path: str, meta: dict):
    """Persist project metadata as JSON so the UI can list projects quickly."""
    safe = meta["name"].lower().replace(" ", "_").replace("-", "_")
    path = _meta_dir(storage_path) / f"{safe}.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def load_all_projects(storage_path: str) -> list[dict]:
    """Return all persisted project metadata dicts, newest-first."""
    meta_dir = _meta_dir(storage_path)
    projects = []
    for jf in sorted(meta_dir.glob("*.json"), reverse=True):
        try:
            projects.append(json.loads(jf.read_text(encoding="utf-8")))
        except Exception:
            pass
    return projects


def delete_project_meta(storage_path: str, project_name: str):
    """Remove the JSON metadata file for a project."""
    safe = project_name.lower().replace(" ", "_").replace("-", "_")
    path = _meta_dir(storage_path) / f"{safe}.json"
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def index_project(
    root:         str,
    storage_path: str | None = None,
    stop_event:   threading.Event | None = None,
    on_file=None,    # callable(file_info, files_done, total_files)
    on_log=None,     # callable(message, level)
) -> dict:
    """
    Index an entire project directory into ChromaDB.

    Returns a summary dict with keys:
      name, root, topic, framework, language, entry_points,
      description, files, chunks, indexed_at
    """
    storage_path = storage_path or config.DATA_DIR

    def log(msg: str, level: str = "info"):
        if on_log:
            on_log(msg, level)

    # ── 1. Detect project type / metadata ─────────────────────────────────
    meta  = detect_project_type(root)
    name  = meta["name"]
    topic = project_topic(name)

    log(f"Project : {name}", "ok")
    log(f"Root    : {root}", "info")
    log(f"Stack   : {meta['framework']}  /  {meta['language']}", "info")
    if meta["description"]:
        log(f"Desc    : {meta['description']}", "info")
    if meta["entry_points"]:
        log(f"Entry   : {', '.join(meta['entry_points'])}", "info")

    # ── 2. Scan files ──────────────────────────────────────────────────────
    log("Scanning files…", "info")
    all_files = list(scan_project(root))
    total     = len(all_files)
    log(f"Found {total} indexable file(s).", "info")

    if total == 0:
        log("Nothing to index — no supported source files found.", "warn")
        summary = {
            **meta,
            "topic":      topic,
            "files":      0,
            "chunks":     0,
            "indexed_at": _now(),
        }
        save_project_meta(storage_path, summary)
        return summary

    # ── 3. Chunk → embed → store each file ────────────────────────────────
    vs           = VectorStore(storage_path=storage_path)
    files_done   = 0
    chunks_saved = 0

    for finfo in all_files:
        if stop_event and stop_event.is_set():
            log("Indexing stopped by user.", "warn")
            break

        rel_path = finfo["rel_path"]
        language = finfo["language"]

        try:
            text = Path(finfo["path"]).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            log(f"  Skip {rel_path}: {exc}", "warn")
            continue

        if not text.strip():
            continue

        # Use the relative path as a pseudo-URL so chunk IDs are stable
        pseudo_url = f"file://{rel_path.replace(os.sep, '/')}"
        title      = f"{rel_path}  [{language}]"

        chunks = chunk_text(
            text, pseudo_url, title, topic,
            chunk_size    = _CODE_CHUNK_SIZE,
            chunk_overlap = _CODE_CHUNK_OVERLAP,
        )
        if not chunks:
            continue

        chunks  = embed_chunks(chunks)
        saved   = vs.save_chunks(chunks, topic)
        chunks_saved += saved
        files_done   += 1

        if on_file:
            on_file(finfo, files_done, total)

    # ── 4. Persist metadata ────────────────────────────────────────────────
    summary = {
        **meta,
        "topic":      topic,
        "files":      files_done,
        "chunks":     chunks_saved,
        "indexed_at": _now(),
    }
    save_project_meta(storage_path, summary)

    log(f"Indexed {files_done}/{total} files  →  {chunks_saved} chunks stored.", "ok")
    return summary


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
