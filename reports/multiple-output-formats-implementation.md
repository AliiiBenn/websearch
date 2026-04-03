# Multiple Output Formats Implementation Report

## Executive Summary

The websearch CLI needs to support multiple output formats to enable better integration with other tools and workflows. This report analyzes the requirements, evaluates implementation approaches, and provides detailed guidance for adding JSON, Markdown, HTML, and plain text output modes.

**Current State:** The CLI outputs formatted text to the console. JSON output is needed for scripting and API integration.

**Recommendation:** Implement a `--format` / `-f` flag with support for `json`, `markdown`, `html`, and `text` formats, using a consistent internal data structure that can be rendered to any format.

---

## Current Architecture Gap

### Current Output Patterns

The CLI currently uses Rich console output for formatted display:

```python
# Current output in main.py
console.print(result.answer)  # Plain text output
console.print(sources_table)  # Rich table
console.print(metadata_table) # Rich metadata
```

**Problems:**
- Output is tightly coupled to console display
- No programmatic/API output mode
- Piping to other tools breaks with Rich formatting
- No machine-readable output option

---

## Implementation Options

### Option 1: Add `--json` Flag

**Approach:** Add a `--json` flag that outputs the raw data structure as JSON.

```python
@click.option("--json", is_flag=True, help="Output as JSON")
def ask(query, json, ...):
    if json:
        output_data = result.to_dict()
        console.print_json(json.dumps(output_data))
```

**Pros:** Simple to implement, useful for scripting

**Cons:** Only JSON, no other formats, breaks existing verbose output

### Option 2: Add `--format` with Choices

**Approach:** Add `--format` with choices: `console`, `json`, `markdown`, `html`, `text`.

```python
@click.option("--format", "-f", type=click.Choice(["console", "json", "markdown", "html", "text"]), default="console")
def ask(query, format, ...):
    if format == "json":
        output_json()
    elif format == "markdown":
        output_markdown()
    # etc.
```

**Pros:** Flexible, clear UX, extensible

**Cons:** More implementation work, need renderers for each format

### Option 3: Unified Output Structure with Renderers

**Approach:** Create an internal `Output` dataclass with all data, then use format-specific renderers.

```python
@dataclass
class CommandOutput:
    answer: str
    sources: list[dict]
    metadata: dict
    cache_hit: bool

def render_json(output: CommandOutput) -> str: ...
def render_markdown(output: CommandOutput) -> str: ...
def render_html(output: CommandOutput) -> str: ...
```

**Pros:** Clean separation, easy to add formats, testable

**Cons:** Most complex initial design

---

## Recommended Approach

**Use Option 3: Unified Output Structure with Renderers**

Rationale:
1. **Extensibility** - Easy to add new formats (XML, PDF, etc.)
2. **Testability** - Renderers can be unit tested independently
3. **Consistency** - All commands use same structure
4. **Clean Architecture** - Data and presentation are separated

---

## Implementation Details

### 1. Create Output Dataclass

```python
# websearch/core/output.py

from dataclasses import dataclass, field
from typing import Any

@dataclass
class CommandOutput:
    """Unified output structure for all commands."""
    answer: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    cache_hit: bool = False
    model: str = ""
    num_results: int = 0
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "metadata": self.metadata,
            "cache_hit": self.cache_hit,
            "model": self.model,
            "num_results": self.num_results,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_cost_usd": self.total_cost_usd,
        }
```

### 2. Create Renderers

```python
# websearch/core/renderers.py

import json
from typing import TextIO

def render_json(output: CommandOutput, file: TextIO | None = None) -> str:
    """Render output as JSON."""
    data = output.to_dict()
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    if file:
        file.write(json_str)
    return json_str

def render_markdown(output: CommandOutput, file: TextIO | None = None) -> str:
    """Render output as Markdown."""
    lines = []

    lines.append(f"## Answer\n\n{output.answer}\n")

    if output.sources:
        lines.append("## Sources\n")
        for i, s in enumerate(output.sources, 1):
            lines.append(f"{i}. [{s['title']}]({s['url']})")
        lines.append("")

    if output.metadata:
        lines.append("## Metadata\n")
        for k, v in output.metadata.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    if file:
        file.write("\n".join(lines))
    return "\n".join(lines)

def render_html(output: CommandOutput, file: TextIO | None = None) -> str:
    """Render output as HTML."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Websearch Result</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; }}
        .source {{ margin: 1rem 0; }}
        .metadata {{ color: #666; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <article>
        <pre>{output.answer}</pre>
    </article>
    <footer class="metadata">
        <p>Model: {output.model} | Cache: {'hit' if output.cache_hit else 'miss'}</p>
    </footer>
</body>
</html>"""
    if file:
        file.write(html)
    return html

def render_text(output: CommandOutput, file: TextIO | None = None) -> str:
    """Render output as plain text."""
    lines = []

    lines.append("ANSWER")
    lines.append("=" * 50)
    lines.append(output.answer)
    lines.append("")

    if output.sources:
        lines.append("SOURCES")
        lines.append("=" * 50)
        for i, s in enumerate(output.sources, 1):
            lines.append(f"{i}. {s['title']}")
            lines.append(f"   {s['url']}")
        lines.append("")

    text = "\n".join(lines)
    if file:
        file.write(text)
    return text
```

### 3. Update CLI Commands

```python
# In main.py

from websearch.core.output import CommandOutput
from websearch.core.renderers import render_json, render_markdown, render_html, render_text

@click.option("--format", "-f",
              type=click.Choice(["console", "json", "markdown", "html", "text"]),
              default="console",
              help="Output format")
def ask(query, count, no_cache, output, verbose, format, model, max_turns):
    # ... existing logic ...

    # Build unified output
    result_output = CommandOutput(
        answer=result.answer,
        sources=result.sources,
        metadata={...},
        cache_hit=result.cached,
        model=result.model,
        num_results=result.num_results,
        duration_ms=result.duration_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_cost_usd=result.total_cost_usd,
    )

    # Render based on format
    if format == "json":
        render_json(result_output, sys.stdout)
    elif format == "markdown":
        render_markdown(result_output, sys.stdout)
    elif format == "html":
        render_html(result_output, sys.stdout)
    elif format == "text":
        render_text(result_output, sys.stdout)
    else:
        # console - existing Rich output
        console.print(result.answer)
```

---

## Auto-Detection of Output Format

### Detect Piping to stdout

```python
import sys

def should_use_json() -> bool:
    """Auto-detect if JSON output should be used."""
    # If stdout is not a TTY, probably piping to another tool
    if not sys.stdout.isatty():
        return True
    # Check for CI environment
    if os.environ.get("CI") == "true":
        return True
    return False

# In command
if should_use_json() and format == "console":
    format = "json"
```

---

## JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "answer": {
      "type": "string",
      "description": "The synthesized answer"
    },
    "sources": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "url": {"type": "string", "format": "uri"},
          "description": {"type": "string"}
        }
      }
    },
    "metadata": {
      "type": "object"
    },
    "cache_hit": {
      "type": "boolean"
    },
    "model": {
      "type": "string"
    },
    "num_results": {
      "type": "integer"
    },
    "duration_ms": {
      "type": "integer"
    },
    "input_tokens": {
      "type": "integer"
    },
    "output_tokens": {
      "type": "integer"
    },
    "total_cost_usd": {
      "type": "number"
    }
  }
}
```

---

## Testing Strategy

```python
# tests/test_renderers.py

def test_render_json():
    output = CommandOutput(answer="Test answer")
    result = render_json(output)
    parsed = json.loads(result)
    assert parsed["answer"] == "Test answer"

def test_render_markdown():
    output = CommandOutput(answer="Test answer")
    result = render_markdown(output)
    assert "## Answer" in result
    assert "Test answer" in result

def test_render_html():
    output = CommandOutput(answer="<script>bad</script>")
    result = render_html(output)
    assert "<script>" not in result  # XSS protection
    assert "&lt;script&gt;" in result  # Escaped
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| XSS in HTML output | Sanitize HTML, escape user content |
| Breaking existing users | Keep console as default format |
| Inconsistent formatting | Unit test all renderers |

---

## Conclusion

A unified output structure with format-specific renderers provides the most flexibility and maintainability. The implementation should:
1. Create `CommandOutput` dataclass for all command data
2. Implement format-specific renderers
3. Add `--format` flag with auto-detection for piping
4. Output JSON schema documentation
