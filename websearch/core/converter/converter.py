"""HTML to Markdown converter with XSS prevention."""

from __future__ import annotations

from markdownify import markdownify as md_convert

from websearch.core.converter.encoding import decode_html
from websearch.core.converter.security import (
    DANGEROUS_TAGS,
    is_dangerous_url,
)
from websearch.core.types.maybe import Just, Maybe, Nothing

# Unicode replacements for smart quotes and special characters
UNICODE_REPLACEMENTS = {
    "\u2018": "'",  # Left single quote
    "\u2019": "'",  # Right single quote
    "\u201c": '"',  # Left double quote
    "\u201d": '"',  # Right double quote
    "\u2013": "-",  # En dash
    "\u2014": "--",  # Em dash
    "\u200b": "",  # Zero-width space
    "\ufeff": "",  # BOM
}


class Converter:
    """Converts HTML content to Markdown format."""

    def __init__(
        self,
        heading_style: str = "atx",
        bold_italic: str = "bold_italic",
        strip: list[str] | None = None,
        keep: list[str] | None = None,
    ):
        """Initialize converter with configuration.

        Args:
            heading_style: "atx" for # headings or "setext" for === headings
            bold_italic: How to render **bold*italic**
            strip: Tags to strip entirely
            keep: Tags to keep with their content
        """
        self.heading_style = heading_style
        self.bold_italic = bold_italic
        self.strip = strip or []
        self.keep = keep or []
        self._config: dict[str, object] = {
            "heading_style": heading_style,
            "bold_italic_style": bold_italic,
            "strip": DANGEROUS_TAGS | set(self.strip),
            "keep": set(self.keep),
        }

    def _normalize_unicode(self, text: str) -> str:
        """Normalize Unicode characters.

        Args:
            text: Text with potential smart quotes

        Returns:
            Text with normalized characters
        """
        for old, new in UNICODE_REPLACEMENTS.items():
            text = text.replace(old, new)
        return text

    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL for href/src attributes.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL or empty string if dangerous
        """
        if is_dangerous_url(url):
            return ""
        return url

    def to_markdown(self, html: bytes) -> Maybe[str]:
        """Convert HTML bytes to Markdown string.

        Args:
            html: Raw HTML content

        Returns:
            Just(markdown_string) on success, Nothing on failure
        """
        try:
            text = decode_html(html)

            # Configure markdownify with XSS prevention
            config = self._config.copy()
            config["strip"] = DANGEROUS_TAGS | set(self.strip)
            config["keep"] = set(self.keep)
            config["a_href_sanitize"] = self._sanitize_url
            config["img_src_sanitize"] = self._sanitize_url

            md = md_convert(text, **config)
            return Just(self._normalize_unicode(md))
        except Exception:
            return Nothing
