from datetime import datetime, timedelta
from pathlib import Path

SCREEN_DIR = Path.home() / ".ss_ai"
RETENTION_DAYS = 3


def cleanup_old_screens():
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    for f in SCREEN_DIR.glob("*.png"):
        try:
            mtime = datetime.utcfromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
        except Exception:
            pass
