"""Opt-in auth-only supervisor. No voice workers, migrations or provider probes."""
import os
import shutil
import signal
import subprocess
import sys
import time

from voice_test import ROOT, alive, check_ports, cleanup, http_ready, wait_ready, web_env


def preflight():
    python = ROOT / '.venv/bin/python'
    if os.name != 'posix':
        raise RuntimeError('Auth launcher requires POSIX process groups.')
    if not os.access(python, os.X_OK) or not (ROOT / '.env').is_file():
        raise RuntimeError('Create .venv, install backend requirements and configure private .env; see docs/contributing/google-auth.md.')
    if not all(shutil.which(name) for name in ('node', 'npm')) or not (ROOT / 'node_modules/next/dist/bin/next').is_file():
        raise RuntimeError('Install Node and run npm ci first.')
    result = subprocess.run([str(python), '-m', 'backend.auth', 'check', '--env-file', '.env'], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
    if result.returncode:
        raise RuntimeError('Auth setup failed. Check Google OAuth, AUTH_SESSION_SECRET and DATABASE_* settings; provision PostgreSQL and explicitly run .venv/bin/python -m backend.auth migrate --env-file .env. See docs/contributing/google-auth.md.')
    return python


def main():
    children = []
    previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        check_ports()
        python = preflight()
        def start(name, command, env=None):
            process = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append((name, process))
        start('api', [str(python), '-m', 'uvicorn', 'backend.api:app', '--env-file', '.env',
                      '--host', '127.0.0.1', '--port', '8000', '--no-proxy-headers', '--no-access-log'],
              env={**os.environ, 'LOCAL_VOICE_ENABLED': 'false'})
        wait_ready(children, lambda: http_ready('http://127.0.0.1:8000/health'))
        start('web', [str(python), 'tests/verify_local.py', '--dev'], env=web_env())
        wait_ready(children, lambda: http_ready('http://127.0.0.1:3000/login'), timeout=120)
        print('Ready: http://127.0.0.1:3000/login (or /signup). Google is contacted only when you continue. Ctrl+C stops API/web.', flush=True)
        while True:
            alive(children)
            time.sleep(.2)
    except KeyboardInterrupt:
        return 130
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print('Auth launcher failed. Check dependencies, database/schema and private configuration; details withheld.', file=sys.stderr)
        return 1
    finally:
        cleanup(children)
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    sys.exit(main())
