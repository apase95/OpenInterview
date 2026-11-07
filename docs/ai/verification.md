# Repeatable AI verification

This is a synthetic text harness and bounded provider probe, not a voice interview.
The worker remains idle. The harness calls `backend.controller.decide`, the shared
pure Python controller intended for a future media adapter. It is not a second
mock controller. No new dependencies or provider/model defaults were introduced.

## Run from the repository root

Use Python 3.12 with the existing `requirements.txt` and backend test dependencies.
The installed LiveKit plugins supply the default public ElevenLabs voice ID;
`ELEVENLABS_VOICE_ID` can optionally override it on the server.

```sh
.venv/bin/python -m unittest discover -s tests -p test_ai_verification.py
.venv/bin/python -m backend.ai_verify
# Explicit opt-in only; reads root .env server-side, environment takes precedence:
.venv/bin/python -m backend.ai_verify --live
```

Unittest's exact filename pattern limits execution to that file. Tests mock
provider requests and do not load real dotenv. The default runner is offline;
CI must never add `--live`. `--output-dir` must name a new directory.
Raw evidence defaults to ignored `artifacts/ai/<run-id>/`. Never commit credentials,
candidate audio or CVs. Do not automatically rerun failed live requests.

## Inputs, outputs and approval

- `fixtures/synthetic/v1.json` supplies a validated Campaign via the existing Bundle.
  The harness replaces its English FAQ with the exact Vietnamese approved test
  catalog in `backend/controller.py`. This is fictional test approval, not recruiter
  sign-off. January 2026 source windows are evaluated at each fixture's fixed time.
- `fixtures/ai/cases.json` v1 stores candidate text, confirmed intent, state,
  optional untrusted proposal, expected action/reason, and three gold transcripts.
  The fictional Nguyễn An test identity is not a real person. Gold transcripts
  are UTF-8; no private candidate data is used.
- `Input` is a typed, **confirmed upstream intent**, not an NLU prediction. Neither
  intent extraction nor the semantics of arbitrary speech is verified. Source refs
  likewise represent an upstream topic resolver, not a model's authority.
- Controller action enums reuse the contract. Proposals must pass schema, current
  criterion/evidence and bounded wording checks. Arbitrary model questions are
  never spoken. Campaign approval alone does not authorize new wording: unknown
  core/FAQ catalog text is blocked. This deliberately narrow catalog must be
  reviewed and extended before another campaign can run.
- End wins over consent phase/deadline/proposals. Skip records null/refused, never
  low ability. Corrections append links while preserving original turns. The pure
  state supports exact-turn dedupe and payload conflict rejection; it does not
  provide database durability, consent orchestration or delivery acknowledgements.
- `cases.json` saves complete deterministic case input, expected and actual
  decision/text/source refs/state and pass/fail. `manifest.json` records run ID,
  UTC time, HEAD, dirty-tree caveat, SDK versions, fixture hashes, duration, counts,
  provider details and artifact hashes (excluding itself and final summary).
  `summary.md` is a concise English scope statement. Live `providers.json` is a
  progressive safe checkpoint, plus local synthetic WAVs. No provider error bodies,
  URLs containing credentials, exception text or environment dumps are saved.

Per-run `listening-review.md` includes gold text, links only to generated WAVs,
and PENDING reviewer/date/name/number/negation fields. Offline runs mark audio
not generated. Manifests also pin controller/config/runner source SHA-256 hashes,
safe model defaults, request budgets and actual live configuration when requested.
The shared JSON writer serializes nested date/datetime values, including case
deadlines and live comparisons. Current terminal/deadline checks override cached
speech; dedupe retains only canonical input hashes and safe output, not private
event text. Followups require nonempty valid finalized evidence. Live policy
acceptance requires the expected action and full expected/actual comparison pass.

## Live budget and interpretation

At most three short TTS requests, three STT requests and two Gemini requests,
sequential, no retries, 45-second timeout per request. The generated PCM is mono
24 kHz, 16-bit, wrapped as WAV. Clips above 20 seconds or cumulative 40 seconds
are not sent to STT. This is a post-generation check, not a provider billing cap.
HTTP response bodies are bounded at 8 MB. Providers may charge failed requests.

Transport is **direct HTTPS**, not LiveKit plugin streaming verification:
ElevenLabs PCM generation → Deepgram batch `/listen`, configured model/language;
Gemini `generateContent` returns proposals passed through the same controller.
The resolved SDK default voice is recorded separately from configured model IDs;
Deepgram public model metadata and Gemini response model version are recorded
when returned. Report model, region and quotas are marked not verified/probed.
LLM schema errors, policy rejection and expected/actual comparison are separate.
Raw model prose does not become production speech or policy.

WER is word-level Levenshtein distance divided by gold word count, with Unicode
NFC, case folding and punctuation removal. Entity/negation checks are separate
normalized substring checks, not semantic correctness. Generated TTS → STT is a
round-trip technical sample, not independent STT/accent validation. No acceptance
threshold or Vietnamese quality approval is invented. Latencies are per-request
elapsed seconds, not first-audible browser latency, p50/p95 or an SLA.

## Human listening (pending)

An authorized Vietnamese reviewer should open each local WAV, compare the gold
text and transcript, and record reviewer/date, run ID, name/number/time/negation
accuracy, pronunciation, intelligibility and any truncation. Do not treat audio
bytes or a transcript as proof of listening. Accent/noise/echo/browser/barge-in,
naturalness, fairness and end-to-end delivery need separate approved samples.

See [actual results and blockers](verification-results.md). Full text/voice gates,
semantic approval, durable state/report work and all sprint parents stay open.
