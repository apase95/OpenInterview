# Contributor conventions

## Keep changes small

Read the relevant code first. Reuse existing code and prefer the standard library
before adding a dependency. Follow nearby naming and formatting. Add abstractions
only when the current task needs them.

Use a branch such as `feat/short-name` or `fix/short-name`. Keep commits focused;
short messages such as `feat: add ...`, `fix: correct ...`, or `init: set up ...`
match the project style. Stage only intended files.

In a pull request, explain what changed, what you checked, and any limits.
Include screenshots for UI changes. Ask for maintainer review and confirm the
target branch rather than assuming a separate staging branch exists.

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
