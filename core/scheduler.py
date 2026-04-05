"""
Lightweight topic re-learning scheduler.

Schedules are persisted in config (settings.json) as:
  "SCHEDULES": {"React JS": 7, "Python": 14}   # topic → interval_days

A background daemon thread calls schedule.run_pending() every 60 s.
When a job fires, it calls the on_trigger(topic) callback (from the bg thread).
The caller must use app.call_from_thread() to reach the UI thread safely.
"""
import threading, time, logging
import schedule as _sched

log = logging.getLogger(__name__)


class TopicScheduler:
    def __init__(self, on_trigger):
        self._on_trigger = on_trigger   # callable(topic: str)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # ── Public API ─────────────────────────────────────────────────────────

    def load_from_config(self, schedules: dict):
        """Register all saved schedules (called on app start)."""
        for topic, days in schedules.items():
            self._register(topic, int(days))

    def set_schedule(self, topic: str, every_n_days: int):
        with self._lock:
            _sched.clear(topic)
            self._register(topic, every_n_days)

    def remove_schedule(self, topic: str):
        with self._lock:
            _sched.clear(topic)

    def get_jobs(self) -> list:
        """Return list of {topic, interval_days, next_run} dicts."""
        out = []
        for job in _sched.get_jobs():
            tag = next(iter(job.tags), None)
            if tag:
                out.append({
                    "topic":        tag,
                    "interval_days": int(job.interval),
                    "next_run":      str(job.next_run)[:16],
                })
        return out

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="scheduler")
        self._thread.start()

    def stop(self):
        self._stop.set()

    # ── Internal ───────────────────────────────────────────────────────────

    def _register(self, topic: str, days: int):
        _sched.every(days).days.do(self._fire, topic).tag(topic)

    def _fire(self, topic: str):
        try:
            self._on_trigger(topic)
        except Exception as e:
            log.warning(f"Scheduler trigger error for '{topic}': {e}")

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                _sched.run_pending()
            self._stop.wait(60)
