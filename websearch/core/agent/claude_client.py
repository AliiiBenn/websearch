"""Claude SDK integration for websearch agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from websearch.core.agent.response_cache import ClaudeResponseCache
from websearch.core.search import Search
from websearch.core.types.maybe import Just, Maybe, Nothing

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from claude_agent_sdk.types import MCPServer, MCPTool
except ImportError:
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    MCPServer = None
    MCPTool = None


def create_websearch_mcp_server(
    api_key: str | None = None,
    cache_ttl: float = 7200,
) -> MCPServer | None:
    """Create an MCP server with websearch tools.

    Args:
        api_key: Optional API key for Brave Search
        cache_ttl: TTL for Claude response cache in seconds

    Returns:
        MCP server instance or None if SDK not available
    """
    if ClaudeSDKClient is None:
        return None

    search_instance = Search(api_key=api_key)
    cache = ClaudeResponseCache(ttl=cache_ttl)

    async def websearch_fetch(
        url: str,
        prompt: str,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Fetch a URL and process with Claude.

        Args:
            url: URL to fetch
            prompt: Prompt for Claude to process the content
            refresh: Skip cache and force fresh fetch

        Returns:
            Dict with response and metadata
        """
        # Check cache first unless refresh is requested
        if not refresh:
            cached = cache.get(url, prompt)
            if cached is not None:
                return cached

        # Fetch URL content
        content = await search_instance.fetch(url, refresh=refresh)
        if content.is_nothing():
            return {
                "error": "Failed to fetch URL",
                "url": url,
            }

        markdown_content = content.just_value()

        # Cache the response
        cache.set(url, prompt, markdown_content)

        return {
            "response": markdown_content,
            "url": url,
            "cached": False,
        }

    async def websearch_search(
        query: str,
        count: int = 10,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Search the web and optionally process with Claude.

        Args:
            query: Search query
            count: Number of results
            prompt: Optional prompt for Claude to process results

        Returns:
            Dict with search results and optional processed response
        """
        results, cache_hit = await search_instance.search(query, count=count)

        if results.is_nothing():
            return {
                "error": "Search failed",
                "query": query,
            }

        search_results = results.just_value()

        if prompt:
            # Process all results with Claude
            processed = []
            for result in search_results.results:
                cached = cache.get(result.url, prompt)
                if cached is not None:
                    processed.append(
                        {
                            **result.__dict__,
                            "processed": cached["response"],
                            "cached": True,
                        }
                    )
                else:
                    content = await search_instance.fetch(result.url)
                    if content.is_just():
                        cache.set(result.url, prompt, content.just_value())
                        processed.append(
                            {
                                **result.__dict__,
                                "processed": content.just_value(),
                                "cached": False,
                            }
                        )
                    else:
                        processed.append(
                            {
                                **result.__dict__,
                                "processed": None,
                                "cached": False,
                            }
                        )
            return {
                "query": query,
                "results": processed,
                "count": len(processed),
                "cache_hit": cache_hit,
            }

        return {
            "query": query,
            "results": [
                {"title": r.title, "url": r.url, "description": r.description, "age": r.age}
                for r in search_results.results
            ],
            "count": len(search_results.results),
            "cache_hit": cache_hit,
        }

    tools: list[MCPTool] = [
        {
            "name": "websearch_fetch",
            "description": "Fetch a URL and optionally process with Claude",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "prompt": {
                        "type": "string",
                        "description": "Prompt for Claude to process the content",
                    },
                    "refresh": {
                        "type": "boolean",
                        "description": "Skip cache and force fresh fetch",
                        "default": False,
                    },
                },
                "required": ["url", "prompt"],
            },
        },
        {
            "name": "websearch_search",
            "description": "Search the web using Brave Search API",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "count": {
                        "type": "integer",
                        "description": "Number of results (1-50)",
                        "default": 10,
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Optional prompt for Claude to process results",
                    },
                },
                "required": ["query"],
            },
        },
    ]

    # Create async tool handlers
    async def handle_tool_call(name: str, arguments: dict[str, Any]) -> Any:
        if name == "websearch_fetch":
            return await websearch_fetch(**arguments)
        elif name == "websearch_search":
            return await websearch_search(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    return MCPServer(tools=tools, handle_tool_call=handle_tool_call)


async def process_content(
    url: str,
    content: str,
    prompt: str,
    model: str = "claude-opus-4-5",
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
    if ClaudeSDKClient is None:
        return Nothing()

    base_url = os.getenv("ANTHROPIC_BASE_URL")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")

    if not auth_token:
        return Nothing()

    sdk = ClaudeSDKClient(
        base_url=base_url,
        auth_token=auth_token,
    )

    try:
        response = await sdk.complete(
            prompt=f"Given the following content from {url}, {prompt}\n\n---\n\n{content}",
            model=model,
            verbose=verbose,
        )
        return Just(response)
    except Exception:
        return Nothing()


@dataclass
class AskResult:
    """Result from ask_with_search."""

    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    cached: bool = False
    model: str = "MiniMax-M2.7"
    num_results: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "cached": self.cached,
            "model": self.model,
            "num_results": self.num_results,
        }


async def ask_with_search(
    query: str,
    count: int = 5,
    cache_enabled: bool = True,
    model: str = "MiniMax-M2.7",
    max_turns: int = 10,
    verbose: bool = False,
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
    if ClaudeSDKClient is None:
        return AskResult(answer="Claude Agent SDK not available", sources=[])

    api_key = os.getenv("BRAVE_API_KEY")
    search = Search(api_key=api_key, cache_enabled=cache_enabled)

    try:
        # Perform web search
        results, cache_hit = await search.search(query, count=count)

        if results.is_nothing():
            return AskResult(answer="Search failed", sources=[])

        search_results = results.just_value()

        # Fetch content from top results
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
            context_parts.append(f"[{i}] {s['title']}\n{s['url']}\n{s.get('description', '')}\n{s.get('content', '')[:500]}...")

        context = "\n\n---\n\n".join(context_parts)

        # Get Claude response
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")

        if not auth_token:
            return AskResult(answer="ANTHROPIC_AUTH_TOKEN not set", sources=sources)

        sdk = ClaudeSDKClient(
            base_url=base_url,
            auth_token=auth_token,
        )

        prompt = f"""You are a helpful assistant that answers questions based on web search results.

Question: {query}

Web Search Results:
{context}

Based on the search results above, provide a comprehensive answer to the question.
Format your response in clear Markdown."""

        try:
            response = await sdk.complete(
                prompt=prompt,
                model=model,
                verbose=verbose,
            )
            answer = response if response else "No response from Claude"
        except Exception as e:
            answer = f"Error getting response from Claude: {str(e)}"

        return AskResult(
            answer=answer,
            sources=[{"title": s["title"], "url": s["url"], "description": s.get("description", "")} for s in sources],
            cached=cache_hit,
            model=model,
            num_results=len(sources),
        )

    finally:
        await search.close()
