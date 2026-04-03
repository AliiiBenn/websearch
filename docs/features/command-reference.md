# Command Reference

## `websearch process`

Fetch a URL and process its content through Claude Agent.

### Synopsis

```bash
websearch process <URL> --prompt <PROMPT> [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<URL>` | The URL to fetch and process |

### Options

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-p` | `--prompt` | (required) | Custom prompt for Claude Agent |
| `-r` | `--refresh` | `false` | Skip cache, force fresh URL fetch |
| `-o` | `--output` | stdout | Output file path |
| `-v` | `--verbose` | `false` | Show verbose/streaming output |
| `-m` | `--model` | `MiniMax-M2.7` | Model to use |
| `-t` | `--ttl` | `7200` | Cache TTL in seconds |
| | `--no-cache` | `false` | Disable response caching |
| | `--no-verify` | `false` | Skip SSL verification |

### Examples

```bash
# Basic usage
websearch process https://example.com --prompt "Summarize this article"

# Extract specific information
websearch process https://docs.python.org --prompt "List all stdlib modules"

# Save to file
websearch process https://blog.example.com/post --prompt "Extract key points" --output summary.md

# Verbose output with custom model
websearch process https://example.com --prompt "Analyze" --verbose --model claude-sonnet-4-5

# Force refresh (skip URL cache)
websearch process https://example.com --prompt "Summarize" --refresh
```

### Output Format (JSON)

```json
{
  "url": "https://example.com",
  "prompt": "Summarize this article",
  "response": "## Summary\n\nThis article covers...",
  "model": "MiniMax-M2.7",
  "cached": false,
  "duration_ms": 2340
}
```

---

## `websearch ask`

Ask a question using Claude Agent with web search capabilities.

### Synopsis

```bash
websearch ask <QUERY> [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<QUERY>` | The question to ask |

### Options

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-n` | `--count` | `5` | Number of search results (1-20) |
| `-o` | `--output` | stdout | Output file path |
| `-v` | `--verbose` | `false` | Show verbose/streaming output |
| `-m` | `--model` | `MiniMax-M2.7` | Model to use |
| `-t` | `--max-turns` | `10` | Maximum conversation turns |
| | `--no-cache` | `false` | Disable caching |
| | `--type` | `web` | Search type: web, news, images, videos |

### Examples

```bash
# Basic question
websearch ask "What is Python?"

# With more context
websearch ask "Latest AI developments" --count 10

# Save answer to file
websearch ask "Explain quantum computing" --output quantum.md

# Interactive mode with verbose
websearch ask "Debug my code" --verbose --max-turns 20

# News search
websearch ask "Latest tech news" --type news
```

### Output Format (JSON)

```json
{
  "query": "What is Python?",
  "answer": "## Answer\n\nPython is a programming language...",
  "sources": [
    {
      "title": "Python Official Website",
      "url": "https://python.org",
      "description": "The official home of Python..."
    }
  ],
  "model": "MiniMax-M2.7",
  "cached": false,
  "num_results": 5
}
```

---

## `websearch fetch`

Fetch a URL and convert to Markdown (existing command).

### Synopsis

```bash
websearch fetch <URL> [OPTIONS]
```

### Options

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-r` | `--refresh` | `false` | Skip cache, force fresh fetch |
| `-o` | `--output` | stdout | Output file path |
| `-v` | `--verbose` | `false` | Show verbose output |
| | `--no-cache` | `false` | Disable caching |
| | `--no-verify` | `false` | Skip SSL verification |

### Examples

```bash
# Basic fetch
websearch fetch https://example.com

# Save to file
websearch fetch https://example.com --output page.md

# Verbose with refresh
websearch fetch https://example.com --verbose --refresh
```

---

## `websearch search`

Search the web using Brave Search API (existing command).

### Synopsis

```bash
websearch search <QUERY> [OPTIONS]
```

### Options

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-n` | `--count` | `10` | Number of results (1-50) |
| `-t` | `--type` | `web` | Result type: web, news, images, videos |
| `-o` | `--output` | stdout | Output file path |
| `-v` | `--verbose` | `false` | Show verbose table output |
| | `--no-cache` | `false` | Disable caching |

### Examples

```bash
# Basic search
websearch search "python tutorial"

# News search with count
websearch search "tech news" --type news --count 5

# JSON output (default, no verbose)
websearch search "python" | jq '.'
```

### Output Formats

**JSON (default):**
```json
{
  "query": "python tutorial",
  "count": 10,
  "results": [
    {
      "title": "Python Tutorial",
      "url": "https://example.com/python",
      "description": "Learn Python...",
      "age": "2 weeks ago"
    }
  ]
}
```

**Verbose table:**
```
Status: cache miss | Source: API

# python tutorial

Found 10 results
---+-------------------------------------+-------------------------------+----------------------------------
 1 | Python Tutorial                    | https://example.com/python    | Learn Python programming...
   | https://example.com/python         |                               |
...
```

---

## Environment Variables

### Required for Agent Processing

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_AUTH_TOKEN` | API authentication token |
| `ANTHROPIC_BASE_URL` | API endpoint (default: https://api.minimax.io/anthropic) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_MODEL` | `MiniMax-M2.7` | Default model |
| `API_TIMEOUT_MS` | `3000000` | Request timeout (3s) |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | Reduce overhead |

### Required for Search

| Variable | Description |
|----------|-------------|
| `BRAVE_API_KEY` | Brave Search API key |

---

## Cache Locations

| Cache Type | Location | TTL |
|------------|-----------|-----|
| URL Content | `~/.cache/websearch/url/` | 2 hours |
| Search Results | `~/.cache/websearch/search/` | 1 hour |
| Claude Responses | `~/.cache/websearch/claude/` | 2 hours |
