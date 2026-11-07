import os
import unittest
import json
import time
import asyncio
import logging
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient


ENV = {
    'APP_ENV': 'development', 'LOCAL_VOICE_ENABLED': 'true',
    'LOCAL_VOICE_SECRET': 'local-only-secret-with-at-least-32-characters',
    'LOCAL_VOICE_ORIGINS': 'http://127.0.0.1:3000',
    'LIVEKIT_URL': 'wss://synthetic.invalid', 'LIVEKIT_API_KEY': 'synthetic-key',
    'LIVEKIT_API_SECRET': 'synthetic-livekit-secret-not-local-secret',
}
HEADERS = {'Origin': ENV['LOCAL_VOICE_ORIGINS'],
           'Authorization': 'Bearer ' + ENV['LOCAL_VOICE_SECRET']}


class LocalVoiceTests(unittest.TestCase):
    def setUp(self):
        from backend.api import attempts
        attempts.clear()

    def test_disabled_and_auth(self):
        from backend.api import app
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(TestClient(app).post('/local/voice/sessions', json={'consent': True}).status_code, 404)
        with patch.dict(os.environ, ENV, clear=True):
            client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 12345))
            self.assertEqual(client.post('/local/voice/sessions', json={'consent': True}).status_code, 403)
            self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS, json={'consent': False}).status_code, 422)
            preflight = client.options('/local/voice/sessions', headers={
                'Origin': ENV['LOCAL_VOICE_ORIGINS'], 'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'authorization,content-type'})
            self.assertEqual(preflight.status_code, 204)
            self.assertEqual(preflight.headers['access-control-allow-origin'], ENV['LOCAL_VOICE_ORIGINS'])

    def test_grants(self):
        import base64
        import json
        from backend.api import voice_token
        with patch.dict(os.environ, ENV, clear=True):
            token = voice_token('local_voice_test', 'participant_test', 60)
        payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
        grants = payload['video']
        self.assertEqual(grants['room'], 'local_voice_test')
        self.assertEqual(grants['canPublishSources'], ['microphone'])
        self.assertFalse(grants['canPublishData'])
        self.assertFalse(grants.get('roomAdmin', False))
        self.assertLessEqual(payload['exp'] - payload['nbf'], 60)

    def test_sessions_limits_end_expiry_and_failure(self):
        from backend.api import app, AGENT_NAME
        rooms = []
        service = SimpleNamespace(
            list_rooms=AsyncMock(side_effect=lambda request: SimpleNamespace(rooms=list(rooms))),
            list_participants=AsyncMock(return_value=SimpleNamespace(participants=[SimpleNamespace(identity='participant_test')])),
            remove_participant=AsyncMock())

        async def create(request):
            rooms.append(SimpleNamespace(name=request.name, metadata=request.metadata))
            self.assertEqual(request.agents[0].agent_name, AGENT_NAME)
            self.assertEqual(json.loads(request.agents[0].metadata)['identity'][:12], 'participant_')

        async def update(request):
            next(r for r in rooms if r.name == request.room).metadata = request.metadata

        async def delete(request):
            rooms[:] = [r for r in rooms if r.name != request.room]

        service.create_room = AsyncMock(side_effect=create)
        service.update_room_metadata = AsyncMock(side_effect=update)
        service.delete_room = AsyncMock(side_effect=delete)
        remote = SimpleNamespace(room=service, aclose=AsyncMock(), agent_dispatch=SimpleNamespace(
            list_dispatch=AsyncMock(return_value=[SimpleNamespace(id='dispatch_test')]), delete_dispatch=AsyncMock()))
        with patch.dict(os.environ, {**ENV, 'LOCAL_VOICE_TOKEN_TTL': '15', 'LOCAL_VOICE_DURATION': '15'}, clear=True), patch('backend.api.voice_api', return_value=remote):
            client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 12345))
            first = client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True})
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.headers['cache-control'], 'no-store')
            self.assertLessEqual(first.json()['expires_at'], first.json()['ends_at'])
            session_id = first.json()['session_id']
            self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True}).status_code, 429)
            self.assertEqual(client.post('/local/voice/sessions/' + session_id + '/end', headers=HEADERS).status_code, 200)
            self.assertTrue(json.loads(rooms[0].metadata)['ended'])
            remote.agent_dispatch.delete_dispatch.assert_awaited_with('dispatch_test', session_id)
            service.remove_participant.assert_awaited_once()
            # End does not free capacity while a previously issued JWT is reusable.
            self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True}).status_code, 429)
            rooms[0].metadata = json.dumps({'deadline': time.time() - 1})
            second = client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True})
            self.assertEqual(second.status_code, 200)
            self.assertNotEqual(second.json()['session_id'], session_id)
            service.list_rooms.side_effect = RuntimeError('PRIVATE_SENTINEL')
            failed = client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True})
            self.assertEqual(failed.status_code, 503)
            self.assertNotIn('PRIVATE_SENTINEL', failed.text)
            self.assertGreater(remote.aclose.await_count, 0)
            service.list_rooms.side_effect = lambda request: SimpleNamespace(rooms=list(rooms))
            rooms.clear()
            service.create_room.side_effect = RuntimeError('PRIVATE_SENTINEL')
            failed = client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True})
            self.assertEqual(failed.status_code, 503)
            self.assertNotIn('PRIVATE_SENTINEL', failed.text)

    def test_boundaries(self):
        from backend.api import app
        with patch.dict(os.environ, ENV, clear=True):
            client = TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 12345))
            for change, status in (({'APP_ENV': 'production'}, 404),
                                   ({'LOCAL_VOICE_ORIGINS': 'https://evil.example:3000'}, 503),
                                   ({'LOCAL_VOICE_SECRET': ENV['LIVEKIT_API_SECRET']}, 503)):
                with patch.dict(os.environ, change):
                    self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True}).status_code, status)
            for origin in ('null', 'http://evil.example:3000', 'http://127.0.0.1:3001'):
                self.assertEqual(client.post('/local/voice/sessions', headers={**HEADERS, 'Origin': origin}, json={'consent': True}).status_code, 403)
            self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS, content='x' * 1025).status_code, 413)
            self.assertEqual(client.post('/local/voice/sessions', headers=HEADERS, json={'consent': True, 'room': 'injected'}).status_code, 422)
            remote = TestClient(app, base_url='http://127.0.0.1', client=('10.0.0.1', 12345))
            self.assertEqual(remote.post('/local/voice/sessions', headers=HEADERS, json={'consent': True}).status_code, 403)

    def test_worker_pipeline(self):
        from backend.worker import voice_session
        config = SimpleNamespace(deepgram_model='nova-3', deepgram_language='vi',
            deepgram_api_key='stt-secret', gemini_controller_model='unchanged-model',
            google_api_key='llm-secret', elevenlabs_model='eleven_flash_v2_5',
            eleven_api_key='tts-secret', elevenlabs_voice_id=None)
        agents = SimpleNamespace(AgentSession=Mock(), APIConnectOptions=Mock(), SessionConnectOptions=Mock())
        plugins = SimpleNamespace(deepgram=SimpleNamespace(STT=Mock()), google=SimpleNamespace(LLM=Mock()),
            elevenlabs=SimpleNamespace(TTS=Mock()), silero=SimpleNamespace(VAD=SimpleNamespace(load=Mock())))
        with patch.dict('sys.modules', {'livekit.agents': agents, 'livekit.plugins': plugins}):
            voice_session(config)
            self.assertEqual(plugins.deepgram.STT.call_args.kwargs['language'], 'vi')
            self.assertEqual(plugins.google.LLM.call_args.kwargs['model'], 'unchanged-model')
            self.assertNotIn('voice_id', plugins.elevenlabs.TTS.call_args.kwargs)
            self.assertFalse(plugins.elevenlabs.TTS.call_args.kwargs['enable_logging'])
            self.assertTrue(agents.AgentSession.call_args.kwargs['allow_interruptions'])
            self.assertEqual(agents.APIConnectOptions.call_args.kwargs['max_retry'], 2)


class VoiceStartupTests(unittest.TestCase):
    def test_help_skips_config_and_config_failure_is_sanitized(self):
        from backend.worker import main
        server = SimpleNamespace(run=AsyncMock(), on=Mock())
        cli = SimpleNamespace(run_app=Mock())
        output = io.StringIO()
        previous = logging.root.manager.disable
        try:
            with patch('backend.worker.voice_server', return_value=server), patch(
                    'backend.worker.load_config', side_effect=ValueError('PRIVATE_SENTINEL')) as config, patch.dict(
                    'sys.modules', {'livekit.agents': SimpleNamespace(cli=cli)}), redirect_stderr(output):
                with patch.object(sys, 'argv', ['worker', '--voice', '--no-env-file', '--help']):
                    main()
                config.assert_not_called()
                cli.run_app.assert_called_once_with(server)
                with patch.object(sys, 'argv', ['worker', '--voice', '--no-env-file', 'start']):
                    with self.assertRaises(SystemExit) as failure:
                        main()
                self.assertEqual(failure.exception.code, 1)
            self.assertIn('Local voice worker failed', output.getvalue())
            self.assertNotIn('PRIVATE_SENTINEL', output.getvalue())
        finally:
            logging.disable(previous)

    def test_start_routes_args_and_reports_registration(self):
        from backend.worker import main
        server = SimpleNamespace(run=AsyncMock(), on=Mock())
        callbacks = {}
        server.on.side_effect = lambda name, callback: callbacks.update({name: callback})

        def run_app(actual):
            self.assertIs(actual, server)
            self.assertEqual(sys.argv, ['worker', 'start'])
            self.assertEqual(logging.root.manager.disable, logging.CRITICAL)
            callbacks['worker_registered']('PRIVATE_SENTINEL', object())

        output = io.StringIO()
        previous = logging.root.manager.disable
        try:
            with patch.object(sys, 'argv', ['worker', '--voice', '--no-env-file', 'start']), patch(
                    'backend.worker.voice_server', return_value=server), patch(
                    'backend.worker.load_config') as config, patch.dict('sys.modules', {
                        'livekit.agents': SimpleNamespace(cli=SimpleNamespace(run_app=run_app))}), redirect_stdout(output):
                main()
                config.assert_called_once_with(load_file=False)
            self.assertIn('registered; waiting for jobs', output.getvalue())
            self.assertNotIn('PRIVATE_SENTINEL', output.getvalue())
        finally:
            logging.disable(previous)

    def test_swallowed_startup_failure_exits_nonzero(self):
        from backend.worker import main
        server = SimpleNamespace(run=AsyncMock(side_effect=RuntimeError('PRIVATE_SENTINEL')), on=Mock())

        def run_app(actual):
            # The installed SDK catches run() errors and returns normally.
            try:
                asyncio.run(actual.run())
            except Exception:
                pass

        output = io.StringIO()
        previous = logging.root.manager.disable
        try:
            with patch.object(sys, 'argv', ['worker', '--voice', '--no-env-file', 'start']), patch(
                    'backend.worker.voice_server', return_value=server), patch('backend.worker.load_config'), patch.dict(
                    'sys.modules', {'livekit.agents': SimpleNamespace(cli=SimpleNamespace(run_app=run_app))}), redirect_stdout(output), redirect_stderr(output):
                with self.assertRaises(SystemExit) as failure:
                    main()
            self.assertEqual(failure.exception.code, 1)
            self.assertIn('Local voice worker failed', output.getvalue())
            self.assertNotIn('PRIVATE_SENTINEL', output.getvalue())
        finally:
            logging.disable(previous)


class VoiceJobTests(unittest.IsolatedAsyncioTestCase):
    async def test_greeting_and_failure_cleanup(self):
        from backend.worker import voice_job
        room = SimpleNamespace(name='local_voice_test', metadata='{"ended":false}')
        lease = {'deadline': time.time() + 60, 'identity': 'participant_test'}
        ctx = SimpleNamespace(job=SimpleNamespace(metadata=json.dumps(lease), room=room), room=room,
            connect=AsyncMock(), wait_for_participant=AsyncMock(),
            add_shutdown_callback=Mock(), shutdown=Mock())
        session = SimpleNamespace(on=Mock(), start=AsyncMock(), say=Mock(), aclose=AsyncMock())
        callbacks = {}
        session.on.side_effect = lambda name, callback: callbacks.update({name: callback})
        session.say.side_effect = lambda *args, **kwargs: callbacks['close'](None)
        external = SimpleNamespace(Agent=Mock(), AutoSubscribe=SimpleNamespace(AUDIO_ONLY='audio'),
                                  room_io=SimpleNamespace(RoomOptions=Mock()))
        with patch.dict('sys.modules', {'livekit.agents': external}), patch(
                'backend.worker.voice_session', return_value=session), patch('backend.worker.load_config'):
            await voice_job(ctx)
            self.assertFalse(session.start.call_args.kwargs['record'])
            self.assertFalse(external.room_io.RoomOptions.call_args.kwargs['text_output'])
            self.assertEqual(external.room_io.RoomOptions.call_args.kwargs['participant_identity'], 'participant_test')
            session.say.assert_called_once()
            session.aclose.assert_awaited_once()
            ctx.shutdown.assert_called_once()
            session.start.side_effect = RuntimeError('PRIVATE_SENTINEL')
            session.aclose.reset_mock()
            ctx.shutdown.reset_mock()
            with patch('builtins.print') as output:
                await voice_job(ctx)
            self.assertNotIn('PRIVATE_SENTINEL', str(output.call_args))
            session.aclose.assert_awaited_once()
            ctx.shutdown.assert_called_once()
