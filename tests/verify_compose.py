"""Opt-in Docker integration check. Own project, synthetic env, cleanup even on failure.

No root dotenv, provider network, raw logs, or compose config output.
"""
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = 'FAKE_PROVIDER_SECRET_7b02e194'


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    started = time.monotonic()
    project = 'oi-check-' + uuid.uuid4().hex[:10]
    # Deliberately include SQL/shell/URI special characters in the app password.
    values = dict(POSTGRES_PASSWORD='synthetic-admin-only',
                  DATABASE_PASSWORD='synthetic-app-\'"@:/;$(safe)',
                  WEB_PORT=str(port()), API_PORT=str(port()),
                  LIVEKIT_URL='wss://synthetic.invalid', LIVEKIT_API_KEY=SENTINEL,
                  LIVEKIT_API_SECRET=SENTINEL, GOOGLE_API_KEY=SENTINEL,
                  DEEPGRAM_API_KEY=SENTINEL, ELEVEN_API_KEY=SENTINEL)
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'XDG_RUNTIME_DIR') if key in os.environ}
    # Explicit env-file prevents Compose's implicit root .env loading.
    with tempfile.TemporaryDirectory(prefix='oi-compose-', dir='/tmp/opencode') as directory:
        filename = Path(directory) / 'synthetic.env'
        filename.write_text('')
        os.chmod(filename, 0o600)
        # Shell environment values override interpolation and do not need dotenv escaping.
        # The file remains explicit and contains only synthetic data.
        env.update(values)
        command = ['docker', 'compose', '--env-file', str(filename), '-p', project, '-f', str(ROOT / 'docker-compose.yml')]

        def run(args, *, check=True, timeout=120, environment=env):
            result = subprocess.run(args, cwd=ROOT, env=environment, capture_output=True, timeout=timeout)
            if check and result.returncode:
                raise AssertionError(f'Command failed ({result.returncode}): {args[0]} {args[1]} (output withheld; synthetic credentials may be present)')
            return result

        def compose(*args, **kwargs):
            return run(command + list(args), **kwargs)

        def up():
            compose('up', '-d', '--wait', '--wait-timeout', '100')
            services = [json.loads(line) for line in compose('ps', '--format', 'json').stdout.decode().splitlines()]
            assert {item['Service'] for item in services} == {'web', 'api', 'worker', 'postgres'}
            assert all(item['Health'] == 'healthy' for item in services)

        def sql(statement):
            return compose('exec', '-T', 'postgres', 'sh', '-c',
                           'PGPASSWORD="$DATABASE_PASSWORD" exec psql -h 127.0.0.1 -U openinterview -d openinterview -v ON_ERROR_STOP=1 -tAc "$1"',
                           'sh', statement).stdout.decode().strip()

        try:
            for key in ('POSTGRES_PASSWORD', 'DATABASE_PASSWORD'):
                missing = {k: v for k, v in env.items() if k != key}
                rejected = compose('config', '--quiet', check=False, environment=missing)
                assert rejected.returncode != 0
                assert values['POSTGRES_PASSWORD'].encode() not in rejected.stderr
                assert values['DATABASE_PASSWORD'].encode() not in rejected.stderr
            print('PASS missing admin/app passwords rejected without values', flush=True)
            filename.write_text('\n'.join(f'{key}={value}' for key, value in values.items() if key != 'DATABASE_PASSWORD') + '\n')
            stage = time.monotonic()
            compose('build', timeout=600)
            print(f'PASS explicit COPY image builds ({time.monotonic() - stage:.2f}s)', flush=True)
            up()
            print('PASS all four services healthy', flush=True)
            for path, expected in (('/', 'Start with a'),):
                with urllib.request.urlopen(f'http://127.0.0.1:{values["WEB_PORT"]}{path}', timeout=5) as response:
                    body = response.read().decode()
                assert expected in body and SENTINEL not in body
                assert '>Example<' not in body and 'AI is speaking' not in body
            for path in ('health', 'ready'):
                with urllib.request.urlopen(f'http://127.0.0.1:{values["API_PORT"]}/{path}', timeout=5) as response:
                    assert response.status == 200
            assert sql("SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname = current_user") == 'f'
            sql("CREATE TABLE persistence_probe (marker text PRIMARY KEY); INSERT INTO persistence_probe VALUES ('synthetic-row')")
            compose('restart', 'postgres', 'api', 'worker')
            up()
            assert sql('SELECT marker FROM persistence_probe') == 'synthetic-row'
            print('PASS non-admin app authentication and row survives postgres/API/worker restart', flush=True)
            compose('down')  # Do not remove volume until after proving recreation persistence.
            up()
            assert sql('SELECT marker FROM persistence_probe') == 'synthetic-row'
            print('PASS row survives compose down (without -v) and up', flush=True)
            for service in ('web', 'api', 'worker'):
                container = compose('ps', '-q', service).stdout.decode().strip()
                info = json.loads(run(['docker', 'inspect', container]).stdout)[0]
                assert info['Config']['User'] not in ('', '0', 'root')
                if service in ('web', 'api'):
                    runtime_env = {value.split('=', 1)[0] for value in info['Config']['Env']}
                    assert not runtime_env.intersection({name for name in values if name.endswith('_KEY') or name == 'LIVEKIT_API_SECRET'})
                    bindings = info['HostConfig']['PortBindings']
                    assert bindings and all(binding['HostIp'] == '127.0.0.1' for entries in bindings.values() for binding in entries)
                image = json.loads(run(['docker', 'image', 'inspect', info['Image']]).stdout)[0]
                assert SENTINEL not in json.dumps(image['Config'])
                # Export the actual runtime filesystem, not a prediction from Dockerfile.
                exported = run(['docker', 'export', container], timeout=60).stdout
                with tarfile.open(fileobj=io.BytesIO(exported)) as archive:
                    for item in archive:
                        name = item.name.removeprefix('./')
                        if not name.startswith('app/'):
                            continue
                        relative = name[4:]
                        assert relative.split('/')[0] not in ('.git', 'tests', 'docs')
                        assert not any(part == '.env' or part.startswith('.env.') for part in Path(relative).parts)
                        assert not relative.endswith('home.png')
                        if service == 'web' and item.isfile() and relative.startswith('.next/static/'):
                            assert SENTINEL.encode() not in archive.extractfile(item).read()
            print('PASS exported runtime /app excludes dotenv/git/tests/docs/screenshots; nonroot images; no baked provider sentinel or public bundle leak', flush=True)
            postgres = compose('ps', '-q', 'postgres').stdout.decode().strip()
            info = json.loads(run(['docker', 'inspect', postgres]).stdout)[0]
            assert not info['HostConfig']['PortBindings']
            networks = info['NetworkSettings']['Networks']
            assert len(networks) == 1
            network = json.loads(run(['docker', 'network', 'inspect', next(iter(networks))]).stdout)[0]
            assert network['Internal']
            print('PASS loopback-only web/API, no DB host port, dedicated internal DB network, provider env absent from web/API', flush=True)
            compose('stop', 'worker')
            container = compose('ps', '-a', '-q', 'worker').stdout.decode().strip()
            state = json.loads(run(['docker', 'inspect', container]).stdout)[0]['State']
            assert state['ExitCode'] == 0 and not state['OOMKilled']
            print('PASS worker graceful container stop (exit 0)', flush=True)
        finally:
            compose('down', '--volumes', '--remove-orphans')
            assert not compose('ps', '-a', '-q').stdout.strip()
            volumes = run(['docker', 'volume', 'ls', '-q', '--filter', f'label=com.docker.compose.project={project}']).stdout
            assert not volumes.strip()
            networks = run(['docker', 'network', 'ls', '-q', '--filter', f'label=com.docker.compose.project={project}']).stdout
            assert not networks.strip()
            print('PASS own containers/network/test volume cleaned', flush=True)
    print(f'PASS compose verification total {time.monotonic() - started:.2f}s')


if __name__ == '__main__':
    main()
