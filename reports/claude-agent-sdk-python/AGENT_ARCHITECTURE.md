# Claude Agent SDK Python - Agent Architecture

## 1. How Agents Are Created and Configured

### Agent Definition Structure

```python
@dataclass
class AgentDefinition:
    description: str           # Human-readable description
    prompt: str               # System prompt for the agent
    tools: list[str] | None  # Allowed tools for this agent
    disallowedTools: list[str] | None
    model: str | None         # Model alias or full model ID
    skills: list[str] | None
    memory: Literal["user", "project", "local"] | None
    mcpServers: list[str | dict[str, Any]] | None
    initialPrompt: str | None
    maxTurns: int | None
    background: bool | None
    effort: Literal["low", "medium", "high", "max"] | int | None
    permissionMode: PermissionMode | None
```

### Creating Agents

```python
from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions

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

---

## 2. The Agent Loop/Execution Cycle

### Architecture Layers

```
┌─────────────────────────────────────────────┐
│         ClaudeSDKClient / query()           │
│         (Public API Layer)                  │
├─────────────────────────────────────────────┤
│         InternalClient / Query              │
│         (Control Protocol Handler)           │
├─────────────────────────────────────────────┤
│         Transport (SubprocessCLITransport)  │
│         (CLI Process Management)             │
├─────────────────────────────────────────────┤
│         Claude Code CLI Subprocess           │
│         (Actual Agent Execution)             │
└─────────────────────────────────────────────┘
```

### Execution Flow

1. `query()` creates `InternalClient`
2. `InternalClient.process_query()` creates `SubprocessCLITransport`
3. Transport spawns Claude Code CLI as subprocess
4. `Query` handles control protocol
5. Initialize request sent with agent definitions
6. User prompt sent
7. Messages streamed back and parsed
8. On completion, query closes transport

---

## 3. Message Management

### Message Types

```python
Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage | StreamEvent

@dataclass
class UserMessage:
    content: str | list[ContentBlock]
    uuid: str | None = None
    parent_tool_use_id: str | None = None
    tool_use_result: dict[str, Any] | None = None

@dataclass
class AssistantMessage:
    content: list[ContentBlock]
    model: str
    parent_tool_use_id: str | None = None
    error: AssistantMessageError | None = None

@dataclass
class SystemMessage:
    subtype: str  # task_started, task_progress, task_notification
    data: dict[str, Any]

@dataclass
class ResultMessage:
    subtype: str
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    stop_reason: str | None = None
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
```

### Context Window Management

The SDK does NOT directly manage context window - handled by Claude Code CLI:
- `get_context_usage()` returns breakdown of token usage
- `max_turns` limits conversation turns
- `max_budget_usd` caps spending
- `task_budget` sets token budget for the model

---

## 4. Session and History

Sessions stored at: `~/.claude/projects/<project-hash>/<session-uuid>.jsonl`

```python
# Session operations
list_sessions(directory=None, limit=None, offset=0, include_worktrees=True)
get_session_info(session_id, directory=None)
get_session_messages(session_id, directory=None, limit=None, offset=0)
rename_session(session_id, title, directory=None)
tag_session(session_id, tag, directory=None)
delete_session(session_id, directory=None)
fork_session(session_id, directory=None)
```

---

## 5. Customizing Agent Behavior

### ClaudeAgentOptions Configuration

```python
ClaudeAgentOptions(
    # Agent definition
    agents: dict[str, AgentDefinition],

    # Tools
    tools: list[str] | ToolsPreset,
    allowed_tools: list[str],
    disallowed_tools: list[str],
    mcp_servers: dict[str, McpServerConfig],

    # Execution control
    permission_mode: PermissionMode,
    max_turns: int,
    max_budget_usd: float,
    task_budget: TaskBudget,

    # Model
    model: str,
    fallback_model: str,
    thinking: ThinkingConfig,

    # Hooks
    hooks: dict[HookEvent, list[HookMatcher]],
    can_use_tool: CanUseTool,

    # Session
    session_id: str,
    resume: str,
    fork_session: bool,
    continue_conversation: bool,
)
```

### Thinking Configuration

```python
ThinkingConfigDisabled = {"type": "disabled"}
ThinkingConfigEnabled = {"type": "enabled", "budget_tokens": int}
ThinkingConfigAdaptive = {"type": "adaptive"}  # Auto-selects based on task
```

---

## 6. Building a Text Processing Agent

```python
from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    AssistantMessage,
)

# Define a text processing agent
text_processor_agent = AgentDefinition(
    description="Processes and summarizes web content",
    prompt="""You are a text processing agent. When given a URL or fetch result:
1. Extract the main content
2. Summarize key information
3. Format output clearly
Use the WebFetch tool to retrieve content.""",
    tools=["WebFetch", "Read"],
    model="sonnet",
)

options = ClaudeAgentOptions(
    agents={"text-processor": text_processor_agent},
    allowed_tools=["WebFetch"],
    permission_mode="acceptEdits",
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("Use text-processor to fetch and summarize https://example.com")

    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text)
```
