"""Claude SDK integration for websearch agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from websearch.core.search import Search
from websearch.core.types.maybe import Just, Maybe, Nothing

try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )
    from claude_agent_sdk import query as sdk_query
except ImportError:
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    sdk_query = None
    AssistantMessage = None
    TextBlock = None
    ToolUseBlock = None
    ResultMessage = None

from websearch.core.agent.response_cache import AskResultCache


@dataclass
class AskResult:
    """Result from ask_with_search."""

    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    cached: bool = False
    model: str = "MiniMax-M2.7"
    num_results: int = 0
    # Metadata fields
    duration_ms: int | None = None
    duration_api_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost_usd: float | None = None
    num_turns: int | None = None
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "cached": self.cached,
            "model": self.model,
            "num_results": self.num_results,
            "duration_ms": self.duration_ms,
            "duration_api_ms": self.duration_api_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "num_turns": self.num_turns,
            "stop_reason": self.stop_reason,
        }


async def ask_with_search(
    query: str = "",
    count: int = 5,
    cache_enabled: bool = True,
    model: str = "MiniMax-M2.7",
    max_turns: int = 10,
    verbose: bool = False,
    progress_callback=None,
) -> AskResult:
    """Ask a question using web search and Claude Agent synthesis.

    Args:
        query: The question to ask
        count: Number of search results to fetch
        cache_enabled: Whether to use caching
        model: Claude model to use
        max_turns: Maximum conversation turns
        verbose: Whether to show verbose output

    Returns:
        AskResult with answer and sources
    """
    if ClaudeSDKClient is None or sdk_query is None:
        return AskResult(answer="Claude Agent SDK not available", sources=[])

    # Check answer cache first
    answer_cache = AskResultCache()
    if cache_enabled:
        cached = answer_cache.get(query, count, model)
        if cached is not None:
            cached_response = cached["response"]
            return AskResult(
                answer=cached_response.get("answer", ""),
                sources=cached_response.get("sources", []),
                cached=True,
                model=model,
                num_results=cached_response.get("num_results", 0),
            )

    api_key = os.getenv("BRAVE_API_KEY")
    search = Search(api_key=api_key, cache_enabled=cache_enabled)

    try:
        # Perform web search
        if progress_callback:
            progress_callback("searching", "Searching the web...")
        results, cache_hit = await search.search(query, count=count)

        if results.is_nothing():
            return AskResult(answer="Search failed", sources=[])

        search_results = results.just_value()

        # Fetch content from top results
        if progress_callback:
            progress_callback("fetching", f"Reading {len(search_results)} sources...")
        sources = []
        for r in search_results:
            content = await search.fetch(r.url)
            if content.is_just():
                sources.append({
                    "title": r.title,
                    "url": r.url,
                    "description": r.description,
                    "content": content.just_value(),
                })

        # Prepare context from sources
        context_parts = []
        for i, s in enumerate(sources[:count], 1):
            content_preview = s.get("content", "")[:500]
            context_parts.append(f"[{i}] {s['title']}\n{s['url']}\n{s.get('description', '')}\n{content_preview}...")

        context = "\n\n---\n\n".join(context_parts)

        # Get Claude response
        auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")

        if not auth_token:
            return AskResult(answer="ANTHROPIC_AUTH_TOKEN not set", sources=sources)

        env = {
            "ANTHROPIC_AUTH_TOKEN": auth_token,
            "ANTHROPIC_BASE_URL": base_url,
        }

        options = ClaudeAgentOptions(
            model=model,
            max_turns=max_turns,
            env=env,
        )

        prompt = f"""You are a helpful assistant that answers questions based on web search results.

Question: {query}

Web Search Results:
{context}

Based on the search results above, provide a comprehensive answer to the question.
Format your response in clear Markdown."""

        answer = ""
        # Metadata fields from ResultMessage
        duration_ms: int | None = None
        duration_api_ms: int | None = None
        input_tokens: int | None = None
        output_tokens: int | None = None
        total_cost_usd: float | None = None
        num_turns: int | None = None
        stop_reason: str | None = None

        if progress_callback:
            progress_callback("thinking", "Synthesizing answer...")
        async for message in sdk_query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        answer += block.text
                    elif progress_callback and isinstance(block, ToolUseBlock):
                        progress_callback("tool", f"Using tool: {block.name}")
            elif isinstance(message, ResultMessage):
                # Capture metadata from ResultMessage
                duration_ms = message.duration_ms
                duration_api_ms = message.duration_api_ms
                if message.usage:
                    input_tokens = message.usage.get('input_tokens')
                    output_tokens = message.usage.get('output_tokens')
                total_cost_usd = message.total_cost_usd
                num_turns = message.num_turns
                stop_reason = message.stop_reason
                if verbose and message.total_cost_usd and isinstance(message.total_cost_usd, (int, float)):
                    print(f"Cost: ${message.total_cost_usd:.4f}")

        if not answer:
            answer = "No response from Claude"

        # Cache the answer for future requests
        source_list = [{"title": s["title"], "url": s["url"], "description": s.get("description", "")} for s in sources]
        if cache_enabled:
            answer_cache.set(query, count, model, answer, source_list)

        return AskResult(
            answer=answer,
            sources=source_list,
            cached=False,
            model=model,
            num_results=len(sources),
            duration_ms=duration_ms,
            duration_api_ms=duration_api_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=total_cost_usd,
            num_turns=num_turns,
            stop_reason=stop_reason,
        )

    finally:
        await search.close()


async def process_content(
    url: str,
    content: str,
    prompt: str,
    model: str = "MiniMax-M2.7",
    verbose: bool = False,
) -> Maybe[str]:
    """Process URL content with Claude.

    Args:
        url: URL that was fetched (for context)
        content: Fetched content (markdown)
        prompt: Prompt for Claude to process the content
        model: Claude model to use
        verbose: Whether to print verbose output

    Returns:
        Maybe containing processed response string
    """
    if ClaudeSDKClient is None or sdk_query is None:
        return Nothing()

    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")

    if not auth_token:
        return Nothing()

    env = {
        "ANTHROPIC_AUTH_TOKEN": auth_token,
        "ANTHROPIC_BASE_URL": base_url,
    }

    options = ClaudeAgentOptions(
        model=model,
        env=env,
    )

    full_prompt = f"""Given the following content from {url}, {prompt}

---

{content}"""

    answer = ""
    async for message in sdk_query(prompt=full_prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    answer += block.text
        elif isinstance(message, ResultMessage):
            if verbose and message.total_cost_usd and isinstance(message.total_cost_usd, (int, float)):
                print(f"Cost: ${message.total_cost_usd:.4f}")

    if not answer:
        return Nothing()

    return Just(answer)
