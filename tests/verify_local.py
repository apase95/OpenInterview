"""Explicit local startup/build verification. No root .env or provider calls.

Run with the backend test venv Python. Web is copied from an exact allowlist.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = 'FAKE_PROVIDER_SECRET_7b02e194'
ENV = {key: os.environ[key] for key in ('PATH', 'HOME', 'SYSTEMROOT') if key in os.environ}
ENV.update(NEXT_TELEMETRY_DISABLED='1', GOOGLE_API_KEY=SENTINEL,
           LIVEKIT_API_SECRET=SENTINEL, DEEPGRAM_API_KEY=SENTINEL, ELEVEN_API_KEY=SENTINEL)


def run(command, cwd):
    started = time.monotonic()
    subprocess.run(command, cwd=cwd, env=ENV, check=True, timeout=180)
    print(f'PASS {" ".join(command)} ({time.monotonic() - started:.2f}s)', flush=True)


def available_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def get_started(command, cwd, url):
    process = subprocess.Popen(command, cwd=cwd, env=ENV, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                raise AssertionError('Server exited before HTTP check')
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    assert response.status == 200
                    body = response.read().decode()
                # Reject a bind-race response from another server while our child exits.
                time.sleep(0.2)
                if process.poll() is not None:
                    raise AssertionError('Server exited during HTTP check')
                return body
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        finally:
            # Also reap descendants even if the session leader exited first.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)


def main():
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='openinterview-web-') as directory:
        web = Path(directory)
        for filename in ('package.json', 'package-lock.json', 'tsconfig.json', 'next-env.d.ts',
                         'app/layout.tsx', 'app/page.tsx', 'app/globals.css',
                         'postcss.config.mjs', 'next.config.mjs',
                         'public/images/logo.svg', 'public/images/robot.svg'):
            target = web / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / filename, target)
        # Keep traced packages inside the isolated root for standalone output too.
        shutil.copytree(ROOT / 'node_modules', web / 'node_modules', symlinks=True)
        run(['npm', 'run', 'build'], web)
        run(['npm', 'run', 'typecheck'], web)
        port = available_port()
        html = get_started(['node', str(web / 'node_modules/next/dist/bin/next'), 'start',
                            '--hostname', '127.0.0.1', '--port', str(port)], web, f'http://127.0.0.1:{port}/')
        for text in ('Start with a', 'conversation.', 'View roles', 'I have an invitation', 'Voice interview', '/images/robot.svg'):
            assert text in html, text
        for text in ('>Example<', 'AI is speaking', '>Voice interviews in Vietnamese<', 'waveform'):
            assert text not in html, text
        assert SENTINEL not in html
        files = list((web / '.next/static').rglob('*'))
        assert any(path.is_file() for path in files)
        assert any('.h-14' in path.read_text() for path in files if path.suffix == '.css')
        for path in files:
            if path.is_file():
                assert SENTINEL.encode() not in path.read_bytes(), str(path)
        print('PASS production Home HTTP 200/content and fake-secret scan of HTML + .next/static')
    port = available_port()
    result = get_started([sys.executable, '-m', 'uvicorn', 'backend.api:app', '--host', '127.0.0.1', '--port', str(port)], ROOT, f'http://127.0.0.1:{port}/health')
    assert json.loads(result) == {'status': 'ok', 'service': 'api'}
    print(f'PASS independent API HTTP /health; verification total {time.monotonic() - started:.2f}s')


if __name__ == '__main__':
    main()
