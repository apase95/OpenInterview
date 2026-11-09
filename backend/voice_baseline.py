# %%
"""Opt-in synthetic audio probe. No room, VAD, browser or endpointing measurement.

Default execution prints an offline plan and makes no provider requests.
With --live, three sequential cases allow at most 12 requests, no retries and
60 seconds per case. Audio/text limits bound output, not provider charges.
Measured SDK stages do not establish intelligibility or end-to-end latency.
"""
import argparse
import asyncio
import json
import logging
import time
import uuid
import wave
from pathlib import Path

from backend.voice_latency import stats

# %%
CASES = (
    ('name', 'synthetic_name', 'Tên tôi là Nguyễn An.'),
    ('numbers', 'synthetic_numbers', 'Tôi có ba năm kinh nghiệm và có thể bắt đầu lúc chín giờ.'),
    ('negation', 'synthetic_negation', 'Tôi không thể làm việc vào Chủ nhật.'),
)
LIMITS = {'cases': 3, 'requests': 12, 'case_timeout_seconds': 60,
          'retries': 0, 'audio_seconds_per_clip': 15, 'audio_bytes_per_clip': 2_000_000,
          'reply_characters': 800}
UNAVAILABLE = ['speech_end', 'endpointing', 'barge_in', 'mouth_to_ear', 'browser_playback']


# %%
async def collect_audio(stream, *, byte_limit=2_000_000, seconds_limit=15):
    """Collect bounded, format-consistent frames and close the supplied SDK stream.

    First-frame time measures generated audio availability, not room playback.
    """
    start = time.monotonic()
    first = None
    frames = []
    size = 0
    seconds = 0
    async with stream:
        async for packet in stream:
            frame = packet.frame
            if first is None:
                first = time.monotonic() - start
            size += len(frame.data)
            seconds += frame.samples_per_channel / frame.sample_rate
            if size > byte_limit or seconds > seconds_limit:
                raise ValueError('audio_budget')
            if frames and (frame.sample_rate, frame.num_channels) != (frames[0].sample_rate, frames[0].num_channels):
                raise ValueError('audio_format')
            frames.append(frame)
    if not frames:
        raise ValueError('no_audio')
    return frames, {'first_audio_frame_seconds': first, 'completion_seconds': time.monotonic() - start,
                    'audio_file_seconds': seconds}


async def collect_text(stream):
    """Collect bounded nonempty text and time its first content chunk and completion."""
    start = time.monotonic()
    first = None
    text = ''
    async with stream:
        async for chunk in stream:
            content = chunk.delta.content if chunk.delta else None
            if content:
                if first is None:
                    first = time.monotonic() - start
                text += content
                if len(text) > LIMITS['reply_characters']:
                    raise ValueError('text_budget')
    if not text.strip():
        raise ValueError('no_text')
    return text, {'first_text_chunk_seconds': first, 'completion_seconds': time.monotonic() - start}


# %%
async def probe(config, output):
    """Run generated audio through batch STT, LLM and reply TTS, then close providers.

    Transcripts and replies feed later stages but are not saved in the summary.
    Source WAVs are synthetic. A measured status means stages completed, not
    that the words were correct or the reply was heard by a person.
    """
    from livekit.agents import APIConnectOptions, llm
    from livekit.plugins import deepgram, elevenlabs, google
    options = APIConnectOptions(max_retry=0, timeout=20)
    voice = {'voice_id': config.elevenlabs_voice_id} if config.elevenlabs_voice_id else {}
    stt = deepgram.STT(model=config.deepgram_model, language=config.deepgram_language,
                       api_key=config.deepgram_api_key, mip_opt_out=True)
    model = google.LLM(model=config.gemini_controller_model, api_key=config.google_api_key)
    tts = elevenlabs.TTS(model=config.elevenlabs_model, api_key=config.eleven_api_key,
                        enable_logging=False, **voice)
    report = offline_report()
    report.update(mode='live', status='incomplete', attempts=0, cases=[], configured={
        'stt_model': config.deepgram_model, 'stt_language': config.deepgram_language,
        'llm_model': config.gemini_controller_model, 'tts_model': config.elevenlabs_model})
    def checkpoint():
        (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    try:
        for case_id, source, text in CASES:
            row = {'id': case_id, 'source': source, 'status': 'incomplete'}
            report['cases'].append(row)
            stage = 'source_tts'
            try:
                async with asyncio.timeout(LIMITS['case_timeout_seconds']):
                    report['attempts'] += 1
                    frames, row[stage] = await collect_audio(tts.synthesize(text, conn_options=options))
                    with wave.open(str(output / (case_id + '.wav')), 'wb') as wav:
                        wav.setnchannels(frames[0].num_channels)
                        wav.setsampwidth(2)
                        wav.setframerate(frames[0].sample_rate)
                        wav.writeframes(b''.join(bytes(f.data) for f in frames))
                    stage = 'batch_stt'
                    report['attempts'] += 1
                    start = time.monotonic()
                    transcript = await stt.recognize(frames, conn_options=options)
                    row[stage] = {'request_seconds': time.monotonic() - start}
                    if not transcript.alternatives or not transcript.alternatives[0].text.strip():
                        raise ValueError('no_transcript')
                    stage = 'llm_stream'
                    context = llm.ChatContext()
                    context.add_message(role='system', content='Trả lời bằng một câu tiếng Việt ngắn, tối đa 30 từ.')
                    context.add_message(role='user', content=transcript.alternatives[0].text)
                    report['attempts'] += 1
                    reply, row[stage] = await collect_text(model.chat(chat_ctx=context, conn_options=options))
                    stage = 'reply_tts_stream'
                    report['attempts'] += 1
                    _, row[stage] = await collect_audio(tts.synthesize(reply, conn_options=options))
                    row['status'] = 'measured'
            except Exception:
                row.update(status='failed', failed_stage=stage, error='timeout_budget_or_provider_failure')
            checkpoint()
        aggregates = {}
        for row in report['cases']:
            for stage in ('source_tts', 'batch_stt', 'llm_stream', 'reply_tts_stream'):
                for key, value in row.get(stage, {}).items():
                    aggregates.setdefault(stage + '.' + key, []).append(value)
        report['stages'] = {key: stats(values) for key, values in aggregates.items()}
        report['failures'] = sum(row['status'] == 'failed' for row in report['cases'])
        report['status'] = 'measured' if not report['failures'] else 'incomplete'
    finally:
        for provider in (stt, model, tts):
            try:
                await asyncio.wait_for(provider.aclose(), 5)
            except Exception:
                report['status'] = 'incomplete'
        checkpoint()
    return report


# %%
def offline_report():
    """Describe limits and unavailable observations without loading voice providers."""
    return {'mode': 'offline', 'status': 'not_run', 'limits': LIMITS,
            'transport': 'SDK plugins: generated audio -> batch STT -> streaming LLM -> streaming TTS; sequential stages',
            'cases': [{'id': key, 'source': source, 'text': text, 'status': 'not_run'} for key, source, text in CASES],
            'unavailable': UNAVAILABLE, 'stages': {}}


def main():
    """Keep live configuration and artifact creation behind the explicit cost opt-in."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if not args.live:
        print(json.dumps(offline_report(), ensure_ascii=False, sort_keys=True, indent=2))
        return
    print('COST WARNING: opt-in provider calls, maximum 12 requests, 3 cases, 60s/case, no retries. '
          'Audio/output limits are not billing caps. Failed requests may cost money.', flush=True)
    logging.disable(logging.CRITICAL)
    output = Path('artifacts/ai') / ('audio-baseline-' + uuid.uuid4().hex)
    output.mkdir(parents=True)
    try:
        from backend.config import load_config
        report = asyncio.run(probe(load_config(), output))
    except Exception:
        report = {**offline_report(), 'mode': 'live', 'status': 'incomplete',
                  'error': 'configuration_or_setup_failure'}
        (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Baseline ' + report['status'] + '; report: ' + str(output / 'summary.json'))
    if report['status'] != 'measured':
        raise SystemExit(1)


# %%
if __name__ == '__main__':
    main()
