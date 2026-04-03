# Streaming Response Implementation Report

## Executive Summary

The websearch CLI currently requires users to wait for the entire AI response before seeing any output. This report analyzes the architecture gap, evaluates implementation options using the Claude Agent SDK, and provides a detailed recommendation for implementing real-time streaming response output.

**Current State:** The CLI uses `sdk_query()` which accumulates text incrementally but only displays output after the complete response is received.

**Recommendation:** Implement `ClaudeSDKClient` with `include_partial_messages=True` to enable real-time token-by-token streaming output while maintaining compatibility with existing progress bars and verbose modes.

---

## Current Architecture Gap

### How Responses Are Currently Handled

The current implementation uses `sdk_query()`:

```python
async for message in sdk_query(prompt=prompt, options=options):
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                answer += block.text  # Accumulates text
```

**Problem:** While `sdk_query()` is an async iterator that yields messages as they arrive, the current implementation only displays output after collecting the complete text.

### What Happens During a Query

1. `sdk_query()` starts the Claude Code CLI as a subprocess
2. JSONL messages are streamed over stdout
3. Messages include `AssistantMessage` with `TextBlock` content blocks
4. The current code accumulates all text in `answer` string
5. Only after `ResultMessage` is received is the output printed

---

## Implementation Options

### Option 1: Use `sdk_query()` with Incremental Display

**Approach:** Modify the existing code to yield text as `TextBlock` messages arrive.

```python
async def ask_with_search_streaming(query: str, ...):
    answer = ""
    async for message in sdk_query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    answer += block.text
                    yield block.text  # Emit incremental text
```

**Pros:** Minimal code changes, reuses existing `sdk_query()` function

**Cons:** Still uses one-shot query model, cannot interrupt

### Option 2: Switch to `ClaudeSDKClient` with `receive_response()`

**Approach:** Replace `sdk_query()` with `ClaudeSDKClient` using its built-in `receive_response()` helper.

```python
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)

    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
```

**Pros:** Full bidirectional communication, supports interrupts and follow-ups

**Cons:** More complex than `sdk_query()`, requires connection lifecycle management

### Option 3: `ClaudeSDKClient` with `include_partial_messages=True`

**Approach:** Enable raw token streaming via `StreamEvent` messages.

```python
options = ClaudeAgentOptions(
    include_partial_messages=True,
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)

    async for msg in client.receive_response():
        if isinstance(msg, StreamEvent):
            if msg.event.get("type") == "content_block_delta":
                delta = msg.event.get("delta", {})
                if delta.get("type") == "text_delta":
                    print(delta.get("text", ""), end="", flush=True)
```

**Pros:** True token-by-token streaming (real-time)

**Cons:** Most complex, large number of events to process

---

## Recommended Approach

**Use Option 2: `ClaudeSDKClient` with `receive_response()`**

Rationale:
1. Balances complexity and functionality
2. Built-in message handling auto-terminates at `ResultMessage`
3. Future extensibility for interrupt capability and multi-turn conversations
4. Well-documented patterns in SDK examples

---

## Code Examples

### Basic Streaming Pattern with ClaudeSDKClient

```python
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

async def stream_answer(prompt: str, model: str = "MiniMax-M2.7"):
    options = ClaudeAgentOptions(
        model=model,
        env={
            "ANTHROPIC_AUTH_TOKEN": os.getenv("ANTHROPIC_AUTH_TOKEN"),
            "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic"),
        },
        tools=["WebSearch", "WebFetch"],
        allowed_tools=["WebSearch", "WebFetch"],
    )

    answer_parts = []

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
                        answer_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                return "".join(answer_parts)

    return ""
```

### Integration with Rich Progress Bar

```python
from rich.console import Console
from rich.progress import Progress

console = Console()

async def ask_with_progress(query: str, progress_callback=None, verbose: bool = False):
    options = ClaudeAgentOptions(
        model="MiniMax-M2.7",
        max_turns=10,
        env={...},
        tools=["WebSearch", "WebFetch"],
        allowed_tools=["WebSearch", "WebFetch"],
    )

    answer_parts = []

    with Progress(auto_refresh=True, console=console) as progress:
        task = progress.add_task("[cyan]Waiting for Claude...", total=None)

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            progress.update(task, description=f"[dim]Receiving...[/dim]")
                            print(block.text, end="", flush=True)
                            answer_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    progress.remove_task(task)

    return "".join(answer_parts)
```

### Adding `--stream` Flag to CLI

```python
@main.command(name="ask")
@click.option("--stream", "-s", is_flag=True, help="Stream response in real-time")
def ask(query, count, no_cache, output, verbose, stream, model, max_turns):
    # ... pass stream to ask_with_search
```

---

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_streaming_accumulates_text():
    from websearch.core.agent.claude_client import ask_with_search

    result = await ask_with_search(query="test", stream=True)
    assert "Hello world" in result.answer
```

### Integration Tests

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_ask_command_with_streaming():
    result = await asyncio.create_subprocess_exec(
        "python", "-m", "websearch", "ask", "What is 2+2?", "--stream"
    )
    stdout, stderr = await result.communicate()
    assert b"2" in stdout or b"4" in stdout
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Terminal Compatibility | Stream only for interactive terminals, detect piping |
| Cache Invalidation | Only cache after `ResultMessage` |
| Performance Overhead | Make streaming opt-in via `--stream` flag |
| Error Recovery | Implement retry logic with exponential backoff |

---

## Implementation Roadmap

### Phase 1: Core Streaming (Low Risk)
1. Add `--stream` flag to `ask` command
2. Implement `ClaudeSDKClient` pattern alongside existing code
3. Test with verbose mode disabled

### Phase 2: Enhanced Output (Medium Risk)
1. Add Rich console integration for formatted streaming
2. Handle partial messages with `include_partial_messages`
3. Terminal detection for appropriate behavior

### Phase 3: Advanced Features (Future)
1. Interrupt capability with Ctrl+C
2. Multi-turn conversation support
3. Real-time token counting display

---

## Conclusion

Streaming response output is achievable with `ClaudeSDKClient` and its `receive_response()` method. The implementation can be done incrementally, starting with basic text streaming and enhancing over time.
