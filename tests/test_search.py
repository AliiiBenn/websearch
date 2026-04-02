"""Tests for search module."""

import pytest
from datetime import datetime

from websearch.core.search.types import SearchResult, SearchResults
from websearch.core.search.client import BraveApiError, ApiKeyError, RateLimitError, QuotaExceededError


class TestSearchResult:
    """Tests for SearchResult type."""

    def test_create_search_result(self):
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            description="A test description",
            age="2 days ago",
        )
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.description == "A test description"
        assert result.age == "2 days ago"

    def test_search_result_without_age(self):
        result = SearchResult(
            title="Test",
            url="https://example.com",
            description="Desc",
        )
        assert result.age is None

    def test_from_dict(self):
        data = {
            "title": "From Dict",
            "url": "https://example.com/path",
            "description": "Description",
            "age": "1 week ago",
        }
        result = SearchResult.from_dict(data)
        assert result.title == "From Dict"
        assert result.url == "https://example.com/path"
        assert result.description == "Description"
        assert result.age == "1 week ago"

    def test_from_dict_missing_fields(self):
        data = {}
        result = SearchResult.from_dict(data)
        assert result.title == ""
        assert result.url == ""
        assert result.description == ""
        assert result.age is None


class TestSearchResults:
    """Tests for SearchResults container."""

    def test_create_search_results(self):
        results = [
            SearchResult(title="Result 1", url="https://example.com/1", description="First"),
            SearchResult(title="Result 2", url="https://example.com/2", description="Second"),
        ]
        container = SearchResults(
            query="test query",
            count=2,
            results=results,
            raw={"meta": "data"},
        )
        assert container.query == "test query"
        assert container.count == 2
        assert len(container) == 2

    def test_iterate_results(self):
        results = [
            SearchResult(title=f"Result {i}", url=f"https://example.com/{i}", description=f"Desc {i}")
            for i in range(3)
        ]
        container = SearchResults(query="q", count=3, results=results, raw={})
        titles = [r.title for r in container]
        assert titles == ["Result 0", "Result 1", "Result 2"]

    def test_getitem(self):
        results = [
            SearchResult(title=f"Result {i}", url=f"https://example.com/{i}", description=f"Desc {i}")
            for i in range(3)
        ]
        container = SearchResults(query="q", count=3, results=results, raw={})
        assert container[0].title == "Result 0"
        assert container[2].title == "Result 2"

    def test_cached_at(self):
        now = datetime.now()
        container = SearchResults(
            query="q",
            count=0,
            results=[],
            raw={},
            cached_at=now,
        )
        assert container.cached_at == now


class TestBraveApiErrors:
    """Tests for Brave API error classes."""

    def test_brave_api_error(self):
        error = BraveApiError("API error", status_code=500)
        assert str(error) == "API error"
        assert error.status_code == 500

    def test_api_key_error(self):
        error = ApiKeyError("Invalid API key", status_code=401)
        assert isinstance(error, BraveApiError)
        assert error.status_code == 401

    def test_rate_limit_error(self):
        error = RateLimitError("Rate limited", status_code=429)
        assert isinstance(error, BraveApiError)
        assert error.status_code == 429

    def test_quota_exceeded_error(self):
        error = QuotaExceededError("Quota exceeded", status_code=402)
        assert isinstance(error, BraveApiError)
        assert error.status_code == 402
