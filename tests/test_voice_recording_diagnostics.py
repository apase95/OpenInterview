# %%
"""Check shared recording/latency diagnostics with real SDK error models.

A fake model raises local errors through SDK retry machinery; fake session
callbacks feed temporary capture files. Event indexes are not attempt counts,
and these checks do not validate any provider connection or successful retry.
"""
import asyncio
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from livekit.agents import APIError, APIConnectionError, APIStatusError, APITimeoutError
from livekit.agents.llm import LLMError
from livekit.agents.stt import STTError
from livekit.agents.tts import TTSError
from livekit.agents.voice.events import ErrorEvent

SECRET = 'credential-body-url-transcript-SENTINEL'


# %%
class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    """Check shared safe error payloads and first-failure ownership."""
    async def test_real_sdk_retries_forward_events_not_attempt_counts(self):
        """Drive fake model timeouts through SDK retries and retain safe event evidence."""
        from livekit.agents import APIConnectOptions, llm
        from livekit.agents.voice.agent_activity import AgentActivity
        from backend.voice_latency import Recorder
        from backend.voice_recording import Capture
        class Model(llm.LLM):
            def chat(self, **kwargs):
                return Stream(self, **kwargs)
        class Stream(llm.LLMStream):
            async def _run(self):
                raise APITimeoutError(SECRET)
        with tempfile.TemporaryDirectory() as directory:
            recorder = Recorder(Path(directory))
            stop = Mock()
            capture = Capture(Path(directory), {}, stop)
            callbacks = {}
            session = NS(on=lambda name, fn: callbacks.setdefault(name, []).append(fn), _on_error=Mock())
            session.emit = lambda name, event: [fn(event) for fn in callbacks[name]]
            recorder.attach(session)
            capture.attach(session)
            model = Model()
            activity = NS(llm=model, _session=session)
            model.on('error', lambda event: AgentActivity._on_error(activity, event))
            stream = model.chat(chat_ctx=llm.ChatContext(), tools=[],
                                conn_options=APIConnectOptions(max_retry=2, retry_interval=0))
            try:
                with patch('livekit.agents.llm.llm.logger'):
                    async with stream:
                        with self.assertRaises(APIConnectionError):
                            await anext(stream)
            finally:
                await capture.aclose()
                recorder.finish()
            self.assertEqual([r['recoverable'] for r in recorder.rows], [True, True, False])
            self.assertEqual([r['observed_error_index'] for r in recorder.rows], [1, 2, 3])
            self.assertTrue(all(r['retry_count'] is None for r in recorder.rows))
            self.assertEqual(capture.failure, 'unrecoverable_session_error')
            stop.assert_called_once()
            self.assertEqual(recorder.diagnostics.summary()['counts'][0]['count'], 2)
            self.assertNotIn(SECRET, json.dumps(recorder.rows))

    async def test_shared_payload_summary_and_first_failure(self):
        """Feed SDK errors locally and require matching summaries without secret leakage."""
        from backend.voice_latency import Recorder
        from backend.voice_recording import Capture
        callbacks = {}
        session = NS(on=lambda name, fn: callbacks.setdefault(name, []).append(fn))
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(output), redirect_stderr(output), self.assertNoLogs():
            recorder = Recorder(Path(directory))
            stop = Mock()
            capture = Capture(Path(directory), {}, stop)
            recorder.attach(session)
            capture.attach(session)
            try:
                for model, error in ((LLMError, APITimeoutError(SECRET)),
                                     (STTError, APIConnectionError(SECRET)),
                                     (TTSError, APIStatusError(SECRET, status_code=429, body=SECRET, request_id=SECRET))):
                    event = ErrorEvent(error=model(timestamp=0, label=SECRET, error=error, recoverable=True), source=SECRET)
                    for fn in callbacks['error']:
                        fn(event)
                capture.fail('audio_format_limit')
                for fn in callbacks['error']:
                    fn(NS(error=NS(type='llm_error', error=APIError(SECRET), recoverable=False)))
            finally:
                await capture.aclose()
                recorder.finish()
            rows = [json.loads(line) for line in (capture.path / 'events.jsonl').read_text().splitlines()]
            errors = [r for r in rows if r['kind'] == 'session_error']
            for actual, expected in zip(errors, recorder.rows):
                self.assertEqual({k: v for k, v in actual.items() if k not in ('kind', 't')},
                                 {k: v for k, v in expected.items() if k not in ('kind', 'relative_seconds')})
            self.assertEqual([r['category'] for r in errors], ['timeout', 'connection', 'http_status'])
            self.assertTrue(all(r['retry_count'] is None for r in errors))
            self.assertEqual(capture.failure, 'audio_format_limit')
            stop.assert_called_once()
            manifest = json.loads((capture.path / 'manifest.json').read_text())
            summary = json.loads((recorder.path / 'summary.json').read_text())
            self.assertEqual(manifest['provider_errors'], summary['provider_errors'])
            self.assertEqual(summary['provider_errors']['observed_errors'], 4)
            self.assertEqual(summary['provider_errors']['first_error']['category'], 'timeout')
            self.assertEqual(summary['retry_policy']['max_retry'], 2)
            self.assertNotIn(SECRET, json.dumps([rows, manifest, summary, recorder.rows]) + output.getvalue())
