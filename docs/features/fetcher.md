# Fetcher Feature

## Overview

The fetcher retrieves HTML content from URLs using httpx. It handles HTTP requests with retry logic and basic SPA detection.

## Architecture

```
URL
  │
  ▼
┌─────────────────────┐
│      Fetcher        │
└─────────────────────┘
  │
  ├── httpx.get(url) ──→ Ok(bytes)
  │
  └── on error ──→ Err(HttpError)
```

## API

### Fetcher

```python
from websearch.core import Fetcher

fetcher = Fetcher(timeout=30)

result = await fetcher.fetch("https://example.com")

match result:
    case Ok(html_bytes):
        print(f"Got {len(html_bytes)} bytes")
    case Err(error):
        print(f"Failed: {error}")
```

### Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeout | int | 30 | Request timeout in seconds |
| user_agent | str | None | Custom User-Agent header |
| follow_redirects | bool | True | Follow HTTP redirects |
| verify_ssl | bool | True | Verify SSL certificates |
| max_retries | int | 3 | Retry attempts on failure |

### Methods

#### `fetch(url) -> Result[bytes, HttpError]`

Fetches URL content and returns raw HTML bytes.

**Parameters:**
- `url` (str) - The URL to fetch

**Returns:** `Result[bytes, HttpError]`

**Errors:**
- `NetworkError` - Connection failed
- `TimeoutError` - Request timed out
- `HttpError` - HTTP error response (4xx, 5xx)
- `InvalidUrlError` - Malformed URL

## Retry Logic

### Exponential Backoff

```
Attempt 1: immediate
Attempt 2: wait 0.5s
Attempt 3: wait 1.0s
Attempt 4: wait 2.0s
```

```python
def calculate_backoff(attempt: int, base: float = 0.5) -> float:
    """Calculate sleep time with exponential backoff."""
    return base * (2 ** (attempt - 1))
```

### Retry Conditions

**Retry on:**
- 429 Too Many Requests
- 500, 502, 503, 504 Server errors
- TimeoutError (read timeout)
- ConnectionError

**Do NOT retry:**
- 404 Not Found
- 403 Forbidden
- ConnectTimeoutError (indicates unreachable)
- 400 Bad Request

## SPA Detection

### Detection Heuristics

A page is considered a SPA when:

1. **Empty initial content** - HTML body is empty or contains minimal text (< 100 chars)
2. **JS framework markers** - Presence of React, Vue, Angular, Next.js
3. **Dynamic attributes** - `data-vue`, `ng-app`, `data-reactroot`

```python
def is_spa(html: bytes) -> bool:
    """Detect if page is likely a SPA."""
    if len(html) < 500:
        return True

    content_lower = html.lower()
    frameworks = [b"react", b"vue.js", b"angular", b"next", b"nuxt"]
    if any(fw in content_lower for fw in frameworks):
        return True

    if b"data-vue" in content_lower or b"ng-app" in content_lower:
        return True

    return False
```

### Playwright Fallback

When SPA is detected, Playwright renders the page:

1. Launch headless Chromium
2. Navigate to URL
3. Wait for network idle (max 5s)
4. Capture rendered HTML

```python
# Only if playwright is installed
try:
    from playwright.async_api import async_playwright
except ImportError:
    # SPA detection still works, but no rendering
    pass
```

## Error Types

### Hierarchy

```
HttpError (base)
├── NetworkError
│   ├── ConnectionError
│   └── DNSError
├── TimeoutError
├── InvalidUrlError
└── HttpStatusError
    ├── NotFoundError (404)
    ├── ForbiddenError (403)
    └── ServerError (5xx)
```

### Error Properties

All errors include:
- `message` - Human-readable description
- `url` - The URL that failed
- `status_code` - HTTP status (if applicable)

```python
class HttpError(Exception):
    def __init__(self, message: str, url: str, status_code: int | None = None):
        super().__init__(message)
        self.url = url
        self.status_code = status_code
```

## Error Recovery

| Error Type | Recovery |
|------------|----------|
| 429 Rate limit | Retry after backoff |
| 500-504 Server error | Retry with backoff |
| Timeout (read) | Retry |
| 404 Not found | Do not retry |
| 403 Forbidden | Do not retry |

## Resource Management

### Connection Pooling

httpx manages connection pooling automatically. Reuse the same `Fetcher` instance for better performance.

```python
fetcher = Fetcher()  # Reuse for multiple requests
```

### Cleanup

```python
async with Fetcher() as fetcher:
    result = await fetcher.fetch("https://example.com")
# Automatic cleanup on exit
```

## Usage Examples

### Basic Fetch

```python
from websearch.core import Fetcher

fetcher = Fetcher()
result = await fetcher.fetch("https://example.com")

if result.is_ok():
    html = result.unwrap()
    print(f"Fetched {len(html)} bytes")
```

### With Error Handling

```python
from websearch.core import Fetcher
from websearch.core.result import Result, Ok, Err

fetcher = Fetcher(timeout=10)

result = await fetcher.fetch("https://example.com/page")

match result:
    case Ok(html):
        process_html(html)
    case Err(HttpError() as e) if e.status_code == 404:
        print("Page not found")
    case Err(error):
        print(f"Fetch failed: {error}")
```

### Custom Configuration

```python
fetcher = Fetcher(
    timeout=60,
    user_agent="Mozilla/5.0 (compatible; MyBot/1.0)",
    max_retries=5,
)
```

## Logging

```python
import structlog

logger = structlog.get_logger()

async def fetch(self, url: str) -> Result[bytes, HttpError]:
    logger.info("fetching_url", url=url)
    result = await self._fetch(url)

    if result.is_ok():
        logger.info("fetch_success", url=url, bytes=len(result.value))
    else:
        logger.error("fetch_failed", url=url, error=str(result.err()))

    return result
```

## Dependencies

```toml
dependencies = [
    "httpx>=0.25",
]

optional-dependencies = [
    "playwright>=1.40",  # For SPA rendering
]
```

Install with:
```bash
pip install websearch        # Core only
pip install websearch[spa]    # With Playwright
```

## Limitations

- PDF content is not supported
- Authentication-protected pages are not supported
- Proxy support is not implemented
