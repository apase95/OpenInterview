# %%
"""Check controller evidence and verification reports with synthetic inputs.

HTTP requests and plugin construction are replaced in live-path checks. These
tests validate local policy and report handling, not provider or audio quality.
"""
import unittest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone

from backend.controller import State, Input, decide
from backend.ai_verify import campaign, offline, error_rate


# %%
class VerificationTests(unittest.TestCase):
    """Exercise decision safety, privacy and verification output boundaries."""
    def test_cache_cannot_override_current_terminal_or_expiry(self):
        """Require current end and expiry state to take priority over cached turns."""
        from datetime import timedelta
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        c = campaign()
        event = Input(turn_id='syn_cached', text='Xin chào')
        asked = decide(c, State(deadline=now + timedelta(minutes=10)), event, now)
        ended = decide(c, asked.state, Input(turn_id='syn_stop', text='Dừng', intent='end'), now)
        self.assertEqual(decide(c, ended.state, event, now).action, 'end')
        self.assertEqual(decide(c, asked.state, event, now + timedelta(minutes=11)).action, 'wrap')

    def test_cache_minimizes_sensitive_and_restricted_text(self):
        """Keep private text out of cached state while detecting conflicting retries."""
        import json
        from dataclasses import asdict
        from datetime import timedelta
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        for intent in ('sensitive', 'restricted'):
            event = Input(turn_id='syn_private', text='PRIVATE_SENTINEL_DO_NOT_RETAIN', intent=intent)
            result = decide(campaign(), State(deadline=now + timedelta(minutes=10)), event, now)
            self.assertNotIn(event.text, repr(result.state))
            self.assertNotIn(event.text, repr(result.state.results))
            self.assertNotIn(event.text, json.dumps(asdict(result.state), default=str))
            self.assertEqual(decide(campaign(), result.state, event, now).action, 'advance')
            with self.assertRaises(ValueError):
                decide(campaign(), result.state, event.model_copy(update={'text':'changed'}), now)

    def test_followup_requires_nonempty_finalized_evidence(self):
        """Admit a proposed follow-up only when its evidence names a known turn."""
        from datetime import timedelta
        from backend.controller import FOLLOWUP
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        event = Input(turn_id='syn_answer', text='Tôi xử lý hỗ trợ.')
        p = {'action':'ask_followup', 'criterion':'syn_support', 'question':FOLLOWUP}
        for evidence, expected in (([], 'ask_core'), (['syn_missing'], 'ask_core'), (['syn_answer'], 'ask_followup')):
            result = decide(campaign(), State(deadline=now + timedelta(minutes=10)), event, now,
                            {**p, 'evidence_turn_ids':evidence})
            self.assertEqual(result.action, expected)

    def test_cases(self):
        """Require the checked-in offline decision cases to pass."""
        rows = offline()
        self.assertGreaterEqual(len(rows), 12)
        self.assertTrue(all(row['passed'] for row in rows), rows)

    def test_end_and_dedupe(self):
        """Keep explicit stop dominant and repeated stop results stable."""
        c = campaign()
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        s = State(deadline=now, phase='consent')
        event = Input(turn_id='syn_end', text='Dừng lại', intent='end')
        result = decide(c, s, event, now, {'action': 'invent'})
        self.assertEqual(result.action, 'end')
        self.assertEqual(decide(c, result.state, event, now), result)

    def test_metrics(self):
        """Check word-error scoring for edits and an exact Vietnamese match."""
        self.assertEqual(error_rate('a b', 'a c d'), 1)
        self.assertEqual(error_rate('chưa làm', 'chưa làm'), 0)

    def test_multiturn_budget_and_all_phase_end(self):
        """Bound follow-ups and allow an explicit stop in every listed phase."""
        from datetime import timedelta
        from backend.controller import FOLLOWUP
        c = campaign()
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        s = State(deadline=now + timedelta(minutes=10))
        s = decide(c, s, Input(turn_id='syn_first', text='Xin chào'), now).state
        for i in range(2):
            result = decide(c, s, Input(turn_id=f'syn_follow{i}', text='Tôi xử lý hỗ trợ.'), now,
                            {'action':'ask_followup', 'criterion':'syn_support', 'question':FOLLOWUP, 'evidence_turn_ids':[f'syn_follow{i}']})
            self.assertEqual(result.action, 'ask_followup')
            s = result.state
        self.assertEqual(decide(c, s, Input(turn_id='syn_over', text='Tiếp tục'), now,
                               {'action':'ask_followup', 'criterion':'syn_support', 'question':FOLLOWUP, 'evidence_turn_ids':['syn_over']}).action, 'wrap')
        for phase in ('consent', 'basic_info', 'experience', 'light_technical', 'candidate_qa', 'wrap'):
            s = State(deadline=now, phase=phase)
            self.assertEqual(decide(c, s, Input(turn_id='syn_end', text='Dừng', intent='end'), now).action, 'end')

    def test_correction_skip_and_conflict(self):
        """Preserve original evidence, link corrections and reject changed retries."""
        c = campaign()
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        from datetime import timedelta
        s = State(deadline=now + timedelta(minutes=10), turns={'syn_old':'một năm'})
        event = Input(turn_id='syn_new', text='hai năm', intent='correction', target_turn_id='syn_old')
        result = decide(c, s, event, now)
        self.assertEqual(result.state.turns['syn_old'], 'một năm')
        self.assertEqual(result.state.corrections, [{'target':'syn_old', 'replacement':'syn_new'}])
        with self.assertRaises(ValueError):
            decide(c, result.state, event.model_copy(update={'text':'ba năm'}), now)
        skipped = decide(c, s, Input(turn_id='syn_skip', text='bỏ qua', intent='skip'), now)
        self.assertEqual(skipped.state.refused[0]['value'], None)

    def test_live_config_failure_is_safe(self):
        """Replace config loading with a failure and require a secret-free result."""
        from backend.ai_verify import live
        with tempfile.TemporaryDirectory() as folder, patch('backend.config.load_config', side_effect=ValueError('PRIVATE_SECRET')):
            result = asyncio.run(live(Path(folder)))
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('PRIVATE_SECRET', str(result))

    def test_live_http_failure_and_schema(self):
        """Use a fake HTTP session to check sanitized transport and status failures."""
        from backend.ai_verify_live import request
        from unittest.mock import AsyncMock, Mock
        import aiohttp
        session = Mock()
        session.post.side_effect = aiohttp.ClientError('PRIVATE_SECRET')
        body, status = asyncio.run(request(session, 'https://example.com', headers={}))
        self.assertIsNone(body)
        self.assertNotIn('PRIVATE_SECRET', str(status))
        response = Mock(status=403)
        context = Mock()
        context.__aenter__ = AsyncMock(return_value=response)
        context.__aexit__ = AsyncMock(return_value=False)
        session.post.side_effect = None
        session.post.return_value = context
        self.assertEqual(asyncio.run(request(session, 'https://example.com', headers={}))[1]['http_status'], 403)

    def test_live_artifacts_are_serializable(self):
        """Write temporary JSON evidence and require stable date serialization."""
        import json
        from datetime import date, timedelta
        from backend.ai_verify import execute, FIXTURE, write_json
        case = json.loads(FIXTURE.read_text())['cases'][0]
        case['now'] = datetime(2026, 1, 2, tzinfo=timezone.utc)
        case['state'] = {'deadline':case['now'] + timedelta(minutes=10)}
        row = execute(case)
        self.assertTrue(row['passed'])
        evidence = {'providers':{'comparison':row}, 'date':date(2026, 1, 2),
                    'state':State(deadline=case['state']['deadline'])}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            write_json(path, evidence)
            saved = json.loads(path.read_text())
            self.assertEqual(saved['providers']['comparison']['input']['state']['deadline'], '2026-01-02T00:10:00+00:00')
            self.assertEqual(saved['state']['deadline'], '2026-01-02T00:10:00+00:00')

    def test_mocked_live_evidence(self):
        """Use fake plugin and HTTP replies to test artifacts and policy rejection.

        Schema-valid replies must still fail when controller actions disagree;
        generated listening-review links do not establish audio quality.
        """
        import json
        import types
        from unittest.mock import AsyncMock
        from backend.ai_verify_live import probe
        from backend.ai_verify import FIXTURE
        from backend.config import Config
        config = Config(*(['synthetic-only'] * 6))
        def tts(*, voice_id='syntheticvoice'):
            pass
        plugins = types.ModuleType('livekit.plugins')
        plugins.elevenlabs = types.SimpleNamespace(TTS=tts)
        proposal = {'action':'ask_core', 'criterion':'syn_support', 'question':'Bạn từng xử lý yêu cầu hỗ trợ như thế nào?'}
        body = json.dumps({'candidates':[{'content':{'parts':[{'text':json.dumps(proposal)}]}}]}).encode()
        replies = [(b'\x00\x00' * 2400, {'status':'passed'}),
                   (json.dumps({'results':{'channels':[{'alternatives':[{'transcript':'Tôi chưa làm.'}]}]}}).encode(), {'status':'passed'})] * 3
        replies += [(body, {'status':'passed'}), (b'{}', {'status':'passed'})]
        with tempfile.TemporaryDirectory() as folder, patch.dict('sys.modules', {'livekit.plugins':plugins}), patch('backend.ai_verify_live.request', new=AsyncMock(side_effect=replies)) as mock:
            result = asyncio.run(probe(config, Path(folder), json.loads(FIXTURE.read_text())))
            self.assertEqual(mock.await_count, 8)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['llm'][0]['comparison']['passed'], True)
            self.assertEqual(result['llm'][1]['schema'], 'failed')
            saved = json.loads((Path(folder) / 'providers.json').read_text())
            self.assertEqual(saved['attempts'], 8)
            self.assertNotIn('synthetic-only', json.dumps(saved))
            self.assertTrue((Path(folder) / 'negation.wav').exists())
            review = (Path(folder) / 'listening-review.md').read_text()
            for clip in json.loads(FIXTURE.read_text())['audio']:
                self.assertIn(f"[Open WAV]({clip['id']}.wav)", review)
                self.assertIn(clip['gold'], review)
            self.assertIn('Reviewer: PENDING', review)
            self.assertIn('Date: PENDING', review)

        # Real fixture + real controller yields a schema-valid wrap, not the expected
        # ask_core. No fallback substring exists: comparison/action must still fail.
        fixtures = json.loads(FIXTURE.read_text())
        for case in fixtures['cases']:
            if case['id'] in ('core', 'candidate_injection'):
                case['now'] = datetime(2026, 1, 2, tzinfo=timezone.utc)
                case['state'] = {'deadline':datetime(2026, 1, 1, tzinfo=timezone.utc)}
        replies = [(b'\x00\x00' * 2400, {'status':'passed'}),
                   (json.dumps({'results':{'channels':[{'alternatives':[{'transcript':'Tôi chưa làm.'}]}]}}).encode(), {'status':'passed'})] * 3
        replies += [(body, {'status':'passed'})] * 2
        with tempfile.TemporaryDirectory() as folder, patch.dict('sys.modules', {'livekit.plugins':plugins}), patch('backend.ai_verify_live.request', new=AsyncMock(side_effect=replies)):
            result = asyncio.run(probe(config, Path(folder), fixtures))
            self.assertEqual(result['status'], 'failed')
            for row in result['llm']:
                self.assertEqual(row['schema'], 'passed')
                self.assertEqual(row['comparison']['actual']['action'], 'wrap')
                self.assertFalse(row['comparison']['passed'])
                self.assertEqual(row['policy'], 'rejected')
            self.assertEqual(json.loads((Path(folder) / 'providers.json').read_text())['llm'][0]['comparison']['input']['now'], '2026-01-02T00:00:00+00:00')

    def test_default_cli_and_docs(self):
        """Forbid live/config calls by default and check manifest and document links."""
        import contextlib
        import io
        import json
        import re
        from backend.ai_verify import main, ROOT
        with tempfile.TemporaryDirectory() as folder, patch('sys.argv', ['ai_verify', '--output-dir', str(Path(folder) / 'run')]), patch('backend.ai_verify.live', side_effect=AssertionError('must stay offline')), patch('backend.config.load_config', side_effect=AssertionError('no env')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 0)
            manifest = json.loads((Path(folder) / 'run/manifest.json').read_text())
            self.assertFalse(manifest['live_requested'])
            self.assertEqual(manifest['offline']['passed'], 20)
            from backend.ai_verify import sha
            self.assertEqual(manifest['source_checksums']['backend/controller.py'], sha(ROOT / 'backend/controller.py'))
            self.assertIn('sdk_versions', manifest)
            self.assertEqual(manifest['configuration']['offline_defaults']['deepgram_model'], 'nova-3')
            self.assertNotIn('google_api_key', str(manifest['configuration']))
            self.assertTrue((Path(folder) / 'run/listening-review.md').exists())
        for name in ('docs/ai/verification.md', 'docs/ai/verification-results.md', 'docs/planning/validation-plan.md'):
            path = ROOT / name
            text = path.read_text()
            self.assertEqual(sum(line.startswith('```') for line in text.splitlines()) % 2, 0)
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if not link.startswith(('http:', 'https:', '#')):
                    self.assertTrue((path.parent / link.split('#')[0]).exists(), (name, link))


if __name__ == '__main__':
    unittest.main()
