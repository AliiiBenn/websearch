"""Encoding handling for HTML content."""

from __future__ import annotations


def decode_html(raw: bytes) -> str:
    """Decode HTML, handling encoding issues.

    Args:
        raw: Raw HTML bytes

    Returns:
        Decoded HTML string
    """
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
