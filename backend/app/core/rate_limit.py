import time
from collections import defaultdict, deque


class FailureRateLimiter:
    """In-memory sliding-window limiter for failed attempts (single process; use Redis when scaling out)."""

    def __init__(self, max_failures: int, window_seconds: int, clock=time.monotonic):
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        events = self._failures[key]
        cutoff = self._clock() - self._window
        while events and events[0] < cutoff:
            events.popleft()
        return events

    def retry_after(self, key: str) -> int:
        """Seconds until another attempt is allowed; 0 when not blocked."""
        events = self._prune(key)
        if len(events) < self._max:
            return 0
        return max(1, int(events[0] + self._window - self._clock()))

    def record_failure(self, key: str) -> None:
        self._prune(key).append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
