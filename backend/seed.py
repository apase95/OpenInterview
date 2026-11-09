# %%
"""Explicit dev/test-only migrations and synthetic seed. Never loads dotenv.

The CLI requires a dedicated development/test database and explicit confirmation.
Name and environment guards reduce mistakes; they are not a privilege boundary.
Database and fixture failure details are withheld from command output.
"""
import argparse
import hashlib
import os
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from backend.contracts import Bundle

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'backend/migrations/001_contract_v1.sql'
FIXTURE = ROOT / 'fixtures/synthetic/v1.json'
TABLES = ('tenants', 'users', 'campaigns', 'rooms', 'sessions', 'turns',
          'corrections', 'questions', 'answers', 'jobs', 'reports')


# %%
# Guard the connection before opening it. These checks do not inspect DB role
# privileges; operators must supply an appropriately restricted dedicated role.
def connect(*, confirm_synthetic=False):
    names = ('DATABASE_HOST', 'DATABASE_PORT', 'DATABASE_NAME', 'DATABASE_USER', 'DATABASE_PASSWORD')
    if (not confirm_synthetic or os.environ.get('APP_ENV') not in ('development', 'test')
            or not os.environ.get('DATABASE_NAME', '').endswith(('_dev', '_test'))
            or any(not os.environ.get(name) for name in names)):
        raise ValueError('Explicit development/test environment, *_dev/*_test database, all DATABASE_* fields and --confirm-synthetic required')
    connection = psycopg.connect(host=os.environ['DATABASE_HOST'], port=os.environ['DATABASE_PORT'],
                                dbname=os.environ['DATABASE_NAME'], user=os.environ['DATABASE_USER'],
                                password=os.environ['DATABASE_PASSWORD'], connect_timeout=3,
                                options='-c statement_timeout=5000 -c lock_timeout=3000')
    # Fixed schema prevents user-controlled search_path. Dedicated database remains mandatory.
    connection.execute('SET search_path TO public')
    return connection


# Coordinate cooperating migration/seed transactions, not arbitrary DB writers.
def lock(connection):
    connection.execute('SELECT pg_advisory_xact_lock(704193001)')


# %%
# Apply version one once under a transaction lock; refuse changed migration text
# when that version already exists instead of silently replacing its checksum.
def migrate(connection, *, source=MIGRATION):
    content = source.read_text()
    digest = hashlib.sha256(content.encode()).hexdigest()
    with connection.transaction():
        lock(connection)
        connection.execute('CREATE TABLE IF NOT EXISTS contract_migrations (version integer PRIMARY KEY, sha256 text NOT NULL)')
        existing = connection.execute('SELECT sha256 FROM contract_migrations WHERE version=1').fetchone()
        if existing:
            if existing[0] != digest:
                raise ValueError('Migration checksum mismatch')
            return False
        connection.execute(content)
        connection.execute('INSERT INTO contract_migrations VALUES (1,%s)', (digest,))
    return True


# %%
# Validate the full synthetic bundle and migration before inserting missing rows.
# Existing identical rows are reused; conflicting IDs abort the transaction.
def seed(connection, bundle):
    # Revalidate even if called with a constructed/copied model. No unchecked seed API.
    bundle = Bundle.model_validate(bundle.model_dump(mode='json'))
    data = bundle.model_dump(mode='json')
    with connection.transaction():
        lock(connection)
        digest = hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
        if connection.execute('SELECT sha256 FROM contract_migrations WHERE version=1').fetchone() != (digest,):
            raise ValueError('Verified migration required before seed')
        for table in TABLES:
            # Never mix this fixture with domain data, even in a misnamed development DB.
            if connection.execute(sql.SQL("SELECT 1 FROM {} WHERE left(id,4) <> 'syn_' LIMIT 1").format(sql.Identifier(table))).fetchone():
                raise ValueError('Non-synthetic data present; use a dedicated database')
        changed = 0
        for table in TABLES:
            name = sql.Identifier(table)
            for row in data[table]:
                if table == 'tenants':
                    key_sql, keys = sql.SQL('id=%s'), (row['id'],)
                    insert = sql.SQL('INSERT INTO {} (id,data) VALUES (%s,%s)').format(name)
                else:
                    key_sql, keys = sql.SQL('tenant_id=%s AND id=%s'), (row['tenant_id'], row['id'])
                    insert = sql.SQL('INSERT INTO {} (tenant_id,id,data) VALUES (%s,%s,%s)').format(name)
                existing = connection.execute(sql.SQL('SELECT data FROM {} WHERE ').format(name) + key_sql, keys).fetchone()
                if existing:
                    if existing[0] != row:
                        raise ValueError('Synthetic ID conflict; transaction rolled back')
                else:
                    connection.execute(insert, (*keys, Jsonb(row)))
                    changed += 1
        return changed


# %%
# Validate seed input before connecting. No automatic migration or destructive
# reset is performed by the seed command; failures produce a fixed public message.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('migrate', 'seed'))
    parser.add_argument('--confirm-synthetic', action='store_true')
    args = parser.parse_args()
    try:
        # Validate before connecting and never display input/connection errors.
        bundle = Bundle.model_validate_json(FIXTURE.read_text()) if args.command == 'seed' else None
        with connect(confirm_synthetic=args.confirm_synthetic) as connection:
            result = migrate(connection) if args.command == 'migrate' else seed(connection, bundle)
        print(f'{args.command}: verified; changes={int(result)}')
    except Exception:
        parser.exit(1, 'Refused or failed: check explicit dev/test guards, fixture, migration checksum and database constraints. Details withheld.\n')


if __name__ == '__main__':
    main()
