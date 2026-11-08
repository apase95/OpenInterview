"""Isolated offline error evidence; no recording dependency or provider calls."""
import asyncio
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from livekit.agents import APIStatusError, APITimeoutError

SECRET = 'credential-body-url-transcript-SENTINEL'


class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_sparse_invalid_and_bounded(self):
        from backend.voice_diagnostics import Diagnostics, sanitize_error
        for status in (-1, 600, True, '429', None):
            error = APIStatusError(SECRET, status_code=503)
            error.status_code = status
            row = sanitize_error(NS(error=NS(type='tts_error', error=error, recoverable=1)))
            self.assertEqual(row['category'], 'http_status')
            self.assertIsNone(row['http_status'])
            self.assertIsNone(row['recoverable'])
        for event in (None, NS(), NS(error=None), NS(error=NS(type=[], recoverable=SECRET)),
                      NS(error=NS(error=RuntimeError(SECRET)), source=SECRET)):
            row = sanitize_error(event)
            self.assertEqual(row['component'], 'unknown')
            self.assertEqual(row['category'], 'unknown')
            self.assertNotIn(SECRET, json.dumps(row))
        self.assertEqual(sanitize_error(NS(error=NS(error=asyncio.CancelledError())))['category'], 'cancelled')
        diagnostics = Diagnostics(limit=2)
        event = NS(error=NS(type='llm_error', recoverable=True, error=APITimeoutError(SECRET)))
        self.assertEqual([diagnostics.observe(event)['observed_error_index'] for _ in range(3)], [1, 2, None])
        self.assertEqual(diagnostics.summary()['counts'][0]['count'], 2)
        self.assertEqual(diagnostics.summary()['dropped'], 1)

    async def test_worker_policy_uses_reported_values(self):
        from backend.worker import voice_session
        from backend.voice_diagnostics import RETRY_POLICY
        agents = NS(AgentSession=Mock(), APIConnectOptions=Mock(), SessionConnectOptions=Mock())
        plugins = NS(deepgram=NS(STT=Mock()), google=NS(LLM=Mock()),
                     elevenlabs=NS(TTS=Mock()), silero=NS(VAD=NS(load=Mock())))
        config = NS(elevenlabs_voice_id=None, deepgram_model='', deepgram_language='', deepgram_api_key='',
                    gemini_controller_model='', google_api_key='', elevenlabs_model='', eleven_api_key='')
        with patch.dict('sys.modules', {'livekit.agents': agents, 'livekit.plugins': plugins}):
            voice_session(config)
        self.assertEqual(agents.APIConnectOptions.call_args.kwargs, RETRY_POLICY)
        self.assertEqual(RETRY_POLICY, {'max_retry': 2, 'retry_interval': 1, 'timeout': 10})
        self.assertEqual(agents.SessionConnectOptions.call_args.kwargs['max_unrecoverable_errors'], 1)
