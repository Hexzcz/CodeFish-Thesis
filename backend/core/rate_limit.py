"""A small sliding-window rate limiter.

Two things in this app need one for different reasons: Nominatim asks callers
not to hammer it, and /route runs Dijkstra, Yen's k-shortest-paths and XGBoost
inference across every edge — one script can saturate the server, and during a
flood that is the endpoint that must stay up.

It lives in `core` because both an adapter and the API layer use it, and an
adapter may not import the API.

Deliberately in-memory and per-process. Behind several workers each gets its
own allowance, so the effective limit is the configured one times the number of
workers. That is fine for what this defends against — an accident or a single
script — and a shared limiter would mean Redis, which this app does not have
and should not grow for this.
"""
import time
from collections import defaultdict
from typing import Dict, List


class RateLimiter:
    """Allows `max_requests` per `window_seconds` for each caller."""

    def __init__(self, max_requests: int, window_seconds: float, name: str = ""):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self._seen: Dict[str, List[float]] = defaultdict(list)

    def allows(self, key: str) -> bool:
        """Record a request from `key` and say whether it is within the limit."""
        now = time.time()
        recent = [t for t in self._seen[key] if now - t < self.window_seconds]

        if len(recent) >= self.max_requests:
            self._seen[key] = recent
            return False

        recent.append(now)
        self._seen[key] = recent
        return True

    def retry_after(self, key: str) -> int:
        """Whole seconds until `key` may try again. Never less than one."""
        recent = self._seen.get(key) or []
        if len(recent) < self.max_requests:
            return 1
        oldest = min(recent)
        return max(1, int(self.window_seconds - (time.time() - oldest)) + 1)

    def forget(self, key: str) -> None:
        """Drop a caller's history. Used by tests; harmless in production."""
        self._seen.pop(key, None)
