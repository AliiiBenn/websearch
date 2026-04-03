# AI Agent Processing Layer

## Overview

The websearch CLI includes an AI-powered processing layer that uses Claude Agent SDK to analyze, summarize, and transform fetched web content. This layer sits between the raw HTML fetch and the final output, providing intelligent content processing.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────┐
│   User      │────▶│  CLI Command  │────▶│  Search.fetch   │────▶│   HTML      │
│             │     │  (process)   │     │                 │     │   Content   │
└─────────────┘     └──────────────┘     └─────────────────┘     └──────┬──────┘
                                                                          │
                    ┌──────────────┐     ┌─────────────────┐              │
                    │   Claude    │◀────│   MCP Tool      │◀─────────────┘
                    │   Agent     │     │ (websearch_fetch)│
                    │   SDK       │     └─────────────────┘
                    │             │              │
                    │  ┌──────────┴──┐         │
                    │  │ Custom      │         │
                    │  │ Processing  │◀────────┘
                    │  │ Tools       │
                    │  └─────────────┘
                    │
                    └──────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │  Processed  │
                    │  Output     │
                    └─────────────┘
```

## Key Features

### 1. Intelligent Content Processing

Claude Agent analyzes fetched content and can:
- Summarize key points
- Extract specific information
- Classify content type
- Answer questions about the content
- Extract entities (names, dates, locations)
- Compare multiple sources

### 2. MCP Tool Integration

The SDK uses the Model Context Protocol (MCP) to provide tools to Claude:

| Tool | Description |
|------|-------------|
| `mcp__websearch__websearch_fetch` | Fetch URL and return as Markdown |
| `mcp__websearch__websearch_search` | Search the web via Brave API |
| `mcp__websearch__extract_entities` | Extract named entities |
| `mcp__websearch__classify_content` | Classify content into categories |

### 3. Custom Prompts

Users can provide custom instructions to guide Claude's analysis:

```bash
websearch process https://example.com --prompt "Extract all dates and events mentioned"
```

### 4. Response Caching

Claude Agent responses are cached based on URL + prompt hash:
- TTL: 2 hours (configurable)
- Cache key: SHA256(URL + prompt)
- Location: `~/.cache/websearch/claude/`

### 5. Streaming Output

The `--verbose` flag enables streaming output, showing Claude's responses in real-time.

## Environment Variables

The processing layer requires:

```bash
export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
export ANTHROPIC_AUTH_TOKEN="your-auth-token"
```

Or configure via `claude_code` settings.

## Usage Examples

### Process a URL with Custom Prompt

```bash
# Summarize an article
websearch process https://news.example.com/article --prompt "Give me a 3-bullet summary"

# Extract technical information
websearch process https://docs.example.com/api --prompt "List all endpoints and their methods"

# Answer questions
websearch process https://example.com/faq --prompt "What are the top 5 most asked questions?"
```

### Ask a Question with Web Search

```bash
# Ask a question
websearch ask "What is Python programming?"

# With more search results
websearch ask "Latest developments in AI" --count 10

# With specific model
websearch ask "Explain quantum computing" --model MiniMax-M2.7
```

### Output Formats

#### JSON Output (Default)

```bash
websearch process https://example.com --prompt "Summarize"
```

```json
{
  "url": "https://example.com",
  "prompt": "Summarize",
  "response": "## Summary\n\nThis article discusses...",
  "cached": false
}
```

#### Verbose Output

```bash
websearch process https://example.com --prompt "Summarize" --verbose
```

Shows real-time streaming output from Claude Agent with cache status.

## Caching Strategy

| Cache Type | TTL | Key Strategy |
|------------|-----|-------------|
| URL Content | 2 hours | SHA256(normalized URL) |
| Search Results | 1 hour | SHA256(query + count + type) |
| Claude Responses | 2 hours | SHA256(URL + prompt) |

Cache can be disabled with `--no-cache` flag.

## Error Handling

| Error | Exit Code | Cause |
|-------|----------|-------|
| `AgentFetchError` | 1 | Failed to fetch URL |
| `AgentResponseError` | 2 | Claude returned error |
| `CacheError` | 3 | Cache write failure |
| `AuthError` | 4 | Missing/invalid API credentials |

## Performance Considerations

### Streaming Mode

Use `--verbose` for real-time feedback on long operations:

```bash
websearch process https://long article.com --verbose
```

### Batch Operations

For multiple URLs, consider:

```bash
# Process URLs sequentially
for url in $(cat urls.txt); do
  websearch process $url --prompt "Summarize" --output "${url##*/}.md"
done
```

### Cache Optimization

Repeated queries with same URL + prompt return cached results instantly:

```bash
# First call - fetches and processes
websearch process https://example.com --prompt "Summarize"

# Second call - returns cached result
websearch process https://example.com --prompt "Summarize"
# Output: [cache hit]
```

## Related Documentation

- [Command Reference](./command-reference.md) - Detailed command options
- [Integration Guide](./agent-integration.md) - Technical implementation details
