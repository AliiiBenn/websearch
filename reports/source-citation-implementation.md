# Source Citation Implementation Report

## Executive Summary

The websearch CLI `ask` command currently provides numbered source references `[1]`, `[2]`, etc. to the AI model during prompt construction, but the resulting answer text contains no inline citation markers. Sources are displayed only as a separate Rich table in verbose mode, disconnected from the answer content.

**Current State:** Sources are passed as numbered context `[1] Wikipedia\nhttps://...\nDescription...` but the model returns unmarked text, leaving users unable to verify which claims came from which sources.

**Recommendation:** Implement a **hybrid approach** combining prompt engineering with post-processing validation. This ensures citations are included in the model's response while maintaining robustness against hallucinated or malformed citations.

---

## 1. Current Architecture Gap

### 1.1 How Sources Are Currently Handled

**Code Location:** `C:\Users\dpereira\Documents\github\websearch\websearch\core\agent\claude_client.py`

**Source Context Construction (lines 137-143):**
```python
context_parts = []
for i, s in enumerate(sources[:count], 1):
    content_preview = s.get("content", "")[:500]
    context_parts.append(f"[{i}] {s['title']}\n{s['url']}\n{s.get('description', '')}\n{content_preview}...")

context = "\n\n---\n\n".join(context_parts)
```

**Prompt Sent to Model (lines 165-173):**
```python
prompt = f"""You are a helpful assistant that answers questions based on web search results.

Question: {query}

Web Search Results:
{context}

Based on the search results above, provide a comprehensive answer to the question.
Format your response in clear Markdown."""
```

### 1.2 Current Data Structures

**AskResult dataclass (lines 34-50):**
```python
@dataclass
class AskResult:
    """Result from ask_with_search."""
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    cached: bool = False
    model: str = "MiniMax-M2.7"
    num_results: int = 0
    # Metadata fields
    duration_ms: int | None = None
    duration_api_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost_usd: float | None = None
    num_turns: int | None = None
    stop_reason: str | None = None
```

**Source Structure:**
```python
{
    "title": str,      # e.g., "Wikipedia - Python (programming language)"
    "url": str,        # e.g., "https://en.wikipedia.org/wiki/Python_(programming_language)"
    "description": str, # e.g., "Python is a high-level general-purpose..."
    "content": str     # Full markdown content (only in memory, not cached)
}
```

### 1.3 Current Output Flow

In `main.py` (lines 291-303):
```python
# Output result - only answer text is printed
if output:
    output.write_text(result.answer)
    if verbose:
        console.print(f"[green]Saved to {output}[/green]")
else:
    console.print(result.answer)
```

In verbose mode, sources are displayed separately (lines 234-256):
```python
sources_table = Table(title="Sources", ...)
for i, s in enumerate(result.sources, 1):
    sources_table.add_row(str(i), s["title"], s["url"], ...)
console.print(sources_table)
```

### 1.4 Identified Gaps

| Gap | Description |
|-----|-------------|
| No inline citations | Answer text has no citation markers, even though sources are numbered in context |
| Disconnected display | Sources shown separately in Rich table, not linked to answer claims |
| No citation format | No standard citation syntax (e.g., `[1]`, `[^1]`, or footnotes) |
| No validation | No mechanism to verify citations match actual sources |

---

## 2. Implementation Options

### Option 1: Prompt Engineering Only

**Approach:** Modify the system prompt to explicitly instruct the model to include citations in a specific format.

**Prompt Modification:**
```python
prompt = f"""You are a helpful assistant that answers questions based on web search results.

Question: {query}

Web Search Results:
{context}

Based on the search results above, provide a comprehensive answer to the question.
IMPORTANT: You MUST cite your sources using inline citation markers in the format [1], [2], etc.
corresponding to the numbered sources above. Every factual claim should have a citation.
Format your response in clear Markdown."""
```

**Pros:**
- Minimal code changes
- Leverages model's inherent citation capability
- No post-processing complexity

**Cons:**
- Unreliable - model may hallucinate citations
- No validation of citation accuracy
- Inconsistent output format
- Requires careful prompt engineering

---

### Option 2: Post-Processing Only

**Approach:** After receiving the answer, parse it and inject citation markers based on content matching with sources.

```python
def inject_citations(answer: str, sources: list[dict[str, Any]]) -> str:
    """Parse answer and inject citation markers based on source content matching."""
    cited_answer = answer

    for i, source in enumerate(sources, 1):
        # Simple approach: look for source titles or key phrases
        title = source["title"]
        # Remove source number suffix like " - Wikipedia" for matching
        base_title = re.sub(r'\s*[-|].*$', '', title)

        # Replace first occurrence of title-like text with [i] title
        pattern = re.compile(re.escape(base_title), re.IGNORECASE)
        if pattern.search(cited_answer):
            cited_answer = pattern.sub(f"[{i}] {base_title}", cited_answer, count=1)

    return cited_answer
```

**Pros:**
- Full control over citation format
- Deterministic output
- Can validate citations against sources

**Cons:**
- Complex content matching is error-prone
- May incorrectly match or miss matches
- Loses semantic understanding of which claims came from which sources

---

### Option 3: Hybrid Approach (Recommended)

**Approach:** Combine prompt engineering with post-processing validation.

**Step 1 - Prompt Engineering:**
```python
prompt = f"""You are a helpful assistant that answers questions based on web search results.

Question: {query}

Web Search Results:
{context}

Instructions:
1. Answer the question based on the sources provided.
2. Use inline citation markers in the format [1], [2], etc. after each factual claim.
3. Place citations immediately after the claim, before punctuation when possible.
4. Multiple claims from the same source can share a citation: "fact1 [1], fact2 [1]".
5. If a claim cannot be verified by a source, do not make that claim.

Example format:
"The Python language [1] was created by Guido van Rossum [1] and is known for its readability [2]."

Format your response in clear Markdown."""
```

**Step 2 - Validation with Correction:**
```python
def validate_and_format_citations(
    answer: str,
    sources: list[dict[str, Any]],
    strict: bool = False
) -> tuple[str, list[str]]:
    """Validate citations in answer and format for display.

    Returns:
        tuple of (formatted_answer, list_of_warnings)
    """
    warnings = []
    formatted = answer

    # Pattern to find citation markers
    citation_pattern = re.compile(r'\[(\d+)\]')
    found_citations = set(citation_pattern.findall(formatted))

    # Validate citation numbers are in range
    max_source_num = len(sources)
    for cite_num in found_citations:
        if int(cite_num) > max_source_num:
            warnings.append(f"Citation [{cite_num}] exceeds number of sources ({max_source_num})")
            if strict:
                # Remove invalid citation
                formatted = formatted.replace(f"[{cite_num}]", "")

    # Optional: Add source reference section at end
    if found_citations and not formatted.rstrip().endswith("]"):
        formatted += "\n\n---\n\n**Sources:**\n"
        for i, source in enumerate(sources, 1):
            if str(i) in found_citations:
                formatted += f"[{i}] {source['title']} - {source['url']}\n"

    return formatted, warnings
```

**Pros:**
- Balances reliability with flexibility
- Model provides semantic citations
- Post-processing validates and corrects
- Configurable strictness level

**Cons:**
- More complex than single approaches
- Requires careful integration

---

## 3. Recommended Approach

**Use Option 3: Hybrid Approach**

Rationale:
1. **Reliability**: Model provides semantic citations based on understanding; post-processing catches errors
2. **Flexibility**: Can be tuned for strictness based on use case
3. **User Experience**: Produces consistent, verifiable output
4. **Maintainability**: Clear separation between generation and validation

---

## 4. Implementation Details

### 4.1 New Module: `websearch/core/agent/citations.py`

```python
"""Source citation handling for agent responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from websearch.core.types.maybe import Maybe, Just, Nothing


@dataclass
class CitationResult:
    """Result of citation processing."""
    answer: str
    citations_used: list[int]
    warnings: list[str]
    has_citations: bool


def extract_citation_numbers(answer: str) -> set[int]:
    """Extract all citation numbers from an answer.

    Args:
        answer: The answer text containing [1], [2], etc markers

    Returns:
        Set of citation numbers found
    """
    pattern = re.compile(r'\[(\d+)\]')
    return {int(n) for n in pattern.findall(answer)}


def validate_citations(
    answer: str,
    sources: list[dict[str, Any]],
    strict: bool = False,
) -> tuple[str, list[str]]:
    """Validate and clean citation markers in answer.

    Args:
        answer: The answer text with citation markers
        sources: List of source dictionaries
        strict: If True, remove invalid citations; if False, keep but warn

    Returns:
        Tuple of (validated_answer, warnings_list)
    """
    warnings = []
    validated = answer
    max_source = len(sources)

    # Find all citations
    citation_pattern = re.compile(r'\[(\d+)\]')
    found = citation_pattern.findall(validated)

    # Check for out-of-range citations
    for cite_num in found:
        num = int(cite_num)
        if num > max_source:
            msg = f"Invalid citation [{cite_num}]: only {max_source} sources available"
            warnings.append(msg)
            if strict:
                validated = validated.replace(f"[{cite_num}]", "")

    return validated, warnings


def add_citations_section(
    answer: str,
    sources: list[dict[str, Any]],
    citations_used: set[int],
) -> str:
    """Append a source reference section to the answer.

    Args:
        answer: The answer text
        sources: List of source dictionaries
        citations_used: Set of citation numbers used in the answer

    Returns:
        Answer with source references appended
    """
    if not citations_used:
        return answer

    # Check if answer already ends with a sources section
    if re.search(r'\*\*Sources:\*\*\s*$', answer) or re.search(r'\n\n---\n\n\*\*Sources:\*\*$', answer):
        return answer

    result = answer.rstrip()
    result += "\n\n---\n\n**Sources:**\n"

    for i, source in enumerate(sources, 1):
        if i in citations_used:
            title = source.get("title", "Unknown")
            url = source.get("url", "")
            result += f"[{i}] {title} - {url}\n"

    return result


def process_citations(
    answer: str,
    sources: list[dict[str, Any]],
    strict: bool = False,
    include_sources_section: bool = True,
) -> CitationResult:
    """Process citations in an agent answer.

    Args:
        answer: The raw answer from the agent
        sources: List of source dictionaries with title, url, description
        strict: If True, remove invalid citations
        include_sources_section: If True, append source references

    Returns:
        CitationResult with processed answer and metadata
    """
    if not sources:
        return CitationResult(
            answer=answer,
            citations_used=[],
            warnings=["No sources provided"],
            has_citations=False,
        )

    # Validate existing citations
    validated, warnings = validate_citations(answer, sources, strict)

    # Extract citation numbers used
    citations_used = extract_citation_numbers(validated)

    # Optionally append source section
    if include_sources_section and citations_used:
        validated = add_citations_section(validated, sources, citations_used)

    return CitationResult(
        answer=validated,
        citations_used=sorted(list(citations_used)),
        warnings=warnings,
        has_citations=len(citations_used) > 0,
    )
```

### 4.2 Modified: `claude_client.py`

**Add import:**
```python
from websearch.core.agent.citations import process_citations
```

**Modify `ask_with_search` function (around line 215):**
```python
# After getting the answer from sdk_query
# ... existing code ...

if not answer:
    answer = "No response from Claude"

# Process citations in the answer
source_list = [{"title": s["title"], "url": s["url"], "description": s.get("description", "")} for s in sources]
citation_result = process_citations(
    answer=answer,
    sources=source_list,
    strict=False,  # Keep invalid citations but warn
    include_sources_section=True,
)

# Log citation warnings if verbose
if citation_result.warnings:
    import sys
    print(f"Citation warnings: {citation_result.warnings}", file=sys.stderr)

# Cache the answer (use original answer without sources section for cache)
if cache_enabled:
    answer_cache.set(query, count, model, citation_result.answer, source_list)

return AskResult(
    answer=citation_result.answer,  # Use processed answer
    sources=source_list,
    cached=False,
    model=model,
    num_results=len(sources),
    duration_ms=duration_ms,
    duration_api_ms=duration_api_ms,
    input_tokens=input_tokens,
    output_tokens=output_tokens,
    total_cost_usd=total_cost_usd,
    num_turns=num_turns,
    stop_reason=stop_reason,
)
```

### 4.3 New CLI Option: `--citations/--no-citations`

**In `main.py`, modify the `ask` command:**

```python
@main.command(name="ask")
@click.argument("query")
@click.option("--count", "-n", default=5, help="Number of search results (1-20)")
@click.option("--no-cache", is_flag=True, help="Disable caching")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--model", "-m", default="MiniMax-M2.7", help="Model to use")
@click.option("--max-turns", "-t", default=10, help="Max conversation turns")
@click.option("--citations/--no-citations", default=True, help="Include inline source citations (default: enabled)")
def ask(query, count, no_cache, output, verbose, model, max_turns, citations):
    """Ask a question using web search and Claude Agent synthesis."""
    # ... existing setup code ...

    async def _ask():
        # ... existing progress setup ...

        result = await ask_with_search(
            query=query,
            count=count,
            cache_enabled=not no_cache,
            model=model,
            max_turns=max_turns,
            verbose=verbose,
            progress_callback=update_progress,
            include_citations=citations,  # New parameter
        )

        # ... rest of existing code ...
```

**Modify `ask_with_search` signature:**
```python
async def ask_with_search(
    query: str = "",
    count: int = 5,
    cache_enabled: bool = True,
    model: str = "MiniMax-M2.7",
    max_turns: int = 10,
    verbose: bool = False,
    progress_callback=None,
    include_citations: bool = True,  # New parameter
) -> AskResult:
```

**Apply citations conditionally:**
```python
# After getting answer from sdk_query
source_list = [{"title": s["title"], "url": s["url"], "description": s.get("description", "")} for s in sources]

if include_citations:
    citation_result = process_citations(
        answer=answer,
        sources=source_list,
        strict=False,
        include_sources_section=True,
    )
    final_answer = citation_result.answer
    if verbose and citation_result.warnings:
        from rich.console import Console
        err_console = Console(stderr=True)
        for warning in citation_result.warnings:
            err_console.print(f"[yellow]Warning: {warning}[/yellow]")
else:
    final_answer = answer

# Use final_answer for output and caching
```

---

## 5. Testing Strategy

### 5.1 Unit Tests for Citation Processing

```python
# tests/test_citations.py
import pytest
from websearch.core.agent.citations import (
    extract_citation_numbers,
    validate_citations,
    process_citations,
    add_citations_section,
)


class TestExtractCitationNumbers:
    def test_single_citations(self):
        assert extract_citation_numbers("Answer [1] here") == {1}
        assert extract_citation_numbers("[2] start") == {2}

    def test_multiple_citations(self):
        assert extract_citation_numbers("[1] and [2] and [3]") == {1, 2, 3}

    def test_duplicate_citations(self):
        assert extract_citation_numbers("[1] [1] [1]") == {1}

    def test_no_citations(self):
        assert extract_citation_numbers("No citations here") == set()


class TestValidateCitations:
    def test_valid_citations(self):
        sources = [{"title": "A", "url": "http://a.com"}]
        result, warnings = validate_citations("[1] content", sources)
        assert result == "[1] content"
        assert warnings == []

    def test_invalid_citation_strict(self):
        sources = [{"title": "A", "url": "http://a.com"}]
        result, warnings = validate_citations("[99] content", sources, strict=True)
        assert "[99]" not in result
        assert len(warnings) == 1

    def test_invalid_citation_non_strict(self):
        sources = [{"title": "A", "url": "http://a.com"}]
        result, warnings = validate_citations("[99] content", sources, strict=False)
        assert "[99]" in result
        assert len(warnings) == 1


class TestProcessCitations:
    def test_empty_sources(self):
        result = process_citations("Answer [1]", [])
        assert result.answer == "Answer [1]"
        assert result.has_citations is False

    def test_adds_sources_section(self):
        sources = [
            {"title": "Source A", "url": "http://a.com"},
            {"title": "Source B", "url": "http://b.com"},
        ]
        result = process_citations("[1] and [2]", sources, include_sources_section=True)
        assert "[1] Source A - http://a.com" in result.answer
        assert "[2] Source B - http://b.com" in result.answer

    def test_filters_sources_section_to_used(self):
        sources = [
            {"title": "Source A", "url": "http://a.com"},
            {"title": "Source B", "url": "http://b.com"},
        ]
        result = process_citations("[1] only", sources, include_sources_section=True)
        assert "Source A" in result.answer
        assert "Source B" not in result.answer
```

### 5.2 Integration Test

```python
@pytest.mark.asyncio
async def test_ask_with_citations():
    from websearch.core.agent.claude_client import ask_with_search

    result = await ask_with_search(
        query="What is Python?",
        count=3,
        cache_enabled=False,
        include_citations=True,
    )

    # Check that answer has citation markers
    assert "[" in result.answer and "]" in result.answer
    assert result.sources is not None
    assert len(result.sources) > 0


@pytest.mark.asyncio
async def test_ask_without_citations():
    from websearch.core.agent.claude_client import ask_with_search

    result = await ask_with_search(
        query="What is Python?",
        count=3,
        cache_enabled=False,
        include_citations=False,
    )

    # Answer should be plain without citations section
    assert "Sources:" not in result.answer
```

---

## 6. Example Output Formats

### 6.1 Default Output (with citations)

```
$ websearch ask "What is Python used for?"

Python is a high-level, interpreted programming language [1] known for its
readable syntax and versatility. It is widely used in:

- **Web Development**: Django and Flask frameworks [2]
- **Data Science**: Pandas, NumPy, and scikit-learn libraries [3]
- **Automation**: Scripting and DevOps tasks [1]

---

**Sources:**
[1] Python.org - https://python.org
[2] Django Project - https://www.djangoproject.com
[3] Pandas - https://pandas.pydata.org
```

### 6.2 Plain Output (--no-citations)

```
$ websearch ask "What is Python?" --no-citations

Python is a high-level, interpreted programming language known for its
readable syntax and versatility. It is used in web development, data
science, automation, and many other fields.
```

### 6.3 Verbose Output

```
$ websearch ask "What is Python?" --verbose

[dim]Cache: cache miss[/dim]

# What is Python?

Python is a high-level, interpreted programming language [1] known for its
readable syntax.

Sources:
#   Title                     URL                      Cached
-   -----                     ---                      ------
1   Python.org                https://python.org       no
2   Wikipedia - Python        https://en.wikipedia...  no

Response Metadata:
Metric      Value
Duration    3,245 ms (3,100 ms API)
Tokens      1,234 in / 567 out
Cost        $0.0234
Turns       2
Stop        end_turn

Python is a high-level, interpreted programming language [1] known for its
readable syntax...

---

**Sources:**
[1] Python.org - https://python.org
```

---

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model ignores citation instructions | Medium | High | Implement post-processing validation; iterate on prompt |
| Hallucinated citations (e.g., [99]) | Medium | Medium | Validate citation numbers against source count |
| Citations placed incorrectly | Medium | Low | Design clear examples in prompt; post-processing can adjust |
| Performance overhead from processing | Low | Low | Citation processing is O(n) on answer length, negligible |
| Breaking existing cached answers | Low | Medium | Cache stores original answer; reprocess on read if needed |
| Confusion when citations disabled | Low | Low | Clear CLI flag `--no-citations` for plain output |

---

## 8. Backward Compatibility

### 8.1 Cache Behavior

Cached answers store the full processed answer (with citations). This is acceptable because:
1. Users can opt out with `--no-citations` to get raw answers
2. Cached answers are valid and useful
3. Reprocessing would add complexity without significant benefit

### 8.2 API Compatibility

The `AskResult` dataclass remains unchanged. The `sources` field format is unchanged. No breaking changes to public APIs.

---

## 9. Future Enhancements

1. **Hoverable Citations**: In terminal emulators supporting hyperlinks, make citation numbers link to source URLs
2. **Footnote Style**: Add option for footnote-style citations `[^1]` instead of inline `[1]`
3. **Citation Count Statistics**: Add metadata about how many citations were used
4. **Source Ranking**: Show which sources were cited most frequently

---

## 10. Conclusion

Implementing source citations requires a hybrid approach combining prompt engineering with post-processing validation. The model generates semantically meaningful citations, while the post-processing step validates citation numbers and optionally appends a source reference section.

This approach provides:
- Inline citation markers for claim verification
- A sources reference section for easy access
- Validation warnings for invalid citations
- Backward compatibility with existing behavior

The implementation can be done incrementally, starting with basic citation markers and adding the sources section as a follow-up enhancement.

---

## References

- Current implementation: `C:\Users\dpereira\Documents\github\websearch\websearch\core\agent\claude_client.py`
- Ask command: `C:\Users\dpereira\Documents\github\websearch\websearch\main.py`
- AskResult dataclass: `C:\Users\dpereira\Documents\github\websearch\websearch\core\agent\claude_client.py` (lines 34-50)
- Streaming implementation report: `C:\Users\dpereira\Documents\github\websearch\reports\streaming-response-implementation.md`