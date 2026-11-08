# %%
"""Run an idle worker scaffold or an explicitly selected local voice worker.

Voice mode uses paid providers with server-only configuration and bounded leases.
Metrics and private recording are separate opt-ins; SDK/cloud recording stays off.
This conversation test does not assess candidates or confirm browser playback.
"""
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


# %%
def voice_session(config):
    """Build the configured STT/LLM/TTS pipeline with VAD and shared retry policy.

    ElevenLabs logging is explicitly disabled and Deepgram opts out of MIP.
    Retry settings are policy, not observed retry counts or recovery guarantees.
    """
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


# %%
async def voice_job(ctx):
    """Validate a short local lease and bind audio to its named participant.

    Disable Python logging to avoid provider text in SDK logs. Optional metrics
    use safe allowlists; consented capture contains private text/audio instead.
    Cleanup closes the session before draining capture and freezing metrics.
    """
    import logging
    logging.disable(logging.CRITICAL)
    from livekit.agents import Agent, AutoSubscribe, room_io
    session = None
    recorder = None
    capture = None
    recording = False
    try:
        lease = json.loads(ctx.job.metadata)
        remaining = lease['deadline'] - time.time()
        if (lease.get('ended') or not 0 < remaining <= 600
                or not ctx.job.room.name.startswith('local_voice_')
                or not lease['identity'].startswith('participant_')):
            return
        from backend.voice_recording import approved
        recording = approved(lease)
        config = load_config(load_file=False)
        session = voice_session(config)
        if os.getenv('LOCAL_VOICE_METRICS') == 'true':
            from backend.voice_latency import Recorder
            try:
                recorder = Recorder()
                recorder.attach(session)
            except OSError:
                print('Voice metrics unavailable (details suppressed).', flush=True)
        stopped = asyncio.Event()
        if recording:
            from pathlib import Path
            from backend.voice_recording import Capture
            capture = Capture(Path('artifacts/ai'), {
                name: getattr(config, name) for name in ('deepgram_model', 'deepgram_language',
                    'gemini_controller_model', 'elevenlabs_model', 'elevenlabs_voice_id')}, stopped.set)
            capture.manifest['metrics_session_id'] = recorder.path.name if recorder else None
            capture.attach(session)
        # These callbacks stop the job; recoverable errors do not count retries.
        session.on('close', lambda event: stopped.set())
        session.on('error', lambda event: stopped.set() if not event.error.recoverable else None)
        ctx.add_shutdown_callback(session.aclose)
        async with asyncio.timeout(max(0, lease['deadline'] - time.time())):
            await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
            room_lease = json.loads(ctx.room.metadata)
            if room_lease.get('ended'):
                return
            if room_lease.get('recording', False) != lease.get('recording', False):
                raise ValueError('Recording lease mismatch')
            await asyncio.wait_for(ctx.wait_for_participant(identity=lease['identity']), timeout=min(30, remaining))
            instructions = (
                    'Bạn là trợ lý thử hội thoại tiếng Việt. Đây chỉ là thử nghiệm giọng nói, '
                    'không phải phỏng vấn hay đánh giá tuyển dụng. Trả lời ngắn gọn. '
                    'Không bịa chính sách nhân sự hoặc công ty. Không yêu cầu dữ liệu riêng tư.')
            if capture:
                from backend.voice_recording import recording_agent
                agent = recording_agent(capture, instructions)
            else:
                agent = Agent(instructions=instructions)
            await session.start(
                agent=agent,
                room=ctx.room, record=False,
                room_options=room_io.RoomOptions(participant_identity=lease['identity'],
                    audio_input=True, audio_output=True, video_input=False,
                    text_input=False, text_output=False, close_on_disconnect=True,
                    delete_room_on_close=False))
            if capture:
                await asyncio.wait_for(capture.ready.wait(), timeout=5)
                if not getattr(capture, 'output_attached', False) or capture.failure:
                    raise RuntimeError('Recording setup failed')
            session.say('Xin chào! Đây là phiên thử hội thoại tiếng Việt, không phải đánh giá tuyển dụng.',
                        allow_interruptions=True)
            await stopped.wait()
    except asyncio.CancelledError:
        if capture:
            capture.fail('job_cancelled')
        if recorder:
            recorder.emit(kind='job_cancelled')
        raise
    except Exception:
        if recording and capture is None:
            print('Local voice recording failed; session stopped (details suppressed).', flush=True)
        if capture:
            capture.fail('job_failure_or_timeout')
        if recorder:
            recorder.emit(kind='job_failure')
        print('Local voice session stopped (timeout or service failure).', flush=True)
    finally:
        # Session callbacks may still fire during close, before recorders finalize.
        if session:
            try:
                await asyncio.wait_for(session.aclose(), timeout=5)
            except Exception:
                if capture:
                    capture.fail('session_close_failure')
                pass
        if capture:
            await capture.aclose()
            if capture.failure:
                print('Local voice recording failed; session stopped (details suppressed).', flush=True)
        if recorder:
            recorder.finish()
        ctx.shutdown(reason='local voice session ended')


# %%
def voice_server():
    """Register the local test job; server connection retries are separate policy."""
    from livekit.agents import AgentServer
    from livekit.plugins import silero  # Register VAD download hook for download-files.
    server = AgentServer(max_retry=2, num_idle_processes=0)
    server.rtc_session(agent_name='local-voice-test')(voice_job)
    return server


# %%
async def idle():
    """Maintain a heartbeat until a stop signal; this scaffold processes no jobs."""
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


# %%
def main():
    """Select voice mode explicitly, otherwise validate config and run the scaffold.

    Configuration checks do not test providers. The voice wrapper preserves a
    failed exit status when the SDK CLI catches a server startup/run exception.
    """
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


# %%
if __name__ == '__main__':
    main()
