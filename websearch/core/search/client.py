"""Brave Search API client."""

from __future__ import annotations

import os
from typing import Any

import httpx

from websearch.core.search.types import SearchResults, SearchResult


class BraveApiError(Exception):
    """Base Brave API error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ApiKeyError(BraveApiError):
    """Missing or invalid API key."""

    pass


class RateLimitError(BraveApiError):
    """Too many requests."""

    pass


class QuotaExceededError(BraveApiError):
    """API quota exceeded."""

    pass


class BraveClient:
    """Client for Brave Search API."""

    BASE_URL = "https://api.search.brave.com/res/v1"

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        """Initialize Brave client.

        Args:
            api_key: Brave API key (or BRAVE_API_KEY env var)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "Accept": "application/json",
            }
            if self.api_key:
                headers["X-Subscription-Token"] = self.api_key

            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BraveClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _handle_error(self, status_code: int, response: dict[str, Any]) -> None:
        """Handle API error response."""
        error_msg = response.get("message", "Unknown error")

        if status_code == 401:
            raise ApiKeyError(f"Invalid or missing API key: {error_msg}", status_code)
        if status_code == 429:
            raise RateLimitError(f"Rate limited: {error_msg}", status_code)
        if status_code == 402:
            raise QuotaExceededError(f"Quota exceeded: {error_msg}", status_code)

        raise BraveApiError(f"API error: {error_msg}", status_code)

    async def web_search(
        self,
        query: str,
        count: int = 10,
        search_type: str = "web",
    ) -> SearchResults:
        """Search the web using Brave Search API.

        Args:
            query: Search query
            count: Number of results (1-50)
            search_type: Type of search (web, news, images, videos)

        Returns:
            SearchResults container

        Raises:
            ApiKeyError: Missing or invalid API key
            RateLimitError: Too many requests
            QuotaExceededError: API quota exceeded
            BraveApiError: Other API errors
        """
        client = await self._get_client()

        # Map search type to Brave API parameter
        if search_type == "web":
            endpoint = "web/search"
        elif search_type == "news":
            endpoint = "news/search"
        elif search_type == "images":
            endpoint = "images/search"
        elif search_type == "videos":
            endpoint = "videos/search"
        else:
            endpoint = "web/search"

        params = {
            "q": query,
            "count": min(max(count, 1), 50),  # Clamp to 1-50
        }

        try:
            response = await client.get(endpoint, params=params)
        except httpx.HTTPError as exc:
            raise BraveApiError(f"Request failed: {exc}")

        status_code = response.status_code

        if status_code == 200:
            data = response.json()
            # Results are nested under "web" key for web search
            web_results = data.get("web", {}).get("results", [])
            results = [
                SearchResult.from_dict(item)
                for item in web_results
            ]
            return SearchResults(
                query=query,
                count=len(results),
                results=results,
                raw=data,
            )
        else:
            try:
                error_data = response.json()
            except Exception:
                error_data = {}

            self._handle_error(status_code, error_data)
