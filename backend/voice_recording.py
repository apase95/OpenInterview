# %%
"""Private, bounded local evidence. Never enable SDK/cloud recording.

SDK RecorderAudioOutput supplies room-sink progress slicing and event forwarding;
we use its wrapper only, not RecorderIO or its encoder/upload lifecycle.
Consent/configuration must agree before capture. Local files contain private
audio, transcripts and filtered text context, not anonymous metrics alone.
Generated text and room-sink estimates never prove browser or ear playback.
"""
import asyncio
from contextlib import ExitStack
import fcntl
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid
import wave
from backend.voice_diagnostics import Diagnostics, RETRY_POLICY

# %%
MODE = 'local-pipeline-v1'
SECONDS = 600
RATE = 16000
RAW_LIMIT = 128 * 1024 * 1024
RESERVATION = 256 * 1024 * 1024
STORAGE_LIMIT = 1024 * 1024 * 1024
FRAME_LIMIT = 120000


# %%
def approved(lease):
    """Fail closed unless lease recording mode agrees with the server opt-in."""
    mode = lease.get('recording', False)
    enabled = os.getenv('LOCAL_VOICE_RECORDING') == 'true'
    if (mode is not False and mode != MODE) or (mode == MODE) != enabled:
        raise ValueError('Recording configuration mismatch')
    return mode == MODE


def private_file(path, mode='wb'):
    """Create an exclusive owner-only file without following a final symlink."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    return os.fdopen(fd, mode)


# %%
class Capture:
    """Own private capture files, a bounded queue and one background writer.

    Duration, storage, frame and event limits stop the session on failure rather
    than silently continuing unrecorded. The pinned SDK wrapper is required.
    """
    def __init__(self, root, config, stop):
        if version('livekit-agents') != '1.8.11':
            raise RuntimeError('Unverified recording SDK')
        self.started = time.monotonic()
        self.loop = asyncio.get_running_loop()
        self.ready = asyncio.Event()
        self.stop = stop
        self.failure = None
        self.failure_event = None
        self.closed = False
        self.ids = {}
        self.total = 0
        self.event_bytes = 0
        self.frame_count = 0
        self.diagnostics = Diagnostics()
        self.q = queue.Queue(maxsize=128)
        self.manifest = {
            'schema_version': 1, 'mode': MODE, 'config': config,
            'sdk': {name: version(name) for name in ('livekit-agents', 'livekit',
                'livekit-plugins-deepgram', 'livekit-plugins-google', 'livekit-plugins-elevenlabs')},
            'clock': 'worker monotonic relative seconds',
            'input': 'exact frames entering Agent.default.stt_node, arrival minus frame duration; not provider receipt',
            'output': 'room-output submission attempts (including cancelled capture); replay uses room sink progress/pacing estimate, not browser or ear playback',
            'replay': '16kHz PCM16 stereo: left STT input, right room-output estimate; gaps and overlaps preserved',
            'resampling': 'channel mean then linear interpolation for debug replay; raw PCM preserved',
            'spoken_text': 'unavailable', 'context_filter': 'only message role and string content; excludes tools, metadata, nontext and reasoning',
            'limits': {'seconds': SECONDS, 'raw_bytes': RAW_LIMIT, 'queue_frames': 128,
                       'frame_bytes': 262144, 'frames': FRAME_LIMIT, 'event_bytes': 1024 * 1024,
                       'owned_storage_bytes': STORAGE_LIMIT, 'reservation_bytes': RESERVATION},
            'status': 'incomplete', 'unsettled_output': False,
            'retry_policy': RETRY_POLICY,
        }
        root.mkdir(parents=True, exist_ok=True)
        # A fixed accounting slot remains after close. Four owned captures max;
        # no deletion, and no reading unrelated artifacts or interview content.
        lock_fd = os.open(root / '.voice-capture.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(lock_fd, 'rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            owned = [p for p in root.iterdir() if re.fullmatch(r'voice-capture-[0-9a-f]{32}', p.name)]
            if len(owned) * RESERVATION + RESERVATION > STORAGE_LIMIT:
                raise OSError('Local recording storage full')
            self.path = root / ('voice-capture-' + uuid.uuid4().hex)
            self.path.mkdir(mode=0o700)
            with private_file(self.path / 'reservation') as reserve:
                reserve.write(str(RESERVATION).encode())
        self.manifest['session_id'] = self.path.name
        # Open synchronously before allowing a consented session to run.
        self.stack = ExitStack()
        try:
            self.events = self.stack.enter_context(private_file(self.path / 'events.jsonl'))
            self.raw = {name: self.stack.enter_context(private_file(self.path / (name + '.pcm')))
                        for name in ('input', 'submitted', 'output')}
            self.manifest_file = self.stack.enter_context(private_file(self.path / 'manifest.json'))
            self.manifest_file.write(json.dumps(self.manifest).encode())
            self.manifest_file.flush()
        except BaseException:
            self.stack.close()
            raise
        self.thread = threading.Thread(target=self._write, name='local-voice-capture', daemon=True)
        self.thread.start()
        self.timer = self.loop.call_later(SECONDS, self.fail, 'duration_limit')

    @property
    def recording(self):
        return not self.closed and self.failure is None

    @property
    def _encoding(self):
        return self.recording

    def fail(self, status, **details):
        """Keep the first failure and schedule session stop safely from either thread."""
        if self.failure is None:
            self.failure_event = {'kind': 'capture_failure', 't': time.monotonic() - self.started,
                                  'reason': status, **details}
            self.failure = status
            self.loop.call_soon_threadsafe(self.stop)

    def turn(self, raw):
        if raw is None:
            return None
        if raw not in self.ids:
            if len(self.ids) >= 2048:
                self.fail('turn_limit')
                return None
            self.ids[raw] = len(self.ids) + 1
        return self.ids[raw]

    def put(self, item):
        """Queue without blocking the audio path; queue saturation stops capture."""
        if not self.recording:
            return
        try:
            self.q.put_nowait(item)
        except queue.Full:
            self.fail('queue_limit')

    def event(self, kind, **row):
        """Encode caller-selected evidence under the cumulative event-byte budget."""
        if not self.recording:
            return
        encoded = (json.dumps({'kind': kind, 't': time.monotonic() - self.started, **row}, ensure_ascii=False) + '\n').encode()
        self.event_bytes += len(encoded)
        if self.event_bytes > 1024 * 1024:
            self.fail('event_limit')
        else:
            self.put(('event', encoded))

    def audio(self, name, frame, start=None):
        """Validate PCM metadata and cumulative limits before copying bounded chunks.

        Input arrival minus duration is an estimate, not provider receipt time.
        Submitted audio records attempts, including later cancellation.
        """
        if not self.recording:
            return
        size = frame.data.nbytes
        details = dict(track=name, bytes=size, sample_rate=frame.sample_rate,
                       channels=frame.num_channels, samples=frame.samples_per_channel)
        if (any(type(value) is not int for value in
                (frame.sample_rate, frame.num_channels, frame.samples_per_channel))
                or not 8000 <= frame.sample_rate <= 96000
                or not 1 <= frame.num_channels <= 2
                or frame.samples_per_channel <= 0
                or size != frame.samples_per_channel * frame.num_channels * 2):
            self.fail('audio_format_limit', guard='metadata', **details)
            return
        if size > 262144 and name != 'output':
            self.fail('audio_frame_limit', guard='oversized', **details)
            return
        self.total += size
        self.frame_count += max(1, (size + 262143) // 262144)
        start = time.monotonic() - self.started - frame.duration if start is None else start
        if (self.total > RAW_LIMIT or self.frame_count > FRAME_LIMIT or not math.isfinite(start)
                or frame.duration > SECONDS or start + frame.duration > SECONDS):
            self.fail('audio_limit', **details)
            return
        # SDK progress joins ordinary submitted frames into multi-second segments.
        # Copy only bounded PCM16 sample-aligned queue items, not the entire segment.
        data = frame.data.cast('B')
        for offset in range(0, size, 262144):
            if not self.recording:
                break
            self.put(('audio', name, bytes(data[offset:offset + 262144]), frame.sample_rate,
                      frame.num_channels, start + offset / (2 * frame.num_channels * frame.sample_rate)))

    def _end_run(self, *, channel):
        self.event('output_segment_end')

    def output_position(self, started_at, frame):
        # SDK reports wall timestamps. Translate their age onto the worker clock.
        self.audio('output', frame, time.monotonic() - self.started - (time.time() - started_at))

    def attach(self, session):
        """Observe speech and sanitized errors; unrecoverable errors stop the session.

        Callbacks remain attached but event writes are gated by capture state.
        Observed errors do not establish how many SDK retries ran.
        """
        self.session = session
        def speech(event):
            handle = event.speech_handle
            turn = self.turn(handle.id)
            self.event('speech_created', turn=turn)
            handle.add_done_callback(lambda h: self.event('speech_done', turn=turn,
                interrupted=h.interrupted, spoken_text='unavailable'))
        session.on('speech_created', speech)
        def error(event):
            if self.closed:
                return
            row = self.diagnostics.observe(event)
            self.event('session_error', **row)
            if row['recoverable'] is False:
                self.fail('unrecoverable_session_error')
        session.on('error', error)
        session.on('close', lambda e: self.event('session_close'))

    # %%
    def _write(self):
        """Drain queued evidence, preserve raw PCM and build a debug replay/transcript.

        Replay mixes resampled input and room-output estimates, not submitted
        attempts. Text remains generated/unverified; all owned files close here.
        """
        try:
            import numpy as np
            tracks = np.zeros((SECONDS * RATE, 2), dtype=np.int16)
            through = 0
            offsets = dict.fromkeys(self.raw, 0)
            entries = []
            assistant = {}
            states = {}
            while (item := self.q.get()) is not None:
                if item[0] == 'event':
                    self.events.write(item[1])
                    row = json.loads(item[1])
                    kind, turn = row['kind'], row.get('turn')
                    if kind == 'final_stt':
                        alternatives = row.get('alternatives', [])
                        entries.append({'speaker': 'user', 'turn': None, 't': row['t'],
                            'state': 'final_stt', 'text': alternatives[0]['text'] if alternatives else row.get('text', ''),
                            'alternatives': alternatives})
                    elif kind == 'assistant_text':
                        # Unknown turn chunks stay separate rather than inventing a join.
                        if turn is None or turn not in assistant:
                            entry = {'speaker': 'assistant', 'turn': turn, 't': row['t'],
                                     'chunks': [], 'spoken_text': 'unavailable'}
                            entries.append(entry)
                            if turn is not None:
                                assistant[turn] = entry
                        else:
                            entry = assistant[turn]
                        entry['chunks'].append(row['text'])
                    elif kind == 'speech_done':
                        states[turn] = 'interrupted' if row['interrupted'] else 'done_unverified'
                    continue
                _, name, data, rate, channels, start = item
                self.raw[name].write(data)
                self.events.write((json.dumps({'kind': 'audio', 'track': name, 't': start,
                    'offset_bytes': offsets[name], 'bytes': len(data), 'sample_rate': rate,
                    'channels': channels, 'format': 's16le'}) + '\n').encode())
                offsets[name] += len(data)
                if name == 'submitted':
                    continue
                samples = np.frombuffer(data, dtype='<i2').reshape(-1, channels).mean(axis=1)
                count = round(len(samples) * RATE / rate)
                if not count:
                    continue
                mono = np.interp(np.arange(count) * rate / RATE, np.arange(len(samples)), samples)
                pos = round(start * RATE)
                lo, hi = max(pos, 0), min(pos + count, len(tracks))
                if hi > lo:
                    channel = 0 if name == 'input' else 1
                    summed = tracks[lo:hi, channel].astype(np.int32) + mono[lo-pos:hi-pos].astype(np.int32)
                    tracks[lo:hi, channel] = np.clip(summed, -32768, 32767)
                    through = max(through, hi)
            for name, channel in (('input.wav', 0), ('output.wav', 1), ('replay.wav', None)):
                with private_file(self.path / name) as target, wave.open(target, 'wb') as wav:
                    wav.setparams((2 if channel is None else 1, 2, RATE, 0, 'NONE', 'not compressed'))
                    data = tracks[:through] if channel is None else tracks[:through, channel]
                    wav.writeframes(data.astype('<i2').tobytes())
            for entry in entries:
                if entry['speaker'] == 'assistant':
                    entry['text'] = ''.join(entry['chunks'])
                    entry['state'] = states.get(entry['turn'], 'unsettled')
            with private_file(self.path / 'transcript.json') as target:
                target.write(json.dumps({'schema_version': 1,
                    'user_turn_mapping': 'unavailable; final STT segments in receipt order, alternatives/corrections retained',
                    'assistant_text': 'generated/submitted, not confirmed spoken',
                    'entries': entries}, ensure_ascii=False, indent=2).encode())
        except Exception:
            self.fail('write_failure')
        finally:
            try:
                # One reserved terminal record bypasses the stopped/full event queue.
                if self.failure_event is not None:
                    self.events.write((json.dumps(self.failure_event) + '\n').encode())
                self.events.write((json.dumps({'kind': 'capture_closed',
                    't': time.monotonic() - self.started, 'reason': self.failure or 'closed'}) + '\n').encode())
            except OSError:
                self.fail('write_failure')
            self.manifest['status'] = self.failure or 'closed'
            self.manifest['closure_reason'] = self.failure or 'closed'
            if self.failure_event is not None:
                self.manifest['failure'] = self.failure_event
            self.manifest['raw_bytes'] = self.total
            self.manifest['provider_errors'] = self.diagnostics.summary()
            try:
                self.manifest_file.seek(0)
                self.manifest_file.truncate()
                self.manifest_file.write(json.dumps(self.manifest, ensure_ascii=False, indent=2).encode())
            except OSError:
                self.fail('manifest_write_failure')
            try:
                self.stack.close()
            except OSError:
                self.fail('close_write_failure')

    async def aclose(self):
        """Stop admission and the timer, then drain/join the writer off the event loop."""
        if self.closed:
            return
        self.closed = True
        self.timer.cancel()
        # Off-loop even when a slow writer has filled the queue. A dead writer
        # must not leave close blocked on a queue nobody consumes.
        def finish():
            while self.thread.is_alive():
                try:
                    self.q.put(None, timeout=.05)
                    break
                except queue.Full:
                    pass
            self.thread.join()
        await asyncio.to_thread(finish)


# %%
def output_wrapper(capture, sink):
    """Wrap room output to record submissions and SDK sink-progress estimates.

    Playback callbacks describe the room sink only; browser receipt is unknown.
    """
    from livekit.agents.voice.recorder_io.recorder_io import RecorderAudioOutput
    class Output(RecorderAudioOutput):
        async def capture_frame(self, frame):
            # Bound the SDK wrapper's per-segment accumulator by our cumulative budget.
            capture.audio('submitted', frame)
            capture.manifest['unsettled_output'] = True
            try:
                await super().capture_frame(frame)
            except asyncio.CancelledError:
                capture.event('output_capture_cancelled')
                raise

        def on_playback_finished(self, **kwargs):
            capture.event('playback_finished', interrupted=kwargs['interrupted'],
                          playback_position=kwargs['playback_position'], spoken_text='unavailable')
            super().on_playback_finished(**kwargs)
            capture.manifest['unsettled_output'] = self._pending_playback_count > 0

    return Output(recording_io=capture, audio_output=sink, on_played=capture.output_position)


# %%
def recording_agent(capture, instructions):
    """Tee default agent stages without replacing their provider behavior.

    Save final STT alternatives, generated text and text-only context locally.
    Filtering omits tools/nontext metadata, not private words inside text.
    """
    from livekit.agents import Agent
    from livekit.agents import stt
    from livekit.agents.voice.agent_activity import _SpeechHandleContextVar
    def current_turn():
        # Pinned SDK context follows generation tasks, unlike current_speech
        # which can name another turn during preemptive generation.
        handle = _SpeechHandleContextVar.get(None)
        return capture.turn(handle.id if handle else None)
    class RecordedAgent(Agent):
        async def on_enter(self):
            try:
                if self.session.output.audio is None:
                    raise RuntimeError('Recording output unavailable')
                self.session.output.audio = output_wrapper(capture, self.session.output.audio)
                capture.output_attached = True
            except Exception:
                capture.fail('output_setup_failure')
                raise
            finally:
                capture.ready.set()

        async def stt_node(self, audio, model_settings):
            async def tee():
                async for frame in audio:
                    capture.audio('input', frame)
                    yield frame
            # Default returns an async iterable, not an awaited coroutine in this SDK.
            async for event in Agent.default.stt_node(self, tee(), model_settings):
                if not isinstance(event, str) and event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                    capture.event('final_stt', alternatives=[{'text': a.text, 'language': a.language}
                                                          for a in event.alternatives])
                yield event

        def llm_node(self, chat_ctx, tools, model_settings):
            messages = []
            filtered = 0
            for item in chat_ctx.items:
                if item.type != 'message' or item.role not in ('user', 'assistant', 'system', 'developer'):
                    filtered += 1
                    continue
                text = [part for part in item.content if isinstance(part, str)]
                filtered += len(item.content) - len(text)
                messages.append({'role': item.role, 'content': text})
            capture.event('llm_context', turn=current_turn(),
                          messages=messages, filtered_items=filtered, tools_omitted=len(tools))
            return Agent.default.llm_node(self, chat_ctx, tools, model_settings)

        async def transcription_node(self, text, model_settings):
            turn = current_turn()
            async for chunk in Agent.default.transcription_node(self, text, model_settings):
                if isinstance(chunk, str):
                    capture.event('assistant_text', turn=turn, text=chunk, spoken_text='unavailable')
                yield chunk

    return RecordedAgent(instructions=instructions)
