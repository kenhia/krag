# Contract: LLMClient

**Module**: `src/krag/synthesis/llm_client.py`  
**Status**: Modified (API migration + new parameters)

## Interface

```python
class LLMClient:
    """Client for local LLM inference using llama-cpp-python chat completion API."""

    def __init__(
        self,
        model: str | Path | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        n_ctx: int = 2048,
        n_threads: int | None = None,
        n_gpu_layers: int = 0,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
        min_p: float = 0.05,
        model_cache_path: str | Path | None = None,
    ) -> None: ...

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        repeat_penalty: float | None = None,
    ) -> str:
        """Generate answer using chat completion API.

        Args:
            messages: Chat messages [{"role": "system", ...}, {"role": "user", ...}]
            temperature: Override instance default
            max_tokens: Override instance default
            top_p: Override instance default
            repeat_penalty: Override instance default

        Returns:
            Generated answer string.
        """
        ...
```

## Behavioral Contract

- `generate()` uses `model.create_chat_completion(messages=...)` instead of `model(prompt)`.
- Stop sequences are handled automatically by the chat completion API using GGUF metadata.
- The `query` and `context` parameters from the old signature are replaced by `messages` — callers must pre-build chat messages via `PromptBuilder.build()`.
- All generation parameters have per-call overrides for flexibility (eval harness may override for determinism).
- Returns empty string on error (logged), never raises during generation.
- Debug logging (FR-012): logs the complete messages list at DEBUG level before generation.
