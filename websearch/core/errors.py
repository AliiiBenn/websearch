"""HTTP error types for the fetcher."""

from __future__ import annotations


class HttpError(Exception):
    """Base HTTP error."""

    def __init__(
        self,
        message: str,
        url: str,
        *,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.url = url
        self.status_code = status_code

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"{cls}({self.args[0]!r}, url={self.url!r}, status_code={self.status_code!r})"


class NetworkError(HttpError):
    """Network-level error (DNS, connection, etc.)."""

    pass


class DNSError(NetworkError):
    """DNS resolution failed."""

    pass


class ConnectionError(NetworkError):
    """TCP connection failed."""

    pass


class HttpTimeoutError(HttpError):
    """Request timed out."""

    pass


class ConnectTimeoutError(HttpTimeoutError):
    """Connection establishment timed out."""

    pass


class ReadTimeoutError(HttpTimeoutError):
    """Read operation timed out."""

    pass


class InvalidUrlError(HttpError):
    """URL is malformed."""

    pass


class TooManyRedirectsError(HttpError):
    """Too many redirects."""

    pass


class HttpStatusError(HttpError):
    """HTTP response indicated an error."""

    pass


class NotFoundError(HttpStatusError):
    """404 Not Found."""

    pass


class ForbiddenError(HttpStatusError):
    """403 Forbidden."""

    pass


class RateLimitError(HttpStatusError):
    """429 Too Many Requests."""

    pass


class ServerError(HttpStatusError):
    """5xx Server Error."""

    pass
