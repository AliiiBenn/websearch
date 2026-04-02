# Converter Feature

## Overview

The converter transforms HTML content to Markdown format using selectolax for parsing and markdownify for conversion.

## Architecture

```
HTML bytes
    │
    ▼
┌─────────────────────┐
│     Converter       │
└─────────────────────┘
    │
    ▼
Maybe[str]
```

## API

### Converter

```python
from websearch.core import Converter

converter = Converter()

result = converter.to_markdown(html_bytes)

match result:
    case Just(md):
        print(md)
    case Nothing:
        print("Failed to convert")
```

### Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| heading_style | str | "atx" | ATX (#) or setex (===) headings |
| bold_italic | str | "bold_italic" | How to render **bold*italic** |
| strip | list[str] | [] | Tags to strip |
| keep | list[str] | [] | Tags to keep with content |

## Methods

### `to_markdown(html) -> Maybe[str]`

Converts HTML bytes to Markdown string.

**Parameters:**
- `html` (bytes) - Raw HTML content

**Returns:** `Maybe[str]` - Markdown on success, Nothing on failure

## Features

### What Gets Converted

- Headings (h1-h6)
- Paragraphs and line breaks
- Bold and italic text
- Links and images
- Lists (ordered and unordered)
- Blockquotes
- Code blocks (inline and fenced)
- Tables
- Horizontal rules

### What Gets Removed

- Scripts and styles
- Navigation elements (nav, header, footer)
- Comments
- Empty elements

## Security

### XSS Prevention

The converter removes dangerous elements and attributes:

```python
# Tags removed entirely
DANGEROUS_TAGS = {"script", "style", "iframe", "object", "embed", "form"}

# Attributes removed
DANGEROUS_ATTRS = {"onerror", "onclick", "onload", "onmouseover"}
```

JavaScript URLs (javascript:, data: with script) are stripped from href/src.

## Encoding

The converter handles common encoding issues:

1. Try UTF-8 first
2. Fall back to latin-1
3. Use errors="replace" for unrecoverable encoding

```python
def _decode_html(self, raw: bytes) -> str:
    """Decode HTML, handling encoding issues."""
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")
```

## Unicode Handling

Smart quotes and special characters are normalized:

```python
def _normalize_unicode(self, md: str) -> str:
    """Normalize Unicode characters."""
    replacements = {
        "\u2018": "'",  # Left single quote
        "\u2019": "'",  # Right single quote
        "\u201c": '"',  # Left double quote
        "\u201d": '"',  # Right double quote
        "\u2013": "-",  # En dash
        "\u2014": "--", # Em dash
        "\u200b": "",   # Zero-width space
        "\ufeff": "",   # BOM
    }
    for old, new in replacements.items():
        md = md.replace(old, new)
    return md
```

## Error Handling

Conversion returns `Nothing` on failure:

```python
async def to_markdown(self, html: bytes) -> Maybe[str]:
    try:
        tree = selectolax_parser(html)
        md = markdownify(tree, **self.config)
        return Just(self._normalize_unicode(md))
    except Exception:
        return Nothing
```

## Usage Examples

### Basic Conversion

```python
from websearch.core import Converter

converter = Converter()
result = converter.to_markdown(b"<h1>Hello</h1><p>World</p>")

if result.is_just():
    print(result.just_value())
```

### With Error Handling

```python
from websearch.core import Converter
from websearch.core.types.maybe import Nothing

converter = Converter()
result = converter.to_markdown(b"<html>...")

match result:
    case Just(md):
        print("Converted successfully")
    case Nothing:
        print("Conversion failed")
```

### Custom Configuration

```python
converter = Converter(
    heading_style="setext",  # Use === for h1, --- for h2
    keep=["article"],       # Keep article tag content
)
```

## Dependencies

```toml
dependencies = [
    "selectolax>=0.3",
    "markdownify>=0.12",
]
```

## Limitations

- Complex JavaScript-rendered content requires fetcher SPA detection
- Some site-specific HTML may need custom handling
- PDF content is not supported (handled by fetcher)
