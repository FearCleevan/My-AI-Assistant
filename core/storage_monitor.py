import os


def get_folder_size(path: str) -> int:
    """Total bytes used by a directory tree."""
    total = 0
    if not os.path.exists(path):
        return 0
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def format_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def usage_bar(used: int, limit: int, width: int = 10) -> str:
    pct = min(1.0, used / limit) if limit > 0 else 0
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


def within_limit(path: str, limit_gb: float) -> tuple:
    """Returns (ok: bool, used_bytes: int, limit_bytes: int)."""
    limit = int(limit_gb * 1024 ** 3)
    used = get_folder_size(path)
    return used < limit, used, limit
