# %%
"""Opt-in owned disposable PostgreSQL auth proof. No dotenv or provider calls.

Requires Docker and may download its database image. Uses synthetic credentials
and a non-admin app role to test migrations, flow consumption and session storage.
Finally removes only this run's named container and volume, if Docker responds.
This does not verify Google tokens, browser login or full production security.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from unittest.mock import patch

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import auth, workspace


# %%
def main():
    """Provision an isolated database, exercise auth persistence, then remove it."""
    started = time.monotonic()
    name = 'oi-auth-' + uuid.uuid4().hex[:12]
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'XDG_RUNTIME_DIR') if key in os.environ}

    def docker(*args, check=True):
        """Capture Docker output and withhold it from failures to avoid credential leaks."""
        result = subprocess.run(['docker', *args], env=env, capture_output=True, timeout=90)
        if check and result.returncode:
            raise AssertionError('Docker failed; output withheld')
        return result.stdout.decode().strip()

    def wait(admin):
        """Poll only the owned database with bounded connection attempts."""
        for _ in range(100):
            try:
                with psycopg.connect(**admin) as c:
                    c.execute('SELECT 1')
                return
            except psycopg.OperationalError:
                time.sleep(.1)
        raise AssertionError('Owned PostgreSQL not ready')

    try:
        docker('volume', 'create', name)
        docker('run', '-d', '--name', name, '--mount', f'type=volume,src={name},dst=/var/lib/postgresql/data',
               '-e', 'POSTGRES_PASSWORD=synthetic-admin', '-p', '127.0.0.1::5432', 'postgres:16.11-alpine')
        port = docker('port', name, '5432/tcp').rsplit(':', 1)[1]
        admin = dict(host='127.0.0.1', port=port, user='postgres', password='synthetic-admin', dbname='postgres', connect_timeout=1)
        wait(admin)
        # Admin access only provisions the test role/database; app checks use that role.
        with psycopg.connect(**admin, autocommit=True) as c:
            c.execute("CREATE ROLE synthetic_auth LOGIN PASSWORD 'synthetic-app' NOSUPERUSER NOCREATEDB NOCREATEROLE")
            c.execute('CREATE DATABASE auth_test OWNER synthetic_auth')
        values = dict(APP_ENV='test', APP_ORIGIN='https://example.test',
                      GOOGLE_OAUTH_REDIRECT_URI='https://example.test/auth/google/callback',
                      GOOGLE_OAUTH_CLIENT_ID='synthetic-client', GOOGLE_OAUTH_CLIENT_SECRET='synthetic-secret',
                      AUTH_SESSION_SECRET='synthetic-session-secret-at-least-32-characters',
                      DATABASE_HOST='127.0.0.1', DATABASE_PORT=port, DATABASE_NAME='auth_test',
                      DATABASE_USER='synthetic_auth', DATABASE_PASSWORD='synthetic-app')
        s = auth.Settings('synthetic-client', 'synthetic-secret', 'https://example.test/auth/google/callback',
                          'https://example.test', 'synthetic-session-secret-at-least-32-characters', True, 28800)
        store = auth.Store()
        with patch.dict(os.environ, values, clear=True):
            # Temporary SQL copies test rollback and checksum guards without editing sources.
            with tempfile.TemporaryDirectory(prefix='oi-auth-rollback-') as directory:
                source = Path(directory) / 'broken.sql'
                source.write_text(auth.MIGRATION.read_text() + '\nSELECT nonexistent_auth_function();')
                with patch.object(auth, 'MIGRATION', source), auth.connect() as c:
                    try:
                        auth.migrate(c)
                    except psycopg.Error:
                        pass
                    else:
                        raise AssertionError('Broken migration accepted')
                    assert c.execute("SELECT to_regclass('public.auth_accounts') AS accounts, to_regclass('public.auth_migrations') AS migrations").fetchone() == {'accounts': None, 'migrations': None}
            with auth.connect() as c:
                assert auth.migrate(c) is True
                assert auth.migrate(c) is False
                auth.check(c)
            # Checksum mismatch refuses without changing any existing auth data.
            with tempfile.TemporaryDirectory(prefix='oi-auth-proof-') as directory:
                source = Path(directory) / 'changed.sql'
                source.write_text(auth.MIGRATION.read_text() + '\n-- changed')
                with patch.object(auth, 'MIGRATION', source), auth.connect() as c:
                    try:
                        auth.migrate(c)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Migration checksum mismatch accepted')
            state, browser, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
            store.create_flow(s, state, browser, nonce, verifier, '/roles')
            assert store.consume(s, state, 'different-browser') is None
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: store.consume(s, state, browser), range(2)))
            assert sum(result is not None for result in results) == 1
            assert store.consume(s, state, browser) is None
            store.create_flow(s, state, browser, nonce, verifier, '/')
            with auth.connect() as c:
                c.execute("UPDATE auth_flows SET expires_at=now()-interval '1 second'")
            assert store.consume(s, state, browser) is None
            token, fresh, other = (secrets.token_urlsafe(32) for _ in range(3))
            claims = dict(sub='subject-one', email='same@example.test', name='Candidate')
            store.login(s, claims, token, '')
            first_id = store.session(s, token)['id']
            assert store.session(s, token)['role'] == 'candidate'
            with auth.connect() as c:
                rows = c.execute('SELECT token_hash FROM auth_sessions').fetchall()
                assert rows == [{'token_hash': s.digest('session', token)}]
            store.login(s, claims, fresh, token)
            assert store.session(s, token) is None
            assert store.session(s, fresh)['id'] == first_id
            store.login(s, {**claims, 'sub': 'subject-two'}, other, '')
            assert store.session(s, other)['id'] != first_id  # no email merging
            with auth.connect() as c:
                c.execute("UPDATE auth_sessions SET expires_at=now()-interval '1 second' WHERE token_hash=%s", (s.digest('session', other),))
            assert store.session(s, other) is None
            # Exercise the real new migration and SQL; no provider or real data.
            store.create_flow(s, state, browser, nonce, verifier, '/rooms/routing_room')
            assert store.consume(s, state, browser)['return_to'] == '/rooms/routing_room'
            candidate = store.session(s, fresh)
            with auth.connect() as c:
                second = c.execute("SELECT id FROM auth_accounts WHERE subject='subject-two'").fetchone()
                c.execute("""INSERT INTO web_room_previews
                    (id,candidate_id,campaign_id,campaign_name,role_id,opens_at,closes_at,timezone,contact)
                    VALUES ('routing_room',%s,'scope-one','Synthetic scope','frontend',
                            now()-interval '1 minute',now()+interval '30 minutes','UTC','hr@example.test')""", (first_id,))
            repo = workspace.Store()
            assert len(repo.rooms(candidate)) == 1
            assert repo.rooms({'id': str(second['id'])}) == []
            with ThreadPoolExecutor(max_workers=2) as pool:
                joined = list(pool.map(lambda _: repo.join(candidate, 'routing_room'), range(2)))
            assert joined[0]['id'] == joined[1]['id']
            preview_id = joined[0]['id']
            try:
                repo.session({'id': str(second['id'])}, preview_id)
            except workspace.HTTPException as error:
                assert error.status_code == 404
            else:
                raise AssertionError('Cross-account session access accepted')
            ended = repo.session(candidate, preview_id, True)
            assert ended == repo.session(candidate, preview_id, True)
            assert repo.join(candidate, 'routing_room')['ended_at'] == ended['ended_at']
            with auth.connect() as c:
                grant_id = uuid.uuid4()
                c.execute("""INSERT INTO web_access_grants(id,account_id,permission,campaign_id,granted_by)
                    VALUES (%s,%s,'hr','scope-one',%s)""", (grant_id, first_id, first_id))
            assert store.session(s, fresh)['grants'] == []
            with auth.connect() as c:
                c.execute('UPDATE web_access_grants SET confirmed_at=now() WHERE id=%s', (grant_id,))
            assert store.session(s, fresh)['grants'] == [{'permission': 'hr', 'campaign_id': 'scope-one'}]
            with auth.connect() as c:
                c.execute('UPDATE web_access_grants SET revoked_at=now() WHERE id=%s', (grant_id,))
            assert store.session(s, fresh)['grants'] == []
            docker('restart', name)
            port = docker('port', name, '5432/tcp').rsplit(':', 1)[1]
            os.environ['DATABASE_PORT'] = port
            admin['port'] = port
            wait(admin)
            assert store.session(s, fresh)['id'] == first_id
            assert repo.session(candidate, preview_id)['ended_at'] == ended['ended_at']
            store.logout(s, fresh)
            assert store.session(s, fresh) is None
            result = subprocess.run([sys.executable, '-m', 'backend.auth', 'check'], env=dict(os.environ),
                                    capture_output=True, timeout=5)
            assert result.returncode == 0, 'Auth check CLI failed; output withheld'
        print('PASS migration rollback/idempotency/checksum; browser binding; atomic concurrent one-use/expired flow; hashed sessions; rotation; candidate/no email merge; expiry; restart durability; logout; check CLI')
    finally:
        docker('rm', '-f', name, check=False)
        docker('volume', 'rm', name, check=False)
        assert not docker('ps', '-aq', '--filter', f'name=^/{name}$')
        assert not docker('volume', 'ls', '-q', '--filter', f'name=^{name}$')
        print('PASS only owned auth container/volume cleaned')
    print(f'PASS PostgreSQL auth proof ({time.monotonic()-started:.2f}s)')


# %%
if __name__ == '__main__':
    main()
