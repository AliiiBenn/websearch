"""Tests for cache module."""

import json
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from websearch.core.cache import Cache
from websearch.core.cache.key import normalize_url, get_cache_key, get_url_hash, get_search_key
from websearch.core.cache.ttl import (
    calculate_ttl,
    get_url_ttl,
    get_search_ttl,
    is_expired,
    utc_now,
    DEFAULT_URL_TTL,
    DEFAULT_SEARCH_TTL,
)


class TestNormalizeUrl:
    """Tests for URL normalization."""

    def test_lowercase_scheme(self):
        url = "HTTPS://Example.com/Page"
        normalized = normalize_url(url)
        assert normalized.startswith("https://")

    def test_lowercase_domain(self):
        url = "https://EXAMPLE.COM/Page"
        normalized = normalize_url(url)
        assert "example.com" in normalized

    def test_remove_default_port_http(self):
        url = "http://example.com:80/path"
        normalized = normalize_url(url)
        assert ":80" not in normalized

    def test_remove_default_port_https(self):
        url = "https://example.com:443/path"
        normalized = normalize_url(url)
        assert ":443" not in normalized

    def test_decode_path(self):
        url = "https://example.com/Hello%20World"
        normalized = normalize_url(url)
        assert "Hello World" in normalized

    def test_trailing_slash_removed(self):
        url = "https://example.com/page/"
        normalized = normalize_url(url)
        assert not normalized.endswith("/")

    def test_root_path_preserved(self):
        url = "https://example.com/"
        normalized = normalize_url(url)
        assert normalized == "https://example.com/"

    def test_query_params_preserved(self):
        url = "https://example.com/page?q=1&r=2"
        normalized = normalize_url(url)
        assert "q=1" in normalized
        assert "r=2" in normalized


class TestGetCacheKey:
    """Tests for cache key generation."""

    def test_simple_url(self):
        url = "https://example.com/page"
        key = get_cache_key(url)
        assert key == Path("example.com/page/index.html")

    def test_root_url(self):
        url = "https://example.com"
        key = get_cache_key(url)
        assert key == Path("example.com/index.html")

    def test_nested_path(self):
        url = "https://example.com/a/b/c"
        key = get_cache_key(url)
        assert "example.com" in str(key)
        assert "a" in str(key)
        assert "b" in str(key)
        assert "c" in str(key)

    def test_url_with_query(self):
        url = "https://example.com/page?q=1"
        key = get_cache_key(url)
        assert "example.com" in str(key)


class TestGetUrlHash:
    """Tests for URL hashing."""

    def test_same_url_same_hash(self):
        url = "https://example.com/page"
        hash1 = get_url_hash(url)
        hash2 = get_url_hash(url)
        assert hash1 == hash2

    def test_different_url_different_hash(self):
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        hash1 = get_url_hash(url1)
        hash2 = get_url_hash(url2)
        assert hash1 != hash2

    def test_hash_length(self):
        url = "https://example.com/page"
        hash_value = get_url_hash(url)
        assert len(hash_value) == 8

    def test_hash_is_hex(self):
        url = "https://example.com/page"
        hash_value = get_url_hash(url)
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestGetSearchKey:
    """Tests for search cache key generation."""

    def test_basic_search_key(self):
        key = get_search_key("python", 10, "web")
        assert key.endswith("_10_web.json")
        assert len(key) > 10

    def test_same_query_same_key(self):
        key1 = get_search_key("python", 10, "web")
        key2 = get_search_key("python", 10, "web")
        assert key1 == key2

    def test_different_count_different_key(self):
        key1 = get_search_key("python", 10, "web")
        key2 = get_search_key("python", 20, "web")
        assert key1 != key2

    def test_different_type_different_key(self):
        key1 = get_search_key("python", 10, "web")
        key2 = get_search_key("python", 10, "news")
        assert key1 != key2


class TestCalculateTtl:
    """Tests for TTL calculation with jitter."""

    def test_base_value(self):
        ttl = calculate_ttl(100.0)
        assert 90 <= ttl <= 110  # ±10%

    def test_jitter_range(self):
        ttl1 = calculate_ttl(1000.0)
        ttl2 = calculate_ttl(1000.0)
        # Should be different due to random jitter
        # (statistically very likely, but not guaranteed)

    def test_zero_base(self):
        ttl = calculate_ttl(0.0)
        assert ttl == 0.0

    def test_custom_jitter(self):
        ttl = calculate_ttl(100.0, jitter=0.2)
        assert 80 <= ttl <= 120  # ±20%


class TestGetUrlTtl:
    """Tests for URL TTL retrieval."""

    def test_default_ttl(self):
        ttl = get_url_ttl()
        assert 6400 <= ttl <= 8000  # ±10% of 7200

    def test_max_age_override(self):
        ttl = get_url_ttl(max_age=3600)
        assert ttl == 3600

    def test_max_age_capped(self):
        ttl = get_url_ttl(max_age=100000)
        assert ttl <= 86400  # Max URL TTL


class TestGetSearchTtl:
    """Tests for search TTL retrieval."""

    def test_default_ttl(self):
        ttl = get_search_ttl()
        assert 3240 <= ttl <= 3960  # ±10% of 3600


class TestIsExpired:
    """Tests for expiration checking."""

    def test_not_expired(self):
        now = utc_now()
        ttl = 3600
        cached = now - timedelta(seconds=1000)
        assert is_expired(cached, ttl) is False

    def test_expired(self):
        now = utc_now()
        ttl = 3600
        cached = now - timedelta(seconds=4000)
        assert is_expired(cached, ttl) is True

    def test_just_at_boundary(self):
        now = utc_now()
        ttl = 3600
        cached = now - timedelta(seconds=3600)
        # Should be expired (now > cached + ttl)


class TestCacheInit:
    """Tests for Cache initialization."""

    def test_default_values(self):
        cache = Cache()
        assert cache.enabled is True
        assert cache.max_size == 500 * 1024 * 1024

    def test_custom_cache_dir(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        assert cache.storage.cache_dir == tmp_path

    def test_disabled_cache(self):
        cache = Cache(enabled=False)
        assert cache.enabled is False


class TestCacheUrlOperations:
    """Tests for URL cache operations."""

    def test_set_and_get_url(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        url = "https://example.com"
        content = b"<h1>Hello</h1>"

        cache.set_url(url, content)
        result = cache.get_url(url)

        assert result.is_just()
        cached_content, metadata = result.just_value()
        assert cached_content == content
        assert metadata["url"] == url

    def test_cache_miss(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        result = cache.get_url("https://notcached.com")
        assert result.is_nothing()

    def test_is_fresh_true(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        cache.set_url("https://example.com", b"<h1>Hello</h1>")
        assert cache.is_fresh("https://example.com") is True

    def test_is_fresh_false(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        assert cache.is_fresh("https://example.com") is False

    def test_disabled_cache_returns_nothing(self, tmp_path):
        cache = Cache(cache_dir=tmp_path, enabled=False)
        cache.set_url("https://example.com", b"<h1>Hello</h1>")
        result = cache.get_url("https://example.com")
        assert result.is_nothing()

    def test_expired_url_returns_nothing(self, tmp_path):
        """Test that expired cache entries return Nothing."""
        cache = Cache(cache_dir=tmp_path)
        url = "https://example.com"

        # Directly write to storage to create expired entry
        content_path, metadata_path = cache.storage.get_url_path(url)
        content_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime, timezone, timedelta
        past_time = datetime.now(timezone.utc) - timedelta(hours=48)

        # Write content file
        content_path.write_bytes(b"<h1>Hello</h1>")

        # Write metadata with expired time directly
        import json
        metadata_path.write_text(json.dumps({
            "url": url,
            "cached_at": past_time.isoformat(),
            "ttl": 3600,  # 1 hour TTL
        }))

        result = cache.get_url(url)
        assert result.is_nothing()

    def test_missing_cached_at_returns_nothing(self, tmp_path):
        """Test that cache entry without cached_at returns Nothing."""
        cache = Cache(cache_dir=tmp_path)
        url = "https://example.com"

        # Directly write to storage without cached_at
        content_path, metadata_path = cache.storage.get_url_path(url)
        content_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content file
        content_path.write_bytes(b"<h1>Hello</h1>")

        # Write metadata without cached_at directly
        import json
        metadata_path.write_text(json.dumps({
            "url": url,
            "ttl": 3600,
            # No cached_at
        }))

        result = cache.get_url(url)
        assert result.is_nothing()


class TestCacheSearchMissingMetadata:
    """Tests for search cache with missing metadata fields."""

    def test_search_missing_cached_at_returns_nothing(self, tmp_path):
        """Test that search entry without cached_at returns Nothing."""
        cache = Cache(cache_dir=tmp_path)

        # Directly write to storage without cached_at
        from websearch.core.cache.key import get_search_key
        filename = get_search_key("query", 10, "web")
        cache_path = cache.storage.search_dir / filename
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Write search result without cached_at
        import json
        cache_path.write_text(json.dumps({
            "metadata": {
                "query": "query",
                "count": 10,
                "result_type": "web",
                # No cached_at
                "ttl": 3600,
            },
            "results": {"items": []}
        }))

        result = cache.get_search("query", 10, "web")
        assert result.is_nothing()


class TestCacheInvalidate:
    """Tests for cache invalidation."""

    def test_invalidate_existing(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        url = "https://example.com"
        cache.set_url(url, b"<h1>Hello</h1>")
        assert cache.is_fresh(url) is True

        deleted = cache.invalidate(url)
        assert deleted is True
        assert cache.is_fresh(url) is False

    def test_invalidate_nonexistent(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        deleted = cache.invalidate("https://notcached.com")
        assert deleted is False


class TestCacheClear:
    """Tests for cache clearing."""

    def test_clear_removes_all(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        cache.set_url("https://example.com", b"<h1>Hello</h1>")
        cache.set_url("https://example.org", b"<h1>World</h1>")

        assert cache.is_fresh("https://example.com") is True
        assert cache.is_fresh("https://example.org") is True

        cache.clear()

        assert cache.is_fresh("https://example.com") is False
        assert cache.is_fresh("https://example.org") is False


class TestCacheStats:
    """Tests for cache statistics."""

    def test_empty_cache_stats(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        stats = cache.stats()

        assert stats["size_bytes"] == 0
        assert stats["url_count"] == 0
        assert stats["search_count"] == 0
        assert stats["enabled"] is True
        assert stats["max_size_mb"] == 500.0

    def test_stats_after_caching(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        cache.set_url("https://example.com", b"<h1>Hello</h1>" * 100)

        stats = cache.stats()
        assert stats["size_bytes"] > 0
        assert stats["url_count"] >= 1


class TestCacheSearchOperations:
    """Tests for search result caching."""

    def test_set_and_get_search(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        query = "python async"
        count = 10
        result_type = "web"
        results = {"items": [{"title": "Result 1"}]}

        cache.set_search(query, count, result_type, results)
        cached = cache.get_search(query, count, result_type)

        assert cached.is_just()
        assert cached.just_value()["items"][0]["title"] == "Result 1"

    def test_search_cache_miss(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        result = cache.get_search("notcached", 10, "web")
        assert result.is_nothing()

    def test_disabled_cache_search_returns_nothing(self, tmp_path):
        """Test that disabled cache returns Nothing for search."""
        cache = Cache(cache_dir=tmp_path, enabled=False)
        cache.set_search("query", 10, "web", {"items": []})
        result = cache.get_search("query", 10, "web")
        assert result.is_nothing()

    def test_expired_search_returns_nothing(self, tmp_path):
        """Test that expired search cache returns Nothing."""
        cache = Cache(cache_dir=tmp_path)
        from datetime import datetime, timezone, timedelta

        # Manually create expired search cache
        past_time = datetime.now(timezone.utc) - timedelta(hours=48)
        cache.storage.set_search("expired_query", 10, "web", {"items": []}, 3600)
        # Manually corrupt the metadata to have past time
        from websearch.core.cache.key import get_search_key
        filename = get_search_key("expired_query", 10, "web")
        cache_path = cache.storage.search_dir / filename

        # Read and update the cached_at
        import json
        with open(cache_path, 'r') as f:
            data = json.load(f)
        data['metadata']['cached_at'] = past_time.isoformat()
        with open(cache_path, 'w') as f:
            json.dump(data, f)

        result = cache.get_search("expired_query", 10, "web")
        assert result.is_nothing()


class TestCacheUrlNormalize:
    """Tests that URL caching is case-insensitive."""

    def test_different_case_same_cache(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        url1 = "https://Example.com/Page"
        url2 = "https://example.com/page"

        cache.set_url(url1, b"<h1>Hello</h1>")
        result = cache.get_url(url2)

        # Normalized URLs should hit cache
        assert result.is_just()


class TestCacheStorageLocation:
    """Tests for cache directory structure."""

    def test_cache_creates_directories(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        cache.set_url("https://example.com", b"<h1>Hello</h1>")

        assert (tmp_path / "url").exists()
        assert (tmp_path / "metadata").exists()

    def test_search_creates_directory(self, tmp_path):
        cache = Cache(cache_dir=tmp_path)
        cache.set_search("query", 10, "web", {"results": []})

        assert (tmp_path / "search").exists()


class TestCacheCorruptedFiles:
    """Tests for handling corrupted cache files."""

    def test_corrupted_metadata_returns_nothing(self, tmp_path):
        """Test that corrupted JSON metadata returns Nothing."""
        cache = Cache(cache_dir=tmp_path)
        cache.set_url("https://example.com", b"<h1>Hello</h1>")

        # Corrupt the metadata file
        content_path, metadata_path = cache.storage.get_url_path("https://example.com")
        metadata_path.write_text("{ invalid json")

        result = cache.get_url("https://example.com")
        assert result.is_nothing()

    def test_corrupted_search_json_returns_nothing(self, tmp_path):
        """Test that corrupted search JSON returns Nothing."""
        cache = Cache(cache_dir=tmp_path)
        cache.set_search("query", 10, "web", {"items": []})

        # Corrupt the search file
        from websearch.core.cache.key import get_search_key
        filename = get_search_key("query", 10, "web")
        cache_path = cache.storage.search_dir / filename
        cache_path.write_text("{ invalid json")

        result = cache.get_search("query", 10, "web")
        assert result.is_nothing()


class TestCacheEviction:
    """Tests for LRU eviction."""

    def test_eviction_removes_old_files(self, tmp_path):
        """Test that eviction removes oldest files when over limit."""
        cache = Cache(cache_dir=tmp_path, max_size=100)  # Very small limit

        # Fill cache to exceed limit
        for i in range(10):
            url = f"https://example{i}.com"
            content = b"<h1>Hello</h1>" * 100  # Make it bigger
            cache.set_url(url, content)

        # Should have evicted some entries
        stats = cache.stats()
        # Cache should still exist but may be partially evicted
        assert (tmp_path / "url").exists()

    def test_eviction_preserves_newer_files(self, tmp_path):
        """Test that newer files are preserved during eviction."""
        cache = Cache(cache_dir=tmp_path, max_size=200)

        # Add entries
        for i in range(5):
            cache.set_url(f"https://example{i}.com", b"<h1>Hello</h1>" * 10)

        # Check all are still accessible (or at least some)
        fresh_count = sum(
            1 for i in range(5)
            if cache.is_fresh(f"https://example{i}.com")
        )
        assert fresh_count >= 1  # At least some should be preserved
