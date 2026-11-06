"""Worker idle-loop liveness, not interview/provider readiness."""
import os
from pathlib import Path
import time

HEARTBEAT = Path('/tmp/openinterview-worker-heartbeat')


def healthy(path=HEARTBEAT):
    try:
        pid = int(path.read_text())
        if pid <= 0 or not 0 <= time.time() - path.stat().st_mtime < 20:
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


if __name__ == '__main__':
    raise SystemExit(0 if healthy() else 1)
