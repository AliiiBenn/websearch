# SDK Documentation

## Overview

The `websearch` SDK provides a Python library interface for web fetching and search capabilities. It is designed to be:

- **Stable** - Public API with semantic versioning
- **Minimal** - Small surface area, easy to learn
- **Composable** - Work together or use standalone

## Installation

```bash
pip install websearch
```

## Quick Start

```python
from websearch import Websearch

client = Websearch()

# Fetch a URL and get Markdown
md = client.fetch("https://example.com")
print(md)

# Search the web
results = client.search("python async tutorial")
for result in results:
    print(result.title, result.url)
```

## Error Handling

The SDK exposes errors as exceptions for ease of use. Internally, core modules use `Result[T, E]` and `Maybe[T]` for composable error handling. The SDK layer converts these to exceptions:

```python
from websearch import Websearch
from websearch.errors import NotFoundError

client = Websearch()

try:
    md = client.fetch("https://example.com")
except NotFoundError:
    print("Page not found")
```

If you need fine-grained control over error handling, use the core modules directly:

```python
from websearch.core import Fetcher
from websearch.core.result import Result, Ok, Err

fetcher = Fetcher()
result = fetcher.fetch("https://example.com")

# Handle Result directly
if result.is_ok():
    html = result.unwrap()
else:
    error = result.err()
    print(f"Failed: {error}")
```

## Client Configuration

### Initialize with custom settings

```python
from websearch import Websearch

client = Websearch(
    timeout=60,
    cache_enabled=True,
    cache_ttl=3600,
    brave_api_key="your_key_here"  # or set BRAVE_API_KEY env
)
```

### Environment variables

```bash
export BRAVE_API_KEY=your_api_key_here
export WEBSEARCH_TIMEOUT=30
export WEBSEARCH_CACHE_ENABLED=true
```

## API Reference

### Websearch Client

#### `client.fetch(url, *, refresh=False)`

Fetch a URL and convert it to Markdown.

```python
md = client.fetch("https://example.com/article")
```

**Parameters:**
- `url` (str) - The URL to fetch
- `refresh` (bool) - Skip cache and force fresh fetch (default: False)

**Returns:** `str` - Markdown content

**Raises:**
- `WebsearchError` - Base error class
- `NetworkError` - Connection failed
- `HttpError` - HTTP error response (404, 500, etc.)

#### `client.search(query, *, count=10, search_type="web")`

Search the web using Brave Search API.

```python
results = client.search("python async", count=20)
```

**Parameters:**
- `query` (str) - Search query
- `count` (int) - Number of results (1-50, default: 10)
- `search_type` (str) - Type: "web", "news", "images", "videos" (default: "web")

**Returns:** `SearchResults` - Container with result items

**Raises:**
- `ApiKeyError` - Missing or invalid API key
- `ApiError` - API returned an error
- `RateLimitError` - Too many requests

### Search Results

#### `SearchResults`

Container for search results.

```python
results = client.search("query")

# Iterate
for item in results:
    print(item.title)

# Access raw response
raw = results.raw
```

**Attributes:**
- `items` - List of `SearchResult` objects
- `raw` - Raw API response dict

#### `SearchResult`

Individual search result.

```python
result = results[0]
print(result.title)      # Title text
print(result.url)        # Full URL
print(result.description) # Snippet/description
print(result.age)        # Age string (e.g., "2 days ago")
```

### Content Fetching

#### `client.fetch_raw(url)`

Fetch URL content without converting to Markdown.

```python
html, metadata = client.fetch_raw("https://example.com")
print(metadata.content_type)  # "text/html"
print(metadata.etag)           # ETag header
```

**Returns:** `tuple(html: bytes, metadata: FetchMetadata)`

#### `FetchMetadata`

Metadata about a fetched URL.

```python
@dataclass
class FetchMetadata:
    url: str
    status_code: int
    content_type: str
    etag: Optional[str]
    last_modified: Optional[str]
    cached: bool
    cached_at: Optional[datetime]
```

## Error Handling

### Exception Hierarchy

```
WebsearchError (base)
├── NetworkError
│   ├── ConnectionError
│   └── TimeoutError
├── HttpError
│   ├── NotFoundError (404)
│   ├── ForbiddenError (403)
│   └── ServerError (5xx)
├── BraveApiError
│   ├── ApiKeyError
│   ├── RateLimitError
│   └── QuotaExceededError
└── CacheError
```

### Handling errors

```python
from websearch import Websearch
from websearch.errors import NotFoundError, RateLimitError

client = Websearch()

try:
    md = client.fetch("https://example.com")
except NotFoundError:
    print("Page not found")
except RateLimitError:
    print("Rate limited, wait and retry")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Clear error messages

Every exception includes actionable information:

```python
try:
    client.search("query")
except RateLimitError as e:
    print(e.message)        # "Rate limited. Please wait 1 second between requests."
    print(e.retry_after)    # 1 (seconds)
```

## Caching

### Enable/disable cache

```python
client = Websearch(cache_enabled=True)  # default
```

### Check cache status

```python
from websearch import Websearch

client = Websearch()
client.cache.stats()
# URL cache: 12 items, 4.2 MB
# Search cache: 45 items, 1.1 MB
```

### Clear cache

```python
client.cache.clear()        # All cache
client.cache.clear("url")   # URL cache only
client.cache.clear("search") # Search cache only
```

### Cache TTL

```python
client = Websearch(cache_ttl=7200)  # 2 hours default

# Per-request override
md = client.fetch("https://example.com", cache_ttl=3600)
```

## Batch Operations

### Fetch multiple URLs

```python
from websearch import Websearch

client = Websearch()

urls = [
    "https://example.com/1",
    "https://example.com/2",
    "https://example.com/3",
]

# Fetch with concurrency
results = client.fetch_many(urls, concurrency=5)

for url, md in results:
    print(f"{url}: {len(md)} chars")
```

### Fetch with errors

```python
from websearch import Websearch, FetchResult

client = Websearch()

results: list[FetchResult] = client.fetch_many(urls, continue_on_error=True)

for result in results:
    if result.success:
        print(f"OK: {result.url}")
    else:
        print(f"FAILED: {result.url} - {result.error}")
```

## Advanced Usage

### Using core modules directly

For advanced use cases, you can access core modules:

```python
from websearch.core import Fetcher, Converter
from websearch.core.brave import BraveClient

# Fetcher for raw HTTP with Playwright support
fetcher = Fetcher()
html = await fetcher.fetch("https://example.com")

# Converter for HTML to Markdown
converter = Converter()
md = converter.convert(html)

# Direct Brave API access
brave = BraveClient()
results = brave.web_search("query", count=10)
```

Note: `core` module may change between versions without notice.

### Custom converter

```python
from websearch import Websearch
from websearch.core import Converter

class MyConverter(Converter):
    def convert_link(self, el, text, url):
        # Custom link formatting
        return f"[{text}]({url})"

client = Websearch(converter=MyConverter())
```

## Types Reference

### Public Types

These types are part of the stable SDK API:

| Type | Description |
|------|-------------|
| `Websearch` | Main client class |
| `SearchResults` | Container for search results |
| `SearchResult` | Individual result item |
| `FetchMetadata` | Metadata for fetched URLs |
| `FetchResult` | Result of batch fetch operation |

### Error Types

| Type | Description |
|------|-------------|
| `WebsearchError` | Base exception |
| `NetworkError` | Network-level errors |
| `HttpError` | HTTP error responses |
| `BraveApiError` | Brave API errors |
| `CacheError` | Cache operation errors |

## Configuration Reference

### Constructor Options

```python
Websearch(
    brave_api_key: Optional[str] = None,
    timeout: int = 30,
    cache_enabled: bool = True,
    cache_ttl: int = 7200,
    cache_dir: Optional[Path] = None,
    user_agent: Optional[str] = None,
    concurrency: int = 5,
)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRAVE_API_KEY` | Brave Search API key | None |
| `WEBSEARCH_TIMEOUT` | Request timeout (seconds) | 30 |
| `WEBSEARCH_CACHE_ENABLED` | Enable caching | true |
| `WEBSEARCH_CACHE_TTL` | Cache TTL (seconds) | 7200 |
| `WEBSEARCH_CACHE_DIR` | Cache directory | Platform-specific |
| `WEBSEARCH_CONCURRENCY` | Default concurrency | 5 |

## Versioning

The SDK follows semantic versioning:

- **Major** - Breaking changes to public API
- **Minor** - New features, backward compatible
- **Patch** - Bug fixes, backward compatible

Public API includes:
- Classes: `Websearch`, `SearchResults`, `SearchResult`
- Methods on `Websearch` client
- Error classes in `websearch.errors`
- Types in `websearch.types`

Anything in `websearch.core` is not versioned and may change.
