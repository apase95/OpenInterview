"""Bounded, content-free SDK observations; never infer delivery success."""
import json
import math
import statistics
import time
import uuid
from collections import Counter
from pathlib import Path
from backend.voice_diagnostics import Diagnostics, RETRY_POLICY

FIELDS = {
    'llm_metrics': ('ttft', 'duration'),
    'tts_metrics': ('ttfb', 'duration', 'audio_duration'),
    'stt_metrics': ('duration', 'audio_duration', 'acquire_time'),
    'eou_metrics': ('end_of_utterance_delay', 'transcription_delay', 'on_user_turn_completed_delay'),
    'vad_metrics': ('inference_duration_total',),
}


def stats(values):
    values = sorted(values)
    return {'count': len(values), 'median': statistics.median(values),
            'p95': values[math.ceil(len(values) * .95) - 1]}


class Recorder:
    def __init__(self, root=Path('artifacts/ai'), limit=2048):
        self.path = root / ('voice-' + uuid.uuid4().hex)
        self.path.mkdir(parents=True)
        self.started = time.monotonic()
        self.limit = limit
        self.rows = []
        self.ids = {}
        self.dropped = 0
        self.finished = False
        self.diagnostics = Diagnostics(limit)

    def turn(self, raw):
        if not raw:
            return None
        if raw not in self.ids and len(self.ids) < self.limit:
            self.ids[raw] = len(self.ids) + 1
        return self.ids.get(raw)

    def emit(self, **row):
        if self.finished:
            return
        if len(self.rows) >= self.limit:
            self.dropped += 1
            return
        row['relative_seconds'] = round(time.monotonic() - self.started, 6)
        self.rows.append(row)

    def metric(self, event):
        metric = event.metrics
        kind = metric.type
        if kind not in FIELDS:
            self.emit(kind='unsupported_metric')
            return
        values = {}
        for field in FIELDS[kind]:
            value = getattr(metric, field, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                # Streaming STT duration is SDK's zero placeholder, not latency.
                if kind == 'stt_metrics' and field == 'duration' and getattr(metric, 'streamed', False):
                    continue
                values[field] = value
        self.emit(kind=kind, turn=self.turn(getattr(metric, 'speech_id', None)),
                  outcome='cancelled' if getattr(metric, 'cancelled', False) else 'observed', values=values)

    def speech(self, event):
        handle = event.speech_handle
        turn = self.turn(handle.id)
        self.emit(kind='speech_created', turn=turn)
        handle.add_done_callback(lambda speech: self.emit(kind='speech_done', turn=turn,
            outcome='interrupted' if speech.interrupted else 'done_unverified'))

    def attach(self, session):
        session.on('metrics_collected', self.metric)
        session.on('speech_created', self.speech)
        def error(event):
            if not self.finished:
                self.emit(kind='error', **self.diagnostics.observe(event))
        session.on('error', error)
        session.on('close', lambda event: self.emit(kind='close'))

    def finish(self):
        if self.finished:
            return
        self.finished = True
        stages = {}
        outcomes = Counter(row['outcome'] for row in self.rows if 'outcome' in row)
        excluded = {row['turn'] for row in self.rows if row.get('turn') is not None
                    and row.get('outcome') in ('interrupted', 'cancelled')}
        cohorts = {'first_measured_turn': {}, 'subsequent_measured_turns': {}}
        measured = sorted({r['turn'] for r in self.rows if r.get('values') and r.get('turn') is not None})
        missing = Counter()
        for row in self.rows:
            if row.get('outcome') == 'cancelled' or row.get('turn') in excluded:
                continue
            for field in FIELDS.get(row['kind'], ()):
                if field not in row.get('values', {}):
                    missing[row['kind'] + '.' + field] += 1
            for field, value in row.get('values', {}).items():
                key = row['kind'] + '.' + field
                stages.setdefault(key, []).append(value)
                if row.get('turn') is not None:
                    group = cohorts['first_measured_turn' if row['turn'] == measured[0] else 'subsequent_measured_turns']
                    group.setdefault(key, []).append(value)
        report = {'session_id': self.path.name, 'stages': {k: stats(v) for k, v in stages.items()},
                  'retry_policy': RETRY_POLICY, 'provider_errors': self.diagnostics.summary(),
                  'cohorts': {c: {k: stats(v) for k, v in fields.items()} for c, fields in cohorts.items()},
                  'outcomes': dict(outcomes), 'errors': sum(r['kind'] == 'error' for r in self.rows),
                  'missing_fields_on_observed_metrics': dict(missing),
                  'unobserved_metric_types': sorted(set(FIELDS) - {r['kind'] for r in self.rows}),
                  'dropped': self.dropped, 'mouth_to_ear': 'unavailable', 'browser_playback': 'unavailable'}
        try:
            (self.path / 'events.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
            (self.path / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        except OSError:
            print('Voice metrics write failed (details suppressed).', flush=True)
