# Verification results — 2026-11-07

Scope: synthetic shared text controller and local evidence runner. No production
approval, human listening, browser voice integration or report generation claim.

## Actual offline evidence

Run `20261107T130043Z-b861a85d`: 20/20 deterministic cases passed.
Artifacts: `artifacts/ai/20261107T130043Z-b861a85d/manifest.json`,
`cases.json`, `summary.md` (repository-relative, ignored local evidence).
The manifest records exact fixture hashes and SDK versions.

Before the live attempt: isolated AI tests 6 passed (0.109 s test time,
0.411 s wall), contract tests 9 passed (0.143 s, 0.361 s wall), provider smoke
offline tests 2 passed (0.010 s, 0.095 s wall). Default harness wall: 0.220 s.
Initial RED: missing controller module; GREEN: the checks above.

## First authorized live attempt — evidence writer failed

Command: `.venv/bin/python -m backend.ai_verify --live`.
Exit 1, wall 10.138 seconds. The runner completed its probe function but failed
serializing a datetime in an LLM comparison into `manifest.json`. Provider results
were only in memory and were **not persisted**. They cannot be claimed as passed,
and no WER, transcript, model availability or voice quality result is fabricated.
No second live invocation was made during that implementation pass. Partial WAV/case files may remain in the
attempt's ignored run directory; the failed command did not print its exact ID.
The safe claim is a failed verification run, not a provider success or failure.

The writer was fixed to emit JSON-safe timestamps, print its directory before
requests, and checkpoint provider results progressively. An offline regression
first reproduced the exact serialization failure, then tests exercised the fix
with synthetic HTTP replies. This does **not** recover or rewrite failed live
evidence. The controller later authorized and ran the second attempt recorded below;
it does not retroactively make the first attempt successful.

Installed signature inspection resolved default ElevenLabs voice ID
`hpp4J3VqNfWAUOO0d1Us`. Signature inspection alone was not proof of successful
use; the second run now records actual use. SDKs: LiveKit Agents and Google/Deepgram/ElevenLabs plugins 1.8.11;
Pydantic 2.14.3 (recorded by the offline manifest). Model defaults are unchanged:
controller `gemini-3.5-flash-lite`, report `gemini-3.8-flash`, Deepgram `nova-3`
language `vi`, ElevenLabs `eleven_flash_v2_5`. Functional availability on the
second run is recorded below; report-model availability remains unverified.

Human listening, accents, independent source audio, plugin streaming, NLU,
natural-language guardrail review, report model and full pipeline remain pending.

## Post-fix offline check

The datetime regression and mocked eight-request probe passed offline; the mock
also covers invalid LLM schema, checkpoint JSON, generated WAV paths and safe
credential omission. Post-fix harness run `20261107T130313Z-9f6bad97` passed 20/20
in 0.221 s wall (manifest duration 0.019 s approximately; see the exact manifest).
Artifacts: `artifacts/ai/20261107T130313Z-9f6bad97/{manifest.json,cases.json,summary.md}`.
These artifacts are offline only, not recovered live results.

Final scoped checks after multi-turn budget/end coverage: AI verification tests
10 passed (0.131 s test time, 0.355 s wall), contract tests 9 passed (0.117 s,
0.317 s wall), `git diff --check` passed. Final offline run
`20261107T130405Z-4e253b86` passed 20/20 in 0.244 s wall; exact inputs, outputs,
SDK versions and hashes are in
`artifacts/ai/20261107T130405Z-4e253b86/manifest.json` and `cases.json`.
Full suites, Docker/database integration, public provider smoke and browser/e2e
were not run for this scoped change. No commits or pushes were made.

## Scoped hardening — offline only

Cache replay after end/expiry, private cache retention and empty followup evidence
were reproduced as three RED tests, then fixed. Dedupe now retains a canonical
SHA-256 payload digest plus bounded safe output. No full input or state snapshot
is stored in the result cache. Live schema-valid but unexpected wrap/deadline
decisions are rejected even without a fallback reason. Nested datetime evidence
is tested with actual cases loaded from the fixture, actual controller calls and
mocked HTTP only. Listening-review generation is checked against generated mock
WAV files; there is no human listening claim.

All 20 existing case IDs/expectations and schema version remain unchanged. The
two followup fixtures now explicitly cite their finalized candidate turn IDs so
the happy path and quota case exercise the nonempty-evidence rule.

Scoped AI tests: 13 passed (0.257 s test time, 0.594 s wall). Per the explicit
request for all offline checks, `python -m unittest discover -s tests -p 'test_*.py'`
ran: 34 passed (3.591 s test time, 4.224 s wall). One Starlette/AnyIO deprecation
warning was emitted. Default offline harness: 20/20, 0.358 s wall. Evidence:
`artifacts/ai/20261107T130752Z-b026e4a0/{manifest.json,cases.json,summary.md,listening-review.md}`.
That manifest pins controller/config/runner hashes, safe configuration, SDKs and
fixtures. No live invocation, real dotenv read or provider request was made in
this hardening pass. Docker/database and browser/e2e checks remain skipped.

## Second authorized live run — technical functional success, not quality approval

The controller authorized and ran one additional bounded invocation after the
fix: `.venv/bin/python -m backend.ai_verify --live`. Saved run
`20261107T130859Z-0d96004c` reports **20/20 offline cases and live technical pass**,
8 provider attempts, no retries, 12.85 seconds runner duration. This documentation
update only reads its saved evidence; no further provider calls were made.

Repository-relative evidence directory:
`artifacts/ai/20261107T130859Z-0d96004c/` contains:

- `manifest.json`: configuration, SDK versions, source/fixture/artifact SHA-256,
  request counts, duration and technical status.
- `providers.json`: actual TTS/STT outputs, transcripts/metrics and both LLM
  schema/policy/expected-versus-actual comparisons.
- `cases.json`: all 20 offline inputs, expected decisions and actual results.
- `summary.md`: technical pass with explicit unverified scope.
- `listening-review.md`: all reviewer/date/quality fields **PENDING**.
- `name.wav`, `numbers.wav`, `negation.wav`: three generated synthetic samples,
  24,000 Hz mono 16-bit PCM, total 7.663 seconds. They were not played or listened
  to during this documentation update.

### Actual provider functions

- **TTS:** ElevenLabs `eleven_flash_v2_5` generated all three WAVs. Actual public
  voice ID `hpp4J3VqNfWAUOO0d1Us`, resolved from the installed plugin signature
  default, is recorded in the run. Receiving audio is not pronunciation approval.
- **STT:** three real Deepgram batch requests used configured `nova-3`, language
  `vi`. All returned transcripts; public response model metadata is
  `general-nova-3`, version `2026-09-24.19075`, architecture `nova-3`.
- **LLM:** two real Gemini requests returned model version
  `gemini-3.5-flash-lite`. Both `core` and `candidate_injection` proposals passed
  schema and expected/actual controller comparisons and were policy-accepted.
  The prompt explicitly instructed the desired bounded `ask_core` proposal.
  This is a narrow functional check, **not injection robustness or broad semantic
  safety proof**.
- **Transport:** direct HTTPS, not LiveKit plugin streaming or browser/media
  integration. SDK versions are LiveKit Agents and Google/Deepgram/ElevenLabs
  plugins **1.8.11**, Pydantic **2.14.3**. Their presence does not prove plugin
  streaming compatibility. Report model `gemini-3.8-flash` was not tested;
  provider region and quotas were not probed.

### Round-trip transcript observations

| Sample | Audio duration | Normalized WER | Entity/negation observation |
| --- | --- | --- | --- |
| name | 2.508 s | 44.44% | `Nguyễn An` preserved; other words wrong |
| numbers | 2.879 s | 0% | `hai năm` and `chín giờ` preserved |
| negation | 2.276 s | 0% | `chưa` and `không` preserved |

Name gold: “Tôi là Nguyễn An, tên giả để kiểm thử.”
Actual transcript: “Tôi là Nguyễn An tên Gia Đế Kiếm Thụ”.
Preserving the name does not make the whole transcript correct. Numbers matched
the gold sentence; negation matched after punctuation normalization. WER uses the
documented NFC/case-folded word metric, not a semantic or pronunciation judgment.

**No approved WER threshold exists.** These are descriptive measurements, not a
quality-gate pass. This three-sample TTS → STT round trip cannot localize the name
sentence error to TTS or STT without listening. It provides no independent-source
STT evaluation, regional-accent/noise/echo coverage or general Vietnamese quality
approval. No human listening, NLU, full text gate, report or voice pipeline gate
is marked complete.

### User listening action — all pending

Open each file locally and compare it with its gold text and transcript:

1. `artifacts/ai/20261107T130859Z-0d96004c/name.wav`
2. `artifacts/ai/20261107T130859Z-0d96004c/numbers.wav`
3. `artifacts/ai/20261107T130859Z-0d96004c/negation.wav`

Use `artifacts/ai/20261107T130859Z-0d96004c/listening-review.md` for the actual WAV
links and record reviewer/date, name pronunciation, number/time accuracy,
negation, intelligibility/truncation and notes. All fields remain **PENDING**;
no human pass or listening claim has been added.

Documentation follow-up validation: all 34 offline unittest checks passed
(2.543 s test time, 2.878 s wall), including local Markdown link-target and
code-fence checks for this results page and both changed planning documents;
`git diff --check` passed. The existing Starlette/AnyIO deprecation warning
remains. No new live run or audio playback was performed for this update.
