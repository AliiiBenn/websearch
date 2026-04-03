# Message Handling: Claude Agent SDK Python

## 1. How Messages Are Structured

### Message Types (Discriminated Union)

```python
Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage | StreamEvent
```

### UserMessage

```python
@dataclass
class UserMessage:
    content: str | list[ContentBlock]
    uuid: str | None = None
    parent_tool_use_id: str | None = None
    tool_use_result: dict[str, Any] | None = None
```

### AssistantMessage

```python
@dataclass
class AssistantMessage:
    content: list[ContentBlock]  # TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
    model: str
    parent_tool_use_id: str | None = None
    error: AssistantMessageError | None = None
```

### ContentBlock Types

```python
ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock

@dataclass
class TextBlock:
    text: str

@dataclass
class ThinkingBlock:
    thinking: str
    signature: str

@dataclass
class ToolUseBlock:
    id: str          # Tool use ID
    name: str        # Tool name (e.g., "Bash", "Read")
    input: dict[str, Any]

@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str | list[dict[str, Any]] | None = None
    is_error: bool | None = None
```

### SystemMessage

```python
@dataclass
class SystemMessage:
    subtype: str  # "task_started", "task_progress", "task_notification"
    data: dict[str, Any]
```

### ResultMessage

```python
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
    result: str | None = None
    structured_output: Any = None
```

### StreamEvent

```python
@dataclass
class StreamEvent:
    uuid: str
    session_id: str
    event: dict[str, Any]  # Raw Anthropic API stream event
    parent_tool_use_id: str | None = None
```

---

## 2. Conversation History Management

### Session Storage

Sessions stored as JSONL files:
```
~/.claude/projects/<project-hash>/<session-uuid>.jsonl
```

### Reading Sessions

```python
from claude_agent_sdk._internal.sessions import list_sessions, get_session_messages

# List all sessions
sessions = list_sessions(directory=None, limit=10)

# Get messages from a session
messages = get_session_messages(
    session_id="abc-123",
    directory=None,
    limit=100,
    offset=0
)
```

### Conversation Chain Reconstruction

```python
def _build_conversation_chain(entries: list[_TranscriptEntry]) -> list[_TranscriptEntry]:
    # Walk from leaf to root via parentUuid
    # Returns messages in chronological order (root -> leaf)
```

### Visibility Filtering

Messages filtered to exclude:
- `isMeta: true` messages
- `isSidechain: true` messages
- `teamName` set messages
- Non user/assistant messages

---

## 3. Context Window Limits

### Thinking Configuration

```python
class ThinkingConfigAdaptive(TypedDict):
    type: Literal["adaptive"]

class ThinkingConfigEnabled(TypedDict):
    type: Literal["enabled"]
    budget_tokens: int

class ThinkingConfigDisabled(TypedDict):
    type: Literal["disabled"]
```

### SDK-Level Limits

```python
@dataclass
class ClaudeAgentOptions:
    max_turns: int | None = None        # Max conversation turns
    max_budget_usd: float | None = None  # Max cost budget
    task_budget: TaskBudget              # Token budgeting
```

### CLI-Level Context Management

The SDK delegates context window management to Claude Code CLI:
- Automatic conversation compaction (`isCompactSummary` messages)
- Token budgeting
- Long conversation truncation

---

## 4. Message Formatting

### Wire Format for Sending Messages

```python
# String prompt conversion
user_message = {
    "type": "user",
    "session_id": "",
    "message": {"role": "user", "content": prompt},
    "parent_tool_use_id": None,
}

# AsyncIterable message format
{
    "type": "user",
    "message": {"role": "user", "content": "..."},
    "parent_tool_use_id": None,
    "session_id": "qa-session",
}
```

### Message Parser

```python
def parse_message(data: dict[str, Any]) -> Message | None:
    match message_type := data.get("type"):
        case "user":
            # Parse UserMessage
        case "assistant":
            # Parse AssistantMessage with content blocks
        case "system":
            # Parse system messages
        case "result":
            # Parse ResultMessage
        case "stream_event":
            # Parse StreamEvent
        case _:
            # Skip unknown types
```

---

## 5. Sending System Prompts

### System Prompt Options

```python
class ClaudeAgentOptions:
    system_prompt: str | SystemPromptPreset | None = None
```

### System Prompt Preset Format

```python
class SystemPromptPreset(TypedDict):
    type: Literal["preset"]
    preset: Literal["claude_code"]
    append: NotRequired[str]
```

### Examples

```python
# No system prompt (vanilla Claude)
async for message in query(prompt="What is 2 + 2?"):
    ...

# String system prompt
options = ClaudeAgentOptions(
    system_prompt="You are a pirate assistant.",
)

# Preset with append
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "Always end your response with a fun fact.",
    },
)
```

---

## 6. Multi-Turn Conversations

### Two APIs

**1. `query()` - Stateless**
```python
# Each call is independent - no conversation state
async for message in query(prompt="First question"):
    ...
async for message in query(prompt="Follow-up"):
    ...  # No context from first question
```

**2. `ClaudeSDKClient` - Stateful**
```python
async with ClaudeSDKClient() as client:
    # First turn
    await client.query("What's the capital of France?")
    async for msg in client.receive_response():
        ...

    # Second turn - maintains context
    await client.query("What's the population?")
    async for msg in client.receive_response():
        ...
```

---

## 7. Sending Fetched Content to Agent

```python
from claude_agent_sdk import ClaudeSDKClient, AssistantMessage, TextBlock

async with ClaudeSDKClient() as client:
    # Send fetched content as user message
    fetched_content = "Web page content here..."

    await client.query(
        f"Analyze this content: {fetched_content}"
    )

    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"Analysis: {block.text}")
```

### With Structured Async Iterable

```python
async def send_fetched_content():
    yield {
        "type": "user",
        "message": {
            "role": "user",
            "content": "Here is the content to analyze:"
        },
        "parent_tool_use_id": None,
        "session_id": "fetch-session",
    }
    yield {
        "type": "user",
        "message": {"role": "user", "content": fetched_content},
        "parent_tool_use_id": None,
        "session_id": "fetch-session",
    }
    yield {
        "type": "user",
        "message": {"role": "user", "content": "What are the key points?"},
        "parent_tool_use_id": None,
        "session_id": "fetch-session",
    }

async with ClaudeSDKClient() as client:
    await client.query(send_fetched_content())
    async for msg in client.receive_response():
        ...
```
