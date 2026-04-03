# Domain Filtering Implementation Report

## Executive Summary

The websearch CLI currently lacks the ability to filter search results by specific domains (include/exclude). This report analyzes the architecture gap, evaluates implementation options using the Brave Search API's domain filtering capabilities, and provides a detailed recommendation for implementing domain filtering.

**Current State:** The `search` command accepts `query`, `count` (1-50), and `search_type` (web, news, images, videos). No domain filtering parameters are supported.

**Recommendation:** Implement domain filtering at the `BraveClient` level with two new parameters (`include_domains`, `exclude_domains`) passed as Brave API `ddg` parameters. This approach is minimally invasive, backward compatible, and leverages existing API capabilities.

---

## Current Architecture Gap Analysis

### Search Flow

```
CLI (main.py:search)
  -> Search.search() (search.py:65)
    -> BraveClient.web_search() (client.py:96)
      -> HTTP GET to Brave API
```

### Current Parameters

**BraveClient.web_search()** (`client.py:96-164`):
```python
params = {
    "q": query,
    "count": min(max(count, 1), 50),
}
```

**Search.search()** (`search.py:65-116`):
```python
async def search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    use_cache: bool = True,
    verbose: bool = False,
) -> tuple[Maybe[SearchResults], bool]:
```

### Gap: No Domain Filtering

The current implementation has no mechanism to:
1. Include only results from specific domains
2. Exclude results from specific domains
3. Cache results with different domain filters separately

---

## Implementation Options

### Option 1: Client-Level Domain Filtering (Recommended)

Add `include_domains` and `exclude_domains` parameters to `BraveClient.web_search()` and `Search.search()`, passing them as Brave API `ddg` parameters.

**Implementation:**

```python
# In client.py - BraveClient.web_search()
async def web_search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> SearchResults:
    params = {
        "q": query,
        "count": min(max(count, 1), 50),
    }

    # Add domain filtering via ddg parameter
    if include_domains:
        params["ddg"] = f"site:({'|'.join(include_domains)})"
    if exclude_domains:
        params["ddg"] = f"-site:({'|'.join(exclude_domains)})"
```

**Pros:**
- Minimal changes to existing architecture
- Leverages Brave API's built-in filtering
- Backward compatible (parameters are optional)
- Cache can include domain filter in key

**Cons:**
- Limited to Brave API's domain filtering syntax
- Complex filters may hit URL length limits

---

### Option 2: Result-Level Filtering

Fetch all results from API, then filter client-side based on domain rules.

**Implementation:**

```python
async def search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> tuple[Maybe[SearchResults], bool]:

    results, cache_hit = await self._search_impl(
        query, count, search_type
    )

    if results.is_just():
        raw_results = results.just_value()

        # Filter by domain
        filtered = [
            r for r in raw_results.results
            if self._domain_matches(r.url, include_domains, exclude_domains)
        ]

        filtered_results = SearchResults(
            query=raw_results.query,
            count=len(filtered),
            results=filtered,
            raw=raw_results.raw,
        )

        return Just(filtered_results), cache_hit

    return results, cache_hit
```

**Pros:**
- Full control over filtering logic
- Can request more results than needed to compensate for filtering

**Cons:**
- Wasteful API calls if many results are filtered out
- Increases latency and API quota usage
- Cache key complexity increases

---

### Option 3: CLI Wrapper with Pre/Post Processing

Handle domain filtering entirely in the CLI layer by modifying queries.

**Implementation:**

```python
def search_with_domain_filter(query: str, include_domains: list[str]):
    if include_domains:
        domain_query = " OR ".join([f"site:{d}" for d in include_domains])
        query = f"({query}) ({domain_query})"
    # Call standard search
```

**Pros:**
- No changes to core search module
- Easy to prototype

**Cons:**
- Query modification can lead to unexpected behavior
- No separation of concerns
- Difficult to cache correctly

---

## Recommended Approach

**Option 1: Client-Level Domain Filtering** is recommended.

Rationale:
1. **Minimal invasiveness** - Only adds optional parameters
2. **API efficiency** - Filtering happens server-side
3. **Correct caching** - Cache key includes domain filter parameters
4. **Clear separation** - Domain filtering is part of the search request
5. **Backward compatible** - Existing code continues to work

---

## Implementation Details

### 1. Update `SearchResult` type (`types.py`)

Add domain property for convenience:

```python
@dataclass
class SearchResult:
    """Individual search result."""

    title: str
    url: str
    description: str
    age: str | None = None

    @property
    def domain(self) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        return urlparse(self.url).netloc
```

### 2. Update `BraveClient.web_search()` (`client.py`)

```python
async def web_search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> SearchResults:
    # ... existing setup code ...

    params: dict[str, Any] = {
        "q": query,
        "count": min(max(count, 1), 50),
    }

    # Build domain filter via ddg parameter
    if include_domains:
        sites = " OR ".join([f"site:{d}" for d in include_domains])
        params["ddg"] = f"({sites})"
    if exclude_domains:
        exclude_sites = " OR ".join([f"-site:{d}" for d in exclude_domains])
        if "ddg" in params:
            params["ddg"] += f" {exclude_sites}"
        else:
            params["ddg"] = f"({exclude_sites})"
```

### 3. Update `Search.search()` (`search.py`)

```python
async def search(
    self,
    query: str,
    count: int = 10,
    search_type: str = "web",
    use_cache: bool = True,
    verbose: bool = False,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> tuple[Maybe[SearchResults], bool]:
    cache_hit = False

    # Generate cache key including domain filters
    cache_key = self.cache.get_search_key(
        query, count, search_type,
        include_domains=include_domains,
        exclude_domains=exclude_domains
    )

    if use_cache:
        cached = self.cache.get_search(cache_key)
        if cached.is_just():
            # Reconstruct from cached data
            data = cached.just_value()
            results = SearchResults(
                query=data["query"],
                count=len(data["results"]),
                results=[SearchResult(**r) for r in data["results"]],
                raw=data,
            )
            return Just(results), True

    try:
        async with BraveClient(api_key=self.api_key, timeout=self.timeout) as client:
            results = await client.web_search(
                query, count, search_type,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
            )
    except BraveApiError:
        return Nothing(), cache_hit

    if use_cache:
        self.cache.set_search(cache_key, {
            "query": results.query,
            "results": [
                {"title": r.title, "url": r.url, "description": r.description, "age": r.age}
                for r in results.results
            ],
        })

    return Just(results), cache_hit
```

### 4. Update Cache Key Generation (`core/cache/key.py`)

```python
def get_search_key(
    query: str,
    count: int,
    result_type: str = "web",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> str:
    """Get cache filename for search results.

    Args:
        query: Search query
        count: Number of results
        result_type: Type of results (web, news, etc.)
        include_domains: List of domains to include
        exclude_domains: List of domains to exclude

    Returns:
        Cache filename with domain filter hash
    """
    query_hash = get_url_hash(query)

    # Include domain filters in key
    filter_hash = ""
    if include_domains:
        filter_hash += "i:" + ",".join(sorted(include_domains))
    if exclude_domains:
        filter_hash += "e:" + ",".join(sorted(exclude_domains))

    if filter_hash:
        filter_hash = "_" + get_url_hash(filter_hash)[:8]

    return f"{query_hash}_{count}_{result_type}{filter_hash}.json"
```

### 5. Update CLI `search` command (`main.py`)

```python
@main.command()
@click.argument("query")
@click.option("-n", "--count", default=10, help="Number of results (1-50, default: 10)")
@click.option("-t", "--type", "search_type", default="web", help=f"Result type: {', '.join(VALID_SEARCH_TYPES)} (default: web)")
@click.option("--include", "-i", "include_domains", multiple=True, help="Include results from domain (can specify multiple)")
@click.option("--exclude", "-e", "exclude_domains", multiple=True, help="Exclude results from domain (can specify multiple)")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Show results in verbose table format")
@click.option("--no-cache", is_flag=True, help="Disable caching")
def search(
    query: str,
    count: int,
    search_type: str,
    include_domains: tuple[str, ...],
    exclude_domains: tuple[str, ...],
    output: Optional[Path],
    verbose: bool,
    no_cache: bool,
):
    """Search the web using Brave Search API."""
    # ... validation code ...

    async def _search():
        search_client = Search(api_key=api_key, cache_enabled=not no_cache)
        try:
            result, cache_hit = await search_client.search(
                query,
                count=count,
                search_type=search_type,
                use_cache=not no_cache,
                include_domains=list(include_domains) if include_domains else None,
                exclude_domains=list(exclude_domains) if exclude_domains else None,
            )
            # ... rest of implementation ...
```

---

## CLI Usage Examples

### Include Only Specific Domains

```bash
# Search for "Python tutorial" only on python.org and realpython.com
websearch search "Python tutorial" --include python.org --include realpython.com

# Shorthand
websearch search "Python tutorial" -i python.org -i realpython.com
```

### Exclude Specific Domains

```bash
# Search for "news" excluding reddit.com and twitter.com
websearch search "news" --exclude reddit.com --exclude twitter.com

# Shorthand
websearch search "news" -e reddit.com -e twitter.com
```

### Combined Include and Exclude

```bash
# Search for "AI news" on tech sites but exclude certain sources
websearch search "AI news" -i techcrunch.com -i theverge.com -e example-ads.com
```

### With Other Options

```bash
# Domain filtering with verbose output
websearch search "web development" -i mozilla.org -i w3.org --verbose

# Domain filtering with JSON output
websearch search "Python" -i python.org -o results.json

# News search with domain filtering
websearch search "technology" -t news -i reuters.com -i associatedpress.com
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_search.py

class TestDomainFiltering:
    """Tests for domain filtering functionality."""

    def test_search_result_domain_property(self):
        result = SearchResult(
            title="Test",
            url="https://docs.python.org/3/tutorial/",
            description="Python tutorial",
        )
        assert result.domain == "docs.python.org"

    def test_search_result_subdomain(self):
        result = SearchResult(
            title="Blog",
            url="https://blog.python.org/2024/01/news.html",
            description="Python blog",
        )
        assert result.domain == "blog.python.org"

    def test_include_domains_filter(self):
        # Test that domain filtering is passed to API
        # (mock the BraveClient)
        pass

    def test_exclude_domains_filter(self):
        # Test that domain exclusion is passed to API
        pass
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_search_with_include_domains():
    """Integration test for include domain filtering."""
    search = Search()
    result, cache_hit = await search.search(
        "Python tutorial",
        count=5,
        include_domains=["python.org"],
    )
    assert result.is_just()
    results = result.just_value()
    for r in results:
        assert "python.org" in r.url

@pytest.mark.asyncio
async def test_search_with_exclude_domains():
    """Integration test for exclude domain filtering."""
    search = Search()
    result, cache_hit = await search.search(
        "news",
        count=10,
        exclude_domains=["reddit.com"],
    )
    assert result.is_just()
    results = result.just_value()
    for r in results:
        assert "reddit.com" not in r.url
```

### Cache Tests

```python
def test_cache_key_includes_domain_filters():
    """Test that cache keys differ for different domain filters."""
    key1 = get_search_key("query", 10, "web", include_domains=["example.com"])
    key2 = get_search_key("query", 10, "web", include_domains=["other.com"])
    key3 = get_search_key("query", 10, "web", exclude_domains=["example.com"])

    assert key1 != key2
    assert key1 != key3
    assert key2 != key3

def test_cache_key_same_domain_filter():
    """Test that same domain filters produce same cache key."""
    key1 = get_search_key("query", 10, "web", include_domains=["example.com"])
    key2 = get_search_key("query", 10, "web", include_domains=["example.com"])
    assert key1 == key2
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Brave API does not support requested filter syntax | Medium | Use alternative `site:` operator syntax in `ddg` parameter |
| URL length limits with many domain filters | Low | Document maximum of ~10 domains per filter; add validation |
| Cache fragmentation from many filter combinations | Low | Use TTL-based cache expiration; document cache behavior |
| Domain matching edge cases (subdomains, ports) | Medium | Implement proper URL parsing; normalize domains before comparison |
| Case sensitivity in domain matching | Low | Always lowercase domains for comparison and filtering |

---

## Summary of Required Changes

| File | Changes |
|------|---------|
| `websearch/core/search/types.py` | Add `domain` property to `SearchResult` |
| `websearch/core/search/client.py` | Add `include_domains`, `exclude_domains` params to `web_search()` |
| `websearch/core/search/search.py` | Add `include_domains`, `exclude_domains` params to `search()`; update cache key |
| `websearch/core/cache/key.py` | Update `get_search_key()` to include domain filters |
| `websearch/main.py` | Add `-i/--include` and `-e/--exclude` CLI options to `search` command |
| `tests/test_search.py` | Add tests for domain filtering and cache key generation |

---

## Conclusion

Domain filtering is a low-priority but useful feature that can be implemented with minimal changes to the existing architecture. The recommended approach leverages Brave API's built-in `ddg` parameter for server-side filtering, ensuring efficiency and backward compatibility. Implementation can be completed in a single phase with approximately 150-200 lines of code across 6 files.