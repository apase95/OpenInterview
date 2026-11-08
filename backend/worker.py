import argparse
import asyncio
import signal
import os
import json
import sys
import time

from backend.config import load_config
from backend.database import ping
from backend.healthcheck import HEARTBEAT


def voice_session(config):
    from livekit.agents import AgentSession, APIConnectOptions, SessionConnectOptions
    from livekit.plugins import deepgram, google, elevenlabs, silero
    from backend.voice_diagnostics import RETRY_POLICY
    retry = APIConnectOptions(**RETRY_POLICY)
    voice = {'voice_id': config.elevenlabs_voice_id} if config.elevenlabs_voice_id else {}
    return AgentSession(
        stt=deepgram.STT(model=config.deepgram_model, language=config.deepgram_language,
                         api_key=config.deepgram_api_key, mip_opt_out=True),
        llm=google.LLM(model=config.gemini_controller_model, api_key=config.google_api_key),
        tts=elevenlabs.TTS(model=config.elevenlabs_model, api_key=config.eleven_api_key,
                           enable_logging=False, **voice),
        vad=silero.VAD.load(), turn_detection='vad', allow_interruptions=True,
        min_endpointing_delay=0.5, max_endpointing_delay=3,
        conn_options=SessionConnectOptions(stt_conn_options=retry, llm_conn_options=retry,
                                          tts_conn_options=retry, max_unrecoverable_errors=1))


async def voice_job(ctx):
    import logging
    logging.disable(logging.CRITICAL)
    from livekit.agents import Agent, AutoSubscribe, room_io
    session = None
    recorder = None
    try:
        lease = json.loads(ctx.job.metadata)
        remaining = lease['deadline'] - time.time()
        if (lease.get('ended') or not 0 < remaining <= 600
                or not ctx.job.room.name.startswith('local_voice_')
                or not lease['identity'].startswith('participant_')):
            return
        session = voice_session(load_config(load_file=False))
        if os.getenv('LOCAL_VOICE_METRICS') == 'true':
            from backend.voice_latency import Recorder
            try:
                recorder = Recorder()
                recorder.attach(session)
            except OSError:
                print('Voice metrics unavailable (details suppressed).', flush=True)
        stopped = asyncio.Event()
        session.on('close', lambda event: stopped.set())
        session.on('error', lambda event: stopped.set() if not event.error.recoverable else None)
        ctx.add_shutdown_callback(session.aclose)
        async with asyncio.timeout(max(0, lease['deadline'] - time.time())):
            await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
            if json.loads(ctx.room.metadata).get('ended'):
                return
            await asyncio.wait_for(ctx.wait_for_participant(identity=lease['identity']), timeout=min(30, remaining))
            await session.start(
                agent=Agent(instructions=(
                    'Bạn là trợ lý thử hội thoại tiếng Việt. Đây chỉ là thử nghiệm giọng nói, '
                    'không phải phỏng vấn hay đánh giá tuyển dụng. Trả lời ngắn gọn. '
                    'Không bịa chính sách nhân sự hoặc công ty. Không yêu cầu dữ liệu riêng tư.')),
                room=ctx.room, record=False,
                room_options=room_io.RoomOptions(participant_identity=lease['identity'],
                    audio_input=True, audio_output=True, video_input=False,
                    text_input=False, text_output=False, close_on_disconnect=True,
                    delete_room_on_close=False))
            session.say('Xin chào! Đây là phiên thử hội thoại tiếng Việt, không phải đánh giá tuyển dụng.',
                        allow_interruptions=True)
            await stopped.wait()
    except asyncio.CancelledError:
        if recorder:
            recorder.emit(kind='job_cancelled')
        raise
    except Exception:
        if recorder:
            recorder.emit(kind='job_failure')
        print('Local voice session stopped (timeout or service failure).', flush=True)
    finally:
        if session:
            try:
                await asyncio.wait_for(session.aclose(), timeout=5)
            except Exception:
                pass
        if recorder:
            recorder.finish()
        ctx.shutdown(reason='local voice session ended')


def voice_server():
    from livekit.agents import AgentServer
    from livekit.plugins import silero  # Register VAD download hook for download-files.
    server = AgentServer(max_retry=2, num_idle_processes=0)
    server.rtc_session(agent_name='local-voice-test')(voice_job)
    return server


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
    if '--voice' in sys.argv:
        import logging
        # SDK debug/error records can include provider text; no transcript logs in this mode.
        logging.disable(logging.CRITICAL)
        sys.argv.remove('--voice')
        no_file = '--no-env-file' in sys.argv
        if no_file:
            sys.argv.remove('--no-env-file')
        failed = False
        try:
            from livekit.agents import cli
            if '--help' not in sys.argv and 'download-files' not in sys.argv:
                load_config(load_file=not no_file)
            server = voice_server()
            run = server.run

            async def observed_run(*args, **kwargs):
                nonlocal failed
                try:
                    return await run(*args, **kwargs)
                except Exception:
                    # The SDK CLI catches this exception and otherwise exits zero.
                    failed = True
                    raise

            server.run = observed_run
            server.on('worker_registered', lambda *_: print(
                'Local voice worker registered; waiting for jobs.', flush=True))
            if 'start' in sys.argv and '--help' not in sys.argv:
                print('Local voice worker starting; registration pending.', flush=True)
            cli.run_app(server)
        except Exception:
            failed = True
        if failed:
            print('Local voice worker failed (configuration, startup or connection failure).',
                  file=sys.stderr, flush=True)
            raise SystemExit(1) from None
        return
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
