# %%
"""Opt-in POSIX voice supervisor. Never print config or arbitrary child output.

Uses private local settings and starts API, cloud-connected worker and web copy.
Worker startup can register with cloud services; voice use may cost money.
Only owned process groups are stopped here; remote cleanup belongs to the worker.
Readiness does not prove browser audio delivery or provider quality.
"""
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REGISTERED = 'Local voice worker registered; waiting for jobs.'


# %%
def web_env():
    """Pass only basic OS paths to the web launcher, not provider credentials."""
    return {key: os.environ[key] for key in ('PATH', 'HOME', 'SYSTEMROOT') if key in os.environ}


def preflight():
    """Validate installed tools and local settings before any worker is launched."""
    python = ROOT / '.venv/bin/python'
    if os.name != 'posix':
        raise RuntimeError('This launcher requires POSIX process groups (Linux/macOS).')
    if not os.access(python, os.X_OK):
        raise RuntimeError('Create .venv with Python 3.12; install backend/requirements-test.txt (see development guide).')
    if not (ROOT / '.env').is_file():
        raise RuntimeError('Copy .env.example to .env and edit it privately; see development guide.')
    if not all(shutil.which(name) for name in ('node', 'npm')) or not all(
            (ROOT / path).exists() for path in ('node_modules/next/dist/bin/next', 'node_modules/livekit-client', 'node_modules/typescript')):
        raise RuntimeError('Install Node and run npm ci first.')
    # These functions only validate local config; no network or model download.
    code = '''from backend.config import load_config
from backend.api import voice_settings
import uvicorn
from livekit.agents import AgentServer
from livekit.plugins import deepgram, google, elevenlabs, silero
load_config()
_, origins, *_ = voice_settings()
assert 'http://127.0.0.1:3000' in origins
'''
    result = subprocess.run([str(python), '-c', code], cwd=ROOT, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=20)
    if result.returncode:
        raise RuntimeError('Check backend dependencies and private .env: six provider settings, development voice gates, separate 32+ character secret, and origin http://127.0.0.1:3000. See development guide.')
    return python


# %%
def check_ports():
    """Probe loopback ports without stopping existing services.

    Closing each probe releases its port, so startup still has a bind race.
    """
    for port in (8000, 3000):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                raise RuntimeError(f'Port {port} unavailable. Ctrl+C the old API/web terminals yourself; no process was stopped.') from None


def http_ready(url):
    """Treat a direct HTTP 200 as readiness, not an end-to-end session check."""
    try:
        # Ignore proxy environment, including credentials embedded in proxy URLs.
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def alive(children):
    """Fail if any recorded child has exited; never inspect unrelated processes."""
    for name, process in children:
        if process.poll() is not None:
            raise RuntimeError(f'{name} exited unexpectedly; startup/session stopped. Check private configuration and setup instructions.')


def wait_ready(children, ready, timeout=60):
    """Bound readiness polling and recheck child survival after a positive probe."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        alive(children)
        if ready():
            time.sleep(0.2)
            alive(children)
            return
        time.sleep(0.1)
    raise RuntimeError('Timed out waiting for readiness; check configuration, model download and provider connectivity.')


# %%
def cleanup(children):
    """Signal owned POSIX groups, then force-stop survivors with bounded waits."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for _, process in reversed(children):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 5
        for _, process in children:
            try:
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass


def worker_output(process, registered):
    """Forward only fixed safe status lines and signal observed registration."""
    allowed = {REGISTERED, 'Local voice worker starting; registration pending.',
               'Local voice recording failed; session stopped (details suppressed).',
               'Local voice worker failed (configuration, startup or connection failure).',
               'Local voice session stopped (timeout or service failure).'}
    for line in process.stdout:
        text = line.strip()
        if text in allowed:
            print('[worker] ' + text, flush=True)
            if text == REGISTERED:
                registered.set()


# %%
def main():
    """Start owned sessions and clean them up on failure, Ctrl+C or SIGTERM."""
    children = []
    old_handler = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        python = preflight()
        check_ports()
        print('Starting dedicated voice test. Cloud registration/cleanup begins now; voice services may cost money. Ctrl+C stops owned services.', flush=True)

        def start(name, command, **kwargs):
            process = subprocess.Popen(command, cwd=ROOT, start_new_session=True,
                                       stderr=subprocess.DEVNULL, **kwargs)
            children.append((name, process))
            return process

        start('api', [str(python), '-m', 'uvicorn', 'backend.api:app', '--env-file', '.env',
                      '--host', '127.0.0.1', '--port', '8000', '--no-proxy-headers', '--no-access-log'], stdout=subprocess.DEVNULL)
        wait_ready(children, lambda: http_ready('http://127.0.0.1:8000/health'))
        registered = threading.Event()
        worker = start('worker', [str(python), '-m', 'backend.worker', '--voice', 'start'],
                       stdout=subprocess.PIPE, text=True)
        threading.Thread(target=worker_output, args=(worker, registered), daemon=True).start()
        wait_ready(children, registered.is_set)
        start('web', [str(python), 'tests/verify_local.py', '--dev'], env=web_env(), stdout=subprocess.DEVNULL)
        wait_ready(children, lambda: http_ready('http://127.0.0.1:3000/local-voice'), timeout=120)
        print('Ready: http://127.0.0.1:3000/local-voice\nEnter the separate local secret in the page; consent before Start. Ctrl+C stops all three services.', flush=True)
        while True:
            alive(children)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print('Stopping owned voice services.', flush=True)
        return 130
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print('Voice launcher failed; owned services will stop. Check local setup (details withheld to protect secrets).', file=sys.stderr)
        return 1
    finally:
        cleanup(children)
        signal.signal(signal.SIGTERM, old_handler)


# %%
if __name__ == '__main__':
    sys.exit(main())
