# Claude Agent SDK Python - Project Structure Analysis

**Project Location:** `C:\Users\dpereira\Documents\github\claude-codex-mcp\projects\claude-agent-sdk-python`
**Version:** 0.1.55
**Python Support:** 3.10+

---

## 1. Overall Project Structure and Directory Layout

```
claude-agent-sdk-python/
├── src/claude_agent_sdk/          # Main package source
│   ├── __init__.py               # Public API exports
│   ├── client.py                 # ClaudeSDKClient class
│   ├── query.py                  # query() function
│   ├── types.py                  # Type definitions
│   ├── _errors.py                # Error classes
│   ├── _version.py               # Version info
│   └── _internal/                # Internal implementation
│       ├── client.py             # InternalClient
│       ├── query.py              # Query class (control protocol)
│       ├── sessions.py           # Session listing
│       ├── session_mutations.py  # Session mutations (fork, rename, delete)
│       ├── message_parser.py     # Message parsing
│       └── transport/            # Transport abstraction
│           ├── __init__.py       # Transport ABC
│           └── subprocess_cli.py # Subprocess CLI transport
├── examples/                      # Usage examples
│   ├── quick_start.py
│   ├── streaming_mode.py
│   ├── streaming_mode_ipython.py
│   ├── streaming_mode_trio.py
│   ├── hooks.py
│   ├── mcp_calculator.py
│   └── ...
├── tests/                         # Unit tests
├── e2e-tests/                     # End-to-end tests
├── scripts/                        # Build and release scripts
├── pyproject.toml                  # Project configuration
├── README.md                       # Documentation
├── CHANGELOG.md                    # Version history
└── CLAUDE.md                       # Project-specific dev notes
```

---

## 2. Main Modules and Their Purposes

### Core Public API (`src/claude_agent_sdk/`)

| Module | Purpose |
|--------|---------|
| `__init__.py` | Main exports: `query()`, `ClaudeSDKClient`, types, `tool()` decorator, `create_sdk_mcp_server()`, session functions |
| `client.py` | `ClaudeSDKClient` - Bidirectional interactive conversations with Claude Code |
| `query.py` | `query()` - Async iterator function for one-shot/unidirectional queries |
| `types.py` | All type definitions: `ClaudeAgentOptions`, message types, hook types, MCP config types |
| `_errors.py` | Error hierarchy: `ClaudeSDKError`, `CLINotFoundError`, `CLIConnectionError`, `ProcessError`, `CLIJSONDecodeError` |

### Internal Implementation (`src/claude_agent_sdk/_internal/`)

| Module | Purpose |
|--------|---------|
| `client.py` | `InternalClient` - Wraps Query for the simple `query()` function path |
| `query.py` | `Query` class - Handles bidirectional control protocol, hook/callback routing, MCP server bridging |
| `transport/subprocess_cli.py` | `SubprocessCLITransport` - Spawns Claude Code CLI as subprocess, manages stdio |
| `sessions.py` | Session listing: `list_sessions()`, `get_session_info()`, `get_session_messages()` |
| `session_mutations.py` | Session mutations: `rename_session()`, `tag_session()`, `delete_session()`, `fork_session()` |
| `message_parser.py` | `parse_message()` - Converts CLI JSON output to typed Python objects |

---

## 3. Entry Points

### Library API Entry Points

#### 1. `query()` Function (One-shot queries)
```python
async for message in query(prompt="What is 2+2?"):
    # Messages: AssistantMessage, UserMessage, SystemMessage, ResultMessage
```
- **File:** `src/claude_agent_sdk/query.py`
- **Simple, stateless, fire-and-forget style**
- Returns async iterator of messages
- Best for: CI/CD pipelines, batch processing, simple prompts

#### 2. `ClaudeSDKClient` Class (Interactive sessions)
```python
async with ClaudeSDKClient() as client:
    await client.query("Hello")
    async for msg in client.receive_response():
        print(msg)
```
- **File:** `src/claude_agent_sdk/client.py`
- **Bidirectional, stateful, interactive**
- Supports: interrupts, custom tools (SDK MCP servers), hooks, multi-turn conversations
- Best for: Chat UIs, REPLs, interactive applications

---

## 4. Core Classes and Their Responsibilities

### ClaudeSDKClient (`client.py`)
Main high-level API for interacting with Claude Code.

**Key Methods:**
- `connect(prompt)` - Establish connection with optional initial prompt
- `query(prompt)` - Send a message/query
- `receive_messages()` - Async iterator of all messages
- `receive_response()` - Async iterator that terminates after ResultMessage
- `interrupt()` - Send interrupt signal
- `set_permission_mode(mode)` - Change permission mode dynamically
- `set_model(model)` - Change AI model dynamically
- `get_mcp_status()` - Query MCP server connection status
- `get_context_usage()` - Get token usage breakdown
- `rewind_files(user_message_id)` - Rewind files to checkpoint
- `reconnect_mcp_server(server_name)` - Reconnect failed MCP server
- `toggle_mcp_server(server_name, enabled)` - Enable/disable MCP server
- `stop_task(task_id)` - Stop running task

### Query (`_internal/query.py`)
Low-level control protocol handler. Manages bidirectional communication with CLI.

**Responsibilities:**
- Control request/response routing
- Hook callback invocation
- Tool permission callbacks (`can_use_tool`)
- SDK MCP server bridging (routes MCP requests to in-process servers)
- Message streaming with proper closure

### SubprocessCLITransport (`_internal/transport/subprocess_cli.py`)
Spawns Claude Code CLI as subprocess and manages communication.

### ClaudeAgentOptions (`types.py`)
Dataclass containing all configuration options.

---

## 5. CLI and Programmatic API Organization

### CLI Usage Pattern
The SDK communicates with Claude Code CLI via subprocess with JSON streaming:
```bash
claude --output-format stream-json --input-format stream-json [options]
```

### Programmatic API Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      User Code                               │
│  async for msg in query(prompt)                             │
│  async with ClaudeSDKClient() as client:                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  ClaudeSDKClient / query() (Public API)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  InternalClient / Query (Control Protocol)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Transport Layer (SubprocessCLITransport)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Claude Code CLI Subprocess                                 │
└─────────────────────────────────────────────────────────────┘
```

### SDK MCP Server Support (In-Process Tools)
```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("greet", "Greet a user", {"name": str})
async def greet_user(args):
    return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

server = create_sdk_mcp_server(name="my-tools", version="1.0.0", tools=[greet_user])
```

### Hook System
Hooks allow Python code to intercept and control agent behavior at specific points:
- `PreToolUse`, `PostToolUse`, `PostToolUseFailure`
- `UserPromptSubmit`, `Stop`, `PreCompact`
- `SubagentStart`, `SubagentStop`, `PermissionRequest`

---

## 6. Key Configuration Files

### `pyproject.toml`
- **Build:** Hatchling with `src/claude_agent_sdk` package
- **Dependencies:** `anyio>=4.0.0`, `typing_extensions>=4.0.0`, `mcp>=0.1.0`
- **Dev dependencies:** pytest, pytest-asyncio, mypy, ruff
- **Python:** 3.10+

### Session Storage
Sessions are stored as JSONL files in:
```
~/.claude/projects/<sanitized-cwd>/<session-id>.jsonl
```

---

## Architecture Insights for Building an Agent Layer on Web Fetching

1. **Transport Abstraction:** The SDK uses an abstract `Transport` layer allowing custom implementations
2. **Message Streaming:** The bidirectional streaming pattern (`AsyncIterator[Message]`) is fundamental
3. **Tool System:** MCP tools are well-integrated with `@tool` decorator providing type-safe tool definitions
4. **Control Protocol:** The SDK uses a request/response control protocol on top of streaming
5. **Hook System:** Comprehensive hook system allows fine-grained control over agent behavior
6. **Session Management:** Sessions persist conversation history for resumption
7. **Subprocess Model:** Claude Code CLI runs as a subprocess; for web fetching, could run a web fetch service similarly
