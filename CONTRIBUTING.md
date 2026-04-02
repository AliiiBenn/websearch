# Contributing to Websearch CLI

We love your input! We want to make contributing to Websearch CLI as easy and transparent as possible.

## Development Process

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
4. **Make** your changes
5. **Run** tests to ensure nothing is broken
6. **Commit** your changes with clear commit messages
7. **Push** to the branch
8. **Open** a Pull Request on GitHub

## Coding Standards

### Python

- Follow PEP 8 style guidelines
- Use type annotations for all function signatures
- Write docstrings for public functions and classes
- Run `ruff check` before committing
- Run `mypy` to verify type annotations

```bash
# Check code style
uv run ruff check websearch/

# Type check
uv run mypy websearch/

# Run all checks before committing
uv run ruff check websearch/
uv run mypy websearch/
uv run pytest tests/
```

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb (e.g., "Add feature", "Fix bug", "Update documentation")
- Reference issues and pull requests where relevant

Example:
```
feat: add search command with Brave API integration

- Add search CLI command
- Support for web, news, images, and videos search types
- Add caching for search results

Closes #123
```

## Testing

All new features should include appropriate tests. We use `pytest` for testing.

```bash
# Run all tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=websearch --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_fetcher.py -v
```

## Project Structure

```
websearch/
├── websearch/
│   ├── __main__.py          # CLI entry point
│   ├── main.py              # CLI commands
│   └── core/
│       ├── cache/           # URL and search result caching
│       ├── converter/       # HTML to Markdown conversion
│       ├── fetcher/         # HTTP fetching with retry
│       ├── search/          # Search API integration
│       └── types/           # Result and Maybe types
├── tests/                   # Test files
└── docs/                   # Documentation
```

## Pull Request Process

1. Update documentation if your changes affect the public API
2. Add tests for any new functionality
3. Ensure all tests pass
4. Update the README if relevant
5. The PR will be reviewed by maintainers

## Code of Conduct

Please note that this project is released with a [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

## Questions?

Feel free to open an issue for general questions or discussions about the project.

For security concerns, please email us at [support@nesalia.com](mailto:support@nesalia.com) instead of opening a public issue.

## License

By contributing to Websearch CLI, you agree that your contributions will be licensed under the MIT License.
