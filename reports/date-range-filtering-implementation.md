# Date Range Filtering Implementation Report

## Executive Summary

The websearch CLI needs date range filtering capabilities to enable time-constrained searches. This report analyzes the current search architecture, evaluates Brave API's freshness parameters, and provides a detailed implementation plan with code examples.

**Current State:** The `search` command and `ask` command use Brave Search API via `Search` class and `BraveClient`, supporting `count` (1-50) and `search_type` (web, news, images, videos) parameters. No date filtering exists.

**Recommendation:** Implement a unified `--freshness` parameter supporting duration strings (e.g., `24h`, `7d`, `30d`) for simplicity, with optional `--before` and `--after` date parameters for advanced use cases. This approach balances ease of use with powerful date filtering capabilities.

---

## Current Architecture Gap

### Search Flow

```
CLI (main.py)
    |
    v
Search.search() --> BraveClient.web_search()
    |                    |
    v                    v
Cache.get_search()    HTTP GET to Brave API
    |
    v
Cache.set_search()
```

### Key Files

| File | Purpose |
|------|---------|
| `websearch/main.py` | CLI commands (`search`, `ask`) |
| `websearch/core/search/search.py` | `Search` class orchestrating search/fetch/cache |
| `websearch/core/search/client.py` | `BraveClient` for Brave API calls |
| `websearch/core/search/types.py` | `SearchResult`, `SearchResults` types |
| `websearch/core/cache/cache.py` | Cache with `get_search()`, `set_search()` |
| `websearch/core/cache/key.py` | Cache key generation |

### Current Search Method Signature

```python
# websearch/core/search/search.py, line 65
async def search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    use_cache: bool = True,
    verbose: bool = False,
) -> tuple[Maybe[SearchResults], bool]:
```

### Cache Key Structure

```python
# websearch/core/cache/key.py, line 87
def get_search_key(query: str, count: int, result_type: str = "web") -> str:
    query_hash = get_url_hash(query)
    return f"{query_hash}_{count}_{result_type}.json"
```

**Gap:** No freshness/date filtering parameters are passed through the chain, and cache keys do not include date filter parameters.

---

## Brave API Freshness Options

Based on Brave Search API documentation, the API supports:

### Freshness Parameter (`freshness`)

Limits results to content published within a specified time period.

| Value | Description |
|-------|-------------|
| `pd` | Past day |
| `pw` | Past week |
| `pm` | Past month |
| `py` | Past year |

### Custom Freshness with `before` and `after`

| Parameter | Format | Description |
|-----------|--------|-------------|
| `before` | `YYYY-MM-DD` | Results published before this date |
| `after` | `YYYY-MM-DD` | Results published after this date |

### Notes

- `freshness` is mutually exclusive with `before`/`after`
- Freshness filtering works best with `web` and `news` search types
- Brave API returns results even if date metadata is unavailable

---

## Implementation Options

### Option 1: Add `--freshness` with Duration Strings

**Approach:** Parse duration strings like `24h`, `7d`, `30d`, `12w`, `1y` and convert to Brave API format.

```python
# Duration to Brave freshness mapping
FRESHNESS_MAP = {
    "24h": "pd",   # Past day
    "7d": "pw",    # Past week
    "30d": "pm",   # Past month
    "12m": "py",   # Past year (12 months)
    "1y": "py",    # Past year
}
```

**CLI Usage:**
```bash
websearch search "AI news" --freshness=24h
websearch ask "latest AI developments" --freshness=7d
```

**Pros:** User-friendly, intuitive, covers common cases

**Cons:** Limited to predefined periods, no custom date ranges

### Option 2: Add `--before` and `--after` Date Parameters

**Approach:** Accept ISO 8601 date strings (`YYYY-MM-DD`) for explicit date ranges.

```python
@click.option("--before", type=str, help="Results published before date (YYYY-MM-DD)")
@click.option("--after", type=str, help="Results published after date (YYYY-MM-DD)")
```

**CLI Usage:**
```bash
websearch search "tech news" --before=2024-01-01 --after=2023-06-01
websearch ask "company earnings" --after=2024-01-01
```

**Pros:** Full flexibility for custom date ranges

**Cons:** More complex CLI, requires date validation

### Option 3: Unified Approach (Recommended)

**Approach:** Combine `--freshness` for simplicity with `--before`/`--after` for advanced use.

```python
# In CLI
@click.option("--freshness", type=str, help="Time filter: 24h, 7d, 30d, 12m, 1y")
@click.option("--before", type=str, help="Before date (YYYY-MM-DD)")
@click.option("--after", type=str, help="After date (YYYY-MM-DD)")
```

**Mutual Exclusion:** `--freshness` is mutually exclusive with `--before`/`--after`.

---

## Recommended Approach

**Use Option 3: Unified Freshness with Date Range Parameters**

Rationale:
1. **User Experience** - Common cases covered by simple `--freshness=24h` syntax
2. **Flexibility** - Advanced users can use `--before`/`--after` for custom ranges
3. **Compatibility** - Maps well to Brave API's `freshness`, `before`, `after` parameters
4. **Backward Compatibility** - Existing commands work without changes
5. **Cache Design** - Date filters can be included in cache keys

---

## Implementation Details

### 1. Add DateFilter Dataclass

```python
# websearch/core/search/types.py

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass
class DateFilter:
    """Date range filter for search queries."""
    mode: Literal["freshness", "range"]
    # For freshness mode
    freshness: str | None = None  # "pd", "pw", "pm", "py"
    # For range mode
    before: datetime | None = None
    after: datetime | None = None

    @classmethod
    def from_freshness(cls, value: str) -> "DateFilter":
        """Create from duration string like '24h', '7d'."""
        duration_map = {
            "24h": "pd",
            "7d": "pw",
            "30d": "pm",
            "12m": "py",
            "1y": "py",
        }
        freshness = duration_map.get(value.lower())
        if freshness is None:
            raise ValueError(f"Invalid freshness value: {value}. Use: 24h, 7d, 30d, 12m, 1y")
        return cls(mode="freshness", freshness=freshness)

    @classmethod
    def from_range(cls, before: str | None, after: str | None) -> "DateFilter":
        """Create from date strings."""
        before_dt = None
        after_dt = None
        if before:
            before_dt = datetime.strptime(before, "%Y-%m-%d")
        if after:
            after_dt = datetime.strptime(after, "%Y-%m-%d")
        return cls(mode="range", before=before_dt, after=after_dt)

    def to_api_params(self) -> dict[str, str]:
        """Convert to Brave API parameters."""
        if self.mode == "freshness":
            return {"freshness": self.freshness}
        else:
            params = {}
            if self.before:
                params["before"] = self.before.strftime("%Y-%m-%d")
            if self.after:
                params["after"] = self.after.strftime("%Y-%m-%d")
            return params
```

### 2. Update BraveClient.web_search()

```python
# websearch/core/search/client.py

async def web_search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    date_filter: DateFilter | None = None,
) -> SearchResults:
    # ... existing code ...

    params = {
        "q": query,
        "count": min(max(count, 1), 50),
    }

    # Add date filter parameters
    if date_filter:
        params.update(date_filter.to_api_params())
```

### 3. Update Search.search() Method

```python
# websearch/core/search/search.py

async def search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    use_cache: bool = True,
    verbose: bool = False,
    date_filter: DateFilter | None = None,
) -> tuple[Maybe[SearchResults], bool]:
    """Search the web using Brave Search API.

    Args:
        query: Search query
        count: Number of results (1-50)
        search_type: Type of search (web, news, images, videos)
        use_cache: Whether to use cached results
        verbose: Whether to return cache hit/miss info
        date_filter: Optional date range filter
    """
    cache_hit = False

    # Build cache key including date filter
    cache_key_parts = [query, str(count), search_type]
    if date_filter:
        if date_filter.mode == "freshness":
            cache_key_parts.append(date_filter.freshness)
        else:
            if date_filter.before:
                cache_key_parts.append(f"before_{date_filter.before.strftime('%Y%m%d')}")
            if date_filter.after:
                cache_key_parts.append(f"after_{date_filter.after.strftime('%Y%m%d')}")

    cache_key = "|".join(cache_key_parts)

    if use_cache:
        cached = self.cache.get_search_by_key(cache_key)
        if cached.is_just():
            # ... reconstruct from cache ...
            cache_hit = True
            return Just(results), cache_hit

    try:
        async with BraveClient(api_key=self.api_key, timeout=self.timeout) as client:
            results = await client.web_search(query, count, search_type, date_filter)
    except BraveApiError:
        return Nothing(), cache_hit

    if use_cache:
        self.cache.set_search_by_key(cache_key, {
            "query": results.query,
            "results": [
                {"title": r.title, "url": r.url, "description": r.description, "age": r.age}
                for r in results.results
            ],
        })

    return Just(results), cache_hit
```

### 4. Update Cache Methods

```python
# websearch/core/cache/cache.py

def get_search_by_key(self, cache_key: str) -> Maybe[dict[str, Any]]:
    """Get cached search results by key string."""
    # ... implementation ...

def set_search_by_key(self, cache_key: str, results: dict[str, Any]) -> None:
    """Cache search results with key string."""
    # ... implementation ...
```

### 5. Update CLI Commands

```python
# websearch/main.py

@main.command()
@click.argument("query")
@click.option("-n", "--count", default=10, help="Number of results (1-50, default: 10)")
@click.option("-t", "--type", "search_type", default="web", help=f"Result type: {', '.join(VALID_SEARCH_TYPES)} (default: web)")
@click.option("--freshness", type=str, help="Time filter: 24h (past day), 7d (past week), 30d (past month), 12m/1y (past year)")
@click.option("--before", type=str, help="Results before date (YYYY-MM-DD)")
@click.option("--after", type=str, help="Results after date (YYYY-MM-DD)")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Show results in verbose table format")
@click.option("--no-cache", is_flag=True, help="Disable caching")
def search(query, count, search_type, freshness, before, after, output, verbose, no_cache):
    """Search the web using Brave Search API."""
    # Validation
    if sum(bool(x) for x in [freshness, before, after]) > 1 and freshness:
        console.print("[red]Error: --freshness cannot be used with --before or --after[/red]")
        sys.exit(2)

    date_filter = None
    if freshness:
        try:
            date_filter = DateFilter.from_freshness(freshness)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(2)
    elif before or after:
        try:
            date_filter = DateFilter.from_range(before, after)
        except ValueError as e:
            console.print(f"[red]Error: Invalid date format. Use YYYY-MM-DD[/red]")
            sys.exit(2)

    # ... rest of search implementation ...
```

### 6. Update ask Command

```python
@main.command(name="ask")
@click.argument("query")
@click.option("--count", "-n", default=5, help="Number of search results (1-20)")
@click.option("--freshness", type=str, help="Time filter: 24h, 7d, 30d, 12m, 1y")
@click.option("--before", type=str, help="Before date (YYYY-MM-DD)")
@click.option("--after", type=str, help="After date (YYYY-MM-DD)")
@click.option("--no-cache", is_flag=True, help="Disable caching")
# ... other options ...
def ask(query, count, freshness, before, after, no_cache, ...):
    # Similar date filter handling
```

---

## CLI Usage Examples

### Freshness Parameter

```bash
# Search for news from the past day
websearch search "AI breakthroughs" --freshness=24h

# Search news from the past week
websearch search "tech news" -t news --freshness=7d

# Ask about recent developments (past month)
websearch ask "latest AI developments" --freshness=30d
```

### Date Range Parameters

```bash
# Before a specific date
websearch search "historical event" --before=2024-01-01

# After a specific date
websearch search "recent news" --after=2024-01-01

# Date range
websearch search "company earnings" --after=2024-01-01 --before=2024-12-31

# Combined with other options
websearch search "AI news" -t news --freshness=7d -n 20 --verbose
```

### Error Handling

```bash
# Invalid freshness value
$ websearch search "test" --freshness=48h
Error: Invalid freshness value: 48h. Use: 24h, 7d, 30d, 12m, 1y

# Invalid date format
$ websearch search "test" --before=2024/01/01
Error: Invalid date format. Use YYYY-MM-DD

# Conflicting parameters
$ websearch search "test" --freshness=24h --before=2024-01-01
Error: --freshness cannot be used with --before or --after
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_date_filter.py

class TestDateFilter:
    def test_from_freshness_24h(self):
        df = DateFilter.from_freshness("24h")
        assert df.mode == "freshness"
        assert df.freshness == "pd"

    def test_from_freshness_7d(self):
        df = DateFilter.from_freshness("7d")
        assert df.freshness == "pw"

    def test_from_freshness_invalid(self):
        with pytest.raises(ValueError):
            DateFilter.from_freshness("48h")

    def test_from_range(self):
        df = DateFilter.from_range(before="2024-01-01", after="2023-06-01")
        assert df.mode == "range"
        assert df.before.year == 2024
        assert df.after.year == 2023

    def test_to_api_params_freshness(self):
        df = DateFilter(mode="freshness", freshness="pd")
        assert df.to_api_params() == {"freshness": "pd"}

    def test_to_api_params_range(self):
        df = DateFilter(mode="range", before=datetime(2024, 1, 1), after=datetime(2023, 6, 1))
        params = df.to_api_params()
        assert params["before"] == "2024-01-01"
        assert params["after"] == "2023-06-01"

class TestDateFilterCLI:
    def test_valid_freshness(self, runner):
        result = runner.invoke(search, ["test", "--freshness=24h"])
        assert result.exit_code == 0

    def test_invalid_freshness(self, runner):
        result = runner.invoke(search, ["test", "--freshness=invalid"])
        assert result.exit_code == 2
        assert "Invalid freshness value" in result.output

    def test_conflicting_params(self, runner):
        result = runner.invoke(search, ["test", "--freshness=24h", "--before=2024-01-01"])
        assert result.exit_code == 2
        assert "cannot be used with" in result.output
```

### Integration Tests

```python
# tests/test_search_with_date_filter.py

@pytest.mark.asyncio
async def test_search_with_freshness():
    search = Search()
    try:
        results, cache_hit = await search.search(
            "test query",
            count=5,
            date_filter=DateFilter.from_freshness("24h")
        )
        assert results.is_just()
        assert len(results.just_value()) <= 5
    finally:
        await search.close()

@pytest.mark.asyncio
async def test_search_with_date_range():
    search = Search()
    try:
        results, cache_hit = await search.search(
            "test query",
            count=5,
            date_filter=DateFilter.from_range(after="2024-01-01")
        )
        assert results.is_just()
    finally:
        await search.close()
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Invalid date format crashes | Medium | Validate date format before API call, show user-friendly error |
| Cache misses with different date filters | Low | Include date filter in cache key generation |
| Brave API doesn't support date filter for all types | Low | Date filter only applies to `web` and `news`; silently ignored for `images`, `videos` |
| Confusing UX with multiple date params | Medium | Enforce mutual exclusivity with clear error messages |
| Freshness values not matching user expectations | Low | Document clearly: `24h` = past day, `7d` = past week, etc. |

---

## Implementation Roadmap

### Phase 1: Core Implementation (Low Risk)
1. Add `DateFilter` dataclass to `types.py`
2. Add `date_filter` parameter to `BraveClient.web_search()`
3. Add `date_filter` parameter to `Search.search()`
4. Add `--freshness` CLI option to `search` command
5. Add unit tests for `DateFilter`

### Phase 2: Extended CLI (Medium Risk)
1. Add `--before` and `--after` CLI options
2. Add date filter support to `ask` command
3. Update cache key generation to include date filters
4. Add integration tests

### Phase 3: Documentation (Low Risk)
1. Update README with date filtering examples
2. Add date filtering section to command reference

---

## Conclusion

Date range filtering can be implemented by extending the current search architecture with a `DateFilter` dataclass and adding CLI options for `--freshness`, `--before`, and `--after`. The implementation maintains backward compatibility while providing powerful date filtering capabilities. The Brave API's native support for `freshness`, `before`, and `after` parameters ensures minimal API integration complexity.