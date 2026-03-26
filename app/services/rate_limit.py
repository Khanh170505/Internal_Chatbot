import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.core.config import get_settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        settings = get_settings()
        now = time.time()
        window_start = now - 60
        bucket = self._hits[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= settings.api_rate_limit_per_minute:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        bucket.append(now)


rate_limiter = InMemoryRateLimiter()
