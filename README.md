# OpenInterview

## Provider smoke setup (Python 3.10+)

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` privately. Never commit keys or share its contents.
`python smoke_test.py` calls external services and may cost money. Each provider
has a 30-second timeout. Exit status is 0 only when all four checks pass.

- LiveKit: admin room-list API only, not a browser/WebRTC connection.
- Gemini: nonempty generated text only, not Vietnamese quality or report validation.
- Deepgram: projects endpoint authentication only, not Nova-3 Vietnamese transcription.
- ElevenLabs: audio frames received only, not playback or Vietnamese quality.

These checks do not validate the full pipeline or the Sprint 1 exit gate.
Run the checks in your environment; do not treat provider access as an end-to-end test.

Offline checks (no keys, SDKs, or network needed):

```sh
python -m unittest discover -s tests -p test_smoke_test.py
```

This stdlib test mocks dotenv and all four providers. It checks import safety,
success/failure exit values, sanitized errors, and the scope disclaimer.
