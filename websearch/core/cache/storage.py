"""File-based cache storage with atomic writes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from websearch.core.cache.key import get_cache_key
from websearch.core.cache.ttl import utc_now


def get_cache_dir() -> Path:
    """Get platform-specific cache directory.

    Returns:
        Path to cache directory
    """
    return Path.home() / ".cache" / "websearch"


class CacheStorage:
    """File-based cache storage."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize cache storage.

        Args:
            cache_dir: Optional custom cache directory
        """
        self.cache_dir = cache_dir or get_cache_dir()
        self.url_dir = self.cache_dir / "url"
        self.search_dir = self.cache_dir / "search"
        self.metadata_dir = self.cache_dir / "metadata"

    def _ensure_dirs(self) -> None:
        """Ensure cache directories exist."""
        self.url_dir.mkdir(parents=True, exist_ok=True)
        self.search_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, content: bytes) -> None:
        """Write file atomically using temp file + rename.

        Args:
            path: Target file path
            content: Content to write
        """
        self._ensure_dirs()
        path.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(mode="wb", delete=False, dir=path.parent) as f:
            f.write(content)
            temp_path = Path(f.name)

        temp_path.replace(path)

    def get_url_path(self, url: str) -> tuple[Path, Path]:
        """Get paths for URL content and metadata.

        Args:
            url: URL to get paths for

        Returns:
            Tuple of (content_path, metadata_path)
        """
        key = get_cache_key(url)
        content_path = self.url_dir / key
        metadata_path = self.metadata_dir / key.with_suffix(".json")
        return content_path, metadata_path

    def get_url(self, url: str) -> tuple[bytes | None, dict | None]:
        """Get cached URL content and metadata.

        Args:
            url: URL to retrieve

        Returns:
            Tuple of (content, metadata) or (None, None) if not cached
        """
        content_path, metadata_path = self.get_url_path(url)

        if not content_path.exists() or not metadata_path.exists():
            return None, None

        try:
            content = content_path.read_bytes()
            metadata = json.loads(metadata_path.read_text())
            return content, metadata
        except (OSError, json.JSONDecodeError):
            return None, None

    def set_url(self, url: str, content: bytes, metadata: dict[str, Any]) -> None:
        """Cache URL content with metadata.

        Args:
            url: URL being cached
            content: HTML content
            metadata: Metadata dict
        """
        content_path, metadata_path = self.get_url_path(url)

        # Add cached_at timestamp
        metadata["cached_at"] = utc_now().isoformat()

        self._atomic_write(content_path, content)
        self._atomic_write(metadata_path, json.dumps(metadata, indent=2).encode())

    def get_search(self, query: str, count: int, result_type: str = "web") -> dict | None:
        """Get cached search results.

        Args:
            query: Search query
            count: Number of results
            result_type: Type of results

        Returns:
            Cached results dict or None
        """
        from websearch.core.cache.key import get_search_key

        filename = get_search_key(query, count, result_type)
        cache_path = self.search_dir / filename

        if not cache_path.exists():
            return None

        try:
            return json.loads(cache_path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def set_search(
        self, query: str, count: int, result_type: str, data: dict, ttl: float
    ) -> None:
        """Cache search results.

        Args:
            query: Search query
            count: Number of results
            result_type: Type of results
            data: Results data
            ttl: TTL in seconds
        """
        from websearch.core.cache.key import get_search_key

        filename = get_search_key(query, count, result_type)
        cache_path = self.search_dir / filename

        metadata = {
            "query": query,
            "count": count,
            "result_type": result_type,
            "cached_at": utc_now().isoformat(),
            "ttl": ttl,
        }

        payload = {"metadata": metadata, "results": data}
        self._atomic_write(cache_path, json.dumps(payload, indent=2).encode())

    def delete(self, url: str) -> bool:
        """Delete cached URL.

        Args:
            url: URL to delete

        Returns:
            True if deleted, False if not found
        """
        content_path, metadata_path = self.get_url_path(url)
        deleted = False

        if content_path.exists():
            content_path.unlink()
            deleted = True

        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        return deleted

    def clear(self) -> None:
        """Clear all cache."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self._ensure_dirs()

    def get_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Cache size in bytes
        """
        total = 0
        if self.cache_dir.exists():
            for path in self.cache_dir.rglob("*"):
                if path.is_file():
                    total += path.stat().st_size
        return total
