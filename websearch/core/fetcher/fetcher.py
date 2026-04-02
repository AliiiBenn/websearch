"""HTTP fetcher with retry logic and SPA detection."""

from __future__ import annotations

import asyncio

import httpx

from websearch.core.fetcher.backoff import calculate_backoff
from websearch.core.fetcher.detection import is_spa
from websearch.core.fetcher.errors import (
    ConnectionError,
    ConnectTimeoutError,
    DNSError,
    ForbiddenError,
    HttpError,
    HttpStatusError,
    HttpTimeoutError,
    InvalidUrlError,
    NotFoundError,
    RateLimitError,
    ReadTimeoutError,
    ServerError,
    TooManyRedirectsError,
)
from websearch.core.types.result import Err, Ok, Result

# Retryable status codes
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Default timeout
DEFAULT_TIMEOUT = 30


class Fetcher:
    """Async HTTP fetcher with retry logic and SPA detection."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str | None = None,
        follow_redirects: bool = True,
        verify_ssl: bool = True,
        max_retries: int = 3,
    ):
        self.timeout = timeout
        self.user_agent = user_agent or "websearch/1.0"
        self.follow_redirects = follow_redirects
        self.verify_ssl = verify_ssl
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._playwright_available: bool | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=self.follow_redirects,
                verify=self.verify_ssl,
                headers={"User-Agent": self.user_agent},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _error_from_response(self, response: httpx.Response, url: str) -> HttpError:
        """Create appropriate error from HTTP response."""
        status = response.status_code

        if status == 404:
            return NotFoundError(f"404 Not Found: {url}", url, status_code=status)
        if status == 403:
            return ForbiddenError(f"403 Forbidden: {url}", url, status_code=status)
        if status == 429:
            return RateLimitError(f"429 Too Many Requests: {url}", url, status_code=status)
        if 500 <= status < 600:
            return ServerError(f"{status} Server Error: {url}", url, status_code=status)

        return HttpStatusError(f"HTTP {status}: {url}", url, status_code=status)

    def _error_from_exception(self, exc: Exception, url: str) -> HttpError:
        """Create appropriate error from exception."""
        if isinstance(exc, httpx.TimeoutException):
            if isinstance(exc, httpx.ConnectTimeout):
                return ConnectTimeoutError(f"Connection timeout: {url}", url)
            if isinstance(exc, httpx.ReadTimeout):
                return ReadTimeoutError(f"Read timeout: {url}", url)
            return HttpTimeoutError(f"Timeout: {url}", url)
        if isinstance(exc, httpx.ConnectError):
            msg = str(exc)
            if "Name or service not known" in msg or "nodename nor servname" in msg:
                return DNSError(f"DNS error: {url}", url)
            return ConnectionError(f"Connection error: {url}", url)
        if isinstance(exc, httpx.TooManyRedirects):
            return TooManyRedirectsError(f"Too many redirects: {url}", url)
        if isinstance(exc, httpx.InvalidURL):
            return InvalidUrlError(f"Invalid URL: {url}", url)

        return ConnectionError(f"Connection error: {exc}", url)

    async def _fetch_one(self, url: str) -> Result[bytes, HttpError]:
        """Fetch a single URL without retry."""
        client = await self._get_client()

        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            return Err(self._error_from_exception(exc, url))

        if not response.is_success:
            return Err(self._error_from_response(response, url))

        return Ok(response.content)

    async def _fetch_with_spa_fallback(self, url: str) -> Result[bytes, HttpError]:
        """Fetch URL, with Playwright fallback for SPAs."""
        result = await self._fetch_one(url)

        if result.is_err():
            return result

        html = result.ok()

        if html is None:
            return Err(ConnectionError("Unexpected null content", url))

        if not is_spa(html):
            return result

        # SPA detected - try Playwright
        if self._playwright_available is None:
            try:
                import playwright  # noqa: F401
                self._playwright_available = True
            except ImportError:
                self._playwright_available = False

        if not self._playwright_available:
            return result

        return await self._fetch_with_playwright(url)

    async def _fetch_with_playwright(self, url: str) -> Result[bytes, HttpError]:
        """Fetch URL using Playwright for JavaScript rendering."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return Err(ConnectionError("Playwright not installed", url))

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=10000)
                        html = await page.content()
                        return Ok(html.encode("utf-8"))
                    finally:
                        await page.close()
                finally:
                    await browser.close()
        except Exception as exc:
            return Err(ConnectionError(f"Playwright error: {exc}", url))

    def _is_retryable_error(self, error: HttpError) -> bool:
        """Determine if an error should be retried."""
        if isinstance(error, RateLimitError):
            return True
        if isinstance(error, ServerError):
            return True
        if isinstance(error, ReadTimeoutError):
            return True
        if isinstance(error, ConnectionError):
            return True
        return False

    async def fetch(self, url: str) -> Result[bytes, HttpError]:
        """Fetch URL with retry logic.

        Args:
            url: The URL to fetch

        Returns:
            Result containing HTML bytes on success, HttpError on failure
        """
        last_error: HttpError | None = None

        for attempt in range(1, self.max_retries + 1):
            result = await self._fetch_with_spa_fallback(url)

            if result.is_ok():
                return result

            error = result.unwrap_err()
            last_error = error

            # Don't retry non-retryable errors
            if not self._is_retryable_error(error):
                return result

            # Don't retry if we've exhausted retries
            if attempt >= self.max_retries:
                return result

            # Sleep before retry
            await asyncio.sleep(calculate_backoff(attempt))

        return Err(last_error) if last_error else Err(
            ConnectionError("Unknown error", url)
        )
