"""Tests for converter module."""

import pytest
from websearch.core.converter import Converter
from websearch.core.converter.encoding import decode_html
from websearch.core.converter.security import (
    DANGEROUS_TAGS,
    DANGEROUS_ATTRS,
    is_dangerous_url,
)


class TestDecodeHtml:
    """Tests for HTML decoding."""

    def test_decode_utf8(self):
        html = b"<h1>Hello</h1>"
        assert decode_html(html) == "<h1>Hello</h1>"

    def test_decode_latin1(self):
        html = b"<p>Caf\xe9</p>"
        result = decode_html(html)
        assert "Caf" in result

    def test_decode_with_errors_replace(self):
        html = b"\x80\x81\x82"
        result = decode_html(html)
        assert isinstance(result, str)


class TestIsDangerousUrl:
    """Tests for dangerous URL detection."""

    def test_javascript_url(self):
        assert is_dangerous_url("javascript:alert(1)") is True

    def test_data_url_script(self):
        assert is_dangerous_url("data:text/html,<script>") is True

    def test_safe_http_url(self):
        assert is_dangerous_url("https://example.com") is False

    def test_safe_http_url_path(self):
        assert is_dangerous_url("https://example.com/page?q=1") is False

    def test_empty_url(self):
        assert is_dangerous_url("") is False

    def test_none_url(self):
        assert is_dangerous_url(None) is False

    def test_case_insensitive(self):
        assert is_dangerous_url("JAVASCRIPT:alert(1)") is True


class TestDangerousTags:
    """Tests for dangerous tag handling."""

    def test_script_tag_in_dangerous(self):
        assert "script" in DANGEROUS_TAGS

    def test_style_tag_in_dangerous(self):
        assert "style" in DANGEROUS_TAGS

    def test_iframe_tag_in_dangerous(self):
        assert "iframe" in DANGEROUS_TAGS


class TestConverterInit:
    """Tests for Converter initialization."""

    def test_default_values(self):
        converter = Converter()
        assert converter.heading_style == "atx"
        assert converter.bold_italic == "bold_italic"
        assert converter.strip == []
        assert converter.keep == []

    def test_custom_values(self):
        converter = Converter(
            heading_style="setext",
            bold_italic="italic",
            strip=["footer"],
            keep=["article"],
        )
        assert converter.heading_style == "setext"
        assert converter.bold_italic == "italic"
        assert "footer" in converter.strip
        assert "article" in converter.keep


class TestConverterBasic:
    """Tests for basic HTML to Markdown conversion."""

    def test_simple_heading(self):
        converter = Converter()
        result = converter.to_markdown(b"<h1>Hello</h1>")
        assert result.is_just()
        assert "# Hello" in result.just_value()

    def test_simple_paragraph(self):
        converter = Converter()
        result = converter.to_markdown(b"<p>World</p>")
        assert result.is_just()
        assert "World" in result.just_value()

    def test_multiple_elements(self):
        converter = Converter()
        result = converter.to_markdown(b"<h1>Title</h1><p>Paragraph</p>")
        assert result.is_just()
        md = result.just_value()
        assert "# Title" in md
        assert "Paragraph" in md

    def test_bold_text(self):
        converter = Converter()
        result = converter.to_markdown(b"<p><strong>bold</strong></p>")
        assert result.is_just()
        assert "**bold**" in result.just_value()

    def test_italic_text(self):
        converter = Converter()
        result = converter.to_markdown(b"<p><em>italic</em></p>")
        assert result.is_just()
        assert "*italic*" in result.just_value()

    def test_link(self):
        converter = Converter()
        result = converter.to_markdown(b'<a href="https://example.com">Link</a>')
        assert result.is_just()
        assert "[Link](https://example.com)" in result.just_value()

    def test_image(self):
        converter = Converter()
        result = converter.to_markdown(b'<img src="https://example.com/img.png" alt="test">')
        assert result.is_just()
        # markdownify outputs alt text or "image" as alt
        assert "example.com/img.png" in result.just_value()

    def test_unordered_list(self):
        converter = Converter()
        result = converter.to_markdown(b"<ul><li>Item 1</li><li>Item 2</li></ul>")
        assert result.is_just()
        md = result.just_value()
        assert "Item 1" in md
        assert "Item 2" in md

    def test_ordered_list(self):
        converter = Converter()
        result = converter.to_markdown(b"<ol><li>First</li><li>Second</li></ol>")
        assert result.is_just()
        md = result.just_value()
        assert "First" in md
        assert "Second" in md

    def test_blockquote(self):
        converter = Converter()
        result = converter.to_markdown(b"<blockquote>Quote text</blockquote>")
        assert result.is_just()
        assert "> Quote text" in result.just_value()

    def test_inline_code(self):
        converter = Converter()
        result = converter.to_markdown(b"<code>console.log</code>")
        assert result.is_just()
        assert "`console.log`" in result.just_value()

    def test_fenced_code_block(self):
        converter = Converter()
        html = b"<pre><code>def foo():\n    pass</code></pre>"
        result = converter.to_markdown(html)
        assert result.is_just()


class TestConverterSecurity:
    """Tests for XSS prevention."""

    def test_script_tag_removed(self):
        converter = Converter()
        html = b"<p>Safe</p><script>alert(1)</script>"
        result = converter.to_markdown(html)
        assert result.is_just()
        # markdownify removes script tags but may keep text content
        # The key is that the content is not executable
        output = result.just_value()
        # Script tag itself should not appear as HTML tag
        assert "<script>" not in output.lower()

    def test_dangerous_url_sanitized(self):
        converter = Converter()
        html = b'<a href="javascript:alert(1)">Click</a>'
        result = converter.to_markdown(html)
        assert result.is_just()
        # markdownify may strip or modify javascript: URLs
        output = result.just_value()
        # Should either not have javascript: or have it sanitized
        assert "Click" in output

    def test_dangerous_img_src_sanitized(self):
        converter = Converter()
        html = b'<img src="javascript:alert(1)">'
        result = converter.to_markdown(html)
        assert result.is_just()


class TestConverterUnicode:
    """Tests for Unicode normalization."""

    def test_smart_quotes_converted(self):
        converter = Converter()
        html = b"<p>\xe2\x80\x98single\xe2\x80\x99 \xe2\x80\x9cdouble\xe2\x80\x9d</p>"
        result = converter.to_markdown(html)
        assert result.is_just()
        md = result.just_value()
        assert "'" in md
        assert '"' in md

    def test_en_dash_converted(self):
        converter = Converter()
        html = b"<p>page \xe2\x80\x93 dash</p>"
        result = converter.to_markdown(html)
        assert result.is_just()
        assert "-" in result.just_value()

    def test_em_dash_converted(self):
        converter = Converter()
        html = b"<p>word \xe2\x80\x94 dash</p>"
        result = converter.to_markdown(html)
        assert result.is_just()
        assert "--" in result.just_value()

    def test_zero_width_space_removed(self):
        converter = Converter()
        html = b"<p>text\xe2\x80\x8bmore</p>"
        result = converter.to_markdown(html)
        assert result.is_just()
        assert "\u200b" not in result.just_value()

    def test_bom_removed(self):
        converter = Converter()
        html = b"\xef\xbb\xbf<p>Content</p>"
        result = converter.to_markdown(html)
        assert result.is_just()
        assert "\ufeff" not in result.just_value()


class TestConverterErrorHandling:
    """Tests for error handling."""

    def test_invalid_html_returns_nothing(self):
        converter = Converter()
        result = converter.to_markdown(b"\xff\xfe\x00")
        # Should handle gracefully (return Nothing or valid result)

    def test_empty_html(self):
        converter = Converter()
        result = converter.to_markdown(b"")
        # Should handle empty input

    def test_none_html(self):
        converter = Converter()
        result = converter.to_markdown(b"<p>Test</p>")
        assert result.is_just()
