"""Opt-in PostgreSQL proof. Own disposable Docker container/volume; no dotenv/providers."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.contracts import Bundle
from backend.seed import TABLES, FIXTURE, MIGRATION, connect, migrate, seed


def main():
    start = time.monotonic()
    name = 'oi-seed-' + uuid.uuid4().hex[:12]
    volume = name + '-data'
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'XDG_RUNTIME_DIR') if k in os.environ}

    def docker(*args, check=True):
        result = subprocess.run(['docker', *args], env=env, capture_output=True, timeout=90)
        if check and result.returncode:
            raise AssertionError('Docker command failed; output withheld')
        return result.stdout.decode().strip()

    def wait():
        for _ in range(100):
            try:
                with psycopg.connect(**admin) as c:
                    c.execute('SELECT 1')
                return
            except psycopg.OperationalError:
                time.sleep(.1)
        raise AssertionError('isolated PostgreSQL did not become ready')

    def rejected(call):
        try:
            call()
        except (ValueError, psycopg.Error):
            return
        raise AssertionError('invalid operation accepted')

    def snapshot(c):
        return {t: c.execute(sql.SQL('SELECT data FROM {} ORDER BY id').format(sql.Identifier(t))).fetchall() for t in TABLES}

    try:
        docker('volume', 'create', volume)
        docker('run', '-d', '--name', name, '--mount', f'type=volume,src={volume},dst=/var/lib/postgresql/data',
               '-e', 'POSTGRES_PASSWORD=synthetic-admin-only', '-p', '127.0.0.1::5432', 'postgres:16.11-alpine')
        port = docker('port', name, '5432/tcp').rsplit(':', 1)[1]
        admin = dict(host='127.0.0.1', port=port, user='postgres', password='synthetic-admin-only', dbname='postgres', connect_timeout=1)
        wait()
        with psycopg.connect(**admin, autocommit=True) as c:
            c.execute("CREATE ROLE synthetic_app LOGIN PASSWORD 'synthetic-app-only' NOSUPERUSER NOCREATEDB NOCREATEROLE")
            c.execute('CREATE DATABASE openinterview_test OWNER synthetic_app')
        values = dict(APP_ENV='test', DATABASE_HOST='127.0.0.1', DATABASE_PORT=port,
                      DATABASE_NAME='openinterview_test', DATABASE_USER='synthetic_app', DATABASE_PASSWORD='synthetic-app-only')
        with patch.dict(os.environ, values, clear=True):
            rejected(lambda: connect())
            for key, value in (('APP_ENV', 'production'), ('DATABASE_NAME', 'openinterview')):
                with patch.dict(os.environ, {key: value}):
                    rejected(lambda: connect(confirm_synthetic=True))
            with connect(confirm_synthetic=True) as c:
                c.commit()
                assert c.execute('SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user').fetchone() == (False,)
                c.commit()
                with tempfile.TemporaryDirectory(prefix='oi-seed-sql-') as directory:
                    broken = Path(directory) / 'broken.sql'
                    broken.write_text(MIGRATION.read_text() + '\nSELECT nonexistent_contract_function();')
                    rejected(lambda: migrate(c, source=broken))
                    assert c.execute("SELECT to_regclass('public.tenants'),to_regclass('public.contract_migrations')").fetchone() == (None, None)
                    c.commit()
                    assert migrate(c) is True
                    assert migrate(c) is False
                    broken.write_text(MIGRATION.read_text() + '\n-- tampered')
                    rejected(lambda: migrate(c, source=broken))
                print('PASS guarded non-admin connection; migration failure rollback, apply twice, checksum mismatch', flush=True)
                bundle = Bundle.model_validate_json(FIXTURE.read_text())
                assert seed(c, bundle) > 0
                before = snapshot(c)
                assert seed(c, bundle) == 0 and snapshot(c) == before
                # A new row is inserted before a later conflicting row: entire seed rolls back.
                conflict = bundle.model_copy(deep=True)
                conflict.tenants.append(conflict.tenants[0].model_copy(update={'id': 'syn_extra'}))
                conflict.reports[0].summary = 'Conflicting synthetic summary'
                rejected(lambda: seed(c, conflict))
                assert snapshot(c) == before
                c.commit()
                for mutate in (
                    lambda d: d['reports'][0]['criteria'][0].update(evidence_turn_ids=['syn_absent']),
                    lambda d: d['turns'][0].update(tenant_id='syn_other'),
                    lambda d: d['questions'][0].update(session_id='syn_other'),
                ):
                    data = json.loads(FIXTURE.read_text())
                    mutate(data)
                    rejected(lambda: seed(c, Bundle.model_validate(data)))
                    assert snapshot(c) == before
                c.commit()
                print('PASS seed twice unchanged; conflicting seed rollback; invalid tenant/session/evidence rejected without writes', flush=True)

                invalid = bundle.model_copy(deep=True)
                invalid.reports[0].criteria[0].evidence_turn_ids = ['syn_absent']
                rejected(lambda: seed(c, invalid))

                def bad_sql(statement, params=()):
                    with c.transaction():
                        c.execute(statement, params)

                room = bundle.rooms[0].model_dump(mode='json')
                for field, value in (('cv_attachment', {'id': 'syn_cv'}), ('candidate_id', 'syn_other'), ('campaign_version', 2), ('status', 'draft')):
                    changed = {**room, field: value}
                    rejected(lambda: bad_sql('UPDATE rooms SET data=%s WHERE id=%s', (Jsonb(changed), room['id'])))
                rejected(lambda: bad_sql("UPDATE campaigns SET data=jsonb_set(data,'{jd}','\"changed\"')"))
                rejected(lambda: bad_sql("UPDATE turns SET data=jsonb_set(data,'{finalized_text}','\"changed\"')"))
                for table, row_id in (('turns', 'syn_refusal'), ('corrections', 'syn_correction')):
                    # Unreferenced turn avoids mistaking FK rejection for append-only protection.
                    try:
                        bad_sql(sql.SQL('DELETE FROM {} WHERE id=%s').format(sql.Identifier(table)), (row_id,))
                    except psycopg.errors.RaiseException as error:
                        assert 'append-only' in error.diag.message_primary
                    else:
                        raise AssertionError('ordinary history DELETE accepted')
                # Same-session FK rejects a target even if that target ID exists elsewhere.
                correction = bundle.corrections[0].model_dump(mode='json')
                rejected(lambda: bad_sql('INSERT INTO corrections (tenant_id,id,data) VALUES (%s,%s,%s)',
                                        ('syn_tenant', 'syn_bad_correction', Jsonb({**correction, 'id':'syn_bad_correction','session_id':'syn_other'}))))

                def cross_session():
                    with c.transaction():
                        # Both sessions and original turns exist: fail the scoped FK,
                        # not merely a missing global ID.
                        other_room = {**room, 'id': 'syn_other_room'}
                        c.execute('INSERT INTO rooms (tenant_id,id,data) VALUES (%s,%s,%s)', ('syn_tenant', other_room['id'], Jsonb(other_room)))
                        other_session = bundle.sessions[0].model_dump(mode='json')
                        other_session.update(id='syn_other_session', room_id=other_room['id'])
                        c.execute('INSERT INTO sessions (tenant_id,id,data) VALUES (%s,%s,%s)', ('syn_tenant', other_session['id'], Jsonb(other_session)))
                        cross = {**correction, 'id': 'syn_cross', 'session_id': other_session['id']}
                        c.execute('INSERT INTO corrections (tenant_id,id,data) VALUES (%s,%s,%s)', ('syn_tenant', cross['id'], Jsonb(cross)))
                rejected(cross_session)

                def non_synthetic():
                    with c.transaction():
                        c.execute('INSERT INTO tenants VALUES (%s,%s)', ('real_marker', Jsonb({'id': 'real_marker', 'name': 'Non-synthetic guard marker'})))
                        seed(c, bundle)
                rejected(non_synthetic)
                for table, original in (('jobs', bundle.jobs[0]), ('reports', bundle.reports[0]), ('turns', bundle.turns[0]), ('sessions', bundle.sessions[0])):
                    row = original.model_dump(mode='json')
                    row['id'] = 'syn_duplicate'
                    rejected(lambda: bad_sql(sql.SQL('INSERT INTO {} (tenant_id,id,data) VALUES (%s,%s,%s)').format(sql.Identifier(table)),
                                            ('syn_tenant', row['id'], Jsonb(row))))
                row = bundle.jobs[0].model_dump(mode='json')
                row.update(status='processing', lease_until=None)
                rejected(lambda: bad_sql('UPDATE jobs SET data=%s WHERE id=%s', (Jsonb(row), row['id'])))
                assert snapshot(c) == before
                c.commit()
                print('PASS DB published binding/CV absence and approved snapshot immutable; transcript UPDATE/DELETE blocked; scoped correction FK; session/event/job/report uniqueness; lease state', flush=True)
            for command in ('migrate', 'seed'):
                result = subprocess.run([sys.executable, '-m', 'backend.seed', command, '--confirm-synthetic'],
                                        cwd=ROOT, env=dict(os.environ), capture_output=True, text=True, timeout=5)
                assert result.returncode == 0 and 'changes=0' in result.stdout, 'CLI rerun failed (output withheld)'
            print('PASS documented migration and seed CLI entry points, unchanged reruns', flush=True)
            docker('restart', name)
            # Docker may allocate a new ephemeral host port on restart.
            port = docker('port', name, '5432/tcp').rsplit(':', 1)[1]
            admin['port'] = port
            os.environ['DATABASE_PORT'] = port
            wait()
            with connect(confirm_synthetic=True) as c:
                assert snapshot(c) == before
                assert seed(c, bundle) == 0
            print('PASS exact rows and durable job/report survive PostgreSQL restart', flush=True)
    finally:
        docker('rm', '-f', name, check=False)
        docker('volume', 'rm', volume, check=False)
        assert not docker('ps', '-aq', '--filter', f'name=^/{name}$')
        assert not docker('volume', 'ls', '-q', '--filter', f'name=^{volume}$')
        print('PASS only owned container and volume cleaned', flush=True)
    print(f'PASS PostgreSQL contract/seed proof ({time.monotonic() - start:.2f}s)')


if __name__ == '__main__':
    main()
