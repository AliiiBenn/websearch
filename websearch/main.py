"""Websearch CLI - Fetch URLs and search the web."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from websearch.core.search import Search
from websearch.core.types.maybe import Nothing

console = Console()


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


if __name__ == "__main__":
    main()
