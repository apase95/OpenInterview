# %%
"""Build server-side voice configuration from environment values on demand.

Import does not load dotenv or contact providers. Placeholder checks help setup
but do not prove that credentials are valid or remote services are reachable.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

# Reject obvious setup placeholders, not every possible invalid credential.
def is_placeholder(value):
    if not value:
        return True
    value = value.strip()
    return 'xxxx' in value or 'your-project' in value or len(value) < 8


# %%
# Hide required credentials from repr while retaining existing provider defaults.
@dataclass(frozen=True)
class Config:
    livekit_url: str = field(repr=False)
    livekit_api_key: str = field(repr=False)
    livekit_api_secret: str = field(repr=False)
    google_api_key: str = field(repr=False)
    deepgram_api_key: str = field(repr=False)
    eleven_api_key: str = field(repr=False)
    gemini_controller_model: str = 'gemini-3.5-flash-lite'
    gemini_report_model: str = 'gemini-3.8-flash'
    deepgram_model: str = 'nova-3'
    deepgram_language: str = 'vi'
    elevenlabs_model: str = 'eleven_flash_v2_5'
    elevenlabs_voice_id: str | None = None


# %%
# Optional dotenv loading preserves existing environment values. Errors name
# missing credentials without printing them; optional overrides are not validated.
def load_config(*, load_file=True):
    if load_file:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    names = ('LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET',
             'GOOGLE_API_KEY', 'DEEPGRAM_API_KEY', 'ELEVEN_API_KEY')
    invalid = [name for name in names if is_placeholder(os.getenv(name))]
    if invalid:
        raise ValueError('Invalid or missing: ' + ', '.join(invalid))
    values = {name.lower(): os.environ[name].strip() for name in names}
    for name in ('GEMINI_CONTROLLER_MODEL', 'GEMINI_REPORT_MODEL', 'DEEPGRAM_MODEL',
                 'DEEPGRAM_LANGUAGE', 'ELEVENLABS_MODEL', 'ELEVENLABS_VOICE_ID'):
        if name in os.environ:
            values[name.lower()] = os.environ[name]
    return Config(**values)
