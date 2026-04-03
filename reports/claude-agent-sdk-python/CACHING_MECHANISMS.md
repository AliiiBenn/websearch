# Caching Mechanisms: Claude Agent SDK Python

## Executive Summary

The **Claude Agent SDK Python** is a thin wrapper around the Claude Code CLI that communicates via JSON over stdin/stdout. **The SDK does NOT have built-in response caching** - each query goes directly to the Claude Code subprocess which communicates with Anthropic's API.

---

## 1. Built-in Caching in the SDK

### What the SDK Actually Has

1. **Tool List Caching** (Internal to MCP Server) - Pre-computation of tool schemas at server creation
2. **Anthropic API Prompt Caching Tokens** - Automatic at API level when identical prompts are sent
3. **Session Storage** - Read-only access to CLI session files in `~/.claude/projects/`

### Session Storage (Not Response Caching)

```python
# Sessions stored as: ~/.claude/projects/<project-hash>/<session-uuid>.jsonl
list_sessions(directory=None, limit=None, offset=0)
get_session_info(session_id, directory=None)
get_session_messages(session_id, directory=None, limit=None, offset=0)
```

---

## 2. How to Implement Response Caching

Since the SDK has no built-in caching, you must implement it externally.

### Core Cache Interface Pattern

```python
from pathlib import Path
from typing import Any, TypeVar
from dataclasses import dataclass
import hashlib
import json
from datetime import datetime, timedelta, timezone

T = TypeVar('T')

@dataclass
class CacheEntry(Generic[T]):
    data: T
    cached_at: datetime
    ttl_seconds: float

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > (self.cached_at + timedelta(seconds=self.ttl_seconds))

class ResponseCache:
    def __init__(
        self,
        cache_dir: Path | None = None,
        enabled: bool = True,
        max_size_bytes: int = 500 * 1024 * 1024,
    ):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "claude_agent_sdk"
        self.enabled = enabled
        self.max_size = max_size_bytes

    def get(self, cache_key: str) -> Any | None:
        if not self.enabled:
            return None

    def set(self, cache_key: str, response: Any, ttl: float = 3600) -> None:
        if not self.enabled:
            return

    def invalidate(self, cache_key: str) -> bool:
        pass

    def clear(self) -> None:
        pass
```

---

## 3. Cache Key Strategies

### Request Hashing (Exact Match)

```python
import hashlib
import json

def normalize_prompt(prompt: str) -> str:
    return prompt.strip().lower()

def get_prompt_hash(prompt: str, options: dict[str, Any] | None = None) -> str:
    normalized = normalize_prompt(prompt)
    if options:
        options_str = json.dumps(options, sort_keys=True)
        combined = f"{normalized}|{options_str}"
    else:
        combined = normalized
    return hashlib.sha256(combined.encode()).hexdigest()[:8]
```

### Composite Cache Keys

```python
def get_cache_key(
    prompt: str,
    options: ClaudeAgentOptions | None = None,
    session_id: str | None = None,
    context_hash: str | None = None,
) -> str:
    components = [get_prompt_hash(prompt)]

    if options:
        relevant_options = {
            "model": options.model,
            "max_turns": options.max_turns,
            "allowed_tools": sorted(options.allowed_tools) if options.allowed_tools else None,
            "system_prompt_hash": hashlib.sha256(
                (options.system_prompt or "").encode()
            ).hexdigest()[:8] if options.system_prompt else None,
        }
        components.append(hashlib.sha256(
            json.dumps(relevant_options, sort_keys=True).encode()
        ).hexdigest()[:8])

    if session_id:
        components.append(f"sess_{session_id[:8]}")

    return "|".join(components)
```

### Semantic Similarity (RAG-Style)

```python
class SemanticCache:
    def __init__(
        self,
        embedding_provider,  # e.g., OpenAI embeddings
        similarity_threshold: float = 0.95,
        cache_dir: Path | None = None,
    ):
        self.embedding_provider = embedding_provider
        self.similarity_threshold = similarity_threshold

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot_product / (norm_a * norm_b)

    def get_similar(self, prompt: str) -> tuple[Any, float] | tuple[None, None]:
        query_embedding = self.embedding_provider.embed(prompt)
        # Find best match above threshold
        # Return (response, similarity_score) or (None, None)
```

---

## 4. TTL and Cache Invalidation

### TTL Implementation

```python
DEFAULT_URL_TTL = 7200   # 2 hours
DEFAULT_SEARCH_TTL = 3600  # 1 hour
MAX_URL_TTL = 86400    # 24 hours
JITTER_FACTOR = 0.1

def calculate_ttl(base_ttl: float, jitter: float = JITTER_FACTOR) -> float:
    jitter_range = base_ttl * jitter
    return base_ttl + random.uniform(-jitter_range, jitter_range)

def is_expired(cached_at: datetime, ttl: float) -> bool:
    expires_at = cached_at + timedelta(seconds=ttl)
    return datetime.now(timezone.utc) > expires_at
```

### TTL Selection Guidelines

| Response Type | Suggested TTL | Rationale |
|---------------|---------------|-----------|
| Factual answers | 24 hours | Facts don't change often |
| Code generation | 2-4 hours | Best practices evolve |
| Analysis/review | 1-2 hours | Context-dependent |
| Tool results | 5-30 min | State-dependent |
| Session resume | 24 hours | Long-term context |

---

## 5. Caching Use Cases

### Identical API Requests

```python
class ExactMatchCache:
    def get(self, prompt: str, options: dict[str, Any] | None = None) -> dict[str, Any] | None:
        key = get_cache_key(prompt, options)
        cache_path = self.cache_dir / f"{key}.json"

        if not cache_path.exists():
            return None

        entry = json.loads(cache_path.read_text())
        cached_at = datetime.fromisoformat(entry["cached_at"].replace("Z", "+00:00"))
        ttl = entry.get("ttl", 3600)

        if is_expired(cached_at, ttl):
            cache_path.unlink()
            return None

        return entry["response"]

    def set(self, prompt: str, response: dict[str, Any], options: dict[str, Any] | None = None, ttl: float = 3600) -> None:
        key = get_cache_key(prompt, options)
        entry = {
            "prompt": prompt,
            "options": options,
            "response": response,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "ttl": ttl,
        }
        (self.cache_dir / f"{key}.json").write_text(json.dumps(entry, indent=2))
```

### Tool Results Caching

```python
class ToolResultCache:
    def get_tool_result(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
        key = self._get_tool_key(tool_name, tool_input)
        cache_path = self.cache_dir / f"{key}.json"
        # Check expiry and return cached result

    def set_tool_result(self, tool_name: str, tool_input: dict[str, Any], result: dict[str, Any], ttl: float = 300) -> None:
        key = self._get_tool_key(tool_name, tool_input)
        # Store result with TTL

    @staticmethod
    def _get_tool_key(tool_name: str, tool_input: dict[str, Any]) -> str:
        combined = f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
```

---

## 6. Cache Stampede Prevention

```python
class StampedeProtectedCache:
    def __init__(self, cache: ExactMatchCache, lock_timeout: float = 30.0):
        self.cache = cache
        self.lock_timeout = lock_timeout
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_compute_async(
        self,
        prompt: str,
        compute_fn: Callable[[], Any],
        options: dict[str, Any] | None = None,
    ) -> Any:
        key = get_cache_key(prompt, options)

        # Try cache first (fast path)
        cached = self.cache.get(prompt, options)
        if cached is not None:
            return cached

        # Get or create lock for this key
        async with self._lock_mutex:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            lock = self._locks[key]

        # Acquire lock with timeout
        try:
            async with asyncio.timeout(self.lock_timeout):
                # Double-check cache after acquiring lock
                cached = self.cache.get(prompt, options)
                if cached is not None:
                    return cached

                result = await compute_fn()
                self.cache.set(prompt, result, options)
                return result
        except asyncio.TimeoutError:
            return await compute_fn()
```

---

## 7. Summary

| Aspect | Finding |
|--------|---------|
| **Built-in SDK Caching** | None - SDK is a thin CLI wrapper |
| **Response Caching** | Must be implemented externally |
| **Anthropic Prompt Caching** | Automatic at API level (cache tokens) |
| **Tool Result Caching** | Can be implemented per-tool |
| **Session Storage** | Read-only access to CLI session files |
| **Recommended Approach** | External cache layer with exact + semantic similarity support |
