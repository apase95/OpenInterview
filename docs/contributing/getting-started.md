# Getting started

The local stack runs the website, API, PostgreSQL, and an idle worker.
It does not run interviews yet. See the [project README](../../README.md).

## Prerequisites

Install Git, Docker Engine with Compose v2+, and Bash on Linux or macOS.
On Windows, use WSL2 with Docker access. Start Docker before continuing.
You do not need host Node.js or Python for the Docker stack.

## Clone and configure

New clones use the default branch, `dev`.

```sh
git clone https://github.com/apase95/OpenInterview.git
cd OpenInterview
# Copy only if you do not already have this private file:
test -e .env.docker || cp .env.docker.example .env.docker
```

Edit `.env.docker` privately. Set `POSTGRES_PASSWORD` and a separate
`DATABASE_PASSWORD`, plus the six provider URL/credential fields in the template.
The worker validates configuration but makes no provider requests or jobs.
Do not change model settings unless your task asks for it.
Never commit private env files or put provider keys in the browser environment.
The root `.env` is for provider smoke checks, not Docker Compose.

### Existing clones (optional)

With local work saved, update and switch to `dev`:

```sh
git fetch origin
git switch dev
# Only if no local dev branch exists: git switch --track origin/dev
# Optional: refresh origin's default-branch pointer
git remote set-head origin -a
```

## Start and stop

```sh
./scripts/dev.sh start
./scripts/dev.sh status
# When finished:
./scripts/dev.sh stop
```

`start` builds images and waits up to 120 seconds for health checks.
Open http://127.0.0.1:3000. API liveness is http://127.0.0.1:8000/health;
database readiness is http://127.0.0.1:8000/ready.
`WEB_PORT` and `API_PORT` can change the ports; check `status` for addresses.

Containers have no hot reload. Run `start` again after changing code.
The stack runs detached: Ctrl+C does not stop it. `stop` keeps the database volume.
Changing passwords in the env file does not rotate passwords in an existing volume.
Do not delete that volume as a normal troubleshooting step.

## Make a change

Branch from `dev`, use a name such as `feat/short-name` or `fix/short-name`,
and open the PR into `dev`. Keep the change small.
Read the [conventions](conventions.md) before opening a pull request.
For direct web/API setup, offline tests, logs, and optional integration checks,
see the [development guide](development.md). Tests need separate host dependencies;
the wrapper does not install them.
