# Contributor conventions

## Keep changes small

Read the relevant code first. Reuse existing code and prefer the standard library
before adding a dependency. Follow nearby naming and formatting. Add abstractions
only when the current task needs them.

Use a branch such as `feat/short-name` or `fix/short-name`. Keep commits focused;
short messages such as `feat: add ...`, `fix: correct ...`, or `init: set up ...`
match the project style. Stage only intended files.

In a pull request, explain what changed, what you checked, and any limits.
Include screenshots for UI changes.

## Branches and pull requests

Create feature/fix branches from `dev` and open normal PRs into `dev`.
Both `dev` and `main` are protected: no direct pushes, including by the owner.
See [getting started](getting-started.md#make-a-change) for the Git command flow.
Get one approval from a different authorized reviewer with write access;
read-only contribution access does not automatically grant review or merge rights.
Resolve conversations and pass all three required checks: `Web checks`,
`Python checks`, `Docker checks`. The PR must be up to date with the latest base
branch, with checks passing for that updated state before merging.
New commits dismiss old approvals; request review again after changes.
Squash merge only, with a concise commit message.
GitHub detects merge conflicts separately; CI checks do not replace that check.

GitHub does not allow authors to approve their own PRs. Owner `apase95` uses a
pull-request-only Repository Admin bypass of the review ruleset, not the separate
checks/PR/integrity ruleset: a PR, passing checks, and an up-to-date branch are
still required. This is not permission to force a merge with failing checks.
The owner is currently the sole admin. Future admins would receive the same
review bypass, so do not grant that role by accident.

`main` is the separate stable branch; target it only for an intentional release PR.
Merging is not an automatic release or deployment. Do not automatically delete
`dev` or `main`. After a squash merge, start the next task on a fresh branch
from updated `dev`, not the old feature branch.
Coordinate base changes for existing feature branches rather than switching them blindly.
Repository settings are managed separately from this workflow.

## Project layout and responsibilities

- `app/`: Next.js App Router pages and styles, using TypeScript and Tailwind v4.
  Keep Server Components by default; add client code only for browser behavior.
- `public/images/`: existing website images. Reuse assets and check rights before release.
- `backend/`: Python FastAPI API, server-only configuration, and idle worker.
- `scripts/dev.sh`: local Docker commands and Python check entry points.
- `docs/`: product proposals, architecture, planning, and contributor guides.

Keep website text in English and interview speech in Vietnamese.
Follow the desktop MVP scope; mobile/responsive work is not a new requirement.
Auth, role routes, interview rooms, media, and report jobs are planned, not
working features. Do not present scaffolding or a design preview as a live product.

## Checks and dependencies

Use `npm ci` for web dependencies. The package scripts are `dev`, `build`,
`start`, and `typecheck`; do not document commands that do not exist.
Python checks use stdlib `unittest`; run the file relevant to your change.
Use `backend/requirements-test.txt` for backend test dependencies, not the root
provider SDK requirements. See the [development guide](development.md) for commands.

Docker builds use explicit source COPY paths and a deny-by-default context.
When adding source files or dependencies, update the relevant Docker allowlist
and COPY paths if needed. Keep private files out of images.
For docs-only edits, check links, images, copy, and `git diff --check`.
Do not add new test or lint tooling just to satisfy an invented workflow.

CI runs on pushes and PRs to `dev`/`main`, and manual dispatch, without path filters.
Web builds before typechecking generated Next.js types; Python runs offline tests;
Docker runs the synthetic four-service build/persistence/cleanup verifier.
There is no lint script or CD job. Add deployment only after a target is agreed.

## Security and data

Validate input at trust boundaries and return safe errors. Never hide a failure
that could lose data. Keep provider configuration on the server; do not expose
keys through browser code, public environment variables, logs, or screenshots.
Do not change provider/model settings without an explicit task.

Never commit secrets, personal data, CV uploads, recordings, or private transcripts.
Use synthetic data in tests and redact logs before sharing them.
Data collection needs consent or another lawful basis, clear notice, and access
controls. Planned CV handling also needs private storage, validation, quarantine,
and scanning before publication; a UI upload control alone is not enough.
Humans make hiring decisions. Do not turn AI output into automatic hiring decisions.

Start with [getting started](getting-started.md); use the
[development guide](development.md) for the detailed runbook.
