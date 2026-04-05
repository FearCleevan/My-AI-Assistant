"""
Background QThread worker for indexing a project directory.
Emits signals so the GUI can update progress without blocking.
"""
from __future__ import annotations
import os, sys, threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QThread, pyqtSignal

from indexer.project_indexer import index_project


class ProjectWorker(QThread):
    log_sig      = pyqtSignal(str, str)        # (message, level)
    progress_sig = pyqtSignal(int, int, str)   # (files_done, total_files, current_rel_path)
    done_sig     = pyqtSignal(dict)            # summary dict from index_project()
    error_sig    = pyqtSignal(str)

    def __init__(self, root: str, storage_path: str):
        super().__init__()
        self.root         = root
        self.storage_path = storage_path
        self._stop        = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            def on_file(finfo, files_done, total):
                self.progress_sig.emit(files_done, total, finfo["rel_path"])

            def on_log(msg: str, level: str = "info"):
                self.log_sig.emit(str(msg), level)

            summary = index_project(
                root         = self.root,
                storage_path = self.storage_path,
                stop_event   = self._stop,
                on_file      = on_file,
                on_log       = on_log,
            )
            self.done_sig.emit(summary)

        except Exception as exc:
            import traceback
            self.error_sig.emit(f"{exc}\n{traceback.format_exc()}")
