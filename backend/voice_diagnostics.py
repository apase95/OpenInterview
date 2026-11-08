"""Allowlisted provider evidence only. Never serialize an SDK event or exception."""
import asyncio
from collections import Counter

RETRY_POLICY = {'max_retry': 2, 'retry_interval': 1, 'timeout': 10}
COMPONENTS = {'llm_error': 'llm', 'stt_error': 'stt', 'tts_error': 'tts',
              'realtime_model_error': 'realtime'}


def field(value, name):
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def sanitize_error(event):
    nested = field(event, 'error')
    kind = field(nested, 'type')
    component = COMPONENTS.get(kind, 'unknown') if type(kind) is str else 'unknown'
    recoverable = field(nested, 'recoverable')
    error = field(nested, 'error')
    category, status, retryable = 'unknown', None, None
    # Lazy import keeps non-voice/offline paths free of SDK imports.
    from livekit.agents._exceptions import APIError, APITimeoutError, APIConnectionError, APIStatusError
    if isinstance(error, (APITimeoutError, TimeoutError)):
        category = 'timeout'
    elif isinstance(error, APIStatusError):
        category = 'http_status'
        code = field(error, 'status_code')
        status = code if type(code) is int and 100 <= code <= 599 else None
    elif isinstance(error, (APIConnectionError, ConnectionError)):
        category = 'connection'
    elif isinstance(error, APIError):
        category = 'api'
    elif isinstance(error, asyncio.CancelledError):
        category = 'cancelled'
    if isinstance(error, APIError):
        value = field(error, 'retryable')
        retryable = value if type(value) is bool else None
    return {'component': component, 'category': category, 'http_status': status,
            'recoverable': recoverable if type(recoverable) is bool else None,
            'retryable': retryable, 'retry_count': None,
            'retry_evidence': 'unavailable_in_sdk_event'}


class Diagnostics:
    def __init__(self, limit=2048):
        self.limit = limit
        self.total = 0
        self.dropped = 0
        self.counts = Counter()
        self.first = None

    def observe(self, event):
        row = sanitize_error(event)
        if self.total < self.limit:
            self.total += 1
            self.counts[tuple(row[k] for k in ('component', 'category', 'http_status', 'recoverable'))] += 1
            row['observed_error_index'] = self.total
            if self.first is None:
                self.first = row.copy()
        else:
            self.dropped = min(self.dropped + 1, 2147483647)
            row['observed_error_index'] = None
        return row

    def summary(self):
        return {'observed_errors': self.total, 'dropped': self.dropped, 'first_error': self.first,
                'counts': [dict(zip(('component', 'category', 'http_status', 'recoverable'), key), count=count)
                           for key, count in self.counts.items()]}
