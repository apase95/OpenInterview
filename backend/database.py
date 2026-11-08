# %%
"""Environment-only DB connection; never load dotenv or expose connection errors.

This readiness helper executes a simple query, not a migration or schema audit.
Exceptions propagate to the API probe, which returns a generic unavailable result.
"""
import os

import psycopg


# %%
# Own and close a short-lived connection. Host and password are mandatory;
# database, role and port retain development defaults when not configured.
def ping():
    if not os.environ.get('DATABASE_HOST') or not os.environ.get('DATABASE_PASSWORD'):
        raise ValueError('Database is not configured')
    with psycopg.connect(
        host=os.environ['DATABASE_HOST'], port=os.getenv('DATABASE_PORT', '5432'),
        dbname=os.getenv('DATABASE_NAME', 'openinterview'),
        user=os.getenv('DATABASE_USER', 'openinterview'),
        password=os.environ['DATABASE_PASSWORD'], connect_timeout=3,
        options='-c statement_timeout=3000',
    ) as connection:
        if connection.execute('SELECT 1').fetchone() != (1,):
            raise RuntimeError('Database check failed')
