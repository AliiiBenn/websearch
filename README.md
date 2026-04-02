<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="public/banner.jpg">
    <source media="(prefers-color-scheme: light)" srcset="public/banner.jpg">
    <img src="public/banner.jpg" alt="Websearch CLI Logo" width="100%">
  </picture>
</p>

<h1 align="center">Websearch CLI</h1>

<p align="center">
  Fetch URLs and search the web from your terminal. Fast, simple, and extensible.
</p>

<p align="center">
  <a href="https://pypi.org/project/websearch/">
    <img src="https://img.shields.io/pypi/v/websearch" alt="PyPI Version">
  </a>
  <a href="https://github.com/AliiiBenn/websearch">
    <img src="https://img.shields.io/github/license/AliiiBenn/websearch" alt="License">
  </a>
  <a href="https://github.com/AliiiBenn/websearch/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/AliiiBenn/websearch/test" alt="Tests">
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.14+-blue" alt="Python">
  </a>
</p>

Fetch web pages and search the internet - all from your command line.

## Why Websearch CLI?

- **Fast** - Async HTTP powered by httpx
- **Smart caching** - Local cache with TTL and automatic eviction
- **Clean output** - HTML to Markdown conversion with XSS protection
- **Type-safe** - 100% type-annotated Python

## Features

- Fetch URLs and convert to Markdown
- Web search via Brave Search API
- Local caching with TTL and size limits
- XSS protection and HTML sanitization
- SPA (Single Page App) detection
- Retry with exponential backoff

## Quick Start

```bash
# Install
uv add websearch

# Fetch a URL as Markdown
websearch fetch https://example.com

# Search the web
websearch search "python async tutorial"

# Fetch with options
websearch fetch https://example.com --no-cache --verbose
websearch search "python" -n 20 -t news
```

## Command Overview

| Command | Description |
|---------|-------------|
| `websearch fetch <url>` | Fetch URL and convert to Markdown |
| `websearch search <query>` | Search the web |
| `websearch ping` | Check if CLI is working |

## Fetch Options

```
--refresh, -r       Skip cache and force fresh fetch
--no-cache          Disable caching
--no-verify         Skip SSL certificate verification
--output, -o PATH    Output file path
--verbose, -v        Show verbose output
```

## Search Options

```
--count, -n <n>      Number of results (1-50, default: 10)
--type, -t <type>   Result type: web, news, images, videos
--output, -o PATH    Output file path
--json               Output raw JSON response
--no-cache           Disable caching
```

## Configuration

Set your Brave API key:

```bash
export BRAVE_API_KEY=your_api_key_here
```

Get your API key at https://brave.com/search/api/

## Development

```bash
# Clone and install
git clone https://github.com/AliiiBenn/websearch.git
cd websearch
uv sync --dev

# Run tests
uv run pytest

# Lint and type-check
uv run ruff check websearch/
uv run mypy websearch/

# Try it out
uv run websearch fetch https://example.com
```

## Contributing

Contributions are welcome! Feel free to open issues or submit PRs.

## License

MIT - See [LICENSE](LICENSE) for details.
