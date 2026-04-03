# CLI Implementation: Claude Agent SDK Python

## 1. CLI Structure

The SDK doesn't implement its own CLI - it wraps Claude Code CLI as a subprocess.

### CLI Communication

```bash
claude --output-format stream-json --input-format stream-json [options]
```

**Key CLI Flags Used:**
- `--output-format stream-json` - JSON streaming output
- `--input-format stream-json` - JSON streaming input via stdin
- `--system-prompt`, `--system-prompt-file`, `--append-system-prompt`
- `--tools`, `--allowedTools`, `--disallowedTools`
- `--max-turns`, `--max-budget-usd`
- `--permission-mode`
- `--mcp-config` - JSON MCP server configuration
- `--include-partial-messages`
- `--fork-session`
- `--settings` - JSON settings (merged with sandbox)
- `--env` - Environment variables for SDK identification

---

## 2. Main Command Groups

The SDK exposes two primary interfaces:

### 1. `query()` Function
- One-shot, stateless queries
- Returns async iterator of messages

### 2. `ClaudeSDKClient` Class
- Bidirectional, stateful conversations
- Context manager for automatic cleanup

---

## 3. Configuration Loading for CLI

### Environment Variables

```python
process_env = {
    **os.environ,                    # System environment
    **self._options.env,             # User-provided env vars
    "CLAUDE_CODE_ENTRYPOINT": "sdk-py",  # SDK indicator
    "CLAUDE_AGENT_SDK_VERSION": __version__,
}
```

### Settings via ClaudeAgentOptions

```python
settings: str | None = None  # JSON string or file path
setting_sources: list[SettingSource] | None = None  # ["user", "project", "local"]
```

---

## 4. Adding New Commands

### For Library Usage (Recommended)

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def process_with_agent(url: str, agent_prompt: str):
    """Process a URL with a specialized agent."""
    options = ClaudeAgentOptions(
        system_prompt=agent_prompt,
        allowed_tools=["WebFetch", "Read"],
        permission_mode="acceptEdits",
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(f"Process this URL: {url}")

        async for msg in client.receive_response():
            # Handle messages
            pass

        return result
```

### As a Standalone CLI Tool

```python
# my_cli_tool.py
import asyncio
import click
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

@click.command()
@click.argument("url")
@click.option("--prompt", "-p", default="Summarize this content")
def process_url(url: str, prompt: str):
    """Process a URL with Claude Agent."""
    asyncio.run(_process_url(url, prompt))

async def _process_url(url: str, prompt: str):
    options = ClaudeAgentOptions(
        system_prompt=f"You are a content processor. {prompt}",
        allowed_tools=["WebFetch"],
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(f"Process: {url}")
        async for msg in client.receive_response():
            print(msg)
```

---

## 5. Interactive vs Non-Interactive Mode

### Non-Interactive (query function)

```python
async for message in query(prompt="What is 2+2?"):
    if isinstance(message, ResultMessage):
        print(f"Result: {message.result}")
```

### Interactive (ClaudeSDKClient)

```python
async with ClaudeSDKClient() as client:
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        await client.query(user_input)

        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(f"Claude: {block.text}")
```

---

## 6. Patterns for Combining Multiple Tools

### Example: Fetch + Process Pipeline

```python
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
)

# 1. Create a custom fetch tool with your websearch library
@tool("websearch_fetch", "Fetch and process URL", {"url": str})
async def websearch_fetch(args: dict) -> dict:
    from websearch.core.search import Search

    search = Search()
    result = await search.fetch(args["url"])
    await search.close()

    if result.is_just():
        return {"content": [{"type": "text", "text": result.just_value()}]}
    return {"content": [{"type": "text", "text": "Failed to fetch"}], "is_error": True}

# 2. Create MCP server
fetch_server = create_sdk_mcp_server(
    name="websearch",
    version="1.0.0",
    tools=[websearch_fetch]
)

# 3. Configure agent
options = ClaudeAgentOptions(
    mcp_servers={"websearch": fetch_server},
    allowed_tools=["mcp__websearch__websearch_fetch"],
    system_prompt="""You are a content processing agent.
When given a URL:
1. Use websearch_fetch to get the content
2. Summarize the key points
3. Format output as clean markdown""",
)

# 4. Use with client
async with ClaudeSDKClient(options=options) as client:
    await client.query("https://example.com")

    async for msg in client.receive_response():
        # Process response
        ...
```

### Multi-Agent Pattern

```python
options = ClaudeAgentOptions(
    agents={
        "fetcher": AgentDefinition(
            description="Fetches web content",
            prompt="You fetch URLs and return content",
            tools=["WebFetch"],
        ),
        "summarizer": AgentDefinition(
            description="Summarizes content",
            prompt="You summarize content concisely",
        ),
    }
)

# Use fetcher agent to get content, then summarizer to process
async with ClaudeSDKClient(options=options) as client:
    await client.query("Use the fetcher agent to get https://example.com, then use summarizer to summarize")
```

---

## 7. Complete Example: websearch-agent Command

```python
#!/usr/bin/env python3
"""websearch-agent: AI-powered web content processing"""

import asyncio
import os
from typing import Optional

import click
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
)

# Custom websearch tool
@tool("websearch_fetch", "Fetch URL content", {"url": str})
async def fetch_url(args: dict) -> dict:
    # Use the websearch library
    from websearch.core.search import Search

    search = Search(cache_enabled=True)
    result = await search.fetch(args["url"], refresh=False)
    await search.close()

    if result.is_just():
        return {"content": [{"type": "text", "text": result.just_value()}]}
    return {"content": [{"type": "text", "text": "Failed to fetch"}], "is_error": True}

@click.command()
@click.argument("url")
@click.option("--prompt", "-p", default="Summarize this content")
@click.option("--model", "-m", default=os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"))
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def main(url: str, prompt: str, model: str, verbose: bool):
    """Fetch and process URL content with AI."""
    asyncio.run(_main(url, prompt, model, verbose))

async def _main(url: str, prompt: str, model: str, verbose: bool):
    fetch_server = create_sdk_mcp_server(
        name="websearch",
        version="1.0.0",
        tools=[fetch_url]
    )

    options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic"),
            "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
        },
        model=model,
        mcp_servers={"websearch": fetch_server},
        allowed_tools=["mcp__websearch__websearch_fetch"],
        system_prompt=f"""You are a content processing agent.
When given a URL, use websearch_fetch to get the content, then {prompt}.""",
        include_partial_messages=verbose,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(f"Process: {url}")

        async for msg in client.receive_response():
            if verbose:
                print(msg)
            elif isinstance(msg, ResultMessage):
                print(msg.result)

if __name__ == "__main__":
    main()
```
