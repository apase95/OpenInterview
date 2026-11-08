import asyncio
import io
import json
import tempfile
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from contextlib import redirect_stdout

from backend.voice_latency import Recorder


class LatencyTests(unittest.TestCase):
    def test_offline_cli_deterministic_without_configuration(self):
        from backend.voice_baseline import main
        outputs = []
        with patch('backend.config.load_config', side_effect=AssertionError('must stay offline')), patch(
                'sys.argv', ['baseline']):
            for _ in range(2):
                output = io.StringIO()
                with redirect_stdout(output):
                    main()
                outputs.append(output.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(json.loads(outputs[0])['status'], 'not_run')

    def test_wiring_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            callbacks = {}
            session = NS(on=lambda name, fn: callbacks.update({name: fn}))
            recorder = Recorder(Path(directory))
            recorder.attach(session)
            done = []
            handle = NS(id='PRIVATE', interrupted=False, add_done_callback=done.append)
            callbacks['speech_created'](NS(speech_handle=handle))
            for value in (1, 2, 3):
                callbacks['metrics_collected'](NS(metrics=NS(type='llm_metrics', speech_id='PRIVATE',
                    ttft=value, duration=4, cancelled=False, label='SECRET')))
            done[0](handle)
            recorder.finish()
            report = json.loads((recorder.path / 'summary.json').read_text())
            self.assertEqual(report['stages']['llm_metrics.ttft']['median'], 2)
            self.assertEqual(report['stages']['llm_metrics.ttft']['p95'], 3)
            self.assertEqual(report['outcomes']['done_unverified'], 1)
            self.assertNotIn('PRIVATE', (recorder.path / 'events.jsonl').read_text())
            self.assertNotIn('SECRET', (recorder.path / 'events.jsonl').read_text())

    def test_interruption_cancel_errors_and_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            callbacks = {}
            recorder = Recorder(Path(directory), limit=8)
            recorder.attach(NS(on=lambda name, fn: callbacks.update({name: fn})))
            done = []
            handle = NS(id='x', interrupted=True, add_done_callback=done.append)
            callbacks['speech_created'](NS(speech_handle=handle))
            done[0](handle)
            callbacks['metrics_collected'](NS(metrics=NS(type='tts_metrics', speech_id='x',
                ttfb=1, duration=2, cancelled=True)))
            for recoverable in (True, False):
                callbacks['error'](NS(error=NS(recoverable=recoverable, message='SECRET')))
            for _ in range(20):
                callbacks['metrics_collected'](NS(metrics=NS(type='unknown', text='SECRET')))
            recorder.finish()
            report = json.loads((recorder.path / 'summary.json').read_text())
            self.assertEqual(report['outcomes']['interrupted'], 1)
            self.assertEqual(report['outcomes']['cancelled'], 1)
            self.assertEqual(report['errors'], 2)
            self.assertNotIn('tts_metrics.ttfb', report['stages'])
            self.assertGreater(report['dropped'], 0)


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_wires_metrics_and_preserves_error_cleanup(self):
        from backend.worker import voice_job
        with tempfile.TemporaryDirectory() as directory:
            recorder = Recorder(Path(directory))
            callbacks = {}
            session = NS(on=lambda name, fn: callbacks.setdefault(name, []).append(fn),
                         start=AsyncMock(), aclose=AsyncMock())
            def say(*args, **kwargs):
                for recoverable in (True, False):
                    for callback in callbacks['error']:
                        callback(NS(error=NS(recoverable=recoverable, message='SECRET')))
            session.say = say
            room = NS(name='local_voice_synthetic', metadata='{}')
            ctx = NS(job=NS(metadata=json.dumps({'deadline': time.time() + 60,
                'identity': 'participant_synthetic'}), room=room), room=room,
                connect=AsyncMock(), wait_for_participant=AsyncMock(),
                add_shutdown_callback=Mock(), shutdown=Mock())
            external = NS(Agent=Mock(), AutoSubscribe=NS(AUDIO_ONLY='audio'),
                          room_io=NS(RoomOptions=Mock()))
            with patch.dict(os.environ, {'LOCAL_VOICE_METRICS': 'true'}), patch.dict(
                    'sys.modules', {'livekit.agents': external}), patch(
                    'backend.worker.voice_session', return_value=session), patch(
                    'backend.worker.load_config'), patch('backend.voice_latency.Recorder', return_value=recorder):
                await asyncio.wait_for(voice_job(ctx), 1)
            session.aclose.assert_awaited_once()
            ctx.shutdown.assert_called_once()
            report = json.loads((recorder.path / 'summary.json').read_text())
            self.assertEqual(report['errors'], 2)
            self.assertEqual([r['recoverable'] for r in recorder.rows if r['kind'] == 'error'], [True, False])

    async def test_sdk_stream_delivers_before_completion_and_propagates_error(self):
        from livekit.agents import APIConnectOptions, APIConnectionError, llm
        gate = asyncio.Event()
        class Model(llm.LLM):
            def chat(self, **kwargs):
                return Stream(self, **kwargs)
        class Stream(llm.LLMStream):
            async def _run(self):
                self._event_ch.send_nowait(llm.ChatChunk(id='synthetic', delta=llm.ChoiceDelta(content='hello')))
                await gate.wait()
                raise APIConnectionError('synthetic failure')
        model = Model()
        errors = []
        model.on('error', errors.append)
        stream = model.chat(chat_ctx=llm.ChatContext(), tools=[], conn_options=APIConnectOptions(max_retry=0))
        async with stream:
            chunk = await asyncio.wait_for(anext(stream), 1)
            self.assertEqual(chunk.delta.content, 'hello')
            self.assertFalse(stream._task.done())
            gate.set()
            with self.assertRaises(APIConnectionError):
                await asyncio.wait_for(anext(stream), 1)
        self.assertEqual(len(errors), 1)
        self.assertFalse(errors[0].recoverable)

    async def test_audio_consumer_reads_first_frame_before_producer_finishes(self):
        from backend.voice_baseline import collect_audio
        from livekit import rtc
        gate = asyncio.Event()
        consumed = asyncio.Event()
        class Stream:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def __aiter__(self):
                yield NS(frame=rtc.AudioFrame(b'\0\0' * 240, 24000, 1, 240))
                consumed.set()
                await gate.wait()
                yield NS(frame=rtc.AudioFrame(b'\0\0' * 240, 24000, 1, 240))
        task = asyncio.create_task(collect_audio(Stream()))
        await asyncio.wait_for(consumed.wait(), 1)
        self.assertFalse(task.done())
        gate.set()
        frames, measured = await task
        self.assertEqual(len(frames), 2)
        self.assertAlmostEqual(measured['audio_file_seconds'], .02)
        with self.assertRaises(ValueError):
            await collect_audio(Stream(), byte_limit=1)


if __name__ == '__main__':
    unittest.main()
