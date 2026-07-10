"""
Small in-process rate limiter used to cap how often we hit the Groq API.
Sliding-window counter, thread-safe. Not distributed -- if you scale this
app to multiple processes/replicas, move this to Redis instead.
"""

import threading
import time
from collections import deque


class GroqRateLimitError(RuntimeError):
    """Raised when the local Groq call budget is exhausted."""


class SlidingWindowRateLimiter:
    def __init__(self, max_calls: int, period_seconds: float):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Raise GroqRateLimitError if the call budget for this window is used up."""
        with self._lock:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > self.period_seconds:
                self._calls.popleft()

            if len(self._calls) >= self.max_calls:
                retry_after = self.period_seconds - (now - self._calls[0])
                raise GroqRateLimitError(
                    f"Groq call budget exceeded ({self.max_calls} calls / "
                    f"{self.period_seconds:.0f}s). Retry in {max(retry_after, 0):.1f}s."
                )

            self._calls.append(now)
