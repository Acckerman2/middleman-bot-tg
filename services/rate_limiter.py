"""
services/rate_limiter.py — In-process sliding-window rate limiter.

Each user gets an independent deque of timestamps.  On every call we
drop entries older than RATE_LIMIT_WINDOW seconds and compare the
remaining count to RATE_LIMIT_MESSAGES.

Thread-safety: asyncio is single-threaded, so a plain dict is safe here.
If you ever move to a multi-process deployment, replace this with a
Redis-backed counter.
"""

from collections import defaultdict, deque
from datetime import datetime, timezone

import config

# user_id → deque of UTC timestamps (float)
_buckets: dict[int, deque] = defaultdict(deque)


def is_rate_limited(user_id: int) -> bool:
    """
    Return True if the user has exceeded the configured rate limit.
    Side-effect: records the current request timestamp.
    """
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - config.RATE_LIMIT_WINDOW

    bucket = _buckets[user_id]

    # Evict stale entries
    while bucket and bucket[0] < window_start:
        bucket.popleft()

    if len(bucket) >= config.RATE_LIMIT_MESSAGES:
        return True  # over limit — do NOT record this attempt

    bucket.append(now)
    return False
