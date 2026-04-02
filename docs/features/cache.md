# Cache Feature

## Overview

The websearch CLI caches fetched URLs and search results to improve performance and reduce API calls. Caching is particularly useful when:

- Re-fetching the same URLs multiple times
- Running scripts that repeatedly query the same data
- Working offline with previously cached content

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

### Cache-Control Headers

The CLI respects HTTP `Cache-Control` headers when available:

- `max-age=N` - Use specified seconds as TTL
- `no-cache` - Skip caching
- `no-store` - Never cache
- `private` - Cache only on client device

### ETag/Last-Modified Support

When fetching a cached URL:

1. Send conditional request with `If-None-Match` or `If-Modified-Since`
2. If server returns `304 Not Modified`, serve from cache
3. If content changed, update cache and serve new content

## Configuration

### Set cache directory

```bash
websearch config cache.dir /path/to/cache
```

### Set default TTL

```bash
websearch config cache.ttl 3600  # 1 hour in seconds
```

### Set max cache size

```bash
websearch config cache.max-size 500M
```

### Configuration file

In `~/.websearchrc`:

```ini
[cache]
directory = ~/.cache/websearch
ttl = 7200
max_size = 500M
enabled = true
```

## Cache Commands

### View cache stats

```bash
websearch cache stats
```

Output:

```
URL cache:
  Items: 47
  Size: 12.3 MB
  oldest: 2024-01-10

Search cache:
  Items: 123
  Size: 2.1 MB
  oldest: 2024-01-14

Total: 14.4 MB
```

### List cached URLs

```bash
websearch cache list
websearch cache list --type url
websearch cache list --type search
```

### Clear cache

```bash
# Clear all cache
websearch cache clear

# Clear URL cache only
websearch cache clear --type url

# Clear search cache only
websearch cache clear --type search

# Clear cache older than 7 days
websearch cache clear --older-than 7d
```

### Invalidate specific URL

```bash
websearch cache invalidate https://example.com
```

### Export/Import cache

```bash
# Export cache to file
websearch cache export /path/to/backup.tar.gz

# Import cache from file
websearch cache import /path/to/backup.tar.gz
```

## Using Cache in Commands

### Force fresh fetch

```bash
websearch get https://example.com --no-cache
```

### Only use cache (offline mode)

```bash
websearch get https://example.com --cache-only
```

### Refresh expired items

```bash
websearch get https://example.com --refresh
```

### Search without cache

```bash
websearch search "query" --no-cache
```

## Programmatic Access

### Python API

```python
from websearch.cache import Cache

cache = Cache()

# Get cached URL
content, metadata = cache.get_url("https://example.com")

# Cache a URL
cache.set_url("https://example.com", html_content, metadata)

# Check if URL is cached and fresh
if cache.is_fresh("https://example.com"):
    print("Cache hit!")
else:
    print("Cache miss or expired")
```

### Cache Key Generation

URLs are cached by their normalized URL:

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

query = "python async"
count = 10
search_type = "web"

cache_key = get_search_key(query, count, search_type)
# cache_key: "dc9a8f5_10_web.json"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WEBSEARCH_CACHE_DIR` | Cache directory path | Platform-specific |
| `WEBSEARCH_CACHE_TTL` | Default TTL in seconds | 7200 |
| `WEBSEARCH_CACHE_MAX_SIZE` | Maximum cache size | 500M |
| `WEBSEARCH_CACHE_ENABLED` | Enable/disable cache | true |

## Troubleshooting

### Cache占用太多空间

```bash
# Check what's using space
websearch cache stats

# Clear old items
websearch cache clear --older-than 7d

# Set smaller max size
websearch config cache.max-size 100M
```

### Cache not being used

1. Verify cache is enabled: `websearch config cache.enabled` should return `true`
2. Check if `--no-cache` flag is being passed
3. Verify TTL hasn't expired
4. Check cache directory permissions

### Invalid cache errors

If you see "Invalid cache file" errors:

1. The cache may be corrupted
2. Try clearing and rebuilding: `websearch cache clear`

## Implementation Details

### Cache Invalidation Strategy

- **LRU (Least Recently Used)** eviction when max size reached
- **TTL-based** expiration checked on each access
- **URL-based** invalidation when forcing refresh

### Concurrency

- Cache writes are atomic (write to temp file, then rename)
- Multiple processes can read simultaneously
- Lock files prevent concurrent writes to same item
