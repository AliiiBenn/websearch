# Agent Integration Guide

## Technical Implementation

This document describes how the Claude Agent SDK is integrated into the websearch CLI as a processing layer.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Layer (main.py)                     │
│    process command          ask command                       │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Agent Layer (core/agent/)                 │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ClaudeClient │  │ResponseCache │  │   MCP Tools     │   │
│  │             │  │              │  │ websearch_fetch │   │
│  │             │  │              │  │ websearch_search│   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Claude Agent SDK (External)                    │
│         ClaudeSDKClient + MCP Protocol                      │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Core Layer (existing)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Search    │  │   Fetcher    │  │    Converter    │   │
│  │             │  │  (httpx)     │  │  (markdownify)   │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Module Structure

```
websearch/
├── core/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── claude_client.py    # Claude SDK integration
│   │   ├── response_cache.py   # Response caching
│   │   └── errors.py           # Agent-specific errors
│   ├── search/
│   │   └── search.py           # Search class
│   ├── fetcher/
│   │   └── fetcher.py          # HTTP fetching
│   └── converter/
│       └── converter.py         # HTML to Markdown
└── main.py                     # CLI commands
```

## ClaudeClient Integration

### Key Imports

```python
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    ToolResultBlock,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
```

### Creating MCP Tools

```python
@tool("websearch_fetch", "Fetch URL as Markdown", {"url": str})
async def websearch_fetch(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool that fetches a URL and returns Markdown."""
    from websearch.core.search import Search

    url = args["url"]
    search = Search(cache_enabled=True)
    result = await search.fetch(url)
    await search.close()

    if result.is_just():
        return {"content": [{"type": "text", "text": result.just_value()}]}
    return {"content": [{"type": "text", "text": "Failed"}], "is_error": True}

@tool("websearch_search", "Search the web", {"query": str, "count": int})
async def websearch_search(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool for web search."""
    from websearch.core.search import Search

    query = args["query"]
    count = args.get("count", 5)

    search = Search(api_key=os.environ["BRAVE_API_KEY"])
    results, _ = await search.search(query, count=count)
    await search.close()

    if results.is_nothing():
        return {"content": [{"type": "text", "text": "Search failed"}], "is_error": True}

    # Format results
    formatted = "\n".join([
        f"[{i}] {r.title}\n{r.url}\n{r.description}\n"
        for i, r in enumerate(results.just_value(), 1)
    ])
    return {"content": [{"type": "text", "text": formatted}]}
```

### Creating MCP Server

```python
def create_websearch_mcp_server() -> McpSdkServerConfig:
    """Create MCP server with websearch tools."""
    return create_sdk_mcp_server(
        name="websearch",
        version="1.0.0",
        tools=[websearch_fetch, websearch_search]
    )
```

### Processing Pipeline

```python
async def process_url_content(
    url: str,
    markdown_content: str,
    prompt: str,
    model: str = "MiniMax-M2.7",
    verbose: bool = False,
) -> str:
    """Process URL content with Claude Agent."""

    system_prompt = f"""You are a content processing agent.
Analyze the provided web content and follow the user's instructions.

User's instructions: {prompt}

Format output as clean Markdown."""

    options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_BASE_URL": os.environ.get(
                "ANTHROPIC_BASE_URL",
                "https://api.minimax.io/anthropic"
            ),
            "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
        },
        model=model,
        mcp_servers={"websearch": create_websearch_mcp_server()},
        allowed_tools=[
            "mcp__websearch__websearch_fetch",
            "mcp__websearch__websearch_search",
        ],
        system_prompt=system_prompt,
        include_partial_messages=verbose,
    )

    query = f"""URL: {url}

Content:
{markdown_content}

---

Follow the instructions: {prompt}"""

    async with ClaudeSDKClient(options=options) as client:
        await client.query(query)

        async for msg in client.receive_response():
            if isinstance(msg, ResultMessage):
                return msg.result if msg.result else ""

    return ""
```

## Response Caching

### Cache Key Generation

```python
import hashlib

def get_cache_key(url: str, prompt: str) -> str:
    """Generate cache key from URL and prompt."""
    combined = f"{url}|{prompt}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]
```

### Cache Structure

```json
{
  "url": "https://example.com",
  "prompt": "Summarize",
  "response": "## Summary\n\n...",
  "cached_at": "2026-04-03T10:00:00Z",
  "ttl": 7200,
  "model": "MiniMax-M2.7"
}
```

### Cache Operations

```python
class ClaudeResponseCache:
    def __init__(self, cache_dir: Path | None = None, enabled: bool = True):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "websearch" / "claude"
        self.enabled = enabled

    def get(self, url: str, prompt: str) -> str | None:
        key = self._get_cache_key(url, prompt)
        cache_path = self.cache_dir / f"{key}.json"

        if not cache_path.exists():
            return None

        # Check expiry and return
        ...

    def set(self, url: str, prompt: str, response: str, ttl: float = 7200) -> None:
        key = self._get_cache_key(url, prompt)
        # Write cache entry
        ...
```

## BYOK Configuration

### With Custom Endpoint (api.minimax.io)

```python
options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_BASE_URL": "https://api.minimax.io/anthropic",
        "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
        "API_TIMEOUT_MS": "3000000",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "ANTHROPIC_MODEL": "MiniMax-M2.7",
    },
    model="MiniMax-M2.7",
    mcp_servers={"websearch": create_websearch_mcp_server()},
    allowed_tools=["mcp__websearch__websearch_fetch"],
)
```

### With Standard Anthropic

```python
options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
    },
    model="claude-sonnet-4-5",
    mcp_servers={"websearch": create_websearch_mcp_server()},
    allowed_tools=["mcp__websearch__websearch_fetch"],
)
```

## Error Handling

### Agent Errors

```python
class AgentError(Exception):
    """Base agent error."""
    pass

class AgentFetchError(AgentError):
    """Failed to fetch URL."""
    pass

class AgentResponseError(AgentError):
    """Claude returned an error."""
    pass

class AgentTimeoutError(AgentError):
    """Agent processing timed out."""
    pass

class AgentAuthError(AgentError):
    """Authentication failed."""
    pass
```

### Error Handling in Commands

```python
async def _process():
    try:
        result = await process_url_content(url, content, prompt, model, verbose)
        if not result:
            console.print("[red]Processing failed[/red]")
            sys.exit(2)
        console.print(result)
    except AgentFetchError:
        console.print("[red]Failed to fetch URL[/red]")
        sys.exit(1)
    except AgentAuthError:
        console.print("[red]Authentication failed. Check ANTHROPIC_AUTH_TOKEN[/red]")
        sys.exit(4)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(3)
```

## Message Types

### Incoming Messages (from Claude)

| Type | Content | Description |
|------|---------|-------------|
| `AssistantMessage` | `list[ContentBlock]` | Claude's response with TextBlock, ToolUseBlock |
| `SystemMessage` | `task_started` etc. | System events |
| `ResultMessage` | `result`, `usage`, `cost` | Final response |
| `StreamEvent` | Raw API event | Partial updates (with `include_partial_messages`) |
| `RateLimitEvent` | Rate limit status | Rate limit changes |

### Content Blocks

```python
# Text content
TextBlock(text="Hello")

# Thinking (extended thinking)
ThinkingBlock(thinking="Let me think...", signature="...")

# Tool use request
ToolUseBlock(id="tool_1", name="websearch_fetch", input={"url": "..."})

# Tool result
ToolResultBlock(tool_use_id="tool_1", content=[{"type": "text", "text": "..."}])
```

## Performance Optimization

### Streaming for Long Content

```python
options = ClaudeAgentOptions(
    # ... other options
    include_partial_messages=True,  # Enable streaming
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)

    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(msg, ResultMessage):
            print(f"\n\nCost: ${msg.total_cost_usd:.4f}")
```

### Stampede Protection

```python
class StampedeProtectedCache:
    def __init__(self, cache: ClaudeResponseCache):
        self.cache = cache
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_compute(self, url: str, prompt: str, compute_fn):
        # Check cache first
        cached = self.cache.get(url, prompt)
        if cached:
            return cached

        # Get lock for this key
        key = self.cache._get_cache_key(url, prompt)
        async with self._locks.setdefault(key, asyncio.Lock()):
            # Double-check cache
            cached = self.cache.get(url, prompt)
            if cached:
                return cached

            # Compute and cache
            result = await compute_fn()
            self.cache.set(url, prompt, result)
            return result
```

## Dependencies

```toml
# pyproject.toml
[dependencies]
claude-agent-sdk = ">=0.1.0"
```

Install:
```bash
uv add claude-agent-sdk
```
