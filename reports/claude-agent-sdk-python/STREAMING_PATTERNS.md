# Streaming Patterns: Claude Agent SDK Python

## 1. How Streaming is Implemented

### Core Architecture

The SDK uses a **bidirectional JSONL protocol** over subprocess stdin/stdout using `anyio` for async I/O.

```python
# From subprocess_cli.py
cmd = [self._cli_path, "--output-format", "stream-json", "--verbose"]
cmd.extend(["--input-format", "stream-json"])
```

**Key features:**
- Uses `anyio` library for async I/O operations
- `TextReceiveStream` wraps process stdout
- `TextSendStream` wraps process stdin
- JSONL (newline-delimited JSON) format for message framing

---

## 2. Consuming Streaming Responses

### Option A: `query()` Function (One-shot)

```python
async for message in query(prompt="What is 2+2?"):
    print(message)
```

### Option B: `ClaudeSDKClient` (Bidirectional)

```python
async with ClaudeSDKClient() as client:
    await client.query("What's the capital of France?")

    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        elif isinstance(msg, ResultMessage):
            print(f"Cost: ${msg.total_cost_usd:.4f}")
```

---

## 3. Streaming and Tools Interact

### Tool Permission Callbacks Require Streaming

```python
if options.can_use_tool:
    if isinstance(prompt, str):
        raise ValueError(
            "can_use_tool callback requires streaming mode. "
            "Please provide prompt as an AsyncIterable instead of a string."
        )
```

### Message Sequence During Tool Use

```
UserMessage → AssistantMessage (with ToolUseBlock) →
UserMessage (with ToolResultBlock) → AssistantMessage → ResultMessage
```

---

## 4. SSE and Chunked Response Handling

### JSONL Framing (Not SSE)

The SDK uses **JSONL (JSON Lines)** over subprocess pipes, not Server-Sent Events.

```python
async for line in self._stdout_stream:
    json_lines = line_str.split("\n")
    for json_line in json_lines:
        if json_line.startswith("{"):
            data = json.loads(json_line)
            yield data
```

### Buffer Size Limits

```python
_DEFAULT_MAX_BUFFER_SIZE = 1024 * 1024  # 1MB buffer limit

if len(json_buffer) > self._max_buffer_size:
    raise SDKJSONDecodeError("JSON message exceeded maximum buffer size")
```

### Partial Messages Streaming

```python
options = ClaudeAgentOptions(include_partial_messages=True)
```

When enabled, `StreamEvent` messages are emitted:
```python
@dataclass
class StreamEvent:
    uuid: str
    session_id: str
    event: dict[str, Any]  # The raw Anthropic API stream event
    parent_tool_use_id: str | None = None
```

---

## 5. Handling Partial Results

```python
options = ClaudeAgentOptions(include_partial_messages=True)

async for message in client.receive_response():
    if isinstance(message, StreamEvent):
        # Extract incremental text from event
        event_type = message.event.get("type")
        if event_type == "content_block_delta":
            delta = message.event.get("delta", {})
            text = delta.get("text", "")
            # Accumulate text
```

---

## 6. Backpressure and Flow Control

### Input Stream Backpressure

Uses `anyio.create_memory_object_stream` with configurable `max_buffer_size`:

```python
self._message_send, self._message_receive = anyio.create_memory_object_stream[
    dict[str, Any]
](max_buffer_size=100)
```

### Write Backpressure with Lock

```python
self._write_lock: anyio.Lock = anyio.Lock()

async def write(self, data: str) -> None:
    async with self._write_lock:
        # All checks inside lock to prevent TOCTOU races
        await self._stdin_stream.send(data)
```

### Graceful Process Shutdown

```python
if self._process.returncode is None:
    try:
        with anyio.fail_after(5):  # 5-second grace period
            await self._process.wait()
    except TimeoutError:
        self._process.terminate()
```

---

## 7. Error Handling During Streams

### Error Types

| Error | Description |
|-------|-------------|
| `ClaudeSDKError` | Base exception |
| `CLIConnectionError` | Cannot connect to Claude Code |
| `CLINotFoundError` | CLI not found |
| `ProcessError` | CLI process failed |
| `CLIJSONDecodeError` | Cannot decode JSON from CLI |
| `MessageParseError` | Cannot parse message |

### Stream Error Propagation

```python
except Exception as e:
    logger.error(f"Fatal error in message reader: {e}")
    # Signal all pending control requests
    for request_id, event in list(self.pending_control_responses.items()):
        self.pending_control_results[request_id] = e
        event.set()
    await self._message_send.send({"type": "error", "error": str(e)})
finally:
    await self._message_send.send({"type": "end"})
```

### Control Request Timeout

```python
async def _send_control_request(self, request: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    try:
        with anyio.fail_after(timeout):
            await event.wait()
    except TimeoutError:
        raise Exception(f"Control request timeout: {request.get('subtype')}")
```

---

## 8. Recommendations for Responsive Agent Experiences

1. **Always consume messages asynchronously** - Use `async for` to avoid blocking
2. **Handle ResultMessage** to know when a response is complete
3. **Use `receive_response()`** helper when you want auto-termination at result
4. **Enable `include_partial_messages`** for real-time streaming UIs
5. **Handle interrupts** via `client.interrupt()` for cancellation
6. **Configure timeouts** for control requests (default 60s)
7. **Monitor `RateLimitEvent`** messages for rate limit awareness
8. **Use `StreamEvent`** for partial content assembly
