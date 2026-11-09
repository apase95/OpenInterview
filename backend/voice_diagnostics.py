# %%
"""Convert voice-provider failures into privacy-safe diagnostic evidence.

Latency metrics and consented recording share this module so their error records
use the same fields. SDK events are reduced to fixed categories and validated
scalar values before aggregation. This module does not write files or log data.

Exception messages, bodies, URLs, labels and request identifiers are deliberately
excluded. A recoverable error describes SDK policy, not proof that a retry ran.
"""
import asyncio
from collections import Counter


# %%
# The worker consumes this policy when constructing provider connection options.
# Retry interval and timeout are seconds. These configured values are separate
# from observed errors; SDK events do not expose an exact retry count.
RETRY_POLICY = {'max_retry': 2, 'retry_interval': 1, 'timeout': 10}
COMPONENTS = {'llm_error': 'llm', 'stt_error': 'stt', 'tts_error': 'tts',
              'realtime_model_error': 'realtime'}


# %%
# Read only named attributes. Missing fields and failing properties become unknown
# values rather than causing diagnostic extraction to fail at that attribute.
def field(value, name):
    """Return an attribute, or None if it is absent or raises an exception."""
    try:
        return getattr(value, name, None)
    except Exception:
        return None


# %%
# Normalize the SDK event without serializing the event, source or exception.
# Unknown types remain unknown; classification never relies on message contents.
def sanitize_error(event):
    """Return JSON-compatible error metadata with an explicitly unknown retry count.

    Component and category come from allowlists. HTTP status must be an integer
    from 100 through 599; recovery flags must be actual booleans. None means the
    evidence is unavailable, not that a status, retry or recovery did not occur.
    The LiveKit exception classes are imported only when this function is used.
    """
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


# %%
# Keep bounded session-local aggregates instead of retaining raw SDK objects.
# Each instance belongs to one observer, such as a metrics or capture recorder;
# it is not a global counter and does not provide cross-thread synchronization.
class Diagnostics:
    """Count sanitized events and retain the first admitted error for inspection.

    After the observation limit, aggregates stop growing and the dropped counter
    saturates at a fixed maximum. An observed error index is not a retry number.
    """

    def __init__(self, limit=2048):
        """Create an empty accumulator with a maximum admitted event count."""
        self.limit = limit
        self.total = 0
        self.dropped = 0
        self.counts = Counter()
        self.first = None

    def observe(self, event):
        """Sanitize one event and count it if capacity remains.

        The safe row is returned even at capacity, with no observation index.
        Callers remain responsible for bounding any downstream event storage.
        """
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
        """Return admitted counts, overflow count and first-error evidence.

        Counts are grouped by component, category, HTTP status and recoverability.
        This is diagnostic metadata, not a measure of successful recovery.
        """
        return {'observed_errors': self.total, 'dropped': self.dropped, 'first_error': self.first,
                'counts': [dict(zip(('component', 'category', 'http_status', 'recoverable'), key), count=count)
                           for key, count in self.counts.items()]}
