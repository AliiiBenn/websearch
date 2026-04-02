"""Tests for fetcher module."""

import pytest
from websearch.core.errors import (
    ConnectTimeoutError,
    ConnectionError,
    DNSError,
    ForbiddenError,
    HttpError,
    HttpTimeoutError,
    InvalidUrlError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ReadTimeoutError,
    ServerError,
    TooManyRedirectsError,
)
from websearch.core.fetcher import Fetcher, calculate_backoff, is_spa


class TestCalculateBackoff:
    """Tests for backoff calculation."""

    def test_first_attempt(self):
        assert calculate_backoff(1) == 0.5

    def test_second_attempt(self):
        assert calculate_backoff(2) == 1.0

    def test_third_attempt(self):
        assert calculate_backoff(3) == 2.0

    def test_fourth_attempt(self):
        assert calculate_backoff(4) == 4.0

    def test_custom_base(self):
        assert calculate_backoff(3, base=1.0) == 4.0


class TestIsSpa:
    """Tests for SPA detection."""

    def test_minimal_content(self):
        html = b"<html><body></body></html>"
        assert is_spa(html) is True

    def test_small_content(self):
        html = b"<html><head></head><body>Hi</body></html>"
        assert is_spa(html) is True

    def test_react_marker(self):
        html = b"<html><body><div id='root'></div><script src='react.js'></script></body></html>"
        html += b"x" * 500  # Make it large enough
        assert is_spa(html) is True

    def test_vue_marker(self):
        html = b"<html><body><div id='app'></div><script src='vue.js'></script></body></html>"
        html += b"x" * 500
        assert is_spa(html) is True

    def test_angular_marker(self):
        html = b"<html><body ng-app='myApp'><div ng-controller='MainCtrl'></div></body></html>"
        html += b"x" * 500
        assert is_spa(html) is True

    def test_data_vue_attribute(self):
        html = b"<html><body><div data-vue='true'></div></body></html>"
        html += b"x" * 500
        assert is_spa(html) is True

    def test_ng_app_attribute(self):
        html = b"<html><body ng-app='myApp'></body></html>"
        html += b"x" * 500
        assert is_spa(html) is True

    def test_normal_html(self):
        # HTML large enough to not trigger minimal content check
        html = b"""<html>
        <head><title>Test</title></head>
        <body>
        <h1>Hello World</h1>
        <p>This is a normal HTML page with actual content.</p>
        <article>
            <h2>Article Title</h2>
            <p>Lots of content here...</p>
        </article>
        </body>
        </html>""" + b"x" * 600  # Pad to >500 bytes
        assert is_spa(html) is False

    def test_with_lots_of_javascript(self):
        # Even with JS, if it has content, it's not necessarily SPA
        html = b"""<html><body>
        <h1>Content Page</h1>
        <p>Actual content here</p>
        <script src="analytics.js"></script>
        <script src="jquery.min.js"></script>
        </body></html>""" + b"x" * 600  # Pad to >500 bytes
        assert is_spa(html) is False


class TestFetcherInit:
    """Tests for Fetcher initialization."""

    def test_default_values(self):
        fetcher = Fetcher()
        assert fetcher.timeout == 30
        assert fetcher.user_agent == "websearch/1.0"
        assert fetcher.follow_redirects is True
        assert fetcher.verify_ssl is True
        assert fetcher.max_retries == 3

    def test_custom_values(self):
        fetcher = Fetcher(
            timeout=60,
            user_agent="CustomBot/1.0",
            follow_redirects=False,
            verify_ssl=False,
            max_retries=5,
        )
        assert fetcher.timeout == 60
        assert fetcher.user_agent == "CustomBot/1.0"
        assert fetcher.follow_redirects is False
        assert fetcher.verify_ssl is False
        assert fetcher.max_retries == 5


class TestFetcherErrorTypes:
    """Tests for error type hierarchy."""

    def test_network_error_is_base(self):
        assert issubclass(NetworkError, HttpError)

    def test_server_error_is_http_status(self):
        assert issubclass(ServerError, HttpError)

    def test_not_found_error(self):
        error = NotFoundError("404", "https://example.com", status_code=404)
        assert error.status_code == 404
        assert error.url == "https://example.com"

    def test_rate_limit_error(self):
        error = RateLimitError("429", "https://example.com", status_code=429)
        assert error.status_code == 429

    def test_forbidden_error(self):
        error = ForbiddenError("403", "https://example.com", status_code=403)
        assert error.status_code == 403

    def test_server_error(self):
        error = ServerError("500", "https://example.com", status_code=500)
        assert error.status_code == 500

    def test_dns_error(self):
        error = DNSError("DNS failed", "https://example.com")
        assert isinstance(error, NetworkError)
        assert isinstance(error, HttpError)

    def test_connection_error(self):
        error = ConnectionError("Connection refused", "https://example.com")
        assert isinstance(error, NetworkError)
        assert isinstance(error, HttpError)

    def test_connect_timeout_error(self):
        error = ConnectTimeoutError("Connection timeout", "https://example.com")
        assert isinstance(error, HttpTimeoutError)
        assert isinstance(error, HttpError)

    def test_read_timeout_error(self):
        error = ReadTimeoutError("Read timeout", "https://example.com")
        assert isinstance(error, HttpTimeoutError)
        assert isinstance(error, HttpError)

    def test_invalid_url_error(self):
        error = InvalidUrlError("Invalid URL", "not-a-url")
        assert isinstance(error, HttpError)

    def test_too_many_redirects_error(self):
        error = TooManyRedirectsError("Too many redirects", "https://example.com")
        assert isinstance(error, HttpError)

    def test_error_repr(self):
        error = NotFoundError("404 Not Found", "https://example.com", status_code=404)
        assert "NotFoundError" in repr(error)
        assert "example.com" in repr(error)
