import argparse
import asyncio
import signal
import os

from backend.config import load_config
from backend.database import ping
from backend.healthcheck import HEARTBEAT


async def idle():
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)
    if os.getenv('DATABASE_HOST'):
        try:
            await asyncio.to_thread(ping)
        except Exception:
            raise SystemExit('Worker database unavailable') from None
    HEARTBEAT.write_text(str(os.getpid()))
    print('Worker scaffold ready; idle (no jobs processed).', flush=True)
    try:
        while not stopped.is_set():
            HEARTBEAT.touch()
            try:
                await asyncio.wait_for(stopped.wait(), timeout=5)
            except TimeoutError:
                pass
    finally:
        HEARTBEAT.unlink(missing_ok=True)
    print('Worker stopped.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-config', action='store_true')
    parser.add_argument('--no-env-file', action='store_true', help='Use environment only; do not read .env')
    args = parser.parse_args()
    try:
        load_config(load_file=not args.no_env_file)
    except ValueError as error:
        parser.exit(1, str(error) + '\n')
    if args.check_config:
        print('Worker configuration valid (no provider connections checked).')
    else:
        asyncio.run(idle())


if __name__ == '__main__':
    main()
