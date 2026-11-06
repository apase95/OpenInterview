#!/bin/sh
set -eu
# Fixed identifiers; psql quotes the password as a SQL literal, never shell SQL.
psql --username "$POSTGRES_USER" --dbname postgres --set=ON_ERROR_STOP=1 \
  --set=app_password="$DATABASE_PASSWORD" <<'SQL'
CREATE ROLE openinterview LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE openinterview OWNER openinterview;
REVOKE ALL ON DATABASE openinterview FROM PUBLIC;
SQL
