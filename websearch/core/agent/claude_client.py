"""Claude SDK integration for websearch agent."""

from __future__ import annotations

import os
from typing import Any

from websearch.core.agent.response_cache import ClaudeResponseCache
from websearch.core.search import Search
from websearch.core.types.maybe import Just, Maybe, Nothing

try:
    from claude_agent_sdk import ClaudeAgentSDK
    from claude_agent_sdk.types import MCPServer, MCPTool
except ImportError:
    ClaudeAgentSDK = None
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
    if ClaudeAgentSDK is None:
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
    if ClaudeAgentSDK is None:
        return Nothing()

    base_url = os.getenv("ANTHROPIC_BASE_URL")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")

    if not auth_token:
        return Nothing()

    sdk = ClaudeAgentSDK(
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
