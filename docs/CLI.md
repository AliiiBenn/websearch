# Websearch CLI Documentation

## Installation

```bash
pip install websearch
```

Or install from source:

```bash
git clone https://github.com/yourusername/websearch.git
cd websearch
pip install -e .
```

## Configuration

### API Key Setup

**Option 1: Interactive prompt (recommended)**

```bash
websearch config key
```

This prompts for the key without displaying it, keeping it out of shell history.

**Option 2: Environment variable**

```bash
export BRAVE_API_KEY=your_api_key_here
```

**Option 3: .env file (for development only)**

Create a `.env` file in your project directory:

```
BRAVE_API_KEY=your_api_key_here
```

Note: Add `.env` to your `.gitignore` to avoid committing secrets.

## Commands

### get

Fetch a URL and convert its HTML content to Markdown.

```bash
websearch get <url>
```

**Arguments:**
- `url` - The URL to fetch and convert

**Options:**
- `-o, --output FILE` - Write output to file instead of stdout
- `-p, --pretty` - Pretty print with syntax highlighting
- `--timeout SECONDS` - Request timeout (default: 30)

**Examples:**

```bash
# Basic usage
websearch get https://example.com

# Output to file
websearch get https://example.com -o output.md

# Pretty print
websearch get https://example.com --pretty
```

---

### search

Search the web using Brave Search API.

```bash
websearch search <query>
```

**Arguments:**
- `query` - The search query string

**Options:**
- `-n, --count NUMBER` - Number of results (default: 10, max: 50)
- `-t, --type TYPE` - Result type: `web`, `news`, `images`, `videos` (default: web)
- `-o, --output FILE` - Write output to file instead of stdout
- `--json` - Output raw JSON response

**Examples:**

```bash
# Basic search
websearch search "python async programming"

# Get 20 results
websearch search "web scraping" -n 20

# Search news
websearch search "AI developments" -t news

# Output to file
websearch search "tutorial" -o results.md
```

---

### help

Show general help or help for a specific command.

```bash
websearch help [command]
```

**Example:**

```bash
websearch help get
```

---

### batch

Fetch multiple URLs and save each as a Markdown file.

```bash
websearch batch <input>
```

**Arguments:**
- `input` - File containing URLs (one per line) or multiple URLs separated by spaces

**Options:**
- `-o, --output-dir DIR` - Output directory for Markdown files (default: current directory)
- `--prefix PREFIX` - Add prefix to output filenames
- `--suffix SUFFIX` - Add suffix to output filenames (before extension)
- `--concurrency N` - Number of concurrent requests (default: 5, max: 20)
- `--continue` - Continue on errors (skip failed URLs)

**Examples:**

```bash
# URLs from file (one per line)
websearch batch urls.txt

# URLs from file to specific directory
websearch batch urls.txt -o ./output/

# Multiple URLs directly
websearch batch https://example.com https://foo.com/bar

# With prefix and concurrency
websearch batch urls.txt --prefix "article_" --concurrency 10
```

**Input file format:**

```
https://example.com/article1
https://example.com/article2
https://foo.com/page
```

Each URL produces a corresponding `.md` file. The filename is derived from the URL path.

---

## Output Formats

### Markdown Output (default for `get`)

The `get` command outputs clean Markdown:

```markdown
# Article Title

Paragraph text with **bold** and *italic* formatting.

## Section Heading

- List item 1
- List item 2

[Link Text](https://example.com)

    code block
```

### JSON Output

The `search` command with `--json` outputs raw API response:

```json
{
  "web_results": [
    {
      "title": "Result Title",
      "url": "https://example.com",
      "description": "Result description..."
    }
  ]
}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Network error |
| 4 | API error (invalid key, quota exceeded) |

## Error Messages

The CLI provides clear, actionable error messages:

### Network Errors

```
Error: Could not connect to "https://example.com"
Hint: Check your internet connection or try again later

Error: Request timeout after 30 seconds
Hint: Use --timeout to increase the timeout value
```

### HTTP Errors

```
Error: 404 Not Found - "https://example.com/missing-page"
Hint: Verify the URL is correct

Error: 403 Forbidden - Access denied
Hint: This page may require authentication or block automated access

Error: 500 Internal Server Error
Hint: The server encountered an error. Try again later.
```

### API Errors

```
Error: API key is missing
Hint: Run "websearch config key" to set your Brave Search API key

Error: API key is invalid
Hint: Check your API key at https://brave.com/search/api/

Error: API quota exceeded
Hint: You've reached your monthly limit. Check pricing at brave.com

Error: Rate limited. Please wait 1 second between requests.
```

### Validation Errors

```
Error: Invalid URL format: "not-a-url"
Hint: URLs must start with http:// or https://

Error: Count must be between 1 and 50, got 100
Hint: Use -n with a value in the valid range

Error: Unknown search type "video". Valid types: web, news, images, videos
```

### Batch Errors

```
Error: Input file not found: "urls.txt"
Hint: Check the file path is correct

Error: All URLs failed to fetch
Hint: Check your internet connection or URL list
```

When using `--continue` in batch mode, errors are logged but processing continues.

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BRAVE_API_KEY` | Brave Search API key | Yes (for search command) |
| `WEBSEARCH_TIMEOUT` | Default request timeout in seconds | No |

---

## Security

### API Key Storage

**Recommended: Environment variable**

```bash
export BRAVE_API_KEY=your_api_key_here
```

This is the safest method. The key is not stored on disk and is cleared when the shell session ends.

**Interactive prompt (safest for CLI)**

```bash
websearch config key
# Prompts for the key without echoing it
```

This approach:
- Does not appear in shell history
- Is not visible in process lists
- Does not require storing the key on disk

### What to Avoid

- **Do not pass the API key directly in commands**
  ```bash
  # UNSAFE - appears in history
  websearch config key "your_api_key_here"
  ```

- **Do not store keys in configuration files**
  - The `[api]` section in `~/.websearchrc` should be left empty
  - Use `keyring` integration for persistent secure storage (advanced)

### Why This Matters

| Method | Shell History | Process List | Disk Storage |
|--------|---------------|--------------|--------------|
| Environment variable | No | Hidden | No |
| Interactive prompt | No | Hidden | No |
| Command argument | Yes | Potential | No |
| Config file | No | No | Yes (encrypted?) |

### Keyring Integration (Optional)

For advanced users who want persistent secure storage:

```bash
pip install websearch[keyring]
websearch config key --use-keyring
```

This stores the API key in your system's credential manager (Windows Credential Manager, macOS Keychain, etc.).

---

## Configuration File

You can create `~/.websearchrc` for default settings:

```ini
[defaults]
timeout = 30
count = 10

[cache]
directory = ~/.cache/websearch
ttl = 7200
max_size = 500M
enabled = true

[batch]
concurrency = 5

[api]
# Leave key empty - use environment variable or interactive prompt instead
# key =
```

---

## Examples

### Full Workflow

```bash
# Configure API key (interactive - recommended)
websearch config key

# Or set environment variable
# export BRAVE_API_KEY=your_key_here

# Search for an article
websearch search "best python async libraries 2024"
# Output: List of relevant articles

# Fetch a specific article as Markdown
websearch get https://realpython.com/async-python/

# Save to file and edit
websearch get https://example.com/article -o article.md
```

### Batch Operations

```bash
# Create a file with URLs
echo "https://example.com/page1" > urls.txt
echo "https://foo.com/article" >> urls.txt

# Fetch all URLs
websearch batch urls.txt

# Fetch to specific directory with concurrency
websearch batch urls.txt -o ./articles/ --concurrency 10

# Continue on errors
websearch batch urls.txt --continue
```

### Piping and Chaining

```bash
# Pipe to other tools
websearch get https://example.com | less

# Search and immediately fetch first result
websearch search "tutorial" -n 1 --json | jq '.[0].url' | xargs websearch get

# Save search results
websearch search "query" -o search_results.md
```

---

## JavaScript (SPA) Pages

The CLI automatically handles JavaScript-rendered pages (SPAs). When a page requires JS to display content:

1. The CLI detects pages that need JavaScript rendering
2. Uses a headless browser to render the page fully
3. Waits for network idle before converting to Markdown

This means pages built with React, Vue, Angular, Next.js, etc. work automatically.

**Note:** Rendering JS pages is slower than static HTML. Use single `get` for one-off fetches and batch with lower concurrency for multiple SPAs.
