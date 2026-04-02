"""Main cache interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from websearch.core.cache.storage import CacheStorage
from websearch.core.cache.ttl import (
    DEFAULT_URL_TTL,
    DEFAULT_SEARCH_TTL,
    get_url_ttl,
    get_search_ttl,
    is_expired,
    utc_now,
)
from websearch.core.types.maybe import Just, Maybe, Nothing


class Cache:
    """URL and search result cache."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        enabled: bool = True,
        max_size: int = 500 * 1024 * 1024,  # 500MB
    ):
        """Initialize cache.

        Args:
            cache_dir: Optional custom cache directory
            enabled: Whether caching is enabled
            max_size: Maximum cache size in bytes
        """
        self.storage = CacheStorage(cache_dir)
        self.enabled = enabled
        self.max_size = max_size

    def get_url(self, url: str) -> Maybe[tuple[bytes, dict[str, Any]]]:
        """Get cached URL content and metadata.

        Args:
            url: URL to retrieve

        Returns:
            Just((content, metadata)) on cache hit,
            Nothing on cache miss or expired
        """
        if not self.enabled:
            return Nothing()

        content, metadata = self.storage.get_url(url)

        if content is None or metadata is None:
            return Nothing()

        # Check expiration
        cached_at = metadata.get("cached_at")
        ttl = metadata.get("ttl", DEFAULT_URL_TTL)

        if cached_at is None:
            return Nothing()

        from datetime import datetime, timezone

        if isinstance(cached_at, str):
            cached_at = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))

        if is_expired(cached_at, ttl):
            return Nothing()

        return Just((content, metadata))

    def set_url(
        self,
        url: str,
        content: bytes,
        metadata: dict[str, Any] | None = None,
        ttl: float | None = None,
    ) -> None:
        """Cache URL content.

        Args:
            url: URL being cached
            content: HTML content
            metadata: Optional additional metadata
            ttl: Optional TTL override
        """
        if not self.enabled:
            return

        # Check size and evict if needed
        self._evict_if_needed()

        meta = metadata.copy() if metadata else {}
        meta["url"] = url
        meta["ttl"] = ttl or get_url_ttl()

        self.storage.set_url(url, content, meta)

    def get_search(
        self, query: str, count: int, result_type: str = "web"
    ) -> Maybe[dict[str, Any]]:
        """Get cached search results.

        Args:
            query: Search query
            count: Number of results
            result_type: Type of results

        Returns:
            Just(results) on cache hit, Nothing otherwise
        """
        if not self.enabled:
            return Nothing()

        data = self.storage.get_search(query, count, result_type)

        if data is None:
            return Nothing()

        metadata = data.get("metadata", {})
        cached_at = metadata.get("cached_at")
        ttl = metadata.get("ttl", DEFAULT_SEARCH_TTL)

        if cached_at is None:
            return Nothing()

        from datetime import datetime, timezone

        if isinstance(cached_at, str):
            cached_at = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))

        if is_expired(cached_at, ttl):
            return Nothing()

        return Just(data.get("results", {}))

    def set_search(
        self,
        query: str,
        count: int,
        result_type: str,
        results: dict[str, Any],
    ) -> None:
        """Cache search results.

        Args:
            query: Search query
            count: Number of results
            result_type: Type of results
            results: Results data
        """
        if not self.enabled:
            return

        ttl = get_search_ttl()
        self.storage.set_search(query, count, result_type, results, ttl)

    def is_fresh(self, url: str) -> bool:
        """Check if URL is cached and fresh.

        Args:
            url: URL to check

        Returns:
            True if cached and not expired
        """
        return self.get_url(url).is_just()

    def invalidate(self, url: str) -> bool:
        """Invalidate cached URL.

        Args:
            url: URL to invalidate

        Returns:
            True if something was deleted
        """
        return self.storage.delete(url)

    def clear(self) -> None:
        """Clear all cache."""
        self.storage.clear()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with size, url_count, search_count
        """
        size = self.storage.get_size()

        url_count = 0
        search_count = 0

        storage = self.storage
        if storage.url_dir.exists():
            url_count = len(list(storage.url_dir.rglob("*.html")))

        if storage.search_dir.exists():
            search_count = len(list(storage.search_dir.rglob("*.json")))

        return {
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "url_count": url_count,
            "search_count": search_count,
            "enabled": self.enabled,
            "max_size_mb": self.max_size / (1024 * 1024),
        }

    def _evict_if_needed(self) -> None:
        """Evict LRU entries if cache exceeds max size."""
        size = self.storage.get_size()

        if size < self.max_size:
            return

        # Collect all cached files with their last access time
        files_with_time = []
        if self.storage.url_dir.exists():
            for path in self.storage.url_dir.rglob("*"):
                if path.is_file():
                    files_with_time.append((path.stat().st_atime, path))

        if self.storage.search_dir.exists():
            for path in self.storage.search_dir.rglob("*.json"):
                if path.is_file():
                    files_with_time.append((path.stat().st_atime, path))

        # Sort by access time (oldest first)
        files_with_time.sort(key=lambda x: x[0])

        # Delete oldest files until under limit
        current_size = size
        for _, path in files_with_time:
            if current_size < self.max_size * 0.9:  # Stop at 90% to avoid frequent eviction
                break
            try:
                file_size = path.stat().st_size
                path.unlink()
                current_size -= file_size

                # Try to delete parent dirs if empty
                parent = path.parent
                while parent != self.storage.cache_dir and parent.exists():
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
            except OSError:
                continue
