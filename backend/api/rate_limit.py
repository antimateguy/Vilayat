"""A small in-memory rate limiter.

Sliding window per client: at most `limit` requests in any `window_seconds`.
The counts live in this process's memory, which is enough for one container and
needs no extra service. With several containers each would count separately.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

MAX_TRACKED_CLIENTS = 10_000


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}
        # Requests are handled on several threads at once.
        self._lock = threading.Lock()

    def check(self, client: str) -> float:
        """Count a request. Returns 0 if it is allowed, otherwise the number of
        seconds until the client may try again."""
        now = self._clock()
        with self._lock:
            times = self._requests.setdefault(client, deque())
            while times and now - times[0] >= self._window:
                times.popleft()
            if len(times) >= self._limit:
                return self._window - (now - times[0])
            times.append(now)
            if len(self._requests) > MAX_TRACKED_CLIENTS:
                self._forget_idle_clients(now)
            return 0.0

    def _forget_idle_clients(self, now: float) -> None:
        """Keep memory bounded when very many different clients have called."""
        idle = [
            client
            for client, times in self._requests.items()
            if not times or now - times[-1] >= self._window
        ]
        for client in idle:
            del self._requests[client]
