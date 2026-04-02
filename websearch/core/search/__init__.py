"""Web search and fetch client."""

from websearch.core.search.client import (
    ApiKeyError,
    BraveApiError,
    BraveClient,
    QuotaExceededError,
    RateLimitError,
)
from websearch.core.search.search import Search, SearchError
from websearch.core.search.types import SearchResult, SearchResults

__all__ = [
    "Search",
    "SearchError",
    "BraveClient",
    "BraveApiError",
    "ApiKeyError",
    "RateLimitError",
    "QuotaExceededError",
    "SearchResult",
    "SearchResults",
]
