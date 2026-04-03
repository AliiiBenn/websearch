"""Websearch CLI - Fetch URLs and search the web."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from websearch.core.search import Search
from websearch.core.types.maybe import Nothing

console = Console()

VALID_SEARCH_TYPES = ["web", "news", "images", "videos"]


def get_api_key() -> Optional[str]:
    """Get API key from environment."""
    return os.environ.get("BRAVE_API_KEY")


@click.group()
def main():
    """Websearch CLI - Fetch URLs and search the web."""
    pass


@main.command()
def ping():
    """Check if the CLI is working."""
    click.echo("pong")


@main.command()
@click.argument("url")
@click.option("--refresh", "-r", is_flag=True, help="Skip cache and force fresh fetch")
@click.option("--no-cache", is_flag=True, help="Disable caching")
@click.option("--no-verify", is_flag=True, help="Skip SSL certificate verification")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def fetch(
    url: str,
    refresh: bool,
    no_cache: bool,
    no_verify: bool,
    output: Optional[Path],
    verbose: bool,
):
    """Fetch a URL and convert to Markdown."""
    async def _fetch():
        search = Search(cache_enabled=not no_cache, verify_ssl=not no_verify)
        try:
            if verbose:
                console.print(f"[dim]Fetching {url}...[/dim]")

            result = await search.fetch(url, refresh=refresh)

            if isinstance(result, Nothing):
                console.print("[red]Failed to fetch URL[/red]")
                sys.exit(1)

            md = result.just_value()

            if output:
                output.write_text(md)
                if verbose:
                    console.print(f"[green]Saved to {output}[/green]")
            else:
                console.print(md)
        finally:
            await search.close()

    asyncio.run(_fetch())


@main.command()
@click.argument("query")
@click.option("-n", "--count", default=10, help="Number of results (1-50, default: 10)")
@click.option("-t", "--type", "search_type", default="web", help=f"Result type: {', '.join(VALID_SEARCH_TYPES)} (default: web)")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Show results in verbose table format")
@click.option("--no-cache", is_flag=True, help="Disable caching")
def search(
    query: str,
    count: int,
    search_type: str,
    output: Optional[Path],
    verbose: bool,
    no_cache: bool,
):
    """Search the web using Brave Search API."""
    api_key = get_api_key()
    if not api_key:
        console.print("[red]Error: BRAVE_API_KEY environment variable is not set[/red]")
        console.print("[dim]Get your API key at https://brave.com/search/api/[/dim]")
        sys.exit(4)

    if count < 1 or count > 50:
        console.print(f"[red]Error: Count must be between 1 and 50, got {count}[/red]")
        sys.exit(2)

    if search_type not in VALID_SEARCH_TYPES:
        console.print(f"[red]Error: Unknown search type \"{search_type}\". Valid types: {', '.join(VALID_SEARCH_TYPES)}[/red]")
        sys.exit(2)

    async def _search():
        search_client = Search(api_key=api_key, cache_enabled=not no_cache)
        try:
            result = await search_client.search(query, count=count, search_type=search_type)

            if isinstance(result, Nothing):
                console.print("[red]Error: Search failed[/red]")
                sys.exit(1)

            search_results = result.just_value()

            if verbose:
                console.print(f"[bold #88c0d0]# {query}[/bold #88c0d0]\n")
                console.print(f"[dim]Found {len(search_results)} results[/dim]\n")

                table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
                table.add_column("#", style="dim", width=3)
                table.add_column("Title", style="white")
                table.add_column("URL", style="dim")
                table.add_column("Description", style="dim", max_width=60)

                for i, r in enumerate(search_results, 1):
                    table.add_row(
                        str(i),
                        f"[link={r.url}]{r.title}[/link]",
                        r.url,
                        r.description[:80] + "..." if len(r.description) > 80 else r.description,
                    )

                console.print(table)

                if output:
                    output.write_text(table.to_string())
                    console.print(f"\n[green]Saved to {output}[/green]")
            else:
                output_data = {
                    "query": query,
                    "count": len(search_results),
                    "results": [
                        {
                            "title": r.title,
                            "url": r.url,
                            "description": r.description,
                            "age": r.age,
                        }
                        for r in search_results
                    ]
                }
                json_str = json.dumps(output_data, indent=2)
                if output:
                    output.write_text(json_str)
                else:
                    console.print(json_str)

        finally:
            await search_client.close()

    asyncio.run(_search())


if __name__ == "__main__":
    main()
