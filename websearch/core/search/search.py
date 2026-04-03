"""Main search interface combining fetcher, converter, cache, and Brave API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from websearch.core.cache import Cache
from websearch.core.converter import Converter
from websearch.core.fetcher import Fetcher, is_spa
from websearch.core.search.client import BraveApiError, BraveClient
from websearch.core.search.types import SearchResult, SearchResults
from websearch.core.types.maybe import Just, Maybe, Nothing


class SearchError(Exception):
    """Base search error."""
    pass


class Search:
    """Web search and fetch client.

    Orchestrates:
    - Brave Search API for web search
    - Fetcher for HTTP requests
    - Converter for HTML to Markdown
    - Cache for URL and search result caching
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
        cache_enabled: bool = True,
        cache_ttl: int = 7200,
        cache_dir: Path | None = None,
        user_agent: str | None = None,
        verify_ssl: bool = True,
    ):
        """Initialize search client.

        Args:
            api_key: Brave API key (or BRAVE_API_KEY env var)
            timeout: Request timeout in seconds
            cache_enabled: Enable caching
            cache_ttl: Cache TTL in seconds
            cache_dir: Custom cache directory
            user_agent: Custom user agent
        """
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.timeout = timeout
        self.cache = Cache(
            cache_dir=cache_dir,
            enabled=cache_enabled,
        )
        self.converter = Converter()
        self.fetcher = Fetcher(
            timeout=timeout,
            user_agent=user_agent,
            verify_ssl=verify_ssl,
        )

    async def search(
        self,
        query: str,
        count: int = 10,
        search_type: str = "web",
        use_cache: bool = True,
        verbose: bool = False,
    ) -> tuple[Maybe[SearchResults], bool]:
        """Search the web using Brave Search API.

        Args:
            query: Search query
            count: Number of results (1-50)
            search_type: Type of search (web, news, images, videos)
            use_cache: Whether to use cached results
            verbose: Whether to return cache hit/miss info

        Returns:
            Tuple of (Maybe[SearchResults], cache_hit_bool)
        """
        cache_hit = False

        if use_cache:
            cached = self.cache.get_search(query, count, search_type)
            if cached.is_just():
                # Reconstruct SearchResults from cached dict
                data = cached.just_value()
                results = SearchResults(
                    query=data["query"],
                    count=len(data["results"]),
                    results=[SearchResult(**r) for r in data["results"]],
                    raw=data,
                )
                cache_hit = True
                return Just(results), cache_hit

        try:
            async with BraveClient(api_key=self.api_key, timeout=self.timeout) as client:
                results = await client.web_search(query, count, search_type)
        except BraveApiError:
            return Nothing(), cache_hit

        if use_cache:
            self.cache.set_search(query, count, search_type, {
                "query": results.query,
                "results": [
                    {"title": r.title, "url": r.url, "description": r.description, "age": r.age}
                    for r in results.results
                ],
            })

        return Just(results), cache_hit

    async def fetch(
        self,
        url: str,
        refresh: bool = False,
        use_cache: bool = True,
    ) -> Maybe[str]:
        """Fetch URL and convert to Markdown.

        Args:
            url: URL to fetch
            refresh: Skip cache and force fresh fetch
            use_cache: Whether to use cached content

        Returns:
            Just(markdown_string) on success, Nothing on failure
        """
        if use_cache and not refresh:
            cached = self.cache.get_url(url)
            if cached.is_just():
                content, metadata = cached.just_value()
                # If content was rendered via Playwright, it's complete
                if metadata.get("spa_rendering_used"):
                    md = self.converter.to_markdown(content)
                    return md
                # Content wasn't SPA-rendered - re-check if it could be SPA
                if is_spa(content):
                    # Content could be an SPA that needs JavaScript rendering
                    # Try to re-fetch with Playwright
                    result = await self.fetcher.fetch(url)
                    if result.is_ok():
                        rendered = result.ok()
                        if rendered is not None:
                            # Cache the rendered content for next time
                            self.cache.set_url(
                                url,
                                rendered,
                                metadata={"spa_rendering_used": True},
                            )
                            md = self.converter.to_markdown(rendered)
                            return md
                    # Playwright unavailable or failed - don't serve potentially
                    # incomplete content
                    return Nothing()
                # Content is definitely not SPA - safe to use
                md = self.converter.to_markdown(content)
                return md

        result = await self.fetcher.fetch(url)

        if result.is_err():
            return Nothing()

        content = result.ok()
        if content is None:
            return Nothing()

        # Check if content could be an SPA that needs JavaScript rendering
        if is_spa(content):
            # Content needs JavaScript rendering but we don't know if it was
            # actually rendered. To be safe, don't cache potentially incomplete
            # raw HTML content.
            if use_cache and not refresh:
                md = self.converter.to_markdown(content)
                return md
        else:
            # Content is definitely not SPA - safe to cache
            if use_cache and not refresh:
                self.cache.set_url(
                    url,
                    content,
                    metadata={"spa_rendering_used": False},
                )

        md = self.converter.to_markdown(content)
        return md

    async def fetch_raw(
        self,
        url: str,
        refresh: bool = False,
    ) -> Maybe[tuple[bytes, dict[str, Any]]]:
        """Fetch URL content without conversion.

        Args:
            url: URL to fetch
            refresh: Skip cache and force fresh fetch

        Returns:
            Just((content_bytes, metadata_dict)) on success, Nothing on failure
        """
        if not refresh:
            cached = self.cache.get_url(url)
            if cached.is_just():
                return cached

        result = await self.fetcher.fetch(url)

        if result.is_err():
            return Nothing()

        content = result.ok()
        if content is None:
            return Nothing()

        metadata = {
            "url": url,
            "content_length": len(content),
        }

        self.cache.set_url(url, content, metadata)

        return Just((content, metadata))

    async def close(self) -> None:
        """Close client and cleanup resources."""
        await self.fetcher.close()

    async def __aenter__(self) -> Search:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
