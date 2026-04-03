# Advanced Patterns: Claude Agent SDK Python

## 1. Advanced Features and Capabilities

### Hook System with 10 Event Types

- `PreToolUse` - Before a tool is called
- `PostToolUse` - After a tool completes successfully
- `PostToolUseFailure` - After a tool fails
- `UserPromptSubmit` - When user submits a prompt
- `Stop` - When agent stops
- `SubagentStop` - When a sub-agent stops
- `PreCompact` - Before context compaction
- `Notification` - System notifications
- `SubagentStart` - When a sub-agent starts
- `PermissionRequest` - When permission is requested

### Custom Agent Definitions

```python
AgentDefinition = {
    description: str,
    prompt: str,
    tools: list[str] | None,
    disallowedTools: list[str] | None,
    model: str | None,
    skills: list[str] | None,
    memory: "user" | "project" | "local" | None,
    mcpServers: list[str | dict[str, Any]] | None,
    initialPrompt: str | None,
    maxTurns: int | None,
    background: bool | None,
    effort: "low" | "medium" | "high" | "max" | int | None,
    permissionMode: PermissionMode | None,
}
```

### In-Process SDK MCP Servers

```python
from claude_agent_sdk import create_sdk_mcp_server, tool

@tool("my_tool", "Description", {"arg": str})
async def my_tool(args):
    return {"content": [{"type": "text", "text": "result"}]}

server = create_sdk_mcp_server(
    name="my-server",
    version="1.0.0",
    tools=[my_tool]
)

options = ClaudeAgentOptions(
    mcp_servers={"server": server},
    allowed_tools=["mcp__server__my_tool"],
)
```

---

## 2. Multi-Agent Architectures

### Multiple Agents via Options

```python
options = ClaudeAgentOptions(
    agents={
        "code-reviewer": AgentDefinition(
            description="Reviews code",
            prompt="You review code...",
            tools=["Read", "Grep"],
        ),
        "test-writer": AgentDefinition(
            description="Writes tests",
            prompt="You write tests...",
            tools=["Read", "Write"],
        ),
    }
)
```

### Subagent Lifecycle Hooks

```python
hooks = {
    "SubagentStart": [HookMatcher(matcher=".*", hooks=[on_subagent_start])],
    "SubagentStop": [HookMatcher(matcher=".*", hooks=[on_subagent_stop])],
}
```

### Filesystem-Based Agents

Via `setting_sources=["project"]` loading from `.claude/agents/`

---

## 3. Guardrails and Content Filtering

### PreToolUse Hook with Deny

```python
async def content_filter(input_data, tool_use_id, context):
    tool_name = input_data["tool_name"]
    tool_input = input_data["tool_input"]

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if any(dangerous in command for dangerous in ["rm -rf", "format", "dd if="]):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Dangerous command blocked",
                }
            }

    return {}

options = ClaudeAgentOptions(
    hooks={"PreToolUse": [HookMatcher(matcher=".*", hooks=[content_filter])]}
)
```

### Permission Modes

```python
permission_mode: PermissionMode
# Values:
# - "default"      # CLI prompts for dangerous tools
# - "acceptEdits" # Auto-accept file edits
# - "plan"         # Plan-only mode
# - "bypassPermissions" / "dontAsk"  # Allow all
```

---

## 4. Retry Logic

### Control Request Retry (Built-in Timeout)

```python
async def _send_control_request(self, request: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    # Default 60s timeout, configurable
    with anyio.fail_after(timeout):
        await event.wait()
```

### MCP Server Reconnection

```python
await client.reconnect_mcp_server(server_name="my-server")
```

### Circuit Breaker Pattern

```python
# Toggle MCP server on failure
await client.toggle_mcp_server(server_name="my-server", enabled=False)

# Check MCP status
status = await client.get_mcp_status()
```

---

## 5. Long-Running Agent Tasks

### Task Tracking Messages

- `TaskStartedMessage` - task begins
- `TaskProgressMessage` - ongoing progress updates
- `TaskNotificationMessage` - task completion/failure/stop

### Stopping Tasks

```python
# Get task ID from TaskStartedMessage
task_id = started_msg.data.get("taskId")

# Stop a running task
await client.stop_task(task_id)
```

### Interrupt for Cancellation

```python
async with ClaudeSDKClient() as client:
    await client.query("Count from 1 to 100 slowly")

    async def consume():
        async for msg in client.receive_messages():
            print(msg)

    task = asyncio.create_task(consume())
    await asyncio.sleep(2)

    await client.interrupt()  # Cancel current operation
    task.cancel()
```

### Resource Limits

```python
ClaudeAgentOptions(
    max_turns=10,           # Max conversation turns
    max_budget_usd=1.0,     # Max cost budget
    task_budget={...},      # Token budgeting
)
```

---

## 6. Observability and Tracing

### Context Usage Tracking

```python
async with ClaudeSDKClient() as client:
    await client.query("Hello")
    async for msg in client.receive_response():
        ...

usage = await client.get_context_usage()
# Returns breakdown of token usage by category
```

### Rate Limit Events

```python
async for message in client.receive_messages():
    if isinstance(message, RateLimitEvent):
        print(f"Rate limit: {message.type}")
```

### MCP Server Status

```python
status = await client.get_mcp_status()
# Returns connection status of all MCP servers
```

### Stderr Callback

```python
options = ClaudeAgentOptions(
    stderr=lambda line: print(f"CLI: {line}", file=sys.stderr),
)
```

---

## 7. Performance Optimization

### In-Process SDK MCP Servers

Avoid subprocess IPC overhead by using SDK-based MCP servers:

```python
@tool("fast_tool", "Fast tool", {"input": str})
async def fast_tool(args):
    return {"content": [{"type": "text", "text": f"Result: {args['input']}"}]}

server = create_sdk_mcp_server(name="fast", version="1.0.0", tools=[fast_tool])
```

vs. external MCP server (requires subprocess):

```python
McpStdioServerConfig(
    command="python -m my_mcp_server",
    args=["--port", "8080"],
)
```

### Streaming with Partial Messages

```python
options = ClaudeAgentOptions(
    include_partial_messages=True,
)

async for message in client.receive_response():
    if isinstance(message, StreamEvent):
        # Accumulate incremental text for real-time display
        delta = message.event.get("delta", {})
        partial_text = delta.get("text", "")
```

### Memory Object Streams

The SDK uses `anyio.create_memory_object_stream` for efficient message passing between reader task and consumer:

```python
self._message_send, self._message_receive = anyio.create_memory_object_stream[
    dict[str, Any]
](max_buffer_size=100)
```

---

## 8. Security Considerations

### Sandbox Settings

```python
sandbox = {
    "enabled": True,
    "autoAllowBashIfSandboxed": False,
    "excludedCommands": ["rm", "dd", "mkfs"],
    "allowedPaths": ["/tmp/project"],
}

options = ClaudeAgentOptions(sandbox=sandbox)
```

### Permission Modes

```python
# Auto-accept edits, prompt for dangerous
permission_mode="acceptEdits"

# Bypass all prompts (use with caution)
permission_mode="bypassPermissions"
```

### Allow Unsandboxed Commands Flag

```python
sandbox = {
    "enabled": True,
    "allowUnsandboxedCommands": False,  # Enforce sandboxing
}
```

---

## 9. Senior-Level Implementation Pattern

### Complete Production Pattern

```python
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    HookMatcher,
    ExactMatchCache,
    StampedeProtectedCache,
)
import os
import asyncio

# 1. Implement caching
cache = StampedeProtectedCache(ExactMatchCache())

# 2. Create tools
@tool("fetch_url", "Fetch URL content", {"url": str})
async def fetch_url(args: dict) -> dict:
    # Use existing websearch library
    ...

fetch_server = create_sdk_mcp_server(name="websearch", version="1.0.0", tools=[fetch_url])

# 3. Implement hooks
async def audit_hook(input_data, tool_use_id, context):
    print(f"Tool: {input_data['tool_name']}")
    return {}

# 4. Configure client
options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_BASE_URL": os.environ["ANTHROPIC_BASE_URL"],
        "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
        "API_TIMEOUT_MS": "3000000",
    },
    model=os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"),
    mcp_servers={"websearch": fetch_server},
    allowed_tools=["mcp__websearch__fetch_url"],
    hooks={
        "PreToolUse": [HookMatcher(matcher=".*", hooks=[audit_hook])],
    },
    permission_mode="acceptEdits",
    max_turns=20,
    max_budget_usd=5.0,
    thinking={"type": "adaptive"},
    include_partial_messages=True,
    sandbox={"enabled": True, "autoAllowBashIfSandboxed": False},
)

# 5. Use with caching
async def cached_query(prompt: str):
    cached = cache.get(prompt)
    if cached:
        return cached

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, ResultMessage):
                result = msg.result
                cache.set(prompt, result)
                return result

# 6. Run
asyncio.run(cached_query("Process https://example.com"))
```

---

## Summary

| Feature | Implementation |
|---------|----------------|
| **Multi-Agent** | Via `agents={}` in ClaudeAgentOptions |
| **Guardrails** | PreToolUse hooks with deny decisions |
| **Retry Logic** | Control request timeouts, MCP reconnection |
| **Long-Running Tasks** | Task tracking messages, interrupt, stop_task |
| **Observability** | get_context_usage(), RateLimitEvent, get_mcp_status() |
| **Performance** | In-process SDK MCP servers, streaming |
| **Security** | Sandbox settings, permission modes |
