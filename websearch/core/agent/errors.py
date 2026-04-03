"""Agent-specific errors."""

from __future__ import annotations


class AgentError(Exception):
    """Base agent error."""

    pass


class AgentFetchError(AgentError):
    """Failed to fetch URL."""

    pass


class AgentResponseError(AgentError):
    """Claude returned an error."""

    pass


class AgentTimeoutError(AgentError):
    """Agent processing timed out."""

    pass


class AgentAuthError(AgentError):
    """Authentication failed."""

    pass
