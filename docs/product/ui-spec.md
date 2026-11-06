# OpenInterview — minimal MVP UI specification

Design proposal only; no app implementation or acceptance is claimed. This scope replaces the older expanded UI design. Use [requirements](../business/requirements.md), [I/O](../architecture/io-contracts.md), [data lifecycle](../architecture/data-artifacts.md) and the existing [24 sprint tasks](../planning/sprint-plan.md).

## Scope and language

Desktop only: exactly seven page types, one 1440 px desktop Figma frame each. Mobile/tablet/responsive work is OUT OF SCOPE. No extra warning/fallback frame. Keep desktop zoom sensible, keyboard focus visible, labels semantic and contrast readable; respect reduced motion. Error/loading/empty/denied states are annotations or variants, not additional frames or galleries. Dialogs/drawers use interaction annotations, not samples piled below the UI.

<a id="ngon-ngu-ui"></a>

All visible website text, accessible names, errors, notices, emails, policies, summaries and generated notes use simple English. Robot/interview speech is Vietnamese. Preserve original Vietnamese finalized transcript and evidence under “Original transcript (Vietnamese)” and “Original evidence (Vietnamese)”; never translate over source data. No language switch or provider/model changes.

## Exactly seven pages

| Page | Route | Content and boundary |
| --- | --- | --- |
| Home | `/` | Compact logo / Roles / Sign in navbar; one hero and one Example robot preview only |
| Sign in | `/login` | Continue with Google; readable account Terms/Privacy notice/dialog; no first-profile wizard |
| Roles | `/roles` | One role card list with assigned rooms embedded; no separate history portal |
| Join room | `/rooms/{id}` | Details, notice/consent, mic permission, speaker test, scheduled waiting and access errors on this same page |
| Interview | `/sessions/{id}/interview` | One large central robot stage and exactly three controls |
| HR | `/hr` | Campaigns, Rooms, Reports tabs in one workspace; inline forms/drawers |
| Admin | `/admin` | Minimal users/HR grants and service/job health; expandable audit metadata |

Google callback is a system transition, not an eighth page/frame. One account/logout menu; HR/Admin entries appear there only with backend permission. No profile, settings, candidate directory, separate calendar, analytics, help/policy/data-request design pages, completion page or state galleries. Policies and contact procedures remain readable within sign-in/join pages, before consent.

### Home: stop after the blue box

Badge “Voice interviews in Vietnamese”; title “Start with a conversation.”; short subtitle “AI leads a short interview. Recruiters review the evidence.” Exactly two hero CTAs: “View roles” and “I have an invitation”, both reaching assigned rooms in Roles after sign-in when needed, with safe return paths. No invitation-code management screen. One large dark-purple robot interview preview labelled “Example”. STOP after preview: no workflow, features, bento, FAQ, testimonials, pricing, bottom CTA, marketing footer or links to removed sections. Internal approved FAQ remains an answering source, not a Home section.

### Sign in and Roles

Google-only basic sign-in/account terms; new accounts are candidates, never self-selected HR/Admin. Backend verifies OAuth state/nonce, identity/invitation match and allowlisted internal return path. Cancel/error stays inline; no auto-join or media on sign-in. Roles are professions (BA, DevOps, Fullstack, Frontend, Backend, AI Engineer), not permissions. Assigned room rows show safe campaign, schedule/timezone and status with a Join room link. “No room assigned” is distinct from fetch failure. Never offer self-created practice rooms or confidential rubric/report access.

### Join room

Authorize identity, organization scope, assignment, campaign version, schedule and revocation before private details or token issuance. Before mic testing, show the actual approved English disclosure: AI, purpose, collected session/transcript/report data, viewers, retention by type, stop/refuse/correction/deletion procedures, limits, policy version and HR contact. No invented durations or hidden policy text. Consent is explicit and unchecked; store version/UTC/choice server-side. Browser permission is not consent. Refusal leaves before media collection.

After consent: “Check microphone”, “Test speaker”, browser permission/error guidance and “Join interview” on this page. Test locally without durable capture; playback acknowledgement does not prove hearing. Waiting is inline “Not available yet” with schedule, no countdown page. Backend rechecks all gates before short-lived room/identity-scoped token; pending prevents duplicate sessions. Wrong/expired/revoked access remains inline without resource-existence leaks. CV is not required from candidate; an inline “Contact recruiter” link allows mismatch reporting before start, not a new workflow. No candidate CV upload/manage/download.

### Interview: stage plus exactly three controls

One large central robot stage. Exactly three visible buttons, with accessible labels matching the next action:

1. “Mute microphone” / “Unmute microphone”.
2. “Mute speaker” / “Unmute speaker”.
3. “End interview”.

No navbar, header, sidebar, dashboard shell, timer, volume, device selector, captions, chat, recording, help/history/profile panels or permanent explanatory paragraphs. Short essential status/errors (“Listening”, “AI is speaking”, “Reconnecting”, “Microphone unavailable”) live INSIDE the stage, not in extra panels or controls. No extra retry/leave button: recovery is bounded and automatic; End stays available in every state. Platform-owned browser permission dialogs are not app controls. Mic mute stops mic publishing; speaker mute affects local playback only; neither ends the session or changes consent.

End immediately stops capture/playback, cancels queued/generating output and ends safely without a confirmation step or forced spoken wrap. Return to Roles with inline “Interview ended”; data already collected follows policy, with no automatic deletion promise. Persist terminal state/report job idempotently; if offline stop media locally and reconcile server termination/stale-session cleanup without resuming audio. Backend still tracks deadline, connection and delivery. Interruption cancels old output; reconnect reauthorizes the same session without replay or duplicate turns. No recording/export in active MVP, not even disabled controls.

### HR: one small workspace

- Campaigns: list + “New campaign” inline/drawer for bounded JD, role, common questions/rubric and FAQ source approval/validity. Real authorized approval locks a version; changes create new versions, not edits to running snapshots.
- Rooms: list + “Create room” for candidate email/name and exact identity binding, role, locked campaign snapshot, schedule/timezone/contact and optional HR CV attachment. “Publish invitation” validates server-side gates. Show “No CV attached” when absent; not an eligibility error. Check recipient/room/CV relationship, HR upload/disclosure authority and separate lawful basis/notice BEFORE upload. Candidate later interview consent is not retroactive authorization.
- HR alone can correct a draft attachment. On publish/invite, lock attachment ID/version/hash or explicit absence with the room. Wrong CV afterward means revoke/cancel old room and create a NEW room; never swap an ongoing session or source history. No candidate CV library or per-career sharing. Backend bounded PDF validation (5 MB configurable proposal), quarantine and successful scan precede publication of any room containing a file; no scan means no publication. See [contract](../business/requirements.md#hợp-đồng-dữ-liệu-tối-thiểu).
- Reports: list + inline detail/drawer with English unverified summary, evidence/requirement status, original Vietnamese finalized turn refs, corrections, FAQ sources, human review and controlled retry. Missing/refused is not low ability. Only confirmed assistant delivery establishes what was asked; no partial/planned/unknown evidence. New input/correction version needs new approval. CV metadata is provenance/reference only, never a finalized candidate turn, scoring input or new AI prompt input.

No broad candidate directory, live eavesdropping/mic controls, scheduling matrix, analytics/settings/approval pages. Retained CV requires private object storage now, scoped URLs for assigned HR/worker only as needed, server-only secrets, audit and retention/deletion including copies/backups; tombstones prevent job/restore resurrection. No default candidate download.

### Admin

Users/invite HR grants with scope, recipient confirmation, backend authorization and audit; no self-elevation. Service/job health is truthful metadata with checked time and unknown/stale/error states. Audit metadata expands inline; no separate settings/audit/data-request screen or browser secrets/config editor. Admin has no default transcript/CV access. Verified correction/deletion procedures remain backend processes with inline policy contacts, not extra dashboards.

## Prototype and validation annotations

Connect Home → Roles → Sign in → Join room consent/device/waiting → Interview → End → Roles feedback; auth may occur earlier. Connect HR campaign approval → room optional attachment/scan → publish → report/evidence/review; Admin grant/status in its one frame. Annotate wrong identity, missing consent, blocked mic, revoked/expired access, reconnect/end races, rejected/missing scan, wrong CV after publish and report retry edges without more frames.

Target WCAG AA contrast (normal text 4.5:1, large text/essential nontext 3:1), visible keyboard focus, sensible desktop zoom and dialog focus trap/restore. Test desktop browsers and English copy; do not claim measured compliance from this document. Preserve limits/retries, durable DB jobs and privacy despite fewer screens. Policy owners, retention values, scan service, exact schema/limits, OAuth matching and browser support need approval before real use.

## Style reference

https://www.figma.com/design/16cDiwbllLuWYqXMUel8ER/AI-Startup-Website-UI-Kit-%E2%80%94-Framer-Website-Kit--Community-?node-id=0-1&p=f&t=dh6doRDbSAdMYd3y-0

Layers/tokens/license have not been inspected. Dark/violet screenshots guide style only: near-black, restrained violet glow, readable light text, thin borders and a simple static/vector robot. Latest blue-box Home and interview screenshots define scope, overriding template content. Screenshot dimensions are source-image sizes, not extra device frames. Do not claim exact sampled tokens or asset reuse rights; check license before reuse.
