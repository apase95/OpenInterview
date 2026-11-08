# Development guide

For the short Docker setup, see [getting started](getting-started.md).
For project context, see [the README](../../README.md). Run direct commands below
from the repository root.
`./scripts/dev.sh` works from any directory. `test` runs offline Python tests;
`verify` explicitly runs the synthetic Docker integration check described below.
Install the backend test requirements before running offline tests.

## Local skeleton

Implemented: static desktop Home, independent FastAPI liveness, and a long-running
idle worker scaffold by default. The opt-in `/local-voice` client below supports
local voice sessions; it is disabled outside development and loopback hosts.
`/roles` and `/login` are planned links and currently return 404. The preview is
a static illustration, not a live session. Home keeps the user-trimmed content:
no badge, Example chip, speaking/waveform or bottom disclaimer. Tailwind v4 is
compiled through PostCSS; the navbar is 56 px with a 30 px logo and compact Sign in.

Tested: Node 24.12.0, npm 11.6.2, Python 3.12 and 3.14.8 on Linux. Web versions are pinned
in package.json/lockfile. Docker pins PostgreSQL 16.11 locally; broader version
agreement and S0-03 approval remain open.

```sh
npm ci
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
does not mean DB/provider readiness. Backend requirements now pin the voice SDKs
too; LiveKit/plugin support on Python 3.14 is unverified. Use Python 3.12 for voice.

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
dotenv. Install web dependencies with `npm ci` first; lifecycle scripts prepare
native build assets.
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

## Opt-in local voice conversation test

This is a separate developer test, not the `/v1` interview contract, recruiter
controller, hiring evaluation, or login system. The default worker
and Compose command remain idle for synthetic scaffold checks. Use the host
Python 3.12 environment for this test; Docker bridge clients intentionally fail
the API's loopback peer check. Do not proxy or expose this service publicly.

Install the pinned SDKs and download the Silero VAD model once using the setup
below (download uses network, but does not call paid STT/LLM/TTS services).

Privately edit root `.env` using `.env.example`. Keep existing provider/model
values. Set `APP_ENV=development`, `LOCAL_VOICE_ENABLED=true`, a new random
`LOCAL_VOICE_SECRET` of at least 32 characters, and exact comma-separated
`LOCAL_VOICE_ORIGINS` (default `http://127.0.0.1:3000`). Origins must be HTTP(S)
loopback URLs with explicit ports, no paths, credentials, wildcards or `null`.
The local secret must differ from LiveKit credentials; never put it in a query,
browser bundle, localStorage, shell argument/history, or log. The local
test client asks the operator to enter it at runtime and keeps it in memory only.
Origin is checked but is **not authentication**. No cookies are used.

### One terminal (recommended)

One-time setup from the repository root (Python 3.12 recommended):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-test.txt
# If pip is missing: uv pip install --python .venv/bin/python -r backend/requirements-test.txt
npm ci
.venv/bin/python -m livekit.agents download-files
```

After the private `.env` setup above, stop the old API, worker and web terminals
with Ctrl+C. Do not keep an old worker registered alongside this launcher.

```sh
npm run test:voice
```

This POSIX foreground supervisor checks config locally, refuses occupied ports
8000/3000, then waits for API health, the explicit named-worker registration event,
and the isolated frontend route. It never installs dependencies or downloads models.
It prints the ready URL only after all three checks. Enter the local secret in the
page at runtime, not in a command. Ctrl+C/SIGTERM stops only owned process groups,
with bounded graceful shutdown then forced cleanup; a child failure stops all three.
Partial startup failures are reported without private child logs. Restart after edits.
Port checks have a small bind race; child-liveness checks reject a failed bind, but
this is not protection against another process deliberately racing startup.

Running this command contacts LiveKit (worker registration and API lease cleanup).
Browser Start may incur paid Deepgram, Gemini and ElevenLabs calls and sends data
to providers as described below. Registration/HTTP readiness is not audio or model
quality validation. End the browser session before stopping; remote cleanup after
forced shutdown depends on worker deadlines and API lease reconciliation on restart.
The frontend still uses the verifier's allowlisted temporary source and minimal
environment, never root dotenv or backend credentials. No logs are saved.

Offline launcher regression check:
`.venv/bin/python -m unittest discover -s tests -p test_voice_launcher.py`.

### Manual fallback

Run in separate terminals from the repository root:

```sh
# Single API process, no --reload, multiple workers, or reverse proxy.
.venv/bin/python -m uvicorn backend.api:app --env-file .env --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
# Loads .env privately; requests registration as named agent local-voice-test.
.venv/bin/python -m backend.worker --voice start
# Offline CLI help only, no config file or provider connection:
.venv/bin/python -m backend.worker --voice --no-env-file --help
```

Only one voice worker `start` terminal is needed. Keep it and the API terminal
open; the installation/download terminal can exit. Do not start a second worker
to diagnose the first. `starting; registration pending` is not readiness;
`registered; waiting for jobs` is printed only on the SDK registration event.
Startup/run exceptions produce a fixed, sanitized failure message and exit 1,
including failures the SDK CLI catches internally. Arbitrary SDK/provider logs
remain blocked; no error details, credentials or transcript text are printed.
Registration does not validate STT/LLM/TTS or browser audio.

Check API liveness at `http://127.0.0.1:8000/health`, not `/` (expected 404).
Opening the API URL cannot start audio. Keep the already registered worker running;
do not start a duplicate. Start the isolated browser app from the repository root:

```sh
npm ci
npm run dev:local
# Open http://127.0.0.1:3000/local-voice
# Offline lifecycle check (only this file):
node --test tests/voice-client.test.mjs
```

This command copies the web allowlist and installed dependencies to a temporary
directory, starts Next directly on fixed port 3000 with a minimal environment, and removes
the copy on exit. It does not read root dotenv or inherit provider credentials.
Restart it after source edits. Do not use plain `npm run dev` with the private
root `.env`: Next auto-loads it. If port 3000 is busy, stop the owned web process
first; a different port needs its exact page origin added to `LOCAL_VOICE_ORIGINS`.
The client always calls `http://127.0.0.1:8000`; do not proxy it.

Manual browser test (not run by the offline checks): enter the separate local
secret, read the provider notice, check consent, and press Start. Only then is
a token requested and microphone permission requested. Allow the microphone;
use Enable audio if autoplay blocks speech. Try microphone and speaker mute,
then End. Also try End while starting and deny microphone permission. End must
stop local media immediately; retry End if remote cleanup is not confirmed.
The client stops at `ends_at`, does not auto-reconnect, and best-effort sends an
authenticated keepalive End on pagehide/unmount. Unload delivery is not guaranteed;
server lease expiry remains the fallback. Secret/token are never stored or shown.

Protocol used by the local client:

- POST `/local/voice/sessions`, `Authorization: Bearer <local secret>`, exact
  allowed `Origin`, JSON `{"consent":true}` when recording is off. With server
  `LOCAL_VOICE_RECORDING=true`, require exactly `{"consent":true,"recording_consent":true}`.
  Body fields cannot turn recording on; mismatched consent is rejected before allocation. OPTIONS allows
  POST with Authorization/Content-Type for allowed loopback origins. Missing or
  false consent never dispatches an agent. Disabled/non-development returns 404.
- Response includes `url`, `room`, generated `identity`, participant `token`,
  `session_id`, Unix `expires_at` and `ends_at`, and server-approved `recording`. It is
  `Cache-Control: no-store`. Do not log the response. Only microphone publishing
  and subscription are granted; no camera, screen, data, metadata changes,
  admin, or agent-session management. No client room/identity/dispatch input.
- After showing the provider notice and obtaining informed consent, connect
  with LiveKit and request microphone permission. End by stopping local media
  immediately and POSTing `/local/voice/sessions/{session_id}/end` with the same
  auth/origin. Retry a 503: it means remote stop was not confirmed. End is
  idempotent; it stops pending dispatch and removes participants. An unexpired
  JWT may reconnect briefly; the reaper removes those participants again.

Limits: TTL defaults to 60 seconds (15–120), duration to 300 seconds (TTL–600),
and concurrent reservations to 1 (1–3), using `LOCAL_VOICE_TOKEN_TTL`,
`LOCAL_VOICE_DURATION`, `LOCAL_VOICE_MAX_SESSIONS`. Authenticated allocation
attempts are limited to 10/minute in memory. **One API process only**: its lock
and attempt counter are not shared across processes or hosts. LiveKit room
metadata holds leases so API restarts reconcile existing reservations before
issuing more. Empty/departed rooms remain for up to 3600 seconds to preserve
these leases. Keep the reserved prefix `local_voice_` exclusive to this test.
Ended/disconnected sessions retain capacity until their original deadline;
there is no token refresh. This prevents freeing capacity while a JWT is still
valid. The API sweeps every second and deletes expired rooms; JWT expiry alone
does not disconnect media. The worker independently stops at the deadline,
on disconnect, or on unrecoverable provider errors, with at most two operation
retries. Cloud outages can delay room deletion; issuance fails closed if lease
reconciliation fails. Restart the API to resume cleanup after a crash; do not
manually delete live lease rooms or run multiple independent API instances.

Before consent, tell testers: microphone audio goes through LiveKit to Deepgram;
transcribed text goes to Google Gemini; generated speech text goes to ElevenLabs
and audio returns through LiveKit. Use synthetic, non-sensitive conversation.
App recording and transcript persistence are disabled by default; separate local
recording consent is required when enabled (see below). Text output and SDK logs
remain disabled; temporary in-memory conversation context is required. Deepgram model
improvement is opted out and ElevenLabs logging disabled where the SDK supports
it. These flags do not promise deletion or zero retention by providers: review
their account settings/terms/regions first. No recording/egress job is created.
Prompt instructions are not a validated HR policy/controller integration.

Offline tests mock external SDK/network boundaries, not token grants or API policy:

```sh
.venv/bin/python -m unittest discover -s tests -p test_local_voice.py
```

No real WebRTC/browser, Vietnamese recognition/voice quality, provider/model
availability, latency, interruption quality or production readiness is claimed.

### Consented local pipeline recording

For synthetic debugging only, set `LOCAL_VOICE_RECORDING=true` in the private
backend `.env`, restart `npm run test:voice`, then check **both** consent boxes.
Leave recording unchecked with the default `LOCAL_VOICE_RECORDING=false`.
API and worker flags must match; the server-owned dispatch lease controls capture.
No transcript UI, recording upload, SDK cloud recording or egress job is enabled.
See [capture files, semantics and retention](../ai/verification.md#local-pipeline-evidence-and-replay).
End the session before stopping the launcher so local evidence can finalize.
For safe provider failure categories and configured policy versus unavailable
exact retry counts, see [error evidence](../ai/verification.md#safe-provider-error-evidence).
The existing `LOCAL_VOICE_METRICS=true` flag enables content-free diagnostics
without recording; no new environment setting or SDK logging is needed.

## Before opening a PR

Run the local checks relevant to your change and report commands, results, and
anything skipped in the PR. For docs-only changes, check links, anchors, code
fences, and `git diff --check`; application tests are not needed.
Local checks do not replace passing GitHub CI on the up-to-date PR branch.
Follow the [review and merge rules](conventions.md#branches-and-pull-requests)
for required checks and approvals; never report a manual check as a CI result.

## Docker local stack (synthetic data first)

Docker Engine and Compose v2+ are required. Always pass `--env-file`; do not use
the provider smoke `.env` for Compose or put provider values in the web environment.
Compose reads the file as data: never `source` or `eval` an env file.

The wrapper handles the explicit Compose file and env path:

| Command | Action |
| --- | --- |
| `./scripts/dev.sh build` | Build images |
| `./scripts/dev.sh start` | Rebuild and start detached; wait up to 120 seconds for health |
| `./scripts/dev.sh stop` | Remove containers; preserve database volume |
| `./scripts/dev.sh restart` | Rebuild and recreate containers; preserve volume |
| `./scripts/dev.sh status` | Show service state and published ports |
| `./scripts/dev.sh logs [web\|api\|worker\|postgres]` | Follow logs, starting with the last 100 lines |
| `./scripts/dev.sh test` | Run all offline Python test files |
| `./scripts/dev.sh verify` | Opt-in synthetic Docker integration check |

`help` needs no setup. `test` and `verify` prefer `.venv/bin/python`, then
`python3`; neither installs dependencies or loads private env files.
For a scoped code change, prefer the relevant unittest filename shown above or below.
There is no container hot reload: run `start` after edits. Ctrl+C in `logs` only
stops following logs, not the detached stack. Review and redact logs before sharing.

```sh
test -e .env.docker || cp .env.docker.example .env.docker
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
worker receives all six provider names; API also receives the three LiveKit
values for the gated local voice endpoints. Selected model defaults are unchanged.
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
and production restore procedures remain future work. The isolated dev/test
contract migration below does not migrate the Compose database automatically.

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
Runtime provider names must match each role exactly: none for web, only the
three LiveKit names for API, and the existing six names for worker. Unexpected
provider credentials fail the check, including names not in the synthetic input.
The base image's public Python signing `GPG_KEY` is not a provider credential.
Finally it removes only its own containers/network/test volume. Build output is
withheld on failure because errors might contain synthetic credentials.
The initial real run passed in 118.40 s; image builds took 64.43 s. The final run
with internal-network/port/env/cleanup assertions passed in 42.66 s (cached build 2.17 s).
This is local scaffold evidence, not production security approval or the Sprint 1 exit gate.

## Contract and synthetic database

Use the [v1 technical contract](../architecture/api-data-contract.md), generated
[OpenAPI](../contracts/openapi-v1.json) and `fixtures/synthetic/v1.json` from the
repository root. Domain `/v1` routes are not implemented; health/readiness and
the separately gated `/local/voice` routes run today. Offline code generation
and validation never import worker configuration, dotenv or provider SDKs:

```sh
.venv/bin/python -m backend.contracts
.venv/bin/python -m unittest discover -s tests -p test_contracts.py
.venv/bin/python tests/verify_seed.py
```

The first command regenerates the committed OpenAPI artifact from Pydantic.
The filename pattern limits the second command to the contract smoke file.
The third is an explicit integration test, not part of offline discovery: it
starts its own `postgres:16.11-alpine` container with generated name, ephemeral
loopback port and separate named volume, creates a non-admin app user/database,
and tests real SQL. It never uses the existing Compose stack or local database.
It tests migration checksum/rollback, migrate twice, seed twice, conflict rollback,
invalid references/evidence, locked CV absence, unique events/jobs/reports, selected
states and restart persistence; finally removes only its owned container/volume.
Docker startup/restart is slower than the isolated offline smoke test.

For manual use, provision an **empty dedicated** `openinterview_dev` or
`openinterview_test` database owned by a non-admin app role. The tool does not
create databases/users. Set `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`,
`DATABASE_USER`, `DATABASE_PASSWORD` privately in the process environment; no
defaults, dotenv auto-load, URI interpolation or provider values are used.
Never point these commands at user data. Compose's `openinterview` name is
intentionally rejected, even if APP_ENV says development.

```sh
# After supplying all five DATABASE_* fields for your dedicated database:
APP_ENV=development .venv/bin/python -m backend.seed migrate --confirm-synthetic
APP_ENV=development .venv/bin/python -m backend.seed seed --confirm-synthetic
# Identical rerun: changes=0; changed existing synthetic ID: fail and roll back.
```

Guards require development/test, a `_dev`/`_test` database name and explicit
confirmation. Seed refuses non-synthetic IDs in its domain tables, validates the
complete fixture before writing and detects differing existing rows. Neither
command drops, truncates, resets or reads `.env` files. Migration is one SQL
transaction, version/checksum checked under advisory lock; a changed applied
migration is rejected, not replayed. No destructive rollback command is provided.
The seeded notice/approvals are fictional, no runtime retention policy is invented,
and the fixed expired room windows cannot authorize a real session.
Production backups, migrations/upgrades, full app state/auth enforcement,
retention/tombstones, CV storage/scanning and worker processing are still open.

## Provider smoke setup (Python 3.10+)

For the shared synthetic text controller and bounded opt-in STT/TTS/LLM evidence
runner, see [AI verification](../ai/verification.md) and its actual results/blockers.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -e .env || cp .env.example .env
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
