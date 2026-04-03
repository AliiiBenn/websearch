"""Claude Agent integration for web search synthesis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from websearch.core.search import Search
from websearch.core.search.types import SearchResult, SearchResults
from websearch.core.types.maybe import Just, Nothing


@dataclass
class AskResult:
    """Result of ask_with_search operation."""

    query: str
    answer: str
    sources: list[dict[str, Any]]
    cached: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "query": self.query,
            "answer": self.answer,
            "sources": self.sources,
            "cached": self.cached,
        }


async def ask_with_search(
    query: str,
    count: int = 5,
    cache_enabled: bool = True,
    model: str = "MiniMax-M2.7",
    max_turns: int = 10,
    verbose: bool = False,
) -> AskResult:
    """Process a query using web search and Claude Agent synthesis.

    Args:
        query: The search query
        count: Number of search results to fetch (1-20)
        cache_enabled: Whether to use caching
        model: Model to use for synthesis
        max_turns: Maximum conversation turns
        verbose: Whether to show verbose output

    Returns:
        AskResult with query, answer, sources, and cached status
    """
    search_client = Search(cache_enabled=cache_enabled)

    try:
        # Perform the search
        result, cache_hit = await search_client.search(
            query, count=count, use_cache=cache_enabled
        )

        if isinstance(result, Nothing):
            return AskResult(
                query=query,
                answer="Search failed. Could not retrieve results.",
                sources=[],
                cached=False,
            )

        search_results = result.just_value()

        # Build sources list with cache status
        sources = []
        for r in search_results.results:
            sources.append({
                "title": r.title,
                "url": r.url,
                "description": r.description,
                "age": r.age,
            })

        # Synthesize answer using Claude Agent with search context
        # Build context from search results
        context_parts = []
        for i, r in enumerate(search_results.results, 1):
            context_parts.append(f"[{i}] {r.title}\nURL: {r.url}\n{r.description}")

        context = "\n\n".join(context_parts)

        # Use Claude Agent to synthesize answer
        # Note: This is a simplified implementation that constructs a prompt
        # In production, this would use the actual Claude API
        answer = await _synthesize_with_claude(
            query=query,
            context=context,
            sources=sources,
            model=model,
            max_turns=max_turns,
        )

        return AskResult(
            query=query,
            answer=answer,
            sources=sources,
            cached=cache_hit,
        )
    finally:
        await search_client.close()


async def _synthesize_with_claude(
    query: str,
    context: str,
    sources: list[dict[str, Any]],
    model: str,
    max_turns: int,
) -> str:
    """Synthesize answer using Claude Agent.

    This is a placeholder implementation. In production, this would
    integrate with the actual Claude API to process the query with
    the search context.

    Args:
        query: The user's query
        context: Formatted search results context
        sources: List of source dicts
        model: Model to use
        max_turns: Max conversation turns

    Returns:
        Synthesized answer string
    """
    # Build a structured prompt for the agent
    prompt = _build_agent_prompt(query, context, sources, max_turns)

    # In a full implementation, this would call the Claude API
    # For now, we return a structured response based on the sources
    answer = _generate_answer_from_sources(query, sources)

    return answer


def _build_agent_prompt(
    query: str,
    context: str,
    sources: list[dict[str, Any]],
    max_turns: int,
) -> str:
    """Build the agent prompt from query and sources."""
    sources_text = "\n".join(
        f"- {s['title']}: {s['url']}" for s in sources
    )

    return f"""You are a research assistant that answers questions based on web search results.

User Query: {query}

Search Results:
{context}

Instructions:
1. Synthesize a comprehensive answer from the search results above
2. Cite your sources using the URL references
3. If the search results don't contain enough information, say so
4. Keep your answer focused and informative

Max conversation turns: {max_turns}

Answer the query based on the provided search results.
"""


def _generate_answer_from_sources(
    query: str,
    sources: list[dict[str, Any]],
) -> str:
    """Generate a formatted answer from sources.

    This creates a basic synthesized answer from the search results.
    In production, this would be replaced with actual Claude API calls.

    Args:
        query: The user's query
        sources: List of search result dicts

    Returns:
        Formatted answer string
    """
    if not sources:
        return "No search results available to answer this query."

    # Build answer from sources
    lines = []
    lines.append(f"Based on web search results for: {query}\n")

    for i, source in enumerate(sources, 1):
        lines.append(f"[{i}] {source['title']}")
        lines.append(f"    URL: {source['url']}")
        if source.get('description'):
            lines.append(f"    {source['description']}")
        lines.append("")

    lines.append("Note: This answer was generated from the search results above.")
    lines.append("In production, this would use Claude API for intelligent synthesis.")

    return "\n".join(lines)


async def process_content(
    markdown_content: str,
    prompt: str,
    model: str = "MiniMax-M2.7",
    verbose: bool = False,
    url: str | None = None,
) -> str:
    """Process content with Claude Agent.

    Args:
        markdown_content: The markdown content to process.
        prompt: The prompt/instructions for Claude.
        model: Model to use (default: MiniMax-M2.7).
        verbose: Whether to include partial messages.
        url: Optional URL source for reference.

    Returns:
        The agent's response as a string.

    Raises:
        AgentAuthError: If authentication fails.
        AgentResponseError: If Claude returns an error.
    """
    import os

    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        ResultMessage,
        AssistantMessage,
        create_sdk_mcp_server,
        tool,
    )

    from websearch.core.agent.errors import AgentAuthError, AgentResponseError

    @tool("websearch_fetch", "Fetch URL as Markdown", {"url": str})
    async def websearch_fetch(args: dict) -> dict:
        """MCP tool that fetches a URL and returns Markdown."""
        from websearch.core.search import Search
        from websearch.core.types.maybe import Nothing

        tool_url = args["url"]
        search = Search(cache_enabled=True)
        result = await search.fetch(tool_url)
        await search.close()

        if isinstance(result, Nothing):
            return {"content": [{"type": "text", "text": "Failed to fetch URL"}], "is_error": True}
        return {"content": [{"type": "text", "text": result.just_value()}]}

    @tool("websearch_search", "Search the web", {"query": str, "count": int})
    async def websearch_search(args: dict) -> dict:
        """MCP tool for web search."""
        from websearch.core.search import Search
        from websearch.core.types.maybe import Nothing

        tool_query = args["query"]
        tool_count = args.get("count", 5)

        search = Search(api_key=os.environ.get("BRAVE_API_KEY"))
        results, _ = await search.search(tool_query, count=tool_count)
        await search.close()

        if isinstance(results, Nothing):
            return {"content": [{"type": "text", "text": "Search failed"}], "is_error": True}

        formatted = "\n".join([
            f"[{i}] {r.title}\n{r.url}\n{r.description}\n"
            for i, r in enumerate(results.just_value().results, 1)
        ])
        return {"content": [{"type": "text", "text": formatted}]}

    mcp_server = create_sdk_mcp_server(
        name="websearch",
        version="1.0.0",
        tools=[websearch_fetch, websearch_search],
    )

    system_prompt = f"""You are a content processing agent.
Analyze the provided web content and follow the user's instructions.

User's instructions: {prompt}

Format output as clean Markdown."""

    query_content = f"Content:\n{markdown_content}\n\n---"

    if url:
        query_content = f"URL: {url}\n\n{query_content}"

    query_content += f"\n\nFollow the instructions: {prompt}"

    options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_BASE_URL": os.environ.get(
                "ANTHROPIC_BASE_URL",
                "https://api.minimax.io/anthropic",
            ),
            "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        },
        model=model,
        mcp_servers={"websearch": mcp_server},
        allowed_tools=[
            "mcp__websearch__websearch_fetch",
            "mcp__websearch__websearch_search",
        ],
        system_prompt=system_prompt,
        include_partial_messages=verbose,
    )

    # Check for auth token
    if not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        raise AgentAuthError("ANTHROPIC_AUTH_TOKEN environment variable is not set")

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(query_content)

            async for msg in client.receive_response():
                if isinstance(msg, ResultMessage):
                    return msg.result if msg.result else ""
                elif isinstance(msg, AssistantMessage):
                    # In verbose mode, we could print partial messages here
                    pass

        return ""
    except AgentAuthError:
        raise
    except Exception as e:
        error_msg = str(e).lower()
        if "auth" in error_msg or "token" in error_msg or "401" in error_msg:
            raise AgentAuthError(f"Authentication failed: {e}")
        raise AgentResponseError(f"Agent processing failed: {e}")
