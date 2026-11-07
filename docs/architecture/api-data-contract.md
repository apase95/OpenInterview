# API and data contract v1 — technical baseline

This is the shared Frontend/Backend/AI baseline, **not implemented domain routes**
or permission to collect real data. Read with [requirements](../business/requirements.md),
[I/O](io-contracts.md), [conversation](conversation-workflow.md),
[lifecycle](data-artifacts.md) and [reports](../report/interview-report.md).
The seven desktop pages and current Home stay unchanged.

## Source and implementation state

- Authoritative typed shapes: `backend/contracts.py` (Pydantic, extra fields rejected).
- Generated [OpenAPI 3.1 JSON](../contracts/openapi-v1.json), including `Bundle`
  and `Event` component schemas; regenerate offline with `python -m backend.contracts`.
  The offline test compares generated and committed documents. Do not edit JSON by hand.
- Reusable [synthetic v1 fixture](../../fixtures/synthetic/v1.json): self-contained
  resources, Vietnamese original turns, English draft report. Fixed January 2026
  windows, `notice_demo_*`, example.com identities, no tokens/Google subjects/CV.
  Fixture approval and consent are **fictional test records**, not human sign-off.
  No fixture is a joinable invitation or an authentication bypass.
- `Bundle` is the synthetic loader format, not a bulk public API. Ordinary typed
  resources do not require synthetic IDs; Bundle enforces fixture-only restrictions.

| Method and path | Access / intent | State |
| --- | --- | --- |
| GET `/health` | Public liveness, no DB/provider probe | Implemented |
| GET `/ready` | Public bounded DB readiness, no provider probe | Implemented |
| GET `/v1/me` | Signed-in account and simple campaign scopes | Spec only |
| GET `/v1/rooms`, `/v1/rooms/{room_id}` | Own assigned rooms; recruiter assigned campaigns | Spec only |
| POST `/v1/campaigns` | Recruiter with tenant create grant; bounded JD/career | Spec only |
| POST `/v1/campaigns/{campaign_id}/proposal` | Assigned recruiter; generate proposed questions/rubric/FAQ | Spec only |
| POST `/v1/campaigns/{campaign_id}/approval` | Assigned recruiter; approve exact proposal version and lock | Spec only |
| POST `/v1/rooms` | Assigned recruiter; draft identity/snapshot/window/optional CV metadata | Spec only |
| POST `/v1/rooms/{room_id}/publication` | Assigned recruiter; validate gates and lock binding | Spec only |
| POST `/v1/rooms/{room_id}/revocation` | Assigned recruiter; revoke, never replace binding | Spec only |
| POST `/v1/rooms/{room_id}/consent` | Own published room; record notice/choice and allocate one session | Spec only |
| POST `/v1/sessions/{session_id}/join-token` | Own consented session; recheck all join gates | Spec only |
| GET `/v1/sessions/{session_id}` | Own session or assigned recruiter | Spec only |
| POST `/v1/sessions/{session_id}/end` | Own session; immediate idempotent stop | Spec only |
| POST `/v1/sessions/{session_id}/corrections` | Assigned recruiter; link existing candidate correction turns | Spec only |
| GET `/v1/reports`, `/v1/reports/{report_id}` | Assigned recruiter only; detail includes source turns/snapshot | Spec only |
| POST `/v1/reports/{report_id}/review` | Assigned recruiter; current input, explicit human review | Spec only |

List responses are JSON arrays, limited to 100 assigned resources in v1; no
directory/search/analytics endpoint. Empty is `[]`, not a fetch error. Static
career cards use BA, DevOps, Fullstack, Frontend, Backend, AI Engineer; careers
are not authorization roles. A future pagination change requires a new contract.
All domain success responses are 200; proposal generation may fail 503 without
publishing a fake proposal. No auth, upload, mock server, CRUD or report worker
is added by this baseline.

## Identity and trust boundary

Planned Google-only login: GET `/auth/google/start`, GET `/auth/google/callback`,
POST `/auth/logout` (also unimplemented; not part of the domain matrix).
Backend checks OAuth state/nonce, issuer/audience/signature/expiry and
`email_verified`; bind Google subject to a pre-authorized invitation's normalized
email only on first binding. Later logins use the verified bound subject, not
arbitrary email/client `user_id`. No automatic HR/operator assignment; separate
authorized grant and audit required. Allowlist relative return paths, no open redirect.

Use opaque server session cookie `__Host-oi_session`, HttpOnly, Secure in production,
SameSite=Lax, Path=/, no Domain. Local HTTP needs a separate dev cookie name;
never weaken production. Mutations require fresh session, same-origin check and
`X-CSRF-Token` matching server session; obtain token from `/v1/me`. Cookie/CSRF
values are never seeded, logged or stored in localStorage. Check tenant plus
campaign/room/session assignment on **every** request and token refresh. Operator
has no default transcript/report/CV access. Unauthorized private IDs return 404
without confirming existence; 403 is for a known account missing an action grant.
Worker access is separate server identity, scoped to the job, not this browser cookie.

Server derives tenant, candidate binding, approval actor/time, consent timestamp,
reviewer/time, IDs and state. Client fields never grant permission. The approval
body is only `version`; it approves the stored proposal, not a caller-supplied
approval actor. Consent does not approve a production notice, upload CV or start
media. Token issuance additionally requires approved campaign, matching verified
identity, live published window, no revocation/tombstone and active session.
Browser token grants only its room/identity and minimum media permissions,
300-second configurable TTL; no room-list/admin grants. No fake JWT is provided.

## Requests, responses and errors

JSON uses snake_case; `schema_version: "1.0"` on resources is non-secret wire
version. Bundle/fixture version is independent of integer campaign/input/report
versions. IDs are opaque 3–80 ASCII letters/digits/underscore/hyphen, start with
a letter; never emails/names in IDs. UTC ISO8601 (`Z` or `+00:00`) timestamps
are audit time. Audio offsets are nonnegative milliseconds from session media
timeline, **not epoch time**; reconnect preserves timeline and records gaps.

All mutations send `Idempotency-Key` (opaque, max 128 characters). Server scopes
it by actor/tenant/method/path and stores request digest/result: same payload
returns original result, changed payload returns 409. Mutating existing resources
also send `If-Match` with opaque ETag from their GET/mutation response; stale ETag
returns 409 `version_conflict`. ETags are row revisions, not schema/input version.
End retries must still stop local media immediately, even with stale state;
server returns existing terminal result after authorization. No duplicate session
on consent/token retries. GET responses provide `X-Contract-Version: 1.0` and
ETag where applicable; successful collection responses have no row ETag.
Join-token success returns the session row ETag, not a revision of the temporary token.
These headers apply to specified domain routes; existing health/readiness are unchanged.

Example planned consent request (demo notice is test-only):

```http
POST /v1/rooms/syn_room_done/consent
Content-Type: application/json
X-CSRF-Token: <session-bound value, not a fixture>
Idempotency-Key: <new opaque request key>
If-Match: "<room revision>"

{"notice_version":"notice_demo_v1_testing_only","choice":true}
```

The exact `Session` response shape is `sessions[0]` in the fixture (ended example;
a real accepted consent initially yields phase `consent`, active session,
`started_at: null` and no terminal timestamps). `started_at` means interview/media
start, not session allocation; it is recorded only after consent and all join/media
gates pass. Before that, no turns/media are allowed and the phase stays `consent`.
Refusal yields ended/refused in phase `consent`, `started_at: null`, no token,
no turns/report job for a never-started interview. After consent/local device
checks, join-token returns this shape, with real values issued only by backend:

```json
{"schema_version":"1.0","session_id":"ss_opaque","room_id":"rm_opaque","identity":"us_opaque","token":"<short-lived server-issued value>","expires_at":"2026-01-02T09:05:00Z"}
```

Consent choice time must be no later than start or end, and start must be no later
than end. A session without a start cannot have a completed outcome. Ending before
joining is permitted (for example candidate_end), but does not create interview evidence.

Other exact request examples (headers above still apply):

| Operation | JSON body (empty means no request body) |
| --- | --- |
| Create campaign | `{"career":"Backend","jd":"Synthetic API support role"}` |
| Generate proposal | empty |
| Approve proposal | `{"version":1}` |
| Create draft room | `{"candidate_email":"candidate@example.com","candidate_name":"Synthetic candidate","campaign_id":"syn_campaign","campaign_version":1,"opens_at":"2026-01-03T09:00:00Z","closes_at":"2026-01-03T10:00:00Z","timezone":"UTC","contact":"recruiter@example.com","cv_attachment":null}` |
| Publish/revoke/token | empty |
| End | `{"reason":"candidate_end"}` |
| Correction | `{"target_turn_id":"syn_answer","replacement_turn_id":"syn_corrected","input_version":2,"reason":"Candidate corrected the original answer"}` |
| Review | `{"note":"Checked against the original finalized turns."}` |

Campaign/room/correction/report response examples are their exact arrays' items
in the fixture, plus default `schema_version: "1.0"` supplied by the models.
`ReportDetail` combines report/session/room/campaign with its turns, corrections,
questions and answers; no unrelated resources. Draft campaign creation returns
empty question/rubric/FAQ arrays and null approval. Proposed/approved snapshots
must have questions and rubric; approval locks all bounded sources.

Error envelope (English message, never stack trace/PII/secret):

```json
{"schema_version":"1.0","code":"version_conflict","message":"Refresh this resource and try again.","request_id":"req_opaque"}
```

| HTTP | Stable code | Handling |
| --- | --- | --- |
| 401 | unauthenticated | Sign in; no media |
| 403 / 404 | forbidden / not_found | Deny without existence leak |
| 409 | version_conflict / invalid_state | Refresh; never silently overwrite |
| 422 | validation_error | Bounded input/schema/reference failure |
| 429 | rate_limited | Retry-After; bounded retry |
| 503 | unavailable | Truthful pending/failure, no fabricated transcript/report |

Existing health endpoints retain their current small bodies, not this domain error envelope.

## State, events, evidence and durability

- Campaign `draft → proposed → approved`; approval is immutable. A changed
  snapshot gets a new opaque ID and incremented version; career/rubric are shared,
  not tailored in difficulty per candidate. FAQ approval is part of snapshot approval.
- Room `draft → published → completed/revoked`. Publication locks identity,
  campaign version, schedule/contact and CV binding **including absence**.
  Wrong binding requires revoke + new room. No attachment is valid. CV metadata
  interface is specified, upload/object store/scanner are not implemented; no
  upload can run or publish with an unscanned file. PDF limit 5 MiB is a configurable
  technical proposal. CV must never become AI input, score or evidence.
- Consent record stores notice version, choice, server UTC. Session status
  `active ↔ interrupted → ended` is separate from phases `consent`, `basic_info`,
  `experience`, `light_technical`, `candidate_qa`, `wrap`. End is terminal and
  effective in every phase. End/local media cancellation does not promise deletion.
- `Event` schema is for internal worker/controller events, not a public route.
  Server allocates session sequence; dedupe `(tenant_id, session_id, event_id)`
  and sequence in DB. Fixture finalized turns carry that envelope inline. Event
  duplicates with changed payload fail; delayed/cancelled generation output is
  not replayed. Unknown delivery/gaps use metadata Event, not invented turn text.
- Turns are append-only STT finals or assistant confirmed/partial delivered text.
  Only fully `confirmed_delivered` establishes a whole question was asked.
  Planned/queued/unknown text is never canonical evidence. Assistant partial is
  only the known text mapping, never a guessed duration prefix.
- Correction appends a link from original to later finalized candidate correction
  turn; preserves original, increments transcript `input_version`. API derives
  correction ID/time/tenant/session. This narrow slice handles candidate-confirmed
  corrections, not arbitrary reviewer-authored candidate speech. New input means
  new report job/report version; old report becomes superseded and must be reviewed anew.
- Facts and criteria use `not_collected/refused/insufficient_evidence/supported`.
  Missing/refused value is null, never a fabricated default or low ability. A
  supported value needs candidate evidence in this session/input snapshot.
  Rubric assessment also has `fulfilled/partial/missing`; absent/refused evidence
  must be missing. CV and assistant turns cannot support candidate facts.
- CandidateQuestion preserves original turn/text/topic. FAQAnswer status remains
  `answered/unknown/conflict/expired`. Answered needs an approved, effective source
  version and confirmed assistant answer turn. Unknown/conflict/expired need
  recruiter followup; no fabricated confirmed answer. Restricted/deferred questions
  instead store disposition/reason and `advance` or `end`, **no FAQAnswer**;
  `restricted` requires `private_information`, `deferred` requires
  `candidate_agreed_defer`; `answer` requires `answer_faq` and a `source_*` reason.
  refusal speech uses permitted generation metadata. This does not add controller
  actions or pretend a known restriction is missing knowledge. Controller retains
  `ask_core/ask_followup/clarify/answer_faq/advance/wrap/end`.
- End, finalized turns/state and unique report job `(tenant, session, input_version)`
  must commit together in future controller code. Worker uses DB row-lock lease,
  max 3 attempts, and unique report per input plus report version. No BackgroundTasks
  durability claim. Draft report reviewer/time are null, explicit authorized review
  is required. No hire/reject action. Seed contains a done job + existing draft report;
  **there is no running report worker**.

## Technical defaults versus pending approvals

| Decision | Baseline / status |
| --- | --- |
| Payload/context | 64 KiB total JSON, strings 4,000 chars, JD 16,000 chars, 20 core questions/criteria/FAQ sources each; enforce HTTP total before parsing when routes are built |
| Interview budget | 600 seconds within 480–720 configuration, 2 followups/topic, 3 STT clarifications/session; recruiter proposal, not sign-off |
| Retry/reconnect | 2 retries per provider operation, backoff 1s/2s; 30s reconnect budget then interrupted end; technical proposal to measure |
| Report jobs | 3 attempts, proposed lease 60s with heartbeat; retry 5s/30s, exhausted failed; worker not implemented |
| Media token | 300s configurable, fresh auth/gates each issue; not a policy promise |
| Guardrail semantics | Metadata mapping above; schema checks do not prove language/content safety |
| Retention/legal basis/notice | **Pending authorized owner approval** per artifact type, including backups/provider copies; no production durations invented |
| CV | Private storage/quarantine/scanner/authority/lawful notice must be provisioned/approved before upload; no file tooling here |
| Remaining gates | Recruiter content and budgets, privacy consent, auth/CRUD/controller, semantic cases, real provider/media, job crash recovery, deletion/restore and UAT remain open |

## What this migration actually enforces

`backend/migrations/001_contract_v1.sql` is a dev/test resource slice: tenant users
and app roles, campaign approval snapshot in bounded JSONB, rooms, sessions,
append-only finalized turns/corrections, questions/answers, durable job/report rows.
Composite FKs enforce tenant/session references; unique indexes enforce room/session,
event/sequence and job/report versions. Triggers reject approved snapshot edits and
published binding edits, including null CV replacement. Ordinary UPDATE and DELETE
of turns/corrections are blocked. Authorized retention/purge requires a deliberate
future policy implementation, including scoped authorization, audit and dependent
data handling; no deletion mechanism or indefinite-retention promise is claimed.
DB checks cover selected
status/lease/reviewer fields. `Bundle` validates full shape, relationships, evidence,
source validity, approval scopes and coherent fixture states **before seed**.
JSONB campaign scopes/facts/rubric/source refs are validated in that layer, not
relational access control. DB constraints are not auth, full semantic validation,
state transition orchestration, tombstone/retention, backup or production migration
approval. Direct SQL must not be treated as a safe application write API.

Migrate/seed are separate, atomic commands, with advisory transaction lock,
recorded SHA-256 migration checksum, exact row conflict detection and no silent
`ON CONFLICT DO NOTHING`. Same fixture reruns change zero rows. Failures roll back;
no destructive down migration/reset is provided. Use a separately provisioned
empty database ending `_dev` or `_test`, environment-only credentials and explicit
`--confirm-synthetic`. Seed refuses any non-`syn_` resource IDs already in its tables.
Nothing auto-migrates/loads on API or Compose startup. See the
[safe commands and PostgreSQL proof](../contributing/development.md#contract-and-synthetic-database).
