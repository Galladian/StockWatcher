"""Small in-memory rate limiting with no extra dependencies.

State lives in this process, so run a single uvicorn worker (the Dockerfile does) and expect the counters to
reset when the app restarts. That is fine for a personal project.
"""
import threading
import time
from collections import deque

_registry: list = []
_MAX_KEY_LENGTH = 200  # someone sending enormous usernames shouldn't be able to bloat memory


def client_ip(request) -> str:
    """The caller's address. Behind Caddy, uvicorn's --proxy-headers makes this the real visitor, not the proxy."""
    return request.client.host if request.client else "unknown"


class _Windowed:
    def __init__(self, limit: int, window: float, max_keys: int = 10_000, clock=time.monotonic):
        self.limit, self.window, self.max_keys, self._clock = limit, window, max_keys, clock
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()
        _registry.append(self)

    def _prune(self, key: str, now: float):
        dq = self._hits.get(key)
        if dq is None:
            return None
        while dq and dq[0] <= now - self.window:
            dq.popleft()
        if not dq:
            self._hits.pop(key, None)
            return None
        return dq

    def _add(self, key: str, now: float) -> None:
        self._hits.setdefault(key, deque()).append(now)
        if len(self._hits) > self.max_keys:
            for k in list(self._hits):
                self._prune(k, now)
            while len(self._hits) > self.max_keys:
                self._hits.pop(next(iter(self._hits)))

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class SlidingWindowLimiter(_Windowed):
    """Allow `limit` hits per `window` seconds for each key."""

    def hit(self, key: str) -> float:
        """0 if the request is allowed, otherwise the number of seconds to wait."""
        key, now = key[:_MAX_KEY_LENGTH], self._clock()
        with self._lock:
            dq = self._prune(key, now)
            if dq is not None and len(dq) >= self.limit:
                return max(0.001, dq[0] + self.window - now)
            self._add(key, now)
            return 0.0


class FailureTracker(_Windowed):
    """Blocks a key once it has `limit` failures inside the window, until the oldest ones age out."""

    def blocked(self, key: str) -> float:
        """0 if the key may try, otherwise the number of seconds until it may."""
        key, now = key[:_MAX_KEY_LENGTH], self._clock()
        with self._lock:
            dq = self._prune(key, now)
            if dq is not None and len(dq) >= self.limit:
                return max(0.001, dq[len(dq) - self.limit] + self.window - now)
            return 0.0

    def record(self, key: str) -> None:
        key, now = key[:_MAX_KEY_LENGTH], self._clock()
        with self._lock:
            self._prune(key, now)
            self._add(key, now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key[:_MAX_KEY_LENGTH], None)


# Every /api request, per visitor
general_limiter = SlidingWindowLimiter(limit=300, window=60)
# The endpoints that call out to Yahoo, per visitor
expensive_limiter = SlidingWindowLimiter(limit=60, window=60)
# Failed logins: per username (stops guessing one account from anywhere) and per visitor (stops trying many accounts)
login_user_failures = FailureTracker(limit=5, window=15 * 60)
login_ip_failures = FailureTracker(limit=20, window=15 * 60)


def reset_all() -> None:
    for item in _registry:
        item.reset()
