# Websearch CLI Project

## Overview

A Python-based CLI tool for web search and HTML-to-Markdown conversion. The tool provides two main capabilities:

1. Fetch any URL and convert its HTML content to clean Markdown
2. Perform web searches using the Brave Search API

## Goal

```
websearch get https://example.com  # Returns Markdown of the page
websearch search "query"           # Search using Brave API
```

## Technology Stack

- **Language:** Python >= 3.8
- **CLI Framework:** Click or argparse
- **HTTP Client:** httpx (async support)
- **JS Rendering:** Playwright for SPA support
- **HTML to Markdown:** See analysis below
- **Search API:** Brave Search API

---

## HTML to Markdown: Library Analysis

### Candidates Evaluated

| Library | Description | License | Last Update |
|---------|-------------|---------|-------------|
| markdownify | Converts HTML to Markdown with flexible tag handling | MIT | Active |
| html2text | Original by Aaron Swartz, converts HTML to readable Markdown | GPLv3 | Less active |

### Recommendation: markdownify

**Rationale:**

1. **Flexibility** - Supports custom converters to handle special cases
2. **Modern Python** - Actively maintained, Python >= 3.8
3. **MIT License** - Permissive, suitable for CLI tools
4. **CLI Support** - Built-in command-line interface
5. **Features** - Handles links, headings, code blocks, tables, bullet styles

**Example:**
```python
from markdownify import markdownify as md

result = md('<b>Hello</b> <a href="https://example.com">World</a>')
# Output: **Hello** [World](https://example.com)
```

**Alternative:** html2text is viable but shows less maintenance activity.

---

## Web Search: Brave Search API

### API Overview

- **Base URL:** `https://api.search.brave.com/res/v1/`
- **Authentication:** API key via `X-Subscription-Token` header or `BRAVE_API_KEY` env var
- **Pricing:** $5/1000 requests with $5 free monthly credits
- **Python SDK:** `brave-search` package

### Available Endpoints

| Endpoint | Description |
|----------|-------------|
| `/web/search` | Full web search results |
| `/images/search` | Image search |
| `/news/search` | News search |
| `/videos/search` | Video search |
| `/suggest/search` | Search suggestions |

### SDK Usage

```python
from brave import Brave

brave = Brave()
results = brave.search(q="query", count=10)
web_results = results.web_results
```

### Environment Variable

```
BRAVE_API_KEY=your_api_key_here
```

---

## Project Structure (Proposed)

```
.
├── src/
│   └── websearch/
│       ├── __init__.py         # sdk.Websearch re-export
│       ├── __main__.py         # Entry point for python -m websearch
│       │
│       ├── sdk/                # Public SDK (published to PyPI)
│       │   ├── __init__.py
│       │   ├── client.py       # Main Websearch class
│       │   ├── errors.py       # Public exceptions
│       │   └── types.py        # Public types
│       │
│       ├── cli/                # CLI (uses sdk)
│       │   ├── __init__.py
│       │   ├── get.py          # websearch get command
│       │   ├── search.py       # websearch search command
│       │   ├── batch.py        # websearch batch command
│       │   ├── config.py       # websearch config command
│       │   └── cache.py        # websearch cache command
│       │
│       └── core/               # Internal implementation (private)
│           ├── __init__.py
│           ├── result.py        # Result[T, E] type
│           ├── maybe.py         # Maybe[T] type
│           ├── fetcher.py      # URL fetching (httpx + playwright)
│           ├── converter.py    # HTML to Markdown (markdownify)
│           ├── cache.py        # Cache management
│           ├── errors.py       # Internal exceptions
│           └── brave/
│               ├── __init__.py
│               ├── client.py   # Brave API client
│               ├── endpoints.py # API endpoints
│               └── models.py    # Response models
├── tests/
├── docs/
├── pyproject.toml
├── .env.example
└── README.md
```

### Architecture: Internal -> SDK -> CLI

```
core/       (internal, implementation detail)
    │
    ▼
sdk/        (public API, semantic versioning)
    │
    ▼
cli/        (user-facing CLI, uses sdk)
```

### Structure Rationale

| Directory | Purpose | Stability |
|-----------|---------|-----------|
| `sdk/` | Public SDK for programmatic use | Versioned API |
| `cli/` | Command implementations | Uses sdk |
| `core/` | Internal implementation | May change |

### SDK Public API

```python
from websearch import Websearch

client = Websearch()
md = client.fetch("https://example.com")
results = client.search("query")
```

### CLI uses SDK

```python
# cli/search.py
from websearch import Websearch

@click.command()
def search(query: str):
    client = Websearch()
    results = client.search(query)
    # format and display
```

---

## Implementation Notes

### HTML to Markdown Pipeline

1. Attempt fetch via `httpx`
2. If page is a SPA (detected via presence of JS bundles or empty initial content):
   - Use `playwright` to render the page in a headless browser
   - Wait for network idle and DOM ready
3. Parse HTML with `selectolax` (fast, pure Python)
4. Convert to Markdown with `markdownify`
5. Output to stdout or file

Note: PDF content is not supported. Authentication-protected pages are not supported.

### CLI Commands

Each command is in its own file under `cli/`:

- `websearch get <url>` - Fetch URL and output Markdown
- `websearch search <query>` - Search via Brave API
- `websearch batch <input>` - Fetch multiple URLs
- `websearch config key` - Set API key interactively
- `websearch cache stats|list|clear` - Cache management
- `websearch --help` - Show help

### Configuration

- API key from environment variable `BRAVE_API_KEY`
- Optional `.env` file support via `python-dotenv`

### SDK as Library (Recommended)

The `sdk/` module is the public API for programmatic use:

```python
from websearch import Websearch

client = Websearch()

# Fetch and convert a URL
md = client.fetch("https://example.com")

# Search via Brave
results = client.search("query")
```

### Core (Internal)

The `core/` module contains the internal implementation:

```python
from websearch.core import Fetcher, Converter
from websearch.core.brave import BraveClient

# Lower-level access
fetcher = Fetcher()
html = await fetcher.fetch("https://example.com")

converter = Converter()
markdown = converter.to_markdown(html)
```

Note: `core/` is internal and may change between versions. Use `sdk/` for stable API.

---

## Functional Error Handling

The internal implementation uses `Result[T, E]` and `Maybe[T]` types for explicit error handling without exceptions.

### Result[T, E]

Represents either a success value (`Ok`) or an error (`Err`).

```python
from websearch.core.result import Result, Ok, Err

def fetch_url(url: str) -> Result[bytes, HttpError]:
    ...

# Match on result
result = fetch_url("https://example.com")
match result:
    case Ok(value):
        print(f"Got {len(value)} bytes")
    case Err(error):
        print(f"Failed: {error.message}")
```

**Methods:**

```python
result.is_ok() -> bool
result.is_err() -> bool
result.ok() -> Optional[T]      # unwrap value or None
result.err() -> Optional[E]     # unwrap error or None
result.unwrap() -> T            # get value or raise
result.unwrap_err() -> E        # get error or raise
result.map(f) -> Result         # transform Ok value
result.map_err(f) -> Result     # transform Err error
result.flat_map(f) -> Result    # chain Result-returning functions
```

### Maybe[T]

Represents an optional value (`Just` or `Nothing`).

```python
from websearch.core.maybe import Maybe, Just, Nothing

def find_header(headers: dict, key: str) -> Maybe[str]:
    ...

# Match on maybe
result = find_header(headers, "content-type")
match result:
    case Just(value):
        print(f"Content-Type: {value}")
    case Nothing:
        print("No Content-Type header")
```

**Methods:**

```python
maybe.is_just() -> bool
maybe.is_nothing() -> bool
maybe.just_value() -> Optional[T]  # get value or None
maybe.map(f) -> Maybe              # transform Just value
maybe.flat_map(f) -> Maybe         # chain Maybe-returning functions
maybe.get_or_else(default) -> T     # get value or default
maybe.to_result(error) -> Result    # convert to Result[T, E]
```

### Usage in Core Modules

Internal modules return `Result` and `Maybe` instead of raising exceptions:

```python
from websearch.core import Fetcher, Converter
from websearch.core.result import Result, Ok, Err
from websearch.core.maybe import Maybe

# Fetcher returns Result
fetcher = Fetcher()
result: Result[bytes, HttpError] = fetcher.fetch("https://example.com")

# Converter returns Maybe (content may need JS rendering)
md: Maybe[str] = converter.to_markdown(html)

# Chaining with flat_map
final: Result[str, Error] = (
    fetcher.fetch(url)
    .flat_map(lambda html: converter.to_markdown(html))
    .flat_map(lambda md: validator.validate(md))
)
```

This approach:
- Makes error handling explicit and composable
- Avoids exception propagation across module boundaries
- Enables functional patterns like `map`, `flat_map`, `filter`
- Easier to test with pure functions

## Dependencies (Proposed)

```
click>=8.0
httpx>=0.25
markdownify>=0.11
selectolax>=0.3
playwright>=1.40
python-dotenv>=1.0
```

Note: No external Brave SDK - we implement our own `core/brave/` client.

---

## References

- [markdownify GitHub](https://github.com/matthewwithanm/python-markdownify)
- [html2text GitHub](https://github.com/Alir3z4/html2text)
- [Brave Search API](https://brave.com/search/api/)
- [brave-search PyPI](https://pypi.org/project/brave-search/)
