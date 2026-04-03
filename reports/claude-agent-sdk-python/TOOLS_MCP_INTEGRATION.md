# Claude Agent SDK Python - Tools and MCP Integration

## 1. How Tools Are Defined and Registered

### Built-in Claude Code Tools

The SDK supports all built-in Claude Code tools through `allowed_tools` and `disallowed_tools`:

```python
@dataclass
class ClaudeAgentOptions:
    tools: list[str] | ToolsPreset | None = None  # Base tool set
    allowed_tools: list[str] = field(default_factory=list)  # Pre-approved tools
    disallowed_tools: list[str] = field(default_factory=list)  # Blocked tools
```

### Custom Tools via SDK MCP Servers

Tools are defined using the `@tool` decorator and bundled via `create_sdk_mcp_server()`:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("add", "Add two numbers", {"a": float, "b": float})
async def add_numbers(args: dict[str, Any]) -> dict[str, Any]:
    result = args["a"] + args["b"]
    return {
        "content": [{"type": "text", "text": f"{args['a']} + {args['b']} = {result}"}]
    }

calculator = create_sdk_mcp_server(
    name="calculator",
    version="2.0.0",
    tools=[add_numbers]
)

options = ClaudeAgentOptions(
    mcp_servers={"calc": calculator},
    allowed_tools=["mcp__calc__add"]
)
```

---

## 2. MCP Server Types Supported

```python
# Stdio Server (external subprocess)
class McpStdioServerConfig(TypedDict):
    type: NotRequired[Literal["stdio"]]
    command: str
    args: NotRequired[list[str]]
    env: NotRequired[dict[str, str]]

# SSE Server (HTTP SSE)
class McpSSEServerConfig(TypedDict):
    type: Literal["sse"]
    url: str
    headers: NotRequired[dict[str, str]]

# HTTP Server
class McpHttpServerConfig(TypedDict):
    type: Literal["http"]
    url: str
    headers: NotRequired[dict[str, str]]

# SDK Server (in-process)
class McpSdkServerConfig(TypedDict):
    type: Literal["sdk"]
    name: str
    instance: "McpServer"
```

---

## 3. How Tool Results Are Passed Back to the Model

### Tool Execution Flow

1. CLI sends `control_request` with `subtype: "mcp_message"`
2. `Query._handle_control_request()` receives it
3. Routes to `_handle_sdk_mcp_request()` with `tools/call` method
4. Server executes tool via registered `call_tool` handler
5. Result is converted to JSONRPC response format
6. Response wrapped in `control_response` and sent back

### Result Content Format

Tools return results in MCP format:
```python
{
    "content": [
        {"type": "text", "text": "result text"},
        {"type": "image", "data": "...", "mimeType": "image/png"}
    ],
    "is_error": True|False
}
```

---

## 4. How to Create Custom Tools

### Complete Example

```python
from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
    ClaudeSDKClient
)
from typing import Any

@tool("fetch_url", "Fetch content from URL", {"url": str})
async def fetch_url(args: dict[str, Any]) -> dict[str, Any]:
    import httpx
    response = await httpx.get(args["url"], timeout=30)
    return {
        "content": [{"type": "text", "text": response.text}],
        "is_error": response.status_code >= 400
    }

fetch_server = create_sdk_mcp_server(
    name="fetch-tools",
    version="1.0.0",
    tools=[fetch_url]
)

options = ClaudeAgentOptions(
    mcp_servers={"fetch": fetch_server},
    allowed_tools=["mcp__fetch__fetch_url"],
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("Use fetch_url to get https://example.com")
```

### Tool Annotations

```python
from mcp.types import ToolAnnotations

@tool(
    "read_data",
    "Read data from source",
    {"source": str},
    annotations=ToolAnnotations(readOnlyHint=True)
)
async def read_data(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"Data from {args['source']}"}]}
```

---

## 5. Tool Permission Callback

```python
from claude_agent_sdk import (
    CanUseTool,
    ToolPermissionContext,
    PermissionResultAllow,
    PermissionResultDeny
)

async def my_permission_callback(
    tool_name: str,
    input_data: dict,
    context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    if tool_name in ["Read", "Glob", "Grep"]:
        return PermissionResultAllow()

    if tool_name in ["Write", "Edit"]:
        file_path = input_data.get("file_path", "")
        if file_path.startswith("/etc/"):
            return PermissionResultDeny(message="Cannot write to system directory")
        return PermissionResultAllow(updated_input={"file_path": f"./safe_output/{file_path.split('/')[-1]}"})

    return PermissionResultAllow()

options = ClaudeAgentOptions(can_use_tool=my_permission_callback)
```

---

## 6. Built-in Tools

Default Claude Code Tools:
- **Read**: Read file contents
- **Write**: Write content to files
- **Edit**: Make targeted edits
- **MultiEdit**: Make multiple edits at once
- **Bash**: Execute shell commands
- **Glob**: Find files by pattern
- **Grep**: Search file contents
- **WebFetch**: Fetch web content
- **WebSearch**: Search the web
- **Notebook**: Jupyter notebook operations

---

## 7. How Streaming and Tool Use Interact

### Message Sequence During Tool Use

```
UserMessage → AssistantMessage (with ToolUseBlock) →
UserMessage (with ToolResultBlock) → AssistantMessage → ResultMessage
```

### Interrupt Capability

```python
async with ClaudeSDKClient() as client:
    await client.query("Count from 1 to 100 slowly")
    consume_task = asyncio.create_task(consume_messages())
    await asyncio.sleep(2)
    await client.interrupt()  # Stop current task
```

---

## 8. Hooks Integration

```python
from claude_agent_sdk import HookMatcher, ClaudeAgentOptions

async def check_bash_command(input_data, tool_use_id, context):
    tool_name = input_data["tool_name"]
    if tool_name == "Bash":
        command = input_data["tool_input"].get("command", "")
        if "forbidden" in command:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Contains forbidden pattern"
                }
            }
    return {}

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[check_bash_command])],
        "PostToolUse": [HookMatcher(matcher="Bash", hooks=[review_tool_output])],
    }
)
```

**Supported Hook Events:**
- `PreToolUse` - Before tool execution
- `PostToolUse` - After successful tool execution
- `PostToolUseFailure` - After failed tool execution
- `UserPromptSubmit` - When user submits a prompt
- `Stop` - When session stops
- `PreCompact` - Before compaction
- `Notification` - System notifications
- `SubagentStart/SubagentStop` - Subagent lifecycle
- `PermissionRequest` - Permission prompts
