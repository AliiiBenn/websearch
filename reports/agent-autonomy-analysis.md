# Claude Agent SDK Integration - Autonomy Analysis Report

## Executive Summary

The current `ask_with_search` implementation in `websearch/core/agent/claude_client.py` operates with **zero autonomous tool use**. The agent is strictly a single-shot text synthesis engine that receives pre-fetched search results as static context and generates a response. It has no ability to use tools dynamically, perform additional searches, or take any autonomous actions during response generation.

---

## 1. Current Implementation Analysis

### 1.1 Code Location
`C:\Users\dpereira\Documents\github\websearch\websearch\core\agent\claude_client.py`

### 1.2 Implementation Pattern

The `ask_with_search` function uses the SDK's `sdk_query()` function (imported as `query`):

```python
options = ClaudeAgentOptions(
    model=model,
    max_turns=max_turns,
    env=env,
)

prompt = f"""You are a helpful assistant that answers questions based on web search results.

Question: {query}

Web Search Results:
{context}
...
"""
async for message in sdk_query(prompt=prompt, options=options):
```

### 1.3 Current `ClaudeAgentOptions` Configuration

The current implementation only uses three options:

| Option | Value | Purpose |
|--------|-------|---------|
| `model` | User-specified | AI model to use |
| `max_turns` | 10 (default) | Maximum conversation turns |
| `env` | ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL | API authentication |

**All other SDK capabilities are unused:**
- No `tools` specified
- No `allowed_tools` specified
- No `mcp_servers` configured
- No `agents` defined
- No `can_use_tool` callback
- No `hooks`
- No permission mode settings

---

## 2. SDK Autonomy Capabilities

### 2.1 Tool Control Options

The SDK provides three layers of tool control:

**A) `tools` - Base Tool Set**
```python
# Specific tools only
options = ClaudeAgentOptions(tools=["Read", "Glob", "Grep"])

# All default Claude Code tools
options = ClaudeAgentOptions(tools={"type": "preset", "preset": "claude_code"})

# Empty list - disables all built-in tools
options = ClaudeAgentOptions(tools=[])
```

**B) `allowed_tools` - Pre-Approval List**
```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Bash"],  # Auto-approved, no prompts
)
```

**C) `disallowed_tools` - Block List**
```python
options = ClaudeAgentOptions(
    disallowed_tools=["Bash", "Write"],  # Explicitly blocked
)
```

### 2.2 Built-in Claude Code Tools

When tools are enabled, the agent has access to:

| Tool | Description |
|------|-------------|
| `Read` | Read file contents |
| `Write` | Write content to files |
| `Edit` | Make targeted edits |
| `MultiEdit` | Make multiple edits at once |
| `Bash` | Execute shell commands |
| `Glob` | Find files by pattern |
| `Grep` | Search file contents |
| `WebFetch` | Fetch web content |
| `WebSearch` | Search the web |
| `Notebook` | Jupyter notebook operations |

### 2.3 Custom Tools via MCP Servers

The SDK supports custom tools through MCP (Model Context Protocol) servers:

**SDK MCP Server (In-Process)**
```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("websearch_search", "Search the web", {"query": str, "count": int})
async def websearch_search(args: dict[str, Any]) -> dict[str, Any]:
    # Custom implementation
    return {"content": [{"type": "text", "text": "results..."}]}

server = create_sdk_mcp_server(
    name="websearch",
    version="1.0.0",
    tools=[websearch_search]
)

options = ClaudeAgentOptions(
    mcp_servers={"websearch": server},
    allowed_tools=["mcp__websearch__websearch_search"],
)
```

### 2.4 Custom Agents

The SDK supports defining custom sub-agents:

```python
options = ClaudeAgentOptions(
    agents={
        "code-reviewer": AgentDefinition(
            description="Reviews code for best practices",
            prompt="You are a code reviewer...",
            tools=["Read", "Grep"],
            model="sonnet",
        ),
    }
)
```

### 2.5 Tool Permission Callbacks

Dynamic tool permission control:
```python
async def my_permission_callback(
    tool_name: str,
    input_data: dict,
    context: ToolPermissionContext
) -> PermissionResultAllow | PermissionResultDeny:
    if tool_name in ["Read", "Glob"]:
        return PermissionResultAllow()
    if tool_name in ["Bash"]:
        return PermissionResultDeny(message="No bash allowed")
    return PermissionResultAllow()

options = ClaudeAgentOptions(can_use_tool=my_permission_callback)
```

### 2.6 Hooks System

Intercept agent behavior at key points:
- `PreToolUse` - Before tool execution
- `PostToolUse` - After successful tool execution
- `PostToolUseFailure` - After failed tool execution
- `UserPromptSubmit` - When user submits a prompt
- `Stop` - When session stops
- `SubagentStart/SubagentStop` - Subagent lifecycle

### 2.7 Permission Modes

Control how the CLI handles tool permissions:

| Mode | Behavior |
|------|----------|
| `default` | CLI prompts for dangerous tools |
| `acceptEdits` | Auto-accept file edits |
| `plan` | Plan-only mode (no tool execution) |
| `bypassPermissions` | Allow all tools (use with caution) |
| `dontAsk` | Allow all tools without prompting |

---

## 3. Query vs. Client: Autonomy Implications

### 3.1 `sdk_query()` (Current Implementation)

**Characteristics:**
- **Unidirectional**: Send all messages upfront, receive all responses
- **Stateless**: Each query is independent, no conversation state
- **Single-shot**: Cannot interrupt or send follow-up messages
- **No dynamic tool use**: If the agent decides to use a tool, it must be pre-configured

**Key quote from SDK documentation:**
> "This function is ideal for simple, stateless queries where you don't need bidirectional communication or conversation management."

### 3.2 `ClaudeSDKClient` (Full Interactive Client)

**Characteristics:**
- **Bidirectional**: Send and receive messages at any time
- **Stateful**: Maintains conversation context across messages
- **Interactive**: Can send follow-ups based on responses
- **Interruptible**: Can stop and redirect the agent mid-execution
- **Dynamic**: Full control over conversation flow

**Capabilities only available with ClaudeSDKClient:**
- Multi-turn conversations with tool use
- Real-time interrupt and redirect
- Dynamic permission mode changes
- MCP server toggling during session
- Context usage monitoring
- File checkpointing and rewind

---

## 4. Current Implementation Limitations

### 4.1 Zero Tool Autonomy

The current implementation provides search results as **static context** in the prompt. The agent cannot:

1. **Perform additional searches** - If initial results are insufficient, the agent cannot search for more
2. **Fetch referenced URLs** - Cannot follow links from search results
3. **Use any tools** - No Read, Write, Bash, or any other Claude Code tools
4. **Modify content** - Cannot edit or process files
5. **Execute commands** - Cannot run shell commands
6. **Verify information** - Cannot cross-reference with other sources

### 4.2 Single-Turn Architecture

The use of `sdk_query()` enforces a single-turn pattern:
- All context must be gathered before the call
- No ability to iterate on results
- No dynamic response to agent insights
- No mid-stream corrections or redirects

### 4.3 No Error Recovery

Without tool use, the agent cannot:
- Retry failed operations
- Try alternative approaches
- Request specific information
- Take corrective action

---

## 5. Theoretical Capabilities with Full SDK

### 5.1 If `tools=["WebSearch", "WebFetch"]` Were Enabled

The agent could:
- Search for additional information as needed
- Fetch content from URLs mentioned in results
- Verify claims against multiple sources
- Follow up on interesting leads
- Iteratively research complex topics

### 5.2 If Custom MCP Tools Were Registered

The agent could use application-specific tools:
- `websearch_search` - Access the app's search functionality
- `websearch_fetch` - Fetch URLs using the app's HTTP client
- `cache_get` / `cache_set` - Interact with response cache
- Any custom business logic tool

### 5.3 If `ClaudeSDKClient` Were Used

The architecture would support:
- Multi-turn research workflows
- Real-time user feedback integration
- Interruptible agent execution
- Dynamic tool selection based on context
- Collaborative human-in-the-loop processing

---

## 6. Autonomy Level Summary

| Aspect | Current Implementation | Full SDK Capability |
|--------|------------------------|---------------------|
| **Tool Use** | None | Full dynamic tool use |
| **Search** | Pre-fetched only | On-demand during response |
| **Context** | Static prompt | Dynamic, tool-acquired |
| **Multi-turn** | Not supported | Full support |
| **Interrupt** | Not supported | Full support |
| **Custom Tools** | None | MCP servers supported |
| **Custom Agents** | None | Agent definitions supported |
| **Permission Control** | None | Callbacks and modes |
| **Hooks** | None | Full hook system |

**Current Autonomy Level: NONE (0/10)**

The agent is a pure text synthesis engine with no agency.

---

## 7. Recommendations for Increasing Autonomy

### 7.1 Minimal Increase: Enable Web Tools

```python
options = ClaudeAgentOptions(
    model=model,
    max_turns=max_turns,
    env=env,
    tools=["WebSearch", "WebFetch"],  # Enable web tools
    allowed_tools=["WebSearch", "WebFetch"],  # Auto-approve
)
```

**Effect:** Agent can search and fetch during response synthesis.

### 7.2 Moderate Increase: Use ClaudeSDKClient

Replace `sdk_query()` with `ClaudeSDKClient`:
```python
async with ClaudeSDKClient(options=options) as client:
    await client.query(prompt)
    async for msg in client.receive_response():
        # Process with interrupt capability
```

**Effect:** Multi-turn conversations, interrupt capability.

### 7.3 Significant Increase: Custom MCP Server

Register the app's search functionality as an MCP tool:
```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("app_search", "Search using app infrastructure", {"query": str})
async def app_search(args):
    results = await search.search(args["query"])
    return {"content": [{"type": "text", "text": format_results(results)}]}

server = create_sdk_mcp_server(name="websearch", version="1.0.0", tools=[app_search])
options = ClaudeAgentOptions(mcp_servers={"app": server})
```

**Effect:** Agent uses app-specific search with full control.

### 7.4 Maximum Autonomy: Full Control

- Use `ClaudeSDKClient` with streaming mode
- Define custom agents for different task types
- Implement `can_use_tool` callbacks for permission control
- Add hooks for logging and monitoring
- Enable `permission_mode='bypassPermissions'` for full autonomy

---

## 8. Conclusion

The current `ask` command implementation is a **read-only text synthesis tool** with zero autonomy. The agent receives pre-processed search results as context and produces a formatted response - it cannot take any autonomous actions.

The Claude Agent SDK provides extensive capabilities for agentic tool use, custom MCP servers, multi-turn conversations, and dynamic permission control. These capabilities are entirely unused in the current implementation.

To move toward a truly autonomous research agent, the implementation would need to:
1. Switch from `sdk_query()` to `ClaudeSDKClient`
2. Enable appropriate tools via `tools` or `allowed_tools`
3. Consider registering custom MCP tools for app-specific functionality
4. Implement permission callbacks for security-conscious tool use

The current architecture is appropriate for a simple "search and summarize" workflow, but would need significant redesign to support autonomous agentic behavior.

---

## References

- SDK Types Definition: `C:\Users\dpereira\Documents\github\websearch\temp\claude-agent-sdk-python\src\claude_agent_sdk\types.py`
- Query Implementation: `C:\Users\dpereira\Documents\github\websearch\temp\claude-agent-sdk-python\src\claude_agent_sdk\query.py`
- Client Implementation: `C:\Users\dpereira\Documents\github\websearch\temp\claude-agent-sdk-python\src\claude_agent_sdk\client.py`
- Tools Example: `C:\Users\dpereira\Documents\github\websearch\temp\claude-agent-sdk-python\examples\tools_option.py`
- Agents Example: `C:\Users\dpereira\Documents\github\websearch\temp\claude-agent-sdk-python\examples\agents.py`
- MCP Calculator Example: `C:\Users\dpereira\Documents\github\websearch\temp\claude-agent-sdk-python\examples\mcp_calculator.py`
- Tool Permission Example: `C:\Users\dpereira\Documents\github\websearch\temp\claude-agent-sdk-python\examples\tool_permission_callback.py`
- Current Implementation: `C:\Users\dpereira\Documents\github\websearch\websearch\core\agent\claude_client.py`
