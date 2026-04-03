# Configuration File Implementation Report

## Executive Summary

The websearch CLI needs a configuration file system to allow users to set default values for API keys, model preferences, output format, and other settings. This eliminates the need to repeatedly specify common options on the command line.

**Current State:** All configuration must be done via environment variables or command-line arguments. No persistent configuration.

**Recommendation:** Implement a YAML-based configuration file system with support for per-command defaults, stored in standard XDG locations (`~/.config/websearch/config.yaml`).

---

## Current Architecture Gap

### Current Configuration Methods

**Environment Variables:**
```bash
export BRAVE_API_KEY="..."
export ANTHROPIC_AUTH_TOKEN="..."
export ANTHROPIC_BASE_URL="..."
```

**Command-line Arguments:**
```bash
websearch ask "query" --model MiniMax-M2.7 --count 10
```

**Problems:**
- Environment variables are global, not per-command
- CLI arguments must be repeated for every command
- No way to have different settings per project/directory
- No user preferences persistence

---

## Implementation Options

### Option 1: TOML Configuration File

**Approach:** Use TOML format (same as pyproject.toml) in `~/.config/websearch.toml`.

```toml
[defaults]
model = "MiniMax-M2.7"
count = 5
verbose = false

[search]
type = "web"

[ask]
max_turns = 10
stream = false

[auth]
brave_api_key = "..."
anthropic_auth_token = "..."
```

**Pros:** Familiar format, built-in Python support

**Cons:** Different from other CLI tools (usually YAML/JSON)

### Option 2: YAML Configuration File

**Approach:** Use YAML format in `~/.config/websearch/config.yaml`.

```yaml
defaults:
  model: MiniMax-M2.7
  count: 5
  verbose: false

search:
  type: web

ask:
  max_turns: 10
  stream: false

auth:
  brave_api_key: ${BRAVE_API_KEY}  # Support env var expansion
  anthropic_auth_token: ${ANTHROPIC_AUTH_TOKEN}
```

**Pros:** Human-readable, supports comments, supports env var expansion

**Cons:** Requires pyyaml dependency

### Option 3: JSON Configuration File

**Approach:** Use JSON format in `~/.config/websearch/config.json`.

```json
{
  "defaults": {
    "model": "MiniMax-M2.7",
    "count": 5
  },
  "ask": {
    "max_turns": 10
  }
}
```

**Pros:** Built-in support, no extra dependency

**Cons:** No comments, verbose for human editing

---

## Recommended Approach

**Use Option 2: YAML Configuration File**

Rationale:
1. **Human-readable** - Easy to edit and understand
2. **Comments** - Can document each setting
3. **Env var expansion** - Security for API keys
4. **Industry standard** - Used by kubectl, gh, and many CLI tools
5. **Hierarchical** - Natural fit for per-command settings

---

## Configuration File Locations

### XDG Base Directory Specification

```
Linux/macOS:  ~/.config/websearch/config.yaml
              or $XDG_CONFIG_HOME/websearch/config.yaml

Windows:       %APPDATA%/websearch/config.yaml
              or $XDG_CONFIG_HOME/websearch/config.yaml
```

### Priority Order

Settings are resolved in this order (later wins):

1. Built-in defaults
2. Global config file (`~/.config/websearch/config.yaml`)
3. Project config file (`.websearch.yaml` in current directory)
4. Environment variables
5. Command-line arguments

---

## Implementation Details

### 1. Configuration Loader

```python
# websearch/core/config.py

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

# XDG Base Directory
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_FILE = CONFIG_DIR / "websearch" / "config.yaml"
PROJECT_CONFIG_FILE = Path(".websearch.yaml")

class Config:
    """Configuration loader with environment variable expansion."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or self._find_config()
        self.data = self._load()

    def _find_config(self) -> Path | None:
        """Find config file, checking project then global."""
        if PROJECT_CONFIG_FILE.exists():
            return PROJECT_CONFIG_FILE
        if CONFIG_FILE.exists():
            return CONFIG_FILE
        return None

    def _load(self) -> dict[str, Any]:
        """Load and parse YAML config."""
        if not self.config_path:
            return {}
        with open(self.config_path) as f:
            return yaml.safe_load(f) or {}

    def _expand_env(self, value: str) -> str:
        """Expand environment variables in strings."""
        if not isinstance(value, str):
            return value
        # Match ${VAR} or $VAR patterns
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
        def replace(match):
            var = match.group(1) or match.group(2)
            return os.environ.get(var, match.group(0))
        return re.sub(pattern, replace, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with dot notation support."""
        keys = key.split(".")
        value = self.data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return self._expand_env(value) if isinstance(value, str) else value

    def get_auth(self, provider: str, key: str) -> str | None:
        """Get auth token from config or environment."""
        # First try environment
        env_key = f"{provider.upper()}_{key.upper()}"
        if os.environ.get(env_key):
            return os.environ[env_key]
        # Then config file
        return self.get(f"auth.{provider}_{key}")
```

### 2. Settings Dataclass

```python
# websearch/core/settings.py

from dataclasses import dataclass, field

@dataclass
class SearchSettings:
    """Search command settings."""
    type: str = "web"
    count: int = 5

@dataclass
class AskSettings:
    """Ask command settings."""
    model: str = "MiniMax-M2.7"
    max_turns: int = 10
    count: int = 5
    verbose: bool = False
    stream: bool = False

@dataclass
class FetchSettings:
    """Fetch command settings."""
    refresh: bool = False

@dataclass
class Settings:
    """All command settings."""
    search: SearchSettings = field(default_factory=SearchSettings)
    ask: AskSettings = field(default_factory=AskSettings)
    fetch: FetchSettings = field(default_factory=FetchSettings)

    @classmethod
    def from_config(cls, config: Config) -> Settings:
        """Create Settings from Config object."""
        return cls(
            search=SearchSettings(
                type=config.get("search.type", "web"),
                count=config.get("search.count", 5),
            ),
            ask=AskSettings(
                model=config.get("ask.model", "MiniMax-M2.7"),
                max_turns=config.get("ask.max_turns", 10),
                count=config.get("ask.count", 5),
                verbose=config.get("ask.verbose", False),
                stream=config.get("ask.stream", False),
            ),
        )
```

### 3. Integration with CLI

```python
# In main.py

from websearch.core.config import Config
from websearch.core.settings import Settings

config = Config()
settings = Settings.from_config(config)

@click.option("--model", "-m", default=settings.ask.model, help="Model to use")
@click.option("--count", "-n", default=settings.ask.count, help="Number of results")
def ask(query, model, count, ...):
    # model and count now use config defaults
    # but can still be overridden on command line
```

### 4. Config File Generation

```python
@click.command()
def init():
    """Create a default config file."""
    config_dir = CONFIG_DIR / "websearch"
    config_dir.mkdir(parents=True, exist_ok=True)

    default_config = """# websearch CLI Configuration
# See https://github.com/AliiiBenn/websearch#configuration

defaults:
  # Default model for AI commands
  model: MiniMax-M2.7
  # Default number of results
  count: 5

search:
  # Default search type: web, news, images, videos
  type: web

ask:
  # Max conversation turns
  max_turns: 10
  # Stream responses in real-time
  stream: false
  # Show verbose output
  verbose: false

# Auth tokens (use environment variables for security)
# auth:
#   brave_api_key: ${BRAVE_API_KEY}
#   anthropic_auth_token: ${ANTHROPIC_AUTH_TOKEN}
"""

    config_file = config_dir / "config.yaml"
    if config_file.exists():
        click.confirm(f"{config_file} exists. Overwrite?", abort=True)

    with open(config_file, "w") as f:
        f.write(default_config)

    click.echo(f"Created {config_file}")
```

---

## Security Considerations

### API Keys

**Never store API keys in config files!**

```yaml
# WRONG - API key in plain text
auth:
  brave_api_key: "ABC123"

# CORRECT - Reference environment variable
auth:
  brave_api_key: ${BRAVE_API_KEY}
```

**Implementation:**
```python
def get_api_key(self, provider: str) -> str | None:
    """Never return API keys from config, only from environment."""
    env_key = f"{provider.upper()}_API_KEY"
    return os.environ.get(env_key)
```

### Config File Permissions

```python
import stat

def secure_config_file(path: Path):
    """Ensure config file has secure permissions."""
    if path.exists():
        # Owner read/write only
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
```

---

## Example Config Files

### Minimal Config

```yaml
defaults:
  model: MiniMax-M2.7
  count: 5
```

### Full Config

```yaml
# websearch CLI Configuration

# Default settings for all commands
defaults:
  model: MiniMax-M2.7  # AI model to use
  count: 5              # Number of results

# Search command settings
search:
  type: web            # web, news, images, videos

# Ask command settings
ask:
  model: MiniMax-M2.7
  max_turns: 10
  count: 5
  verbose: false
  stream: false

# Fetch command settings
fetch:
  refresh: false

# Process command settings
process:
  model: MiniMax-M2.7
  max_turns: 10
```

---

## Testing Strategy

```python
# tests/test_config.py

def test_config_loads_yaml(tmp_path):
    config_dir = tmp_path / "websearch"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
defaults:
  model: test-model
  count: 10
""")
    config = Config(config_path=config_file)
    assert config.get("defaults.model") == "test-model"
    assert config.get("defaults.count") == 10

def test_env_var_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "secret123")
    config = Config(tmp_path / "config.yaml")
    config.data = {"auth": {"key": "${TEST_API_KEY}"}}
    assert config.get("auth.key") == "secret123"

def test_project_config_overrides_global(tmp_path):
    # Create global config
    global_dir = tmp_path / ".config" / "websearch"
    global_dir.mkdir(parents=True)
    (global_dir / "config.yaml").write_text("defaults.count: 5")

    # Create project config
    (tmp_path / ".websearch.yaml").write_text("defaults.count: 10")

    # Project should win
    config = Config()
    assert config.get("defaults.count") == 10
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| API keys in config | Support only env var expansion, document security |
| Breaking changes | Version config format, warn on unknown keys |
| Config complexity | Start with simple defaults-only config |

---

## Conclusion

A YAML-based configuration system with XDG compliance and environment variable expansion provides the best balance of security, usability, and flexibility. Users can set their preferences once and have them apply automatically to all commands.
