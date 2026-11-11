# %%
"""Check container-facing policies without starting Docker containers.

Database readiness uses a mocked connection; heartbeat checks use temporary
files. UI and planning checks inspect source text, not rendered browser output.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


# %%
class ContainerSmoke(unittest.TestCase):
    """Check service credential scope, health evidence and repository constraints."""
    def test_runtime_provider_policy(self):
        """Accept only the required provider variable names for each service."""
        from verify_compose import assert_provider_environment
        livekit = {'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET'}
        providers = livekit | {'GOOGLE_API_KEY', 'DEEPGRAM_API_KEY', 'ELEVEN_API_KEY'}
        for service, names in (('web', set()), ('api', livekit), ('worker', providers)):
            assert_provider_environment(service, names | {'PATH', 'DATABASE_PASSWORD', 'LOCAL_VOICE_SECRET', 'GPG_KEY'})
        for service, names in (('web', {'LIVEKIT_URL'}),
                               ('api', livekit | {'GOOGLE_API_KEY'}),
                               ('api', livekit | {'UNEXPECTED_API_SECRET'}),
                               ('api', livekit - {'LIVEKIT_API_SECRET'}),
                               ('worker', providers - {'DEEPGRAM_API_KEY'})):
            with self.subTest(service=service, names=names), self.assertRaises(AssertionError):
                assert_provider_environment(service, names)

    def test_readiness(self):
        """Mock DB success and failure to check readiness status and redaction."""
        from fastapi.testclient import TestClient
        from backend.api import app
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(TestClient(app).get('/ready').status_code, 503)
        with patch('backend.database.psycopg.connect') as connect, patch.dict(
                os.environ, {'DATABASE_HOST': 'db', 'DATABASE_PASSWORD': 'synthetic'}, clear=True):
            connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (1,)
            self.assertEqual(TestClient(app).get('/ready').status_code, 200)
            connect.side_effect = RuntimeError('password=PRIVATE_SENTINEL')
            response = TestClient(app).get('/ready')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('PRIVATE_SENTINEL', response.text)

    def test_heartbeat(self):
        """Accept a fresh local PID file and reject stale or malformed evidence."""
        from backend.healthcheck import healthy
        with tempfile.TemporaryDirectory() as directory:
            heartbeat = Path(directory) / 'heartbeat'
            heartbeat.write_text(str(os.getpid()))
            self.assertTrue(healthy(heartbeat))
            os.utime(heartbeat, (time.time() - 60,) * 2)
            self.assertFalse(healthy(heartbeat))
            heartbeat.write_text('not-a-pid')
            self.assertFalse(healthy(heartbeat))

    def test_home_scope(self):
        """Check selected page and CSS strings without claiming visual validation."""
        root = Path(__file__).resolve().parents[1]
        page = (root / 'app/page.tsx').read_text()
        self.assertIn('<Header', page)
        self.assertIn('AI leads a short interview. Recruiters review the evidence.', page)
        self.assertNotIn('#invitation', page)
        css = (root / 'app/globals.css').read_text()
        self.assertIn('@theme', css)
        self.assertNotIn('.demo-nav', css)
        for removed in ('className="badge"', 'AI is speaking', '>Example<', 'waveform'):
            self.assertNotIn(removed, page)
        self.assertTrue((root / 'app/globals.css').read_text().startswith('@import "tailwindcss";'))

    def test_planning_keeps_all_parent_tasks_open(self):
        """Require all 24 distinct parent tasks to remain unchecked in plan text."""
        import re
        root = Path(__file__).resolve().parents[1]
        plan = (root / 'docs/planning/sprint-plan.md').read_text()
        tasks = re.findall(r'^- \[([ x])\] \*\*(S\d-\d\d)', plan, re.MULTILINE)
        self.assertEqual(len(tasks), 24)
        self.assertEqual(len({task for _, task in tasks}), 24)
        self.assertTrue(all(state == ' ' for state, _ in tasks))
