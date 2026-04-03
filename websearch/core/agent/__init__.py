"""Claude Agent integration for web search."""

from websearch.core.agent.claude_client import (
    AskResult,
    ask_with_search,
    process_content,
)
from websearch.core.agent.errors import (
    AgentAuthError,
    AgentError,
    AgentFetchError,
    AgentResponseError,
    AgentTimeoutError,
)

__all__ = [
    "AskResult",
    "ask_with_search",
    "process_content",
    "AgentError",
    "AgentFetchError",
    "AgentAuthError",
    "AgentResponseError",
    "AgentTimeoutError",
]
