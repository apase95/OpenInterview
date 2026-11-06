# Getting started

The local stack runs the website, API, PostgreSQL, and an idle worker.
It does not run interviews yet. See the [project README](../../README.md).

## Prerequisites

Install Git, Docker Engine with Compose v2+, and Bash on Linux or macOS.
On Windows, use WSL2 with Docker access. Start Docker before continuing.
You do not need host Node.js or Python for the Docker stack.

## Clone and configure

New clones use the default branch, `dev`. The clone below is for contributors
with repository write access. Without it, use the fork instructions below.

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

Save local work first (commit it on its own branch or stash it), then check
`git status` for a clean working tree. Switch to `dev` before pulling:

```sh
git fetch origin
git checkout dev
git pull origin dev
```

After fetching, `git checkout dev` normally creates a tracking branch if only
`origin/dev` exists. If needed, use `git checkout -b dev origin/dev` only when
there is no local `dev` branch.

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

### With repository write access

Start with saved work and a clean working tree. For each new task:

```sh
git status
git checkout dev
git pull origin dev
git checkout -b feat/short-name
# Make your change and run the relevant checks.
git diff
# Example: stage only the file you intended to change.
git add docs/contributing/getting-started.md
git diff --cached
git commit -m "feat: describe your change"
git push -u origin feat/short-name
```

Replace the branch name, file path, and commit message for your task. Never stage
secrets or private env files. Open a PR from your feature branch into `dev` and
follow the [review and merge rules](conventions.md#branches-and-pull-requests).

`git pull origin dev` updates the branch you are currently on; it does not switch
branches. On a feature branch it integrates `dev` into that feature branch.
Pull may merge or rebase according to your Git settings; it is not a reset or
always a fast-forward. If local `dev` has diverged, stop, inspect, and coordinate
with a maintainer rather than forcing or discarding work.
Optional safety: `git pull --ff-only origin dev` refuses divergent history.

After a squash merge, start a fresh branch from updated `dev` using the first
four commands above. Do not reuse the old feature branch or pull `dev` into it
as your next-task sync step.

### Without repository write access

[Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo)
and clone your fork instead of the official repository. `origin` must point to
your fork; add the official repository as `upstream` once:

```sh
git remote add upstream https://github.com/apase95/OpenInterview.git
```

With work saved and the working tree clean, start each task like this:

```sh
git fetch upstream
git checkout dev
git pull upstream dev
git checkout -b feat/short-name
```

If local `dev` is missing, use `git checkout -b dev upstream/dev` instead of
`git checkout dev`. The same pull/divergence cautions above apply. Make and check
your change, stage intended files, and commit as above. Push with
`git push -u origin feat/short-name`, then open a PR into the official
repository's `dev`, not your fork's `dev`. First-time fork workflows may need
maintainer approval before CI can run.

For direct web/API setup, offline tests, logs, and optional integration checks,
see the [development guide](development.md). Tests need separate host dependencies;
the wrapper does not install them.
