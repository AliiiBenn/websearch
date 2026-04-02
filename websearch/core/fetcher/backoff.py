"""Retry backoff calculation."""

from __future__ import annotations


def calculate_backoff(attempt: int, base: float = 0.5) -> float:
    """Calculate sleep time with exponential backoff.

    Args:
        attempt: Current attempt number (1-indexed)
        base: Base delay in seconds (default 0.5s)

    Returns:
        Seconds to wait before next retry

    Example:
        >>> calculate_backoff(1)  # First retry, immediate
        0.5
        >>> calculate_backoff(2)
        1.0
        >>> calculate_backoff(3)
        2.0
    """
    return base * (2 ** (attempt - 1))
