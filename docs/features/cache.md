# Cache Feature

## Overview

The cache stores fetched URLs and search results to disk for reuse. It reduces redundant network requests and enables offline access to previously fetched content.

## Cache Storage

### Location

- **Linux/macOS:** `~/.cache/websearch/`
- **Windows:** `%LOCALAPPDATA%\websearch\cache\`

### Structure

```
~/.cache/websearch/
├── url/
│   ├── example.com/
│   │   └── index.html
│   └── github.com/
│       └── matthewwithanm/
│           └── python-markdownify
│               └── index.html
├── search/
│   └── dc9a8f5/  # Hashed query
│       └── 10_web.json  # count_type.json
└── metadata/
    └── example.com/
        └── index.html.json
```

### Cache Files

| Type | Format | Filename |
|------|--------|----------|
| URL content | Raw HTML | `index.html` |
| URL metadata | JSON | `index.html.json` |
| Search results | JSON | `{count}_{type}.json` |

## Cache Metadata

Each cached item includes metadata:

```json
{
  "url": "https://example.com",
  "cached_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-15T12:30:00Z",
  "content_hash": "sha256:abc123...",
  "original_size": 45032,
  "http_etag": "\"xyz789\"",
  "http_last_modified": "Mon, 15 Jan 2024 10:00:00 GMT"
}
```

## Cache Behavior

### TTL (Time to Live)

| Cache Type | Default TTL | Max TTL |
|------------|-------------|---------|
| URL content | 2 hours | 24 hours |
| Search results | 1 hour | 6 hours |

### TTL Jitter

To prevent mass expiration at TTL boundary, actual TTL varies by ±10%:

```python
import random

def calculate_ttl(base_ttl: float, jitter: float = 0.1) -> float:
    jitter_range = base_ttl * jitter
    return base_ttl + random.uniform(-jitter_range, jitter_range)
```

### Cache-Control Headers

The CLI respects HTTP `Cache-Control` headers:

- `max-age=N` - Use specified seconds as TTL
- `no-cache` - Skip caching
- `no-store` - Never cache
- `private` - Cache only on client device

### ETag/Last-Modified Support

When fetching a cached URL:

1. Send conditional request with `If-None-Match` or `If-Modified-Since`
2. If server returns `304 Not Modified`, serve from cache
3. If content changed, update cache and serve new content

## Eviction

### LRU (Least Recently Used)

When max cache size is reached, least recently used entries are evicted first.

### Max Size

Default maximum cache size is 500MB. When exceeded:
1. Sort entries by last access time
2. Evict oldest entries until under limit
3. Eviction is immediate, not batched

## Configuration

### CLI Commands

```bash
# View cache stats
websearch cache stats

# List cached URLs
websearch cache list
websearch cache list --type url
websearch cache list --type search

# Clear cache
websearch cache clear
websearch cache clear --type url
websearch cache clear --type search
websearch cache clear --older-than 7d

# Invalidate specific URL
websearch cache invalidate https://example.com
```

### Configuration File

In `~/.websearchrc`:

```ini
[cache]
directory = ~/.cache/websearch
ttl = 7200
max_size = 500M
enabled = true
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WEBSEARCH_CACHE_DIR` | Cache directory path | Platform-specific |
| `WEBSEARCH_CACHE_TTL` | Default TTL in seconds | 7200 |
| `WEBSEARCH_CACHE_MAX_SIZE` | Maximum cache size | 500M |
| `WEBSEARCH_CACHE_ENABLED` | Enable/disable cache | true |

## Usage in Commands

```bash
# Force fresh fetch (bypass cache)
websearch get https://example.com --no-cache

# Only use cache (offline mode)
websearch get https://example.com --cache-only

# Refresh expired items
websearch get https://example.com --refresh

# Search without cache
websearch search "query" --no-cache
```

## Python API

### Basic Usage

```python
from websearch.cache import Cache

cache = Cache()

# Get cached URL
content, metadata = cache.get_url("https://example.com")

# Cache a URL
cache.set_url("https://example.com", html_content, metadata)

# Check if cached and fresh
if cache.is_fresh("https://example.com"):
    print("Cache hit!")
else:
    print("Cache miss or expired")
```

### Cache Key Generation

URLs are normalized before caching:

```python
from websearch.cache import normalize_url, get_cache_key

url = "https://Example.com:443/Page?param=value"
normalized = normalize_url(url)
# normalized: "https://example.com/page?param=value"

cache_key = get_cache_key(normalized)
# cache_key: "example.com/page/param=value"
```

Search results are cached by hashed query:

```python
from websearch.cache import get_search_key

cache_key = get_search_key("python async", 10, "web")
# cache_key: "dc9a8f5_10_web.json"
```

## Concurrency

- Cache writes are atomic (write to temp file, then rename)
- Multiple processes can read simultaneously
- Lock files prevent concurrent writes to same item

## Troubleshooting

### Cache too large

```bash
# Check what's using space
websearch cache stats

# Clear old items
websearch cache clear --older-than 7d

# Set smaller max size
websearch config cache.max-size 100M
```

### Cache not being used

1. Verify cache is enabled: `websearch config cache.enabled` returns `true`
2. Check if `--no-cache` flag is being passed
3. Verify TTL hasn't expired
4. Check cache directory permissions

### Invalid cache errors

1. Cache may be corrupted
2. Try clearing: `websearch cache clear`

## Implementation Details

### Invalidation Strategies

- **LRU** eviction when max size reached
- **TTL-based** expiration checked on each access
- **URL-based** invalidation when forcing refresh

### Storage Format

```
cache/
├── {domain}/
│   └── {path}/
│       ├── index.html           # Cached content
│       └── index.html.json      # Metadata
└── search/
    └── {hash}_{count}_{type}.json
```

## Dependencies

```toml
dependencies = [
    "httpx>=0.25",
]
```

## Limitations

- PDF content is not cached
- Authentication-protected pages are not cached
- Cache is local to this machine (not shared)
