# %%
"""Check recording consent, private files and SDK hooks without provider calls.

Synthetic frames and fake audio/model nodes drive real capture and SDK session
code. Temporary output distinguishes submitted audio from reported playout;
fake sink completion does not prove browser playback or intelligible speech.
"""
import asyncio
import json
import os
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch
import wave

from fastapi.testclient import TestClient
from test_local_voice import ENV, HEADERS


# %%
class ConsentTests(unittest.TestCase):
    """Check server-controlled recording enablement before fake room allocation."""
    def test_explicit_consent_before_allocation(self):
        """Reject missing recording consent before invoking the mocked room API."""
        from backend.api import app
        with patch.dict(os.environ, {**ENV, 'LOCAL_VOICE_RECORDING': 'true'}, clear=True), patch('backend.api.voice_api') as remote:
            client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 9))
            self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS,
                                        json={'consent': True}).status_code, 422)
            remote.assert_not_called()

    def test_approved_lease_and_body_cannot_enable(self):
        """Require server enablement and matching approved metadata on the fake lease."""
        from backend.api import app, attempts
        from backend.voice_recording import approved, MODE
        attempts.clear()
        remote = NS(room=NS(list_rooms=AsyncMock(return_value=NS(rooms=[])),
                           create_room=AsyncMock()), aclose=AsyncMock())
        with patch.dict(os.environ, ENV, clear=True), patch('backend.api.voice_api', return_value=remote):
            client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 9))
            self.assertFalse(approved({}))
            with self.assertRaises(ValueError):
                approved({'recording': MODE})
            self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS,
                json={'consent': True, 'recording_consent': True}).status_code, 422)
            remote.room.create_room.assert_not_called()
            with patch.dict(os.environ, {'LOCAL_VOICE_RECORDING': 'true'}):
                with self.assertRaises(ValueError):
                    approved({})
                response = client.post('/local/voice/sessions', headers=HEADERS,
                    json={'consent': True, 'recording_consent': True})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['recording'])
                request = remote.room.create_room.call_args.args[0]
                lease = json.loads(request.agents[0].metadata)
                self.assertEqual(lease, json.loads(request.metadata))
                self.assertTrue(approved(lease))


# %%
class RecordingTests(unittest.IsolatedAsyncioTestCase):
    """Check bounded capture, private replay output and synthetic SDK integration."""
    async def test_terminal_failure_and_budgets(self):
        """Keep the first terminal budget/format failure and stop later persistence."""
        import queue
        from backend.voice_recording import Capture, RAW_LIMIT
        from livekit import rtc
        frame = rtc.AudioFrame(data=bytes(320), sample_rate=16000,
                               num_channels=1, samples_per_channel=160)
        for guard in ('metadata', 'oversized', 'cumulative', 'queue'):
            with tempfile.TemporaryDirectory() as directory:
                stop = Mock()
                capture = Capture(Path(directory), {}, stop)
                if guard == 'metadata':
                    bad = NS(data=memoryview(bytes(320)), sample_rate=16000,
                             num_channels=1, samples_per_channel=161)
                    capture.audio('output', bad)
                elif guard == 'oversized':
                    large = rtc.AudioFrame(data=bytes(288000), sample_rate=24000,
                                           num_channels=1, samples_per_channel=144000)
                    capture.audio('input', large)
                elif guard == 'cumulative':
                    capture.total = RAW_LIMIT
                    capture.audio('output', frame)
                else:
                    with patch.object(capture.q, 'put_nowait', side_effect=queue.Full):
                        capture.audio('output', frame)
                first = capture.failure
                capture.fail('later_failure')
                capture.event('must_not_persist', text='FAKE_SECRET')
                await capture.aclose()
                stop.assert_called_once()
                self.assertEqual(capture.failure, first)
                rows = [json.loads(s) for s in (capture.path / 'events.jsonl').read_text().splitlines()]
                failures = [r for r in rows if r['kind'] == 'capture_failure']
                self.assertEqual(len(failures), 1)
                self.assertEqual(failures[0]['reason'], first)
                self.assertEqual(rows[-1]['reason'], first)
                self.assertNotIn('FAKE_SECRET', json.dumps(rows))
                self.assertEqual(json.loads((capture.path / 'manifest.json').read_text())['status'], first)

    async def test_long_sdk_segment(self):
        """Use a fake SDK sink to check long-segment chunk offsets and WAV tail data."""
        import time
        from livekit import rtc
        from livekit.agents.voice import io as sdk_io
        from backend.voice_recording import Capture, output_wrapper
        class Sink(sdk_io.AudioOutput):
            def __init__(self):
                super().__init__(label='offline', capabilities=sdk_io.AudioOutputCapabilities(pause=True))
            async def capture_frame(self, frame):
                await super().capture_frame(frame)
            def flush(self):
                super().flush()
            def clear_buffer(self):
                self.on_playback_finished(playback_position=6, interrupted=True)
        for interrupted in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                stop = Mock()
                capture = Capture(Path(directory), {}, stop)
                sink = Sink()
                wrapper = output_wrapper(capture, sink)
                frame = rtc.AudioFrame(data=b'\x01\x00' * 2400, sample_rate=24000,
                    num_channels=1, samples_per_channel=2400)
                try:
                    for _ in range(60):
                        await wrapper.capture_frame(frame)
                    wrapper.flush()
                    with patch('backend.voice_recording.time.time', return_value=time.time()):
                        if interrupted:
                            wrapper.clear_buffer()
                        else:
                            sink.on_playback_progressed(started_at=time.time(), offset=0, duration=6)
                            sink.on_playback_finished(playback_position=6, interrupted=False)
                    self.assertIsNone(capture.failure)
                finally:
                    await capture.aclose()
                stop.assert_not_called()
                self.assertEqual((capture.path / 'output.pcm').read_bytes(), bytes(frame.data) * 60)
                rows = [json.loads(s) for s in (capture.path / 'events.jsonl').read_text().splitlines()]
                chunks = [r for r in rows if r['kind'] == 'audio' and r['track'] == 'output']
                self.assertEqual([r['bytes'] for r in chunks], [262144, 25856])
                self.assertEqual(chunks[1]['offset_bytes'], 262144)
                self.assertAlmostEqual(chunks[1]['t'] - chunks[0]['t'], 131072 / 24000)
                with wave.open(str(capture.path / 'output.wav')) as wav:
                    data = wav.readframes(wav.getnframes())
                    self.assertEqual(data[-2:], b'\x01\x00')

    async def test_full_supported_duration_and_budget(self):
        """Check declared storage/frame limits and the exact capture-duration boundary."""
        from backend.voice_recording import Capture
        from livekit import rtc
        with tempfile.TemporaryDirectory() as directory:
            stop = Mock()
            capture = Capture(Path(directory), {}, stop)
            try:
                self.assertEqual(capture.manifest['limits']['seconds'], 600)
                self.assertEqual(capture.manifest['limits']['frames'], 120000)
                self.assertEqual(capture.manifest['limits']['raw_bytes'], 128 * 1024**2)
                self.assertEqual(capture.manifest['limits']['reservation_bytes'], 256 * 1024**2)
                self.assertEqual(capture.manifest['limits']['owned_storage_bytes'], 1024**3)
                frame = rtc.AudioFrame(data=bytes(320), sample_rate=16000,
                                       num_channels=1, samples_per_channel=160)
                capture.audio('input', frame, 599.98)
                self.assertIsNone(capture.failure)
                capture.audio('input', frame, 600)
                self.assertEqual(capture.failure, 'audio_limit')
            finally:
                await capture.aclose()
            stop.assert_called_once()

    async def test_tracks_and_private_files(self):
        """Check synthetic track mixing, resampling, transcript retention and file modes."""
        import numpy as np
        from livekit import rtc
        from backend.voice_recording import Capture
        with tempfile.TemporaryDirectory() as directory:
            capture = Capture(Path(directory), {}, lambda: None)
            frame = rtc.AudioFrame(data=np.full(160, 1000, dtype=np.int16).tobytes(),
                                   sample_rate=16000, num_channels=1, samples_per_channel=160)
            capture.audio('input', frame, .01)
            capture.audio('output', frame, .015)
            stereo = rtc.AudioFrame(data=np.tile(np.array([1000, 3000], dtype='<i2'), 80).tobytes(),
                sample_rate=8000, num_channels=2, samples_per_channel=80)
            capture.audio('input', stereo, .03)
            capture.event('final_stt', text='xin chào')
            await capture.aclose()
            with wave.open(str(capture.path / 'replay.wav')) as wav:
                self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (2, 2, 16000))
                samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, 2)
            self.assertTrue((samples[:160] == 0).all())
            self.assertTrue((samples[240:320] == 1000).all())
            self.assertTrue((samples[480:640, 0] == 2000).all())
            self.assertTrue((samples[480:640, 1] == 0).all())
            self.assertEqual(capture.path.stat().st_mode & 0o777, 0o700)
            for path in capture.path.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn('xin chào', (capture.path / 'events.jsonl').read_text())

    async def test_actual_agent_nodes_forward_and_filter(self):
        """Patch default SDK nodes to check forwarding and filtered transcript/context data."""
        from backend.voice_recording import recording_agent
        from livekit.agents import Agent, llm
        recorded = []
        capture = NS(event=lambda kind, **row: recorded.append((kind, row)),
                     audio=lambda *args: recorded.append(('audio', args)), turn=lambda raw: 1)
        agent = recording_agent(capture, 'safe prompt')
        frame = object()
        async def frames():
            yield frame
        async def stt(self, audio, settings):
            async for item in audio:
                self_test.assertIs(item, frame)
            yield interim
            yield final
        from livekit.agents import stt as stt_module
        interim = stt_module.SpeechEvent(type=stt_module.SpeechEventType.INTERIM_TRANSCRIPT,
            alternatives=[stt_module.SpeechData(language='vi', text='interim')])
        final = stt_module.SpeechEvent(type=stt_module.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt_module.SpeechData(language='vi', text='corrected final')])
        self_test = self
        with patch.object(Agent.default, 'stt_node', stt):
            self.assertEqual([item async for item in agent.stt_node(frames(), {})], [interim, final])
        self.assertEqual([row for kind, row in recorded if kind == 'final_stt'],
                         [{'alternatives': [{'text': 'corrected final', 'language': 'vi'}]}])
        context = llm.ChatContext()
        context.add_message(role='user', content='synthetic', extra={'provider': 'FAKE_SECRET'})
        context.add_message(role='assistant', content='reply')
        context.items.append(llm.FunctionCall(id='tool', call_id='call', name='fake', arguments='FAKE_SECRET'))
        with patch.object(Agent.default, 'llm_node', return_value='forwarded') as node:
            self.assertEqual(agent.llm_node(context, [], {}), 'forwarded')
            self.assertIs(node.call_args.args[1], context)
        context_rows = json.dumps([row for kind, row in recorded if kind == 'llm_context'])
        self.assertIn('synthetic', context_rows)
        self.assertNotIn('FAKE_SECRET', context_rows)

    async def test_actual_output_hook_discards_tail_and_preserves_lifecycle(self):
        """Use fake sink progress/cancellation to separate played and submitted PCM."""
        import numpy as np
        from livekit import rtc
        from livekit.agents.voice import io as sdk_io
        from backend.voice_recording import Capture, output_wrapper
        class Sink(sdk_io.AudioOutput):
            def __init__(self):
                super().__init__(label='fake room', capabilities=sdk_io.AudioOutputCapabilities(pause=True))
                self.frames = []
                self.cleared = False
                self.cancel_next = False
            async def capture_frame(self, frame):
                if self.cancel_next:
                    self.cancel_event = sdk_io._CaptureCancelledEvent(playback_position=0, interrupted=True)
                    self.emit('playback_finished', self.cancel_event)
                    raise asyncio.CancelledError()
                await super().capture_frame(frame)
                self.frames.append(frame)
            def flush(self):
                super().flush()
            def clear_buffer(self):
                self.cleared = True
                import time
                self.on_playback_progressed(started_at=time.time() - .005, offset=0, duration=.005)
                self.on_playback_finished(playback_position=.005, interrupted=True)
        with tempfile.TemporaryDirectory() as directory:
            capture = Capture(Path(directory), {}, lambda: None)
            sink = Sink()
            wrapper = output_wrapper(capture, sink)
            events = []
            wrapper.on('playback_finished', events.append)
            frame = rtc.AudioFrame(data=np.full(160, 1000, dtype=np.int16).tobytes(),
                sample_rate=16000, num_channels=1, samples_per_channel=160)
            await wrapper.capture_frame(frame)
            wrapper.flush()
            wrapper.clear_buffer()
            event = await wrapper.wait_for_playout()
            self.assertTrue(event.interrupted)
            self.assertEqual(event.playback_position, .005)
            self.assertEqual(len(events), 1)
            self.assertIs(sink.frames[0], frame)
            self.assertTrue(sink.cleared)
            self.assertFalse(capture.manifest['unsettled_output'])
            sink.cancel_next = True
            with self.assertRaises(asyncio.CancelledError):
                await wrapper.capture_frame(frame)
            self.assertIs(events[-1], sink.cancel_event)
            await capture.aclose()
            self.assertEqual((capture.path / 'output.pcm').stat().st_size, 160)
            self.assertEqual((capture.path / 'submitted.pcm').stat().st_size, 640)
            self.assertTrue(capture.manifest['unsettled_output'])
            self.assertIn('output_capture_cancelled', (capture.path / 'events.jsonl').read_text())

    async def test_limits_storage_empty_and_write_failure(self):
        """Check event/storage rejection and safe closure after a mocked write failure."""
        from backend.voice_recording import Capture
        with tempfile.TemporaryDirectory() as directory:
            stop = Mock()
            capture = Capture(Path(directory), {}, stop)
            capture.event_bytes = 1024 * 1024
            capture.event('final_stt', text='not written')
            await capture.aclose()
            self.assertEqual(capture.failure, 'event_limit')
            stop.assert_called_once()
            self.assertFalse(capture.thread.is_alive())
            with wave.open(str(capture.path / 'replay.wav')) as wav:
                self.assertEqual(wav.getnframes(), 0)
            with patch('backend.voice_recording.STORAGE_LIMIT', 1):
                with self.assertRaises(OSError):
                    Capture(Path(directory), {}, stop)
            capture = Capture(Path(directory), {}, stop)
            with patch.object(capture.events, 'write', side_effect=OSError('FAKE_SECRET')):
                capture.event('final_stt', text='synthetic')
                await capture.aclose()
            self.assertEqual(capture.failure, 'write_failure')
            self.assertNotIn('FAKE_SECRET', (capture.path / 'manifest.json').read_text())
            self.assertTrue(capture.events.closed)

    async def test_speech_and_text_hooks(self):
        """Drive fake callbacks to check private transcript chunks and unknown spoken text."""
        from backend.voice_recording import Capture, recording_agent
        from livekit.agents import Agent
        callbacks = {}
        session = NS(on=lambda name, cb: callbacks.update({name: cb}), current_speech=NS(id='speech'))
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr, self.assertNoLogs():
            capture = Capture(Path(directory), {}, lambda: None)
            capture.attach(session)
            capture.event('final_stt', alternatives=[{'text': 'synthetic user', 'language': 'en'}])
            done = []
            callbacks['speech_created'](NS(speech_handle=NS(id='speech', add_done_callback=done.append)))
            done[0](NS(interrupted=True))
            agent = recording_agent(capture, 'prompt')
            from livekit.agents.voice.agent_activity import _SpeechHandleContextVar
            token = _SpeechHandleContextVar.set(NS(id='speech'))
            try:
                async def text():
                    yield 'synthetic '
                    yield 'assistant'
                self.assertEqual([s async for s in agent.transcription_node(text(), {})], ['synthetic ', 'assistant'])
            finally:
                _SpeechHandleContextVar.reset(token)
            await capture.aclose()
            rows = [json.loads(line) for line in (capture.path / 'events.jsonl').read_text().splitlines()]
            self.assertTrue(next(r for r in rows if r['kind'] == 'speech_done')['interrupted'])
            self.assertEqual(next(r for r in rows if r['kind'] == 'assistant_text')['turn'], 1)
            self.assertEqual(stdout.getvalue(), '')
            self.assertEqual(stderr.getvalue(), '')
            transcript = json.loads((capture.path / 'transcript.json').read_text())
            self.assertEqual(transcript['entries'][0]['speaker'], 'user')
            self.assertEqual(transcript['entries'][0]['text'], 'synthetic user')
            assistant = transcript['entries'][1]
            self.assertEqual(assistant['text'], 'synthetic assistant')
            self.assertEqual(assistant['chunks'], ['synthetic ', 'assistant'])
            self.assertEqual(assistant['state'], 'interrupted')
            self.assertEqual(assistant['spoken_text'], 'unavailable')
            self.assertEqual((capture.path / 'transcript.json').stat().st_mode & 0o777, 0o600)

    async def test_real_session_say_calls_recording_hooks_without_text_output(self):
        """Run a real SDK session with fake model/TTS/sink to check recording hooks."""
        import numpy as np
        import time
        from livekit import rtc
        from livekit.agents import AgentSession, llm, tts
        from livekit.agents.voice import io as sdk_io
        from backend.voice_recording import Capture, recording_agent
        class FakeTTS(tts.TTS):
            def __init__(self):
                super().__init__(capabilities=tts.TTSCapabilities(streaming=False), sample_rate=16000, num_channels=1)
            def synthesize(self, text, **kwargs):
                raise AssertionError('overridden node must be used')
        class Model(llm.LLM):
            def chat(self, *, chat_ctx, tools, conn_options, **kwargs):
                return Stream(self, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        class Stream(llm.LLMStream):
            async def _run(self):
                self._event_ch.send_nowait(llm.ChatChunk(id='synthetic',
                    delta=llm.ChoiceDelta(content='synthetic model reply')))
        class Sink(sdk_io.AudioOutput):
            def __init__(self):
                super().__init__(label='fake room', capabilities=sdk_io.AudioOutputCapabilities(pause=True))
            async def capture_frame(self, frame):
                await super().capture_frame(frame)
            def flush(self):
                super().flush()
                self.on_playback_progressed(started_at=time.time() - .01, offset=0, duration=.01)
                self.on_playback_finished(playback_position=.01, interrupted=False)
            def clear_buffer(self):
                pass
        with tempfile.TemporaryDirectory() as directory:
            capture = Capture(Path(directory), {}, lambda: None)
            session = AgentSession(tts=FakeTTS(), llm=Model(), turn_detection='manual')
            session.output.audio = Sink()
            capture.attach(session)
            agent = recording_agent(capture, 'synthetic prompt')
            async def audio(text, settings):
                async for _ in text:
                    pass
                yield rtc.AudioFrame(data=np.full(160, 1000, dtype=np.int16).tobytes(),
                    sample_rate=16000, num_channels=1, samples_per_channel=160)
            agent.tts_node = audio
            try:
                await session.start(agent=agent, record=False, session_host=False)
                await asyncio.wait_for(capture.ready.wait(), 1)
                handle = session.say('synthetic greeting')
                await asyncio.wait_for(handle.wait_for_playout(), 1)
                handle = session.generate_reply(user_input='synthetic question')
                await asyncio.wait_for(handle.wait_for_playout(), 1)
            finally:
                await session.aclose()
                await capture.aclose()
            rows = (capture.path / 'events.jsonl').read_text()
            self.assertIn('synthetic greeting', rows)
            self.assertIn('synthetic question', rows)
            self.assertIn('synthetic model reply', rows)
            self.assertIn('synthetic prompt', rows)
            self.assertIn('assistant_text', rows)
            events = [json.loads(row) for row in rows.splitlines()]
            created = next(row for row in events if row['kind'] == 'speech_created')
            text = next(row for row in events if row['kind'] == 'assistant_text')
            self.assertEqual(text['turn'], created['turn'])
            self.assertGreater((capture.path / 'output.pcm').stat().st_size, 0)


if __name__ == '__main__':
    unittest.main()
