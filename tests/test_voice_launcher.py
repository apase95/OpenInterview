# %%
"""Check voice supervisor readiness and cleanup with mocked child processes.

HTTP readiness, spawning and process-group signals are replaced. These tests
check command ownership and web environment filtering, not live voice startup.
"""
import importlib.util
from pathlib import Path
import signal
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('voice_launcher', Path(__file__).resolve().parents[1] / 'scripts/voice_test.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


# %%
class LauncherTests(unittest.TestCase):
    """Check early exits, occupied ports and forced cleanup of owned groups."""
    def test_ready_and_early_exit(self):
        """Require a live fake child even when the readiness probe reports success."""
        child = Mock(pid=123)
        child.poll.return_value = None
        with patch.object(launcher.time, 'sleep'), patch.object(launcher, 'http_ready', return_value=True):
            launcher.wait_ready([('api', child)], lambda: launcher.http_ready('unused'), timeout=1)
            child.poll.return_value = 1
            with self.assertRaisesRegex(RuntimeError, 'api exited'):
                launcher.wait_ready([('api', child)], lambda: True, timeout=1)

    def test_occupied_port_never_spawns(self):
        """Reject a busy port without creating any child process."""
        with patch.object(launcher, 'preflight'), patch.object(launcher, 'check_ports', side_effect=RuntimeError('occupied')), patch.object(launcher.subprocess, 'Popen') as spawn:
            self.assertEqual(launcher.main(), 1)
            spawn.assert_not_called()

    def test_partial_interrupt_cleans_owned_groups(self):
        """Inspect mocked TERM/KILL signals after interrupted partial startup."""
        child = Mock(pid=123)
        with patch.object(launcher, 'preflight', return_value=Path('/fake/python')), patch.object(launcher, 'check_ports'), patch.object(launcher.subprocess, 'Popen', return_value=child), patch.object(launcher, 'wait_ready', side_effect=KeyboardInterrupt), patch.object(launcher.os, 'killpg') as kill:
            self.assertEqual(launcher.main(), 130)
            self.assertEqual(kill.call_args_list[0].args, (123, signal.SIGTERM))
            self.assertEqual(kill.call_args_list[-1].args, (123, signal.SIGKILL))

    def test_timeout_and_descendants_of_exited_leader(self):
        """Clean groups even after leader exit and reject readiness timeout."""
        child = Mock(pid=456)
        child.poll.return_value = 0
        with patch.object(launcher.os, 'killpg') as kill:
            launcher.cleanup([('worker', child)])
            self.assertEqual([c.args for c in kill.call_args_list], [(456, signal.SIGTERM), (456, signal.SIGKILL)])
        child.poll.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'Timed out'):
            launcher.wait_ready([('worker', child)], lambda: False, timeout=0)

    def test_frontend_environment_allowlist(self):
        """Exclude provider secrets and unsafe inherited options from the web child."""
        with patch.dict(launcher.os.environ, {'GOOGLE_API_KEY': 'private', 'NODE_OPTIONS': 'private', 'NEXT_PUBLIC_SECRET': 'private'}):
            self.assertFalse(set(launcher.web_env()) & {'GOOGLE_API_KEY', 'NODE_OPTIONS', 'NEXT_PUBLIC_SECRET'})

    def test_all_owned_groups_get_forced_fallback(self):
        """Require reverse-order TERM then KILL for every unresponsive fake group."""
        children = [('api', Mock(pid=111)), ('worker', Mock(pid=222)), ('web', Mock(pid=333))]
        for _, child in children:
            child.wait.side_effect = launcher.subprocess.TimeoutExpired('fake', 0)
        with patch.object(launcher.os, 'killpg') as kill:
            launcher.cleanup(children)
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(pid, sig) for sig in (signal.SIGTERM, signal.SIGKILL) for pid in (333, 222, 111)])
