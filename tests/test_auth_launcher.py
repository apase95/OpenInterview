"""Isolated auth supervisor smoke; no config, DB or provider access."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
spec = importlib.util.spec_from_file_location('auth_test', Path(__file__).resolve().parents[1] / 'scripts/auth_test.py')
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


class AuthLauncherTests(unittest.TestCase):
    def test_preflight_explicit_env_and_safe_failure(self):
        with patch.object(auth.os, 'access', return_value=True), patch.object(Path, 'is_file', return_value=True), \
                patch.object(auth.shutil, 'which', return_value='/fake/bin'), \
                patch.object(auth.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            auth.preflight()
            self.assertEqual(run.call_args.args[0][-3:], ['check', '--env-file', '.env'])
            run.return_value.returncode = 1
            with self.assertRaisesRegex(RuntimeError, 'Auth setup failed'):
                auth.preflight()

    def test_starts_only_api_and_isolated_web_and_cleans_owned_children(self):
        with patch.object(auth, 'check_ports'), patch.object(auth, 'preflight', return_value=Path('/fake/python')), \
                patch.object(auth.subprocess, 'Popen', side_effect=[Mock(), Mock()]) as spawn, \
                patch.object(auth, 'wait_ready'), patch.object(auth, 'alive', side_effect=KeyboardInterrupt), \
                patch.object(auth, 'cleanup') as cleanup:
            self.assertEqual(auth.main(), 130)
            commands = [call.args[0] for call in spawn.call_args_list]
            self.assertIn('backend.api:app', commands[0])
            self.assertEqual(spawn.call_args_list[0].kwargs['env']['LOCAL_VOICE_ENABLED'], 'false')
            self.assertEqual(commands[1][-2:], ['tests/verify_local.py', '--dev'])
            self.assertEqual(len(cleanup.call_args.args[0]), 2)
            self.assertNotIn('GOOGLE_OAUTH_CLIENT_SECRET', spawn.call_args_list[1].kwargs['env'])

    def test_busy_port_fails_without_starting_or_killing_external_process(self):
        with patch.object(auth, 'check_ports', side_effect=RuntimeError('Port 8000 unavailable')), \
                patch.object(auth, 'preflight') as preflight, patch.object(auth.subprocess, 'Popen') as spawn, \
                patch.object(auth, 'cleanup') as cleanup:
            self.assertEqual(auth.main(), 1)
            preflight.assert_not_called()
            spawn.assert_not_called()
            cleanup.assert_called_once_with([])

    def test_partial_startup_failure_cleans_api(self):
        with patch.object(auth, 'check_ports'), patch.object(auth, 'preflight', return_value=Path('/fake/python')), \
                patch.object(auth.subprocess, 'Popen', return_value=Mock()) as spawn, \
                patch.object(auth, 'wait_ready', side_effect=RuntimeError('Not ready')), \
                patch.object(auth, 'cleanup') as cleanup:
            self.assertEqual(auth.main(), 1)
            self.assertEqual(spawn.call_count, 1)
            self.assertEqual(len(cleanup.call_args.args[0]), 1)


if __name__ == '__main__':
    unittest.main()
