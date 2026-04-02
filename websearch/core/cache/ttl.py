"""TTL calculation with jitter."""

from __future__ import annotations

import random
from datetime import datetime, timezone, timedelta


# Default TTLs in seconds
DEFAULT_URL_TTL = 7200  # 2 hours
DEFAULT_SEARCH_TTL = 3600  # 1 hour

# Max TTLs
MAX_URL_TTL = 86400  # 24 hours
MAX_SEARCH_TTL = 21600  # 6 hours

# Jitter factor
JITTER_FACTOR = 0.1


def calculate_ttl(base_ttl: float, jitter: float = JITTER_FACTOR) -> float:
    """Calculate TTL with random jitter.

    Args:
        base_ttl: Base TTL in seconds
        jitter: Jitter factor (0.1 = ±10%)

    Returns:
        TTL in seconds with jitter applied
    """
    jitter_range = base_ttl * jitter
    return base_ttl + random.uniform(-jitter_range, jitter_range)


def get_url_ttl(max_age: int | None = None) -> float:
    """Get TTL for URL content.

    Args:
        max_age: Optional Cache-Control max-age value

    Returns:
        TTL in seconds
    """
    if max_age is not None:
        return min(max_age, MAX_URL_TTL)
    return calculate_ttl(DEFAULT_URL_TTL)


def get_search_ttl() -> float:
    """Get TTL for search results.

    Returns:
        TTL in seconds
    """
    return calculate_ttl(DEFAULT_SEARCH_TTL)


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def is_expired(cached_at: datetime, ttl: float) -> bool:
    """Check if cached item has expired.

    Args:
        cached_at: When the item was cached
        ttl: TTL in seconds

    Returns:
        True if expired
    """
    expires_at = cached_at + timedelta(seconds=ttl)
    return utc_now() > expires_at
