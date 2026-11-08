# %%
"""Check config validation, in-process health and idle worker lifecycle.

Credentials are synthetic and dotenv loading is mocked. The worker check starts
a real local scaffold subprocess, not a provider-connected voice worker.
"""
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

FAKE = {name: 'synthetic-safe-value' for name in (
    'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET',
    'GOOGLE_API_KEY', 'DEEPGRAM_API_KEY', 'ELEVEN_API_KEY')}
FAKE['LIVEKIT_URL'] = 'wss://synthetic.invalid'


# %%
class BackendTests(unittest.TestCase):
    """Check safe defaults, secret handling and local worker shutdown."""
    def test_config(self):
        """Validate synthetic settings and redaction without reading a dotenv file."""
        from backend.config import load_config
        with patch.dict(os.environ, FAKE, clear=True):
            config = load_config(load_file=False)
            self.assertEqual(config.gemini_controller_model, 'gemini-3.5-flash-lite')
            self.assertNotIn('synthetic-safe-value', repr(config))
        for value in ('', 'sk_xxxxxxxxxxxxxxxxx'):
            with patch.dict(os.environ, {**FAKE, 'GOOGLE_API_KEY': value}, clear=True):
                with self.assertRaisesRegex(ValueError, '^Invalid or missing: GOOGLE_API_KEY$'):
                    load_config(load_file=False)
        with patch.dict(os.environ, FAKE, clear=True), patch('dotenv.load_dotenv') as loader:
            load_config()
            loader.assert_called_once_with(Path(__file__).resolve().parents[1] / '.env', override=False)

    def test_health_without_credentials(self):
        """Require in-process liveness to work without provider credentials."""
        from fastapi.testclient import TestClient
        from backend.api import app
        with patch.dict(os.environ, {}, clear=True):
            response = TestClient(app).get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'service': 'api'})

    def test_worker(self):
        """Check local worker config exits, idle startup and SIGTERM cleanup."""
        command = [sys.executable, '-m', 'backend.worker', '--no-env-file']
        env = {**os.environ, **FAKE}
        checked = subprocess.run(command + ['--check-config'], env=env, capture_output=True, text=True, timeout=2)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        rejected = subprocess.run(command + ['--check-config'], env={**env, 'GOOGLE_API_KEY': 'xxxx-PRIVATE_SENTINEL'}, capture_output=True, text=True, timeout=2)
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(rejected.stderr.strip(), 'Invalid or missing: GOOGLE_API_KEY')
        self.assertNotIn('PRIVATE_SENTINEL', rejected.stdout + rejected.stderr)
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 2)[0], 'Worker startup timed out')
            self.assertEqual(process.stdout.readline().strip(), 'Worker scaffold ready; idle (no jobs processed).')
            process.send_signal(signal.SIGTERM)
            output, errors = process.communicate(timeout=2)
            self.assertEqual(process.returncode, 0, errors)
            self.assertIn('Worker stopped.', output)
            self.assertNotIn('synthetic-safe-value', output + errors)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
