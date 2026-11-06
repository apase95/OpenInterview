# Development guide

For the short Docker setup and contributor commands, see [the README](../README.md).
`./scripts/dev.sh` works from any directory. `test` runs offline Python tests;
`verify` explicitly runs the synthetic Docker integration check described below.
Install the backend test requirements before running offline tests.

## Local skeleton

Implemented: static desktop Home, independent FastAPI liveness, and a long-running
idle worker scaffold. No auth, rooms, media, provider connections or jobs yet.
`/roles` and `/login` are planned links and currently return 404. The preview is
a static illustration, not a live session. Home keeps the user-trimmed content:
no badge, Example chip, speaking/waveform or bottom disclaimer. Tailwind v4 is
compiled through PostCSS; the navbar is 56 px with a 30 px logo and compact Sign in.

Tested: Node 24.12.0, npm 11.6.2, Python 3.12 and 3.14.8 on Linux. Web versions are pinned
in package.json/lockfile. Docker pins PostgreSQL 16.11 locally; broader version
agreement and S0-03 approval remain open.

```sh
npm ci --ignore-scripts
npm run dev
# Production: npm run build && npm run start
npm run typecheck
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-test.txt
# If the existing venv has no pip: uv pip install --python .venv/bin/python -r backend/requirements-test.txt
.venv/bin/python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
# GET http://127.0.0.1:8000/health -> {"status":"ok","service":"api"}
.venv/bin/python -m backend.worker --check-config
.venv/bin/python -m backend.worker
```

Worker explicitly loads root `.env` at startup; environment overrides file values.
All six provider URL/credential names in `.env.example` are required; placeholders
fail with names only. Model/STT/TTS defaults are unchanged. `--check-config`
validates only, without provider connections. `--no-env-file` uses environment
only. SIGINT/SIGTERM stops the idle scaffold. API needs no credentials; liveness
does not mean DB/provider readiness. Minimal Python requirements are separate
from existing provider SDKs; LiveKit/plugin support on Python 3.14 is unverified.

Offline checks (no real keys or provider calls):

```sh
.venv/bin/python -m unittest discover -s tests -p test_backend.py
.venv/bin/python -m unittest discover -s tests -p test_verify_local.py
python3 -m unittest discover -s tests -p test_smoke_test.py
.venv/bin/python tests/verify_local.py
git diff --check
```

The unittest filename pattern selects that file only. `verify_local.py` is an
explicit build/startup check, not a full e2e suite. It copies exact web files and
two SVG assets to a system temporary directory without dotenv, builds/typechecks, checks Home
HTTP/content, scans HTML and `.next/static` for an injected FAKE provider secret,
then checks independent API HTTP liveness. Backend tests use fake env and mock
dotenv. Install web dependencies with `npm ci --ignore-scripts` first.
The Linux verifier starts Next directly (not through npm), uses ephemeral
loopback ports for both servers, rejects responses if its child exits during
startup, and cleans up each owned process group with bounded waits. Port
selection releases the socket before launch; a small bind race remains, checked
by the post-response child-liveness delay. Regression checks cover successful
startup/cleanup and rejection of an unrelated response after child exit.

Next.js normally reads root dotenv on dev/build: keep provider secrets out of web
environments and use the isolated verifier when a private root `.env` exists.
Web has no provider imports, public keys or environment serialization; config is
Python-only. No auth, provider readiness, measured accessibility or asset-license
approval is claimed. Verify asset rights before release.

## Docker local stack (synthetic data first)

Docker Engine and Compose v2+ are required. Always pass `--env-file`; do not use
the provider smoke `.env` for Compose or put provider values in the web environment.

```sh
cp .env.docker.example .env.docker
# Fill privately: POSTGRES_PASSWORD (admin), separate DATABASE_PASSWORD (app),
# LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, GOOGLE_API_KEY,
# DEEPGRAM_API_KEY, ELEVEN_API_KEY. Placeholders are not working provider keys.
docker compose --env-file .env.docker build
docker compose --env-file .env.docker up -d --wait
docker compose --env-file .env.docker ps
curl --fail http://127.0.0.1:3000/
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
docker compose --env-file .env.docker down
# Rebuild after source/dependency changes:
docker compose --env-file .env.docker up -d --build --wait
```

`WEB_PORT`/`API_PORT` may change the loopback-only host ports. PostgreSQL has no
host port and uses a dedicated internal network. Web has no provider environment;
only worker receives the six provider names. Selected model defaults are unchanged.
API/worker use separate `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`,
`DATABASE_USER`, `DATABASE_PASSWORD` fields, not a password-interpolated URI.
Compose uses fixed database/user `openinterview` and admin `openinterview_admin`.
The app role is not superuser and cannot create databases or roles. Passwords
with special characters are passed safely to psycopg and psql variable quoting.
For dotenv special characters, follow Compose quoting rules; never paste secrets
into shell commands or share `docker compose config`/inspect output.

First boot creates the app role/database using `docker/postgres/init.sh`, mounted
read-only. This is provisioning, **not application migrations**. Init only runs
on an empty named `postgres-data` volume. Changing env passwords on an existing
volume does not rotate stored credentials; arrange an explicit private rotation.
Normal `down` preserves data. `down --volumes` destroys data: use only for an
owned disposable test stack, never as the normal stop command. Backups/restore
and schema migrations are still future work.

The web image uses Next standalone output; all app images run nonroot, use exact
source COPY paths and a deny-by-default build context. Root dotenv, git, tests,
docs and screenshots never enter the build context. API `/health` is liveness;
`/ready` performs bounded authenticated `SELECT 1`, returns sanitized 503 when
DB is missing/down, and needs no provider credentials. PostgreSQL health checks
authenticate over TCP as the app user. Worker pings configured DB once at startup,
then updates a PID/timestamp heartbeat in its idle loop. Heartbeat health means
the idle process is alive, **not** provider, DB-continuity or job readiness.
It makes no provider requests and processes no jobs; SIGTERM exits cleanly.

Use `docker compose --env-file .env.docker logs --tail 50 SERVICE` only locally
when needed; review/redact output before sharing, especially after future logging
changes. Never dump full configuration or private logs into reports.

Opt-in real integration verification (stdlib; no real env or provider calls):

```sh
.venv/bin/python -m unittest discover -s tests -p test_container_smoke.py
.venv/bin/python tests/verify_compose.py
```

The harness uses an explicit temporary synthetic env file/environment, unique
Compose project and free loopback ports. It rejects missing passwords, builds
images, waits for four healthy services, checks Home/API, authenticates a
non-admin role, and writes a row. It checks that row after restart and after
down/up without `-v`, exports runtime filesystems for unwanted app files and
public sentinel leakage, checks nonroot/image env, and tests worker exit 0.
Finally it removes only its own containers/network/test volume. Build output is
withheld on failure because errors might contain synthetic credentials.
The initial real run passed in 118.40 s; image builds took 64.43 s. The final run
with internal-network/port/env/cleanup assertions passed in 42.66 s (cached build 2.17 s).
This is local scaffold evidence, not production security approval or the Sprint 1 exit gate.

## Provider smoke setup (Python 3.10+)

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` privately. Never commit keys or share its contents.
`python smoke_test.py` calls external services and may cost money. Each provider
has a 30-second timeout. Exit status is 0 only when all four checks pass.

- LiveKit: admin room-list API only, not a browser/WebRTC connection.
- Gemini: nonempty generated text only, not Vietnamese quality or report validation.
- Deepgram: projects endpoint authentication only, not Nova-3 Vietnamese transcription.
- ElevenLabs: audio frames received only, not playback or Vietnamese quality.

These checks do not validate the full pipeline or the Sprint 1 exit gate.
Run the checks in your environment; do not treat provider access as an end-to-end test.

Offline checks (no keys, SDKs, or network needed):

```sh
python -m unittest discover -s tests -p test_smoke_test.py
```

This stdlib test mocks dotenv and all four providers. It checks import safety,
success/failure exit values, sanitized errors, and the scope disclaimer.
