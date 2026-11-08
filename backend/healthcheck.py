# %%
"""Worker idle-loop liveness, not interview/provider readiness.

The heartbeat is local process evidence only; no remote service is contacted.
A fresh timestamp and existing PID do not prove a voice session can succeed.
"""
import os
from pathlib import Path
import time

HEARTBEAT = Path('/tmp/openinterview-worker-heartbeat')


# %%
# Require a positive PID, a nonfuture heartbeat under twenty seconds old and a
# successful process-existence probe. Missing files or denied probes fail closed.
def healthy(path=HEARTBEAT):
    try:
        pid = int(path.read_text())
        if pid <= 0 or not 0 <= time.time() - path.stat().st_mtime < 20:
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


# %%
# Container probes consume the exit status rather than diagnostic output.
if __name__ == '__main__':
    raise SystemExit(0 if healthy() else 1)
