import importlib.util
from pathlib import Path
import socket
import sys
import unittest

spec = importlib.util.spec_from_file_location('verify_local', Path(__file__).with_name('verify_local.py'))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class StartupTests(unittest.TestCase):
    def test_owned_server_and_cleanup(self):
        port = verify.available_port()
        command = [sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1']
        self.assertIn('Directory listing', verify.get_started(command, Path(__file__).parent, f'http://127.0.0.1:{port}/'))
        with socket.socket() as probe:
            self.assertNotEqual(probe.connect_ex(('127.0.0.1', port)), 0)

    def test_exited_child_cannot_pass_existing_response(self):
        # A slow HTTP response must not hide a child exiting after the initial poll.
        from unittest.mock import patch
        class Response:
            status = 200
            def __enter__(self):
                import time
                time.sleep(0.1)
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return b'unrelated server'
        with patch.object(verify.urllib.request, 'urlopen', return_value=Response()):
            with self.assertRaisesRegex(AssertionError, 'Server exited'):
                verify.get_started([sys.executable, '-c', 'pass'], Path(__file__).parent, 'http://127.0.0.1:1/')
