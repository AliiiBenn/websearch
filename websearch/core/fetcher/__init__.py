"""HTTP fetcher with retry logic and SPA detection."""

from websearch.core.fetcher.backoff import calculate_backoff
from websearch.core.fetcher.detection import is_spa
from websearch.core.fetcher.fetcher import Fetcher

__all__ = ["Fetcher", "is_spa", "calculate_backoff"]
