# Contract: PromptBuilder

**Module**: `src/krag/synthesis/prompt_builder.py`  
**Status**: Modified (existing class extended)

## Interface

```python
class PromptBuilder:
    """Builds structured chat messages for LLM from query and retrieved context."""

    def __init__(
        self,
        max_context_length: int = 4000,
        path_aliases: list[str] | None = None,
        preset_name: str = "balanced",
        system_prompt_override: str | None = None,
    ) -> None: ...

    def build(self, query: str, results: list[QueryResult]) -> list[dict[str, str]]:
        """Build chat messages from query and results.

        Returns:
            List of message dicts with "role" and "content" keys.
            Empty results → no-context system message.
        """
        ...

    def get_system_prompt(self) -> str:
        """Return the active system prompt (preset or override)."""
        ...

    @staticmethod
    def available_presets() -> list[str]:
        """Return names of built-in presets."""
        ...
```

## Behavioral Contract

- `build()` returns `[{"role": "system", ...}, {"role": "user", ...}]` — always exactly two messages.
- Context chunks are numbered `[1]`, `[2]`, etc. with reduced path in parentheses.
- If `results` is empty or all below threshold (empty after filtering), returns a no-context system message instructing the LLM to say "I don't have enough information."
- `system_prompt_override` replaces the preset's system prompt text when provided; generation parameters still come from the preset.
- Unknown `preset_name` raises `ValueError`.
