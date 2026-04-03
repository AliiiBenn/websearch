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
from rich.progress import Progress
from rich.table import Table

from websearch.core.agent.claude_client import ask_with_search, process_content
from websearch.core.agent.errors import AgentAuthError, AgentFetchError
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
            result, cache_hit = await search_client.search(query, count=count, search_type=search_type, use_cache=not no_cache)

            if isinstance(result, Nothing):
                console.print("[red]Error: Search failed[/red]")
                sys.exit(1)

            search_results = result.just_value()

            if verbose:
                cache_status = "[green]cache hit[/green]" if cache_hit else "[yellow]cache miss[/yellow]"
                console.print(f"[dim]Status: {cache_status} | Source: {'cached' if cache_hit else 'API'}[/dim]\n")
                console.print(f"[bold #88c0d0]# {query}[/bold #88c0d0]\n")
                console.print(f"[dim]Found {len(search_results)} results[/dim]\n")

                table = Table(show_header=True, header_style="bold", box=None, pad_edge=False, min_width=120)
                table.add_column("#", style="dim", width=3, no_wrap=True)
                table.add_column("Result", style="white", no_wrap=True)
                table.add_column("Description", style="dim", max_width=60)

                for i, r in enumerate(search_results, 1):
                    result_cell = f"[link={r.url}]{r.title}[/link]\n[dim]{r.url}[/dim]"
                    table.add_row(
                        str(i),
                        result_cell,
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


@main.command(name="ask")
@click.argument("query")
@click.option("--count", "-n", default=5, help="Number of search results (1-20)")
@click.option("--no-cache", is_flag=True, help="Disable caching")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--model", "-m", default="MiniMax-M2.7", help="Model to use")
@click.option("--max-turns", "-t", default=10, help="Max conversation turns")
def ask(query, count, no_cache, output, verbose, model, max_turns):
    """Ask a question using web search and Claude Agent synthesis."""
    api_key = get_api_key()
    if not api_key:
        console.print("[red]Error: BRAVE_API_KEY environment variable is not set[/red]")
        console.print("[dim]Get your API key at https://brave.com/search/api/[/dim]")
        sys.exit(4)

    if count < 1 or count > 20:
        console.print(f"[red]Error: Count must be between 1 and 20, got {count}[/red]")
        sys.exit(2)

    async def _ask():
        try:
            if verbose:
                console.print(f"[dim]Searching for: {query}[/dim]")
                console.print(f"[dim]Using model: {model} (max {max_turns} turns)[/dim]\n")

            with Progress(auto_refresh=True, console=console) as progress:
                task = progress.add_task("[dim]Starting...[/dim]", total=None)

                def update_progress(step: str, message: str):
                    step_labels = {
                        "searching": "Searching",
                        "fetching": "Reading sources",
                        "thinking": "Synthesizing",
                        "tool": "Using tool",
                    }
                    label = step_labels.get(step, "Processing")
                    progress.update(task, description=f"[dim]{label}: {message}[/dim]")

                result = await ask_with_search(
                    query=query,
                    count=count,
                    cache_enabled=not no_cache,
                    model=model,
                    max_turns=max_turns,
                    verbose=verbose,
                    progress_callback=update_progress,
                )
                progress.remove_task(task)

            if verbose:
                cache_status = "[green]cache hit[/green]" if result.cached else "[yellow]cache miss[/yellow]"
                console.print(f"[dim]Cache: {cache_status}[/dim]\n")

                # Show sources table
                sources_table = Table(
                    show_header=True,
                    header_style="bold",
                    box=None,
                    pad_edge=False,
                    min_width=120,
                    title="Sources",
                )
                sources_table.add_column("#", style="dim", width=3, no_wrap=True)
                sources_table.add_column("Title", style="white", no_wrap=False)
                sources_table.add_column("URL", style="dim", no_wrap=False)
                sources_table.add_column("Cached", style="dim", width=8, no_wrap=True)

                for i, s in enumerate(result.sources, 1):
                    cache_indicator = "[green]yes[/green]" if result.cached else "[yellow]no[/yellow]"
                    sources_table.add_row(
                        str(i),
                        s["title"],
                        s["url"],
                        cache_indicator,
                    )

                console.print(sources_table)
                console.print()

            # Output result
            # Print cache status to stderr (not stdout) so it doesn't break piping
            cache_status = "[green]cache hit[/green]" if result.cached else "[yellow]cache miss[/yellow]"
            from rich.console import Console
            err_console = Console(stderr=True)
            err_console.print(f"[dim][Cache: {cache_status}][/dim]")

            if output:
                output.write_text(result.answer)
                if verbose:
                    console.print(f"[green]Saved to {output}[/green]")
            else:
                console.print(result.answer)

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            sys.exit(1)

    asyncio.run(_ask())


@main.command(name="process")
@click.argument("url")
@click.option("--prompt", "-p", required=True, help="Custom prompt for Claude Agent")
@click.option("--refresh", "-r", is_flag=True, help="Skip cache, force fresh fetch")
@click.option("--no-cache", is_flag=True, help="Disable response caching")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose/streaming output")
@click.option("--model", "-m", default="MiniMax-M2.7", help="Model to use")
def process(url, prompt, refresh, no_cache, output, verbose, model):
    """Fetch URL and process content with Claude Agent."""
    async def _process():
        search = Search(cache_enabled=not no_cache)
        try:
            if verbose:
                console.print(f"[dim]Fetching {url}...[/dim]")

            result = await search.fetch(url, refresh=refresh)

            if isinstance(result, Nothing):
                console.print("[red]Failed to fetch URL[/red]")
                sys.exit(1)

            markdown_content = result.just_value()

            if verbose:
                console.print("[dim]Processing...[/dim]")

            maybe_response = await process_content(
                url=url,
                content=markdown_content,
                prompt=prompt,
                model=model,
                verbose=verbose,
            )

            if isinstance(maybe_response, Nothing):
                console.print("[red]Processing failed[/red]")
                sys.exit(3)

            response = maybe_response.just_value()

            output_data = {
                "url": url,
                "prompt": prompt,
                "response": response,
                "cached": False,
            }

            if output:
                output.write_text(json.dumps(output_data, indent=2))
                if verbose:
                    console.print(f"[green]Saved to {output}[/green]")
            else:
                console.print(json.dumps(output_data, indent=2))

        except AgentFetchError:
            console.print("[red]Failed to fetch URL[/red]")
            sys.exit(1)
        except AgentAuthError:
            console.print("[red]Authentication failed. Check ANTHROPIC_AUTH_TOKEN[/red]")
            sys.exit(4)
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            sys.exit(3)
        finally:
            await search.close()

    asyncio.run(_process())


if __name__ == "__main__":
    main()
