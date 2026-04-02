"""Cache key generation and URL normalization."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote


def normalize_url(url: str) -> str:
    """Normalize URL for consistent caching.

    Args:
        url: Raw URL

    Returns:
        Normalized URL with lowercase scheme/domain, decoded path, sorted query
    """
    parsed = urlparse(url)

    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports
    if (scheme == "http" and netloc.endswith(":80")) or (
        scheme == "https" and netloc.endswith(":443")
    ):
        netloc = netloc.rsplit(":", 1)[0]

    # Decode path
    path = unquote(parsed.path)
    if not path:
        path = "/"

    # Normalize path (remove trailing slash except for root)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Build query with sorted params
    query = parsed.query

    # Rebuild URL
    normalized = f"{scheme}://{netloc}{path}"
    if query:
        normalized += f"?{query}"

    return normalized


def get_cache_key(url: str) -> Path:
    """Get filesystem path for URL cache.

    Args:
        url: Normalized URL

    Returns:
        Path relative to cache directory
    """
    normalized = normalize_url(url)
    parsed = urlparse(normalized)

    domain = parsed.netloc
    path = parsed.path.lstrip("/")

    if not path:
        path = "index.html"
    elif not path.endswith(".html"):
        path = path + "/index.html"

    return Path(domain) / path


def get_url_hash(url: str) -> str:
    """Get SHA256 hash of URL for search cache keys.

    Args:
        url: URL to hash

    Returns:
        Short hex hash (8 characters)
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()[:8]


def get_search_key(query: str, count: int, result_type: str = "web") -> str:
    """Get cache filename for search results.

    Args:
        query: Search query
        count: Number of results
        result_type: Type of results (web, news, etc.)

    Returns:
        Cache filename like "dc9a8f5_10_web.json"
    """
    query_hash = get_url_hash(query)
    return f"{query_hash}_{count}_{result_type}.json"
