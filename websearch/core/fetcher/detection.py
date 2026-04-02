"""SPA detection heuristics."""

from __future__ import annotations

# JavaScript frameworks that indicate a SPA
SPAMARKERS = [
    b"react",
    b"vue.js",
    b"angular",
    b"next",
    b"nuxt",
]

# HTML attributes that indicate dynamic content
DYNAMIC_ATTRIBUTES = [
    b"data-vue",
    b"ng-app",
    b"data-reactroot",
    b"data-ng-app",
]


def is_spa(html: bytes) -> bool:
    """Detect if page is likely a SPA based on content.

    A page is considered a SPA when:
    1. Content is minimal (<500 bytes)
    2. Contains JavaScript framework markers
    3. Contains dynamic content attributes

    Args:
        html: Raw HTML content

    Returns:
        True if page is likely a SPA
    """
    if len(html) < 500:
        return True

    content_lower = html.lower()

    # Check for framework markers
    for marker in SPAMARKERS:
        if marker in content_lower:
            return True

    # Check for dynamic attributes
    for attr in DYNAMIC_ATTRIBUTES:
        if attr in content_lower:
            return True

    return False
