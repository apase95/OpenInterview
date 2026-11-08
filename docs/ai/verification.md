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

## Voice latency observations (opt-in)

Set `LOCAL_VOICE_METRICS=true` on the voice worker to write bounded, content-free
`artifacts/ai/voice-<random-session-id>/events.jsonl` and `summary.json` at cleanup.
Default is off. Metrics do not enable recording. No text, transcript, audio, provider request
IDs, token counts, keys or exception strings are written by this recorder.
Each process uses monotonic relative receipt times, not SDK wall timestamps.
At most 2,048 events and 2,048 SDK speech-ID mappings are retained per session;
overflow is counted. In-memory observations are lost on process crash.

Verified installed SDK hooks: `metrics_collected` (deprecated but supported),
`speech_created`, `SpeechHandle.add_done_callback`, `SpeechHandle.interrupted`,
`error`, `close`. Only SDK `speech_id` joins metrics to speech handles; local
integer turn IDs are not participant IDs, user utterance IDs or provider request
IDs. STT/VAD without a join key remain session-level, never attached to the
latest speech. `say` greetings may be the first measured speech.

LLM TTFT is SDK first-token time; TTS TTFB is SDK first-byte time, not browser
playback. STT streaming duration=0 is a placeholder and is excluded. EOU and
transcription delay are SDK VAD-based estimates; zero can mean no detected speech
end, not instantaneous latency. VAD inference total is not per-turn latency.
Missing fields/types stay explicit. Median and p95 use observed nonnegative,
finite values; p95 is nearest-rank `sorted[ceil(0.95 * n) - 1]`.
Sample counts are metric-event counts, not independent user turns.
First/subsequent cohorts use the first observed joined speech, **not cold/warm**.
Interrupted speech and cancelled requests are excluded from stage summaries;
unjoined errors cannot reliably invalidate a particular turn. Errors, job failure,
job cancellation and SDK outcomes remain in events. `done_unverified` means only
SDK speech completion, never successful browser delivery. These are descriptive
observations, not success-only latency or an SLA. Streaming stages overlap:
do not sum their durations or call their sum end-to-end latency.

## Safe provider error evidence

Metrics `error` and capture `session_error` events use the same safe fields, for example:

```json
{"component":"llm","category":"timeout","http_status":null,"recoverable":true,"retryable":true,"retry_count":null,"retry_evidence":"unavailable_in_sdk_event","observed_error_index":1}
```

Components are `llm`, `stt`, `tts`, `realtime`, or `unknown`. Categories are
`timeout`, `connection`, `http_status`, `api`, `cancelled`, or `unknown`.
Only typed exceptions determine category; messages and chained exceptions are not
inspected. HTTP status is an integer 100–599 or null. Missing/non-boolean recovery
and retryability fields are null, not false. No error text, label, source, class
name, body, URL, request ID, stack or provider object is saved or printed.

`summary.json` and capture `manifest.json` include `provider_errors` (first safe
error, counts by component/category/status/recoverable, observed total and dropped
count). Counts retain at most 2,048 errors independently of the bounded event
writer; overflow is explicit. Capture guard failures remain separate in `failure`
and `closure_reason`; first failure wins. Provider counts can still record a later
error after a capture guard has stopped event writing, until close starts.

Both reports record configured `retry_policy` once: `max_retry=2`,
`retry_interval=1`, `timeout=10`. This is policy, **not observed retry count**.
Installed SDK 1.8.11 forwards typed model errors through `ErrorEvent`; neither
model errors nor session events expose an attempt index or operation ID.
`observed_error_index` counts session errors, not retries or requests.
`retry_count:null` / `unavailable_in_sdk_event` is intentional, even for recoverable
errors. Recovery eligibility (`retryable`) differs from SDK recovery disposition
(`recoverable`), and neither proves that the next attempt ran.

Verified SDK loops: LLM, batch STT and TTS allow up to `max_retry + 1` attempts
for eligible failures. Streaming STT resets its private recovery counter on
provider progress, so this is not a lifetime retry cap. The first retry delay is
actually 0.1 seconds, then configured interval (1 second), despite the SDK docstring
saying immediate. Streaming TTS does not retry after partial audio; LLM can disable
retry after visible chunks via its stream flag. LLM/TTS status 499 returns without
an error event. Non-API exceptions are not generally retried. Timeout is a connection
option, not an end-to-end session deadline. No private stream wrapping or tracing
was added to infer exact counts.

For the next consented synthetic run, enable the existing metrics flag and/or
recording consent as documented above, restart the worker, then End the session
to finalize the new files. Existing artifacts are not upgraded. The old 11.005 s
LLM TTFT and 40.456 s recoverable error do **not** establish a timeout or its cause.

Offline smoke: `.venv/bin/python -m unittest discover -s tests -p test_voice_diagnostics.py`.

## Small synthetic audio baseline

```sh
# Deterministic JSON plan only: no .env, provider imports, files or network:
.venv/bin/python -m backend.voice_baseline
# Explicit paid opt-in, reads .env; NOT run as part of verification:
.venv/bin/python -m backend.voice_baseline --live
.venv/bin/python -m unittest discover -s tests -p test_voice_latency.py
```

The live command warns before loading config or constructing providers. It uses
the existing configured models/plugins, with three fixed Vietnamese name/number/
negation inputs. Maximum 12 application requests, no SDK retries, 60 seconds per
case (20-second connection options), 800 reply characters, 15 seconds/2 MB per
audio clip. These local post-generation limits are **not billing caps**. Failed
requests can cost money. No automatic retry. Failure exits nonzero with an
incomplete report. Synthetic source WAVs and a safe configured-model manifest,
per-stage observations, failures and count/median/nearest-rank p95 go under
ignored `artifacts/ai/audio-baseline-<id>/`. Provider text/errors are not saved.

This deliberately small baseline uses TTS-generated real audio -> **batch STT**
-> streaming LLM -> streaming TTS, sequentially. It records first text chunk,
first audio frame and completion separately. TTS receives completed LLM text;
this is not a replica of the overlapped worker pipeline. It can locate a slow
direct request stage, not compare batch STT against live endpointing. File
duration includes possible silence and is not a speech-end timestamp. Speech
end, endpointing, barge-in, browser playback and mouth-to-ear are unavailable.
Generated synthetic audio is not human-accent/noise or quality validation.

Offline checks cover real SDK LLM stream delivery before producer completion and
error propagation with a fake provider, audio consumer incremental progress and
budget rejection, worker recoverable/fatal error wiring and cleanup, sanitization,
interruption/cancellation exclusion and bounded summaries. They do not prove
provider plugin WebSocket streaming, worker audio scheduling, browser delivery or
actual acoustic interruption. No live/paid baseline has been run for this change.

See [actual results and blockers](verification-results.md). Full text/voice gates,
semantic approval, durable state/report work and all sprint parents stay open.

## Local pipeline evidence and replay

`LOCAL_VOICE_RECORDING=false` is the default, independent of metrics. Set it to
`true` on **both** host API and worker; restart `npm run test:voice`. Check ordinary
provider consent **and** local recording consent before Start. Missing specific
consent is rejected before room allocation/dispatch. Only the server-issued
`local-pipeline-v1` lease permits capture. Worker/room/flag mismatch fails closed.
Compose remains idle and does not forward this flag. No cloud recording is enabled;
`AgentSession.start(record=False)` stays explicit. Do not run with private data.

Each run creates ignored `artifacts/ai/voice-capture-<32 hex>/` (0700, files 0600):

- `manifest.json`: schema, nonsecret configured models/language/voice, installed
  SDK version, local session ID, optional metrics-directory link, limits, status
  and unsettled-output warning. No environment dump, tool internals or request data.
- `events.jsonl`: monotonic relative timestamps, finalized STT alternatives (no
  interims), text-only actual `llm_node` context (not reconstructed history), AI
  text from `transcription_node`, speech-handle interruption/done and output progress
  completion. Nontext context, tools and SDK metadata are omitted and counted.
  AI text is generated/submitted text, **not spoken text**; `spoken_text` is unavailable.
- `input.pcm`, `submitted.pcm`, `output.pcm`: original signed PCM16 frame data,
  indexed by byte offset/sample rate/channels/time in events. `input` is the exact
  tee into `Agent.default.stt_node`, not proof of STT provider receipt. `submitted`
  includes room-output submission attempts, including cancelled captures and queued tails.
  `output` includes only
  room-sink reported progress, excluding discarded queued tails when reported.
- `input.wav`, `output.wav`, `replay.wav`: aligned 16 kHz PCM16 replay; stereo
  replay left=user, right=AI. Source channel means and linear interpolation are
  debug conversions; raw frame format is retained. One worker clock preserves
  silence and overlap. Empty capture produces valid empty WAVs.
- `transcript.json`: readable user final-STT segments and assistant text, derived
  from the same bounded events in the writer thread. User turn mapping is unavailable;
  segments stay in receipt order, with all alternatives/corrections retained.
  Assistant chunks join verbatim by speech turn; unknown-turn chunks stay separate.
  States are `interrupted`, `done_unverified`, or `unsettled`, never proof of spoken
  delivery. Actual LLM context stays only in `events.jsonl`. Finalized only on cleanup.
- `reservation`: small marker reserving a 256 MiB accounting slot, not audio. It remains until deletion.

Verified against pinned LiveKit Agents 1.8.11: `Agent.default.stt_node` forwards
frames immediately; `llm_node` receives the supplied context; `transcription_node`
receives output text. The pinned SDK `_SpeechHandleContextVar` joins generation
tasks to speech handles (not the possibly different currently-playing speech).
`Agent.on_enter` installs the audio wrapper; the worker waits for its ready event
before greeting. The local wrapper reuses **only** SDK `RecorderAudioOutput`
for `capture_frame`, flush/clear, pause, event propagation and progress slicing.
It does not start `RecorderIO`, job recording or its encoder. The room sink derives
progress from `AudioSource.queued_duration` and excludes discarded buffers. SDK
wall-time progress ages are translated to worker monotonic time. A wall-clock jump
can affect this estimate. This is room-submission/pacing evidence, not browser
delivery, acoustic playback, provider recognition quality or mouth-to-ear latency.
Unreported output at shutdown remains raw-only and is marked unsettled, not guessed.

Capture stops the session on 600 seconds, 128 MiB cumulative raw capture (including
submitted + replay-selected frames), 120,000 queue frames, a 128-item queue overflow, 256 KiB input/submitted frame,
unsupported format, 1 MiB text/events budget or write error. Files are written on
a dedicated thread; replay is bounded to 600 seconds in memory. The API duration
remains 300 seconds by default, maximum 600; recording no longer cuts it at 120.
Earlier resource failures still stop the session with an explicit failure status.
SDK output progress may join many submitted frames into one valid long PCM segment.
These segments are validated against format, cumulative and duration limits, then
split into sample-aligned queue items of at most 256 KiB with original timestamps.
Recording failures are not STT recognition errors: inspect manifest `failure` and
`closure_reason`, and the single terminal `capture_failure` event (relative time,
reason, and frame metadata where applicable). Oversized source frames use
`audio_frame_limit`; malformed PCM metadata uses `audio_format_limit`. Terminal
diagnostics bypass the stopped/full queue, without audio/text or exception details.
Disk failure can prevent event persistence; the manifest is attempted separately.
Old captures with only `audio_format_limit` cannot identify the rejected frame.
Missing final STT before shutdown still requires independent recognition evidence;
audio energy alone does not establish what was said or received by the provider.
Repeated LLM contexts share the 1 MiB event budget and can exhaust it early.
Setup failure stops the session, never silently downgrades to unrecorded. Runtime
errors mark failure where the disk is writable. Abrupt process kill/disk failure
can leave incomplete files; initial manifest remains `incomplete` if not finalized.
`closed` means local cleanup, not complete delivery. No durable crash recovery.

Storage has a reservation cap of four owned capture directories / 1 GiB logical
budget under a process-shared POSIX lock, not a disk-free guarantee or preallocation.
Per capture, 128 MiB raw + 76,800,132 bytes for two mono WAVs and stereo replay
leaves room in 256 MiB for 120,000 audio index rows, bounded events/transcript and metadata.
Existing other AI artifacts are neither
read nor deleted and are outside this capture budget. No automatic retention:
after reviewing locally, stop the launcher and remove only your chosen capture:

```sh
# Replace the example ID with the exact owned directory; do not delete artifacts/ai wholesale.
rm -r -- artifacts/ai/voice-capture-0123456789abcdef0123456789abcdef
.venv/bin/python -m unittest discover -s tests -p test_voice_recording.py
```

Never share these files unredacted. Local model context can include the whole
conversation and system prompt. No chain-of-thought, provider request objects,
headers, credentials or arbitrary SDK objects are serialized. Provider retention
is independent of this local setting. Offline fake-frame tests do not establish
WebRTC/browser/Vietnamese quality; no paid recording was made for this change.
