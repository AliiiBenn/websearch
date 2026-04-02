"""Security utilities for XSS prevention."""

from __future__ import annotations

# Tags removed entirely during conversion
DANGEROUS_TAGS = {"script", "style", "iframe", "object", "embed", "form"}

# Attributes removed during conversion
DANGEROUS_ATTRS = {"onerror", "onclick", "onload", "onmouseover"}

# URL schemes that are dangerous
DANGEROUS_URL_SCHEMES = {"javascript", "data"}


def is_dangerous_url(url: str) -> bool:
    """Check if URL has dangerous scheme.

    Args:
        url: URL to check

    Returns:
        True if URL has dangerous scheme
    """
    if not url:
        return False
    lower = url.lower().strip()
    for scheme in DANGEROUS_URL_SCHEMES:
        if lower.startswith(f"{scheme}:"):
            return True
    return False
