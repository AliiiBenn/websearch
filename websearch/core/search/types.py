"""Search result types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class SearchResult:
    """Individual search result."""

    title: str
    url: str
    description: str
    age: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResult:
        """Create from Brave API dict."""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            description=data.get("description", ""),
            age=data.get("age"),
        )


@dataclass
class SearchResults:
    """Container for search results."""

    query: str
    count: int
    results: list[SearchResult]
    raw: dict[str, Any]
    cached_at: datetime | None = None

    def __iter__(self):
        """Iterate over results."""
        return iter(self.results)

    def __len__(self):
        """Number of results."""
        return len(self.results)

    def __getitem__(self, index):
        """Get result by index."""
        return self.results[index]
