# Claude Agent SDK Python - API Client Analysis

## Project Overview

**Key Files:**
- `src/claude_agent_sdk/__init__.py` - Main package exports
- `src/claude_agent_sdk/client.py` - ClaudeSDKClient class
- `src/claude_agent_sdk/query.py` - query() function
- `src/claude_agent_sdk/types.py` - All type definitions
- `src/claude_agent_sdk/_internal/transport/subprocess_cli.py` - Subprocess transport

---

## 1. Creating and Configuring an API Client

### Option 1: Using `query()` function (Simple, Stateless)

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(prompt="What is 2 + 2?"):
    print(message)
```

**With Options:**
```python
options = ClaudeAgentOptions(
    system_prompt="You are a helpful assistant",
    max_turns=10,
    permission_mode='acceptEdits',
    cwd="/path/to/project"
)

async for message in query(prompt="Hello", options=options):
    print(message)
```

### Option 2: Using `ClaudeSDKClient` (Bidirectional, Stateful)

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async with ClaudeSDKClient(options=options) as client:
    await client.query("Hello")
    async for msg in client.receive_response():
        print(msg)
```

### ClaudeAgentOptions Configuration

```python
@dataclass
class ClaudeAgentOptions:
    tools: list[str] | ToolsPreset | None = None
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt: str | SystemPromptPreset | None = None
    mcp_servers: dict[str, McpServerConfig] | str | Path = field(default_factory=dict)
    permission_mode: PermissionMode | None = None
    continue_conversation: bool = False
    resume: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    disallowed_tools: list[str] = field(default_factory=list)
    model: str | None = None
    fallback_model: str | None = None
    betas: list[SdkBeta] = field(default_factory=list)
    cwd: str | Path | None = None
    cli_path: str | Path | None = None
    settings: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    extra_args: dict[str, str | None] = field(default_factory=dict)
    max_buffer_size: int | None = None
    stderr: Callable[[str], None] | None = None
    can_use_tool: CanUseTool | None = None
    hooks: dict[HookEvent, list[HookMatcher]] | None = None
    sandbox: SandboxSettings | None = None
    thinking: ThinkingConfig | None = None
    enable_file_checkpointing: bool = False
```

---

## 2. Available Client Methods

### ClaudeSDKClient Methods:

| Method | Description |
|--------|-------------|
| `connect(prompt)` | Connect to Claude with optional prompt stream |
| `receive_messages()` | AsyncIterator of all messages from Claude |
| `query(prompt, session_id)` | Send a new request in streaming mode |
| `interrupt()` | Send interrupt signal |
| `set_permission_mode(mode)` | Change permission mode |
| `set_model(model)` | Change the AI model |
| `rewind_files(user_message_id)` | Rewind tracked files to state at specific user message |
| `reconnect_mcp_server(server_name)` | Reconnect a disconnected MCP server |
| `toggle_mcp_server(server_name, enabled)` | Enable/disable an MCP server |
| `stop_task(task_id)` | Stop a running task |
| `get_mcp_status()` | Get MCP server connection status |
| `get_server_info()` | Get server initialization info |
| `receive_response()` | AsyncIterator that yields messages until ResultMessage |
| `disconnect()` | Disconnect from Claude |

### query() Function

```python
async def query(
    *,
    prompt: str | AsyncIterable[dict[str, Any]],
    options: ClaudeAgentOptions | None = None,
    transport: Transport | None = None
) -> AsyncIterator[Message]
```

---

## 3. Handling Streaming Responses

### Streaming via AsyncIterator

```python
async for message in query(prompt="Hello"):
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(f"Claude: {block.text}")
```

### Message Types

```python
# Content block types
@dataclass
class TextBlock:
    text: str

@dataclass
class ThinkingBlock:
    thinking: str
    signature: str

@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]

@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str | list[dict[str, Any]] | None = None
    is_error: bool | None = None

# Message types
@dataclass
class UserMessage:
    content: str | list[ContentBlock]
    uuid: str | None = None
    parent_tool_use_id: str | None = None

@dataclass
class AssistantMessage:
    content: list[ContentBlock]
    model: str
    parent_tool_use_id: str | None = None
    error: AssistantMessageError | None = None

@dataclass
class ResultMessage:
    subtype: str
    duration_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
```

### Partial Messages

```python
options = ClaudeAgentOptions(include_partial_messages=True)
```

---

## 4. Error Handling and Retries

### Error Types

```python
class ClaudeSDKError(Exception):  # Base exception
class CLIConnectionError(ClaudeSDKError):  # Cannot connect to CLI
class CLINotFoundError(CLIConnectionError):  # CLI not found
class ProcessError(ClaudeSDKError):  # Process failed
    def __init__(self, message: str, exit_code: int | None = None, stderr: str | None = None)
class CLIJSONDecodeError(ClaudeSDKError):  # Cannot decode JSON from CLI output
class MessageParseError(ClaudeSDKError):  # Cannot parse message
```

### Error Handling Pattern

```python
from claude_agent_sdk import (
    ClaudeSDKError, CLINotFoundError, CLIConnectionError,
    ProcessError, CLIJSONDecodeError
)

try:
    async for message in query(prompt="Hello"):
        pass
except CLINotFoundError:
    print("Please install Claude Code")
except ProcessError as e:
    print(f"Process failed with exit code: {e.exit_code}")
```

### Control Protocol Timeouts
- Default: 60 seconds
- Configurable via `timeout` parameter in `_send_control_request()`

---

## 5. BYOK (Bring Your Own Key) Configuration

### Key Finding: API Endpoint Configuration is Delegated to Claude Code CLI

The SDK does **not** directly configure API endpoints. Instead, it passes environment variables to the Claude Code CLI subprocess.

### User's Configuration Maps to:

```python
options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_BASE_URL": "https://api.minimax.io/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "sk-cp-...",
        "API_TIMEOUT_MS": "3000000",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "ANTHROPIC_MODEL": "MiniMax-M2.7",
    }
)
```

### Environment Variables Supported

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | API authentication (standard) |
| `ANTHROPIC_AUTH_TOKEN` | API authentication (alternative/custom) |
| `ANTHROPIC_BASE_URL` | Custom API endpoint |
| `ANTHROPIC_MODEL` | Model selection |
| `API_TIMEOUT_MS` | Request timeout |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | Disable non-essential traffic |

### Example: Complete Production BYOK Configuration

```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
import os

async def main():
    options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
            "ANTHROPIC_MODEL": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            "API_TIMEOUT_MS": os.environ.get("API_TIMEOUT_MS", "60000"),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        permission_mode="acceptEdits",
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Hello!")
```

---

## Summary Table

| Feature | Implementation |
|---------|----------------|
| **Client Creation** | `query()` function or `ClaudeSDKClient` class |
| **Configuration** | `ClaudeAgentOptions` dataclass |
| **Streaming** | AsyncIterator pattern (`async for message in query(...)`) |
| **Error Handling** | Exception hierarchy: `ClaudeSDKError` base class |
| **Timeouts** | Configurable per request, env var `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` |
| **Rate Limiting** | None (delegated to Claude Code CLI) |
| **Caching** | None (delegated to Claude Code CLI) |
| **BYOK API Keys** | Via `options.env` dict or `ANTHROPIC_API_KEY` env var |
| **Custom CLI Path** | `ClaudeAgentOptions(cli_path="/path/to/claude")` |
