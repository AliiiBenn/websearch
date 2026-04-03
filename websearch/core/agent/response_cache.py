"""Claude response caching for agent operations."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from websearch.core.cache.ttl import utc_now


class ClaudeResponseCache:
    """Cache for Claude agent responses.

    Caches responses based on URL + prompt hash to avoid redundant API calls.

    Attributes:
        TTL: Default TTL for cached responses in seconds (2 hours)
        CACHE_DIR: Location of the cache directory
    """

    TTL: float = 7200  # 2 hours
    CACHE_DIR: Path = Path.home() / ".cache" / "websearch" / "claude"

    def __init__(self, cache_dir: Path | None = None, ttl: float | None = None):
        """Initialize Claude response cache.

        Args:
            cache_dir: Optional custom cache directory
            ttl: Optional custom TTL in seconds
        """
        self.cache_dir = cache_dir or self.CACHE_DIR
        self.ttl = ttl if ttl is not None else self.TTL
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure cache directories exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str, prompt: str) -> str:
        """Generate cache key from URL and prompt.

        Args:
            url: The URL being processed
            prompt: The prompt being used

        Returns:
            SHA256 hash of URL + prompt
        """
        content = f"{url}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> tuple[Path, Path]:
        """Get paths for cached response and metadata.

        Args:
            key: Cache key

        Returns:
            Tuple of (response_path, metadata_path)
        """
        response_path = self.cache_dir / key
        metadata_path = self.cache_dir / f"{key}.meta.json"
        return response_path, metadata_path

    def get(self, url: str, prompt: str) -> dict[str, Any] | None:
        """Get cached response for URL and prompt.

        Args:
            url: The URL that was processed
            prompt: The prompt that was used

        Returns:
            Cached response dict or None if not found or expired
        """
        key = self._get_cache_key(url, prompt)
        response_path, metadata_path = self._get_cache_path(key)

        if not response_path.exists() or not metadata_path.exists():
            return None

        try:
            metadata = json.loads(metadata_path.read_text())

            # Check TTL
            cached_at = metadata.get("cached_at")
            if cached_at:
                from websearch.core.cache.ttl import is_expired

                if is_expired(cached_at, self.ttl):
                    return None

            response = json.loads(response_path.read_text())
            return {"response": response, "metadata": metadata}
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, url: str, prompt: str, response: str) -> None:
        """Cache response for URL and prompt.

        Args:
            url: The URL that was processed
            prompt: The prompt that was used
            response: The response content to cache
        """
        key = self._get_cache_key(url, prompt)
        response_path, metadata_path = self._get_cache_path(key)

        metadata = {
            "url": url,
            "prompt": prompt,
            "cached_at": utc_now().isoformat(),
            "ttl": self.ttl,
        }

        self._atomic_write(response_path, json.dumps(response, indent=2).encode())
        self._atomic_write(metadata_path, json.dumps(metadata, indent=2).encode())

    def _atomic_write(self, path: Path, content: bytes) -> None:
        """Write file atomically using temp file + rename.

        Args:
            path: Target file path
            content: Content to write
        """
        self._ensure_dirs()

        with NamedTemporaryFile(mode="wb", delete=False, dir=path.parent) as f:
            f.write(content)
            temp_path = Path(f.name)

        temp_path.replace(path)

    def invalidate(self, url: str, prompt: str) -> bool:
        """Invalidate cached response for URL and prompt.

        Args:
            url: The URL to invalidate
            prompt: The prompt to invalidate

        Returns:
            True if invalidated, False if not found
        """
        key = self._get_cache_key(url, prompt)
        response_path, metadata_path = self._get_cache_path(key)
        deleted = False

        if response_path.exists():
            response_path.unlink()
            deleted = True

        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        return deleted

    def clear(self) -> None:
        """Clear all cached responses."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self._ensure_dirs()
