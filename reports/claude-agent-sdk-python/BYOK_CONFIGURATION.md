# BYOK Configuration: Claude Agent SDK Python

## 1. How to Configure Custom API Endpoints

### Key Finding: API Endpoint Configuration is Delegated to Claude Code CLI

The SDK does **not** directly configure API endpoints. Instead, it passes environment variables to the Claude Code CLI subprocess.

### User's Configuration:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.minimax.io/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "sk-cp-KXbQ6RCirhaVnc9i_YiTrRueomORxjgYBPP94A8KJIgP6Fh7W_Nsror08GRWKhN4Lpf5sCub7-Ajlmt0LN5IUzlJuqqj9P7Ohd6P4xOY8l9OpR7egoXbME0",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ANTHROPIC_MODEL": "MiniMax-M2.7",
    "ANTHROPIC_SMALL_FAST_MODEL": "MiniMax-M2.7",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "MiniMax-M2.7",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "MiniMax-M2.7",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "MiniMax-M2.7"
  }
}
```

### Maps to ClaudeAgentOptions:

```python
options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_BASE_URL": "https://api.minimax.io/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "sk-cp-KXbQ6RCirhaVnc9i_YiTrRueomORxjgYBPP94A8KJIgP6Fh7W_Nsror08GRWKhN4Lpf5sCub7-Ajlmt0LN5IUzlJuqqj9P7Ohd6P4xOY8l9OpR7egoXbME0",
        "API_TIMEOUT_MS": "3000000",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "ANTHROPIC_MODEL": "MiniMax-M2.7",
        "ANTHROPIC_SMALL_FAST_MODEL": "MiniMax-M2.7",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "MiniMax-M2.7",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "MiniMax-M2.7",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "MiniMax-M2.7",
    }
)
```

---

## 2. How Authentication Tokens are Handled

### Authentication Flow

1. User provides credentials via `env` in `ClaudeAgentOptions`
2. SDK merges environment variables in `SubprocessCLITransport.connect()`:
   ```python
   process_env = {
       **os.environ,
       **self._options.env,
       "CLAUDE_CODE_ENTRYPOINT": "sdk-py",
   }
   ```
3. Claude Code CLI reads environment variables for API authentication

### Environment Variables for Authentication

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | API authentication (standard) |
| `ANTHROPIC_AUTH_TOKEN` | API authentication (alternative/custom) |

---

## 3. All Supported Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `ANTHROPIC_API_KEY` | API authentication | e2e-tests |
| `ANTHROPIC_AUTH_TOKEN` | API authentication (alternative) | User example |
| `ANTHROPIC_BASE_URL` | Custom API endpoint | User example |
| `ANTHROPIC_MODEL` | Model selection | User example |
| `API_TIMEOUT_MS` | Request timeout | User example |
| `CLAUDE_CODE_ENTRYPOINT` | SDK entry point indicator (set by SDK) | subprocess_cli.py |
| `CLAUDE_AGENT_SDK_VERSION` | SDK version (set by SDK) | subprocess_cli.py |
| `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING` | File checkpointing | subprocess_cli.py |
| `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` | Stream close timeout | client.py |
| `CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK` | Skip CLI version check | subprocess_cli.py |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | Disable non-essential traffic | User example |

---

## 4. How to Set Custom Model Names

### Option A: Via `ClaudeAgentOptions.model`

```python
options = ClaudeAgentOptions(model="MiniMax-M2.7")
```

### Option B: Via `env` Environment Variable

```python
options = ClaudeAgentOptions(
    env={"ANTHROPIC_MODEL": "MiniMax-M2.7"}
)
```

### Option C: Runtime Model Change via `set_model()`

```python
async with ClaudeSDKClient() as client:
    await client.query("Hello")
    await client.set_model("claude-sonnet-4-5")
    await client.query("Continue with Sonnet")
```

---

## 5. Configuration Files vs Profiles

### Key Finding: The SDK Uses Settings Files, Not Profiles

```python
# Settings files via ClaudeAgentOptions.settings
settings: str | None = None

# Settings source loading
setting_sources: list[SettingSource] | None = None
# Where SettingSource = Literal["user", "project", "local"]
```

Settings files:
- `"user"`: `~/.claude/settings.json`
- `"project"`: `.claude/settings.json`
- `"local"`: `.claude-local/settings.json`

---

## 6. Configuration Flow

```
Python SDK (Your Code)
    │
    v
ClaudeSDKClient / query()
    │
    v
SubprocessCLITransport
    |  [Merges env vars + starts Claude Code CLI as subprocess]
    v
Claude Code CLI (Subprocess)
    |  [Reads environment variables for API config]
    v
Anthropic API (or Custom Endpoint like api.minimax.io)
```

---

## 7. Best Practices for BYOK Deployments

### Authentication Best Practices

1. **Use environment variables, not hardcoded values**
   ```python
   options = ClaudeAgentOptions(
       env={"ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"]}
   )
   ```

2. **Use secrets management in production** (Kubernetes Secrets, Docker secrets, CI/CD secrets)

### Custom Endpoint Best Practices

1. **Verify endpoint compatibility** - Custom endpoints must be compatible with Claude API protocol
2. **Set appropriate timeouts** - `API_TIMEOUT_MS: "3000000"` for 3 second timeout

### Production Deployment Checklist

- [ ] Use environment variables for all credentials
- [ ] Set `ANTHROPIC_BASE_URL` for custom endpoints
- [ ] Set `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_API_KEY` for authentication
- [ ] Configure `API_TIMEOUT_MS` appropriate for your use case
- [ ] Use `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` to reduce overhead
- [ ] Set `ANTHROPIC_MODEL` to your desired model
- [ ] Configure `permission_mode` and `allowed_tools` for security
- [ ] Consider `sandbox` settings for additional isolation

---

## 8. Complete Production BYOK Configuration

```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
import os

async def main():
    options = ClaudeAgentOptions(
        env={
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic"),
            "ANTHROPIC_AUTH_TOKEN": os.environ["ANTHROPIC_AUTH_TOKEN"],
            "ANTHROPIC_MODEL": os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"),
            "API_TIMEOUT_MS": os.environ.get("API_TIMEOUT_MS", "3000000"),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        },
        model=os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"),
        fallback_model="claude-sonnet-4-5",
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],
        setting_sources=["user"],
        sandbox={"enabled": True, "autoAllowBashIfSandboxed": False, "excludedCommands": ["rm", "dd"]}
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Hello!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
