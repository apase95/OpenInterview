# Web routing and account-bound preparation

Implementation branch: `fix/url-routing`, based on `refactor/tailwind-v4-ui`.

| URL | Behavior |
| --- | --- |
| `/` | Spec Home; both calls to action reach assigned rooms |
| `/login?return_to=/rooms/{id}` | One Google flow; canonical destination preserved |
| `/roles` | Six professions, with only rooms assigned to the signed-in account |
| `/rooms/{id}` | Server-authorized details, preparation notice, local device opt-in, waiting and joining |
| `/sessions/{id}/interview` | Restorable session URL; stage plus exactly three controls |
| `/hr` | Campaigns / Rooms / Reports tabs; server-confirmed campaign scopes |
| `/admin` | Users, grant audit metadata and database/job health; separate Admin grant |

`/signup` is only a permanent redirect to Login, not another page. `/auth/*`
remains a compatibility rewrite for registered OAuth callbacks. `/local-voice`
remains the separate development-only diagnostic.

## Trust and persistence

Next.js 16 uses `proxy.ts` instead of the deprecated `middleware.ts` name.
The proxy resolves the cookie with backend `/auth/me`, rather than trusting
cookie existence. Private resource pages also resolve their resource on the
server. Each `/workspace/*` API independently resolves the database session;
private reads check assignment and revocation. Mutations require the exact
public Origin and session-bound CSRF digest. HR queries filter exact campaign
scopes. Admin never implies HR. Unconfirmed/revoked grants provide no access.

All browser product requests use `/api/*` with same-origin cookies. The proxy
target is server-owned `API_BACKEND_URL`, falling back to `AUTH_BACKEND_URL` or
loopback port 8000. Set the same target at build and runtime because Next rewrite
destinations are compiled into the build. Docker defaults to `http://api:8000`.
OAuth credentials remain only in the API process; no public API-base variable.

The old anonymous `/demo/*` routes and self-created/share-code rooms are removed.
`web_room_previews` binds an assignment to `auth_accounts.id`, not an email or
client-supplied identity. `web_session_previews` survives frontend reload and API
restart. A room row lock plus unique room binding makes concurrent joins reuse
one session, including after it ends. The server checks the opening/closing
window on creation and active session reads. Owner-authorized End remains
idempotent after revocation or expiry. End stops the local preview immediately;
failed server confirmation is marked and retried with a sessionStorage marker
containing only the opaque session ID. No auth cookie/token is stored there.
Room identity/campaign/schedule bindings are immutable at the database level;
correct a wrong assignment by revoking it and creating a new room ID.

## Explicit migration and provisioning

Run the existing operator commands with the intended private environment file:

```sh
python -m backend.auth migrate --env-file .env
python -m backend.auth check --env-file .env
```

Migration `003_web_access.sql` is recorded as auth migration version 2. It
extends the stored OAuth return-path constraint and creates grants, assigned
preparation rooms and sessions. The existing `002_auth.sql` bytes/checksum are
unchanged. Both versions are checked; migrate uses one transaction/advisory lock.
There is no automatic startup migration, seed privilege, email merging or
self-elevation. Run migrations against a disposable database before deployment.

An authorized operator must provision preparation assignments and grants against
verified account IDs using the existing database administration process.
`web_access_grants` records the actor, scope, creation, confirmation and revocation.
Only confirmed, non-revoked grants are returned by `/auth/me`.
The UI intentionally provides no unimplemented mutation that claims success.
New accounts without an assignment see “No room assigned”.

## API slice

Browser prefix: `/api`; backend paths:

- `GET /workspace/roles`, `GET /workspace/rooms`, `GET /workspace/rooms/{id}`.
- `POST /workspace/rooms/{id}/sessions` with exactly `{"acknowledged":true}`.
- `GET /workspace/sessions/{id}`, `POST /workspace/sessions/{id}/end`.
- `GET /workspace/hr`, `GET /workspace/admin`.

These routes are a preparation slice, not an implementation of the specified
`/v1/*` domain contract. There is no live AI, recording, transcript, report job,
approved interview consent, email binding/invitation delivery, CV upload, campaign
authoring or grant mutation UI. An approved policy/version, retention by type,
tenant-aware domain bindings, media lifecycle and domain services remain required
before enabling real interviews. The Reports tab accurately shows no reports;
job health is unknown rather than fabricated.

## Checks and limits

Run `npm run typecheck`, `npm run build`,
`node --test tests/auth-ui.test.mjs tests/candidate-ui.test.mjs`, and
`python -m unittest tests.test_google_auth tests.test_candidate_demo`.
Offline API checks use stand-in identity/repository implementations. The explicit
`python tests/verify_auth.py` proof uses an owned Docker PostgreSQL instance to
exercise real migration/SQL/restart behavior; it requires Docker. Mocked checks
and the loopback browser harness do not prove real Google login or PostgreSQL
execution. No production configuration or real account data is needed by them.
