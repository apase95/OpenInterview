"""Explicit local startup/build verification. No root .env or provider calls.

Run with the backend test venv Python. Web is copied from an exact allowlist.
"""
import json
from contextlib import contextmanager, nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = 'FAKE_PROVIDER_SECRET_7b02e194'
ENV = {key: os.environ[key] for key in ('PATH', 'HOME', 'SYSTEMROOT') if key in os.environ}
ENV.update(NEXT_TELEMETRY_DISABLED='1', GOOGLE_API_KEY=SENTINEL,
           LIVEKIT_API_SECRET=SENTINEL, DEEPGRAM_API_KEY=SENTINEL, ELEVEN_API_KEY=SENTINEL,
           GOOGLE_OAUTH_CLIENT_SECRET='FAKEGOOGLE_OAUTH_CLIENT_SECRET', AUTH_SESSION_SECRET='FAKE_AUTH_SESSION_SECRET')


def run(command, cwd):
    started = time.monotonic()
    subprocess.run(command, cwd=cwd, env=ENV, check=True, timeout=180)
    print(f'PASS {" ".join(command)} ({time.monotonic() - started:.2f}s)', flush=True)


def available_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


@contextmanager
def auth_stub():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == '/auth/proxy-smoke?probe=1' else 404)
            self.end_headers()
            self.wfile.write(b'synthetic-auth-proxy')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def get_started(command, cwd, url, checks=()):
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
                for check in checks:
                    check_url, host, expected, *content = check
                    request = urllib.request.Request(check_url, headers={'Host': host})
                    try:
                        with urllib.request.urlopen(request, timeout=10) as checked:
                            assert checked.status == expected
                            checked_body = checked.read()
                            for secret in (SENTINEL.encode(), b'FAKEGOOGLE_OAUTH_CLIENT_SECRET', b'FAKE_AUTH_SESSION_SECRET'):
                                assert secret not in checked_body
                            if content:
                                assert content[0].encode() in checked_body
                    except urllib.error.HTTPError as error:
                        assert error.code == expected
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
    with tempfile.TemporaryDirectory(prefix='openinterview-web-') as directory, (nullcontext() if '--dev' in sys.argv else auth_stub()) as stub_origin:
        web = Path(directory)
        for filename in ('package.json', 'package-lock.json', 'tsconfig.json', 'next-env.d.ts',
                         'app/layout.tsx', 'app/page.tsx', 'app/globals.css',
                         'postcss.config.mjs', 'next.config.mjs',
                         'public/images/logo.svg', 'public/images/robot.svg'):
            target = web / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / filename, target)
        # Keep traced packages inside the isolated root for standalone output too.
        shutil.copytree(ROOT / 'app/local-voice', web / 'app/local-voice')
        shutil.copytree(ROOT / 'app/roles', web / 'app/roles')
        for route in ('login', 'signup', 'auth-ui'):
            shutil.copytree(ROOT / 'app' / route, web / 'app' / route)
        shutil.copytree(ROOT / 'node_modules', web / 'node_modules', symlinks=True)
        if '--dev' in sys.argv:
            # No inherited provider variables or root dotenv. Edit source, then restart.
            dev_env = {key: ENV[key] for key in ('PATH', 'HOME', 'SYSTEMROOT', 'NEXT_TELEMETRY_DISABLED') if key in ENV}
            if os.environ.get('AUTH_BACKEND_URL'):
                dev_env['AUTH_BACKEND_URL'] = os.environ['AUTH_BACKEND_URL']
            print('Isolated web: http://127.0.0.1:3000/local-voice (restart after edits)', flush=True)
            # Fixed port: Next must fail rather than attach to an incremented port.
            # Keep the isolated source until the child has fully stopped.
            previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
            process = subprocess.Popen(['node', str(web / 'node_modules/next/dist/bin/next'),
                                        'dev', '--hostname', '127.0.0.1', '--port', '3000'],
                                       cwd=web, env=dev_env)
            try:
                if process.wait():
                    raise RuntimeError('Isolated frontend exited unsuccessfully')
            except KeyboardInterrupt:
                pass
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
                signal.signal(signal.SIGTERM, previous)
            return
        ENV['AUTH_BACKEND_URL'] = stub_origin
        run(['npm', 'run', 'build'], web)
        run(['npm', 'run', 'typecheck'], web)
        port = available_port()
        html = get_started(['node', str(web / 'node_modules/next/dist/bin/next'), 'start',
                            '--hostname', '127.0.0.1', '--port', str(port)], web, f'http://127.0.0.1:{port}/',
                           [(f'http://127.0.0.1:{port}/local-voice', f'127.0.0.1:{port}', 404),
                            (f'http://127.0.0.1:{port}/login', f'127.0.0.1:{port}', 200),
                            (f'http://127.0.0.1:{port}/signup', f'127.0.0.1:{port}', 200, 'Continue with Google'),
                            (f'http://127.0.0.1:{port}/auth/proxy-smoke?probe=1', f'127.0.0.1:{port}', 200, 'synthetic-auth-proxy')])
        for text in ('Start with a', 'conversation.', 'View roles', 'I have an invitation', 'Voice interview', '/images/robot.svg'):
            assert text in html, text
        for text in ('>Example<', 'AI is speaking', '>Voice interviews in Vietnamese<', 'waveform'):
            assert text not in html, text
        assert SENTINEL not in html
        files = list((web / '.next/static').rglob('*'))
        assert any(path.is_file() for path in files)
        assert 'aria-label="Main navigation"' in html and 'href="/login"' in html
        css = ''.join(''.join(path.read_text().split()) for path in files if path.suffix == '.css')
        assert 'min-h-12' in html and 'size-6 overflow-hidden' in html
        for utility in ('.min-h-12{min-height:calc(var(--spacing)*12)}',
                        '.size-6{width:calc(var(--spacing)*6);height:calc(var(--spacing)*6)}',
                        '.justify-items-center{justify-items:center}',
                        '.grid-cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}',
                        '@media(max-width:760px)', '@media(max-width:480px)',
                        '--spacing:.25rem', '--color-page:#0b0812'):
            assert utility in css, utility
        assert '.demo-nav{' not in css and '.auth-card{' not in css
        for path in files:
            if path.is_file():
                assert SENTINEL.encode() not in path.read_bytes(), str(path)
                for secret in (b'FAKEGOOGLE_OAUTH_CLIENT_SECRET', b'FAKE_AUTH_SESSION_SECRET'):
                    assert secret not in path.read_bytes(), str(path)
        print('PASS production Home HTTP 200/content and fake-secret scan of HTML + .next/static')
        port = available_port()
        voice_url = f'http://127.0.0.1:{port}/local-voice'
        voice_html = get_started(['node', str(web / 'node_modules/next/dist/bin/next'), 'dev',
                                 '--hostname', '127.0.0.1', '--port', str(port)], web, voice_url,
                                [(voice_url, 'remote.example:3000', 404)])
        assert 'Local voice test' in voice_html and 'Deepgram' in voice_html
        assert SENTINEL not in voice_html
        print('PASS local-voice development HTTP 200, hostile Host 404, production 404')
    port = available_port()
    result = get_started([sys.executable, '-m', 'uvicorn', 'backend.api:app', '--host', '127.0.0.1', '--port', str(port)], ROOT, f'http://127.0.0.1:{port}/health')
    assert json.loads(result) == {'status': 'ok', 'service': 'api'}
    print(f'PASS independent API HTTP /health; verification total {time.monotonic() - started:.2f}s')


if __name__ == '__main__':
    main()
