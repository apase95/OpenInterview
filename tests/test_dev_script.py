# %%
"""Check development shell command dispatch with fake Docker/Python binaries.

The real shell script runs in a temporary path containing spaces. Recorded
arguments prove dispatch and quoting, not Docker or test-suite success.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


# %%
class DevScriptTests(unittest.TestCase):
    """Check help, argument rejection, compose commands and interpreter selection."""
    def test_commands(self):
        """Record fake executable calls and compare exact supported command arguments."""
        source = Path(__file__).resolve().parents[1] / 'scripts/dev.sh'
        self.assertTrue(source.is_file(), 'scripts/dev.sh must exist')
        with tempfile.TemporaryDirectory(prefix='contributor space ') as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            shutil.copyfile(source, root / 'scripts/dev.sh')
            (root / 'docker-compose.yml').write_text('services: {}\n')
            binary = root / 'bin'
            binary.mkdir()
            record = root / 'calls.jsonl'
            fake = '#!' + shutil.which('python3') + '\nimport json, os, sys\nwith open(os.environ["RECORD"], "a") as f: f.write(json.dumps(sys.argv[1:]) + "\\n")\n'
            for name in ('docker', 'python3'):
                target = binary / name
                target.write_text(fake)
                target.chmod(0o755)
            env = {'PATH': str(binary) + os.pathsep + os.defpath, 'RECORD': str(record)}

            def run(*args, code=0):
                record.write_text('')
                result = subprocess.run(['bash', str(root / 'scripts/dev.sh'), *args],
                                        cwd='/', env=env, capture_output=True, text=True, timeout=2)
                self.assertEqual(result.returncode, code, result.stderr)
                return [json.loads(line) for line in record.read_text().splitlines()]

            self.assertEqual(run(), [])
            self.assertEqual(run('help'), [])
            for args in (('oops',), ('stop', '-v'), ('logs', '--help'), ('logs', 'web', 'api'), ('test', 'extra')):
                self.assertEqual(run(*args, code=2), [])
            self.assertEqual(run('start', code=1), [])
            self.assertEqual(run('test'), [['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py']])
            self.assertEqual(run('verify')[-1], [str(root / 'tests/verify_compose.py')])
            (root / '.env.docker').write_text('SYNTHETIC=only\n')
            prefix = ['compose', '--project-directory', str(root), '--env-file', str(root / '.env.docker'), '-f', str(root / 'docker-compose.yml')]
            for command, expected in (
                ('build', ['build']), ('start', ['up', '-d', '--build', '--wait', '--wait-timeout', '120']),
                ('stop', ['down']), ('restart', ['up', '-d', '--build', '--force-recreate', '--wait', '--wait-timeout', '120']),
                ('status', ['ps']), ('logs', ['logs', '-f', '--tail', '100'])):
                with self.subTest(command=command):
                    calls = run(command)
                    self.assertEqual(calls, [['compose', 'version'], ['info'], prefix + expected])
            for service in ('web', 'api', 'worker', 'postgres'):
                self.assertEqual(run('logs', service)[-1], prefix + ['logs', '-f', '--tail', '100', service])
            venv = root / '.venv/bin'
            venv.mkdir(parents=True)
            shutil.copyfile(binary / 'python3', venv / 'python')
            (venv / 'python').chmod(0o755)
            self.assertEqual(run('test'), [['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py']])
