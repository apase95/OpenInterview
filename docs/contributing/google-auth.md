# Google sign-in: backend-owned OIDC

Sign-up and sign-in use the same Google authorization-code flow. The identity
key is `(https://accounts.google.com, sub)`, never email. All new accounts are
`candidate`. This does not grant tenant, room, HR or operator access. `/roles`
and `/demo/*` remain synthetic. `/v1/me` is not implemented by this feature.

## Local setup (run yourself, no provider call during tests)

Install: `uv pip install --python .venv/bin/python -r backend/requirements-test.txt`.
Set these privately in an explicitly selected env file or export them:

```
APP_ENV=development
APP_ORIGIN=http://127.0.0.1:3000
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/auth/google/callback
GOOGLE_OAUTH_CLIENT_ID=<Google Web client ID>
GOOGLE_OAUTH_CLIENT_SECRET=<Google Web client secret>
AUTH_SESSION_SECRET=<independent random secret, at least 32 characters>
AUTH_SESSION_TTL=28800
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_NAME=openinterview_dev
DATABASE_USER=<non-admin app user>
DATABASE_PASSWORD=<private app password>
```

Generate the session secret with a secure password generator (32 random bytes
or more). Length is checked; entropy cannot be measured. This is not the Gemini
`GOOGLE_API_KEY`. Never put these secrets in `NEXT_PUBLIC_*` variables.
Register exactly `http://127.0.0.1:8000/auth/google/callback` in Google Console,
use Web client / External Testing / test-user access, scopes `openid email profile`.
Use `127.0.0.1` consistently, not mixed with `localhost`.

Provision the database/app role separately. Auth never creates a DB/user, never
runs on startup, and does not run/modify the old synthetic seed migration:

```
.venv/bin/python -m backend.auth migrate --env-file .env
.venv/bin/python -m backend.auth check --env-file .env
.venv/bin/python -m uvicorn backend.api:app --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

The commands above are for the operator to run, not tests. No env file is read
at import. Explicit `--env-file` does not override existing environment values.
All five DB fields are required. The role must be non-superuser, without
CREATEDB/CREATEROLE, with CREATE permission on public for migration and normal
table access for runtime. Migration uses an advisory lock, transaction,
`auth_migrations` version/checksum, and is idempotent. Checksum drift refuses.
Failures are sanitized with setup guidance; run `check` to diagnose missing
schema/config before opening login. Health is liveness, not auth readiness.
In production migration additionally requires `--confirm-production`.

Production requires fixed HTTPS callback/frontend URLs with the same hostname
and scheme, no wildcard, no Host/X-Forwarded-derived redirects. Use same-origin
reverse proxy and keep query strings out of all proxy/server access logs.
Backend filters Uvicorn auth query strings; do not enable HTTP wire/debug logs.
The API Docker image includes auth and its migration. Compose does not forward
auth secrets automatically: pass the listed auth variables explicitly to API
only, plus existing DATABASE_* values; invoke migration/check in that container.

## Exact frontend interface

Next/reverse proxy forwards `/auth/:path*` to backend; no new CORS policy.
Browser navigates to `/auth/google/start?return_to=/roles&intent=signin` or
`intent=signup`. Intent is copy only. Only literal `/` and `/roles` return paths
are allowed; other values fall back to `/`. Unknown query values are not echoed.

* `GET /auth/google/start`: 303 Google redirect and 10-minute flow cookie, or
  303 fixed `APP_ORIGIN/login?error=<enum>` on provider/DB failure.
* `GET /auth/google/callback`: Google calls the configured backend URL. State,
  browser binding, nonce, PKCE and signed OIDC claims are mandatory. Flow is
  atomically consumed before exchange (also on cancellation). Success: 303 to
  fixed origin plus stored allowlisted path and a fresh session cookie. Old
  browser session row is invalidated in the same login transaction.
* `GET /auth/me`: 200 `{ "user": { "id": "UUID", "email": "...",
  "name": "optional or null", "role": "candidate" }, "csrf_token": "..." }`.
  No picture, OAuth tokens or domain privileges. 401 `{"detail":"unauthenticated"}`.
* `POST /auth/logout`: send credentials, exact `Origin: APP_ORIGIN`, and
  `X-CSRF-Token` from `/auth/me`. 204 after DB invalidation, then cookie deletion.
  Invalid/missing origin/token: 403 `{"detail":"csrf_invalid"}`. DB failure:
  503, cookie retained so the user can retry.

JSON 503 errors are `{"detail":"auth_unavailable"}` (disabled/invalid auth
config) or `{"detail":"service_unavailable"}` (unexpected/DB error).
Disabled config never redirects using an unvalidated origin.
If configuration is invalid, Continue may display safe JSON 503 instead of a login
page. Run the explicit configuration check before starting; no request Host is
used as a fallback redirect. The compact navbar reads `/auth/me` once on mount
and signs out with the runtime CSRF value; failed logout can be retried.
Callback/start redirect error enums: `access_denied`, `state_invalid`,
`identity_invalid`, `provider_unavailable`, `service_unavailable`.
UI must use fixed messages and never render raw provider query/error text.
All auth responses have `Cache-Control: no-store` and `Referrer-Policy: no-referrer`.
No password, role picker, invitation binding or email-only account merging.

Production cookies: `__Host-oi_session`, `__Host-oi_flow`, Secure, HttpOnly,
SameSite=Lax, Path=/, no Domain. HTTP loopback development uses `oi_session_dev`
and `oi_flow_dev`, otherwise the same protections except Secure. Session default
8 hours, configurable 300–86400 seconds, no sliding renewal. Flows last 10 minutes.
Session/state/browser identifiers are random and persisted only as purpose-bound
HMAC-SHA256 digests. Nonce/verifier stay server-side. CSRF is session-bound HMAC.
Secret rotation invalidates existing sessions and flows. No refresh/access token
is persisted; no offline access requested. Profiles are untrusted display data:
frontend must escape name/email. Email verification must be boolean true.

## Offline checks and limits

```
.venv/bin/python -m unittest tests.test_google_auth
.venv/bin/python tests/verify_auth.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Unit tests mock HTTP transport and DB boundary, but use Authlib's actual RSA
signature/claim validation. The opt-in verifier creates/cleans only a unique
owned Docker PostgreSQL container/volume; it never targets configured user data.
It proves migration/checksum, atomic flow consume under contention, hash storage,
session rotation, no email merge, expiry, restart durability and logout.

Provider metadata/JWKS cache is per process, default 5 minutes, max 1 hour,
honors max-age/no-store. HTTP timeout is 5 seconds per request, no retries or
redirect following. Unknown signing keys fail closed until cache expiry; user
can retry later. RS256 only. Expiry clock skew tolerance 30 seconds. API auth
does not import VAD/start voice workers. No live Google login is claimed by
offline checks. No rate limiting or scheduled expiry cleanup service: expired
rows are removed on new flow creation; use proxy rate limits before public use.
