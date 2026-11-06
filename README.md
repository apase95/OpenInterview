# OpenInterview

OpenInterview is building voice interviews in Vietnamese, with an English website.
Today it has a static Home page, a FastAPI API, PostgreSQL, and an idle worker
scaffold—not a working interview agent. Auth, rooms, media and jobs are not built.

## Start locally

Install Git, Docker Engine with Compose v2+, and Bash (use WSL2 on Windows).

```sh
git clone https://github.com/apase95/OpenInterview.git
cd OpenInterview
cp .env.docker.example .env.docker
# Edit .env.docker privately before starting.
./scripts/dev.sh start
```

Set `POSTGRES_PASSWORD` and a separate `DATABASE_PASSWORD`. Fill the six provider
URL/credential fields listed in the template. Never commit or share private env
files. The worker validates configuration but makes no provider requests.
Do not use the provider smoke `.env` for Docker or put provider keys in web env.

Default URLs: web http://127.0.0.1:3000, API liveness
http://127.0.0.1:8000/health, and database readiness
http://127.0.0.1:8000/ready. `WEB_PORT` and `API_PORT` can change these ports;
use `status` to see the published addresses.

| Command (`./scripts/dev.sh …`) | Action |
| --- | --- |
| `help` (or no command) | Show commands; no setup needed |
| `build` | Build images |
| `start` | Rebuild and start detached; wait up to 120 seconds for health |
| `stop` | Remove containers; keep database volume |
| `restart` | Rebuild and recreate containers; keep database volume |
| `status` | Show service state and published ports |
| `logs [web\|api\|worker\|postgres]` | Follow logs, starting with the last 100 lines |
| `test` | Run offline Python tests |
| `verify` | Opt-in synthetic Docker integration check |

Containers have no hot reload: run `start` again after code changes.
Ctrl+C does not stop a detached stack; in `logs` it only stops following logs.
Use `stop` to stop the stack. Review and redact logs before sharing them.
Changing passwords in the env file does not rotate an existing database password.
Never remove the database volume unless you intend to lose its data.

## Test and contribute

Offline tests need Python 3.12+ and the backend test dependencies:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-test.txt
./scripts/dev.sh test
# Optional: Docker integration, synthetic data only; builds images and takes longer.
./scripts/dev.sh verify
```

`test` prefers `.venv/bin/python`, then `python3`; it does not load env files or
call providers. `verify` uses its own temporary synthetic env and Docker project,
and removes only its own test resources. It needs no private `.env.docker`.
Neither command installs dependencies for you.

Create a branch such as `feat/short-name`, make a small change, and run `test`
plus checks relevant to your change. Use a short commit message (`feat: …`,
`fix: …`, or `init: …`), push your branch, and open a pull request. Describe the
change, checks and limits; wait for maintainer review. Do not include secrets.

See the [development guide](docs/development.md) for direct web/API setup,
configuration, verification limits, database notes and provider smoke scope.
The real `python smoke_test.py` calls external providers and may cost money;
it is never run by this wrapper.

Planning: [docs index](docs/README.md), [sprint plan](docs/planning/sprint-plan.md),
and [implementation checklist](docs/planning/implementation-checklist.md).
