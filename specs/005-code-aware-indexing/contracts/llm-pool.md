# Contract: LLM Pool

## Interface

```python
class LLMPool:
    """Multi-LLM lifecycle manager with routing and hot-swap.

    Manages one or two LLMs (text and code). Routes queries to the appropriate
    LLM based on retrieved chunk composition. Handles hot-swap when only one
    LLM fits in VRAM.
    """

    def __init__(
        self,
        text_model_path: Path,
        code_model_path: Path | None = None,
        load_multi_llm: bool = False,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1,
        **llm_kwargs: Any,
    ) -> None:
        """Initialize LLM pool.

        Args:
            text_model_path: Path to the general-purpose LLM GGUF file.
            code_model_path: Path to the code LLM GGUF file, or None if not configured.
            load_multi_llm: If True, attempt to load both LLMs simultaneously.
            n_ctx: Context window size for all LLMs.
            n_gpu_layers: GPU layers (-1 = all layers on GPU).
            **llm_kwargs: Additional kwargs passed to llama_cpp.Llama().

        Behavior:
            - Always loads text LLM on init.
            - If load_multi_llm=True and code_model_path is set:
                - Check VRAM via torch.cuda.mem_get_info().
                - If both fit: load both (simultaneous mode).
                - If not: log warning, load text LLM only (hot-swap mode).
            - If load_multi_llm=False: load text LLM only.

        Raises:
            FileNotFoundError: If text_model_path doesn't exist.
            RuntimeError: If text LLM fails to load.
        """
        ...

    def route_and_generate(
        self,
        messages: list[dict[str, str]],
        retrieved_chunks: list["QueryResult"],
        llm_override: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """Route to appropriate LLM and generate response.

        Routing logic:
        1. If llm_override is set ("text" or "code"), use that LLM.
        2. If both LLMs are loaded (simultaneous mode):
           - Count chunks with code metadata (language field set).
           - If >50% code → route to code LLM.
           - Otherwise → route to text LLM.
           - Tiebreaker: use currently loaded LLM (avoid swap).
        3. If only one LLM is loaded:
           - If override requests different LLM → hot-swap.
           - Otherwise → use current LLM.

        Args:
            messages: Chat messages (system + user) from PromptBuilder.
            retrieved_chunks: Query results used for routing decision.
            llm_override: CLI --llm switch value ("text", "code", or None).
            **kwargs: Passed to llama_cpp.Llama.create_chat_completion().

        Returns:
            Tuple of (response_text, llm_name_used).
            llm_name_used is "text" or "code".

        Thread safety:
            This method acquires self._lock for the entire operation.
            Only one generation can occur at a time.
        """
        ...

    def determine_route(
        self,
        chunks: list["QueryResult"],
        override: str | None = None,
    ) -> str:
        """Determine which LLM should handle this query.

        Does NOT perform any swap — just returns the recommendation.

        Args:
            chunks: Retrieved query results.
            override: CLI --llm override.

        Returns:
            "text" or "code".
        """
        ...

    def swap_to(self, name: str) -> float:
        """Hot-swap to the named LLM.

        Unloads current LLM, loads the requested one.
        Thread-safe (acquires self._lock).

        Args:
            name: "text" or "code".

        Returns:
            Swap duration in seconds.

        Raises:
            ValueError: If name is not "text" or "code".
            ValueError: If code_model_path was not configured.
        """
        ...

    def get_active_llm(self) -> str | None:
        """Return name of currently loaded LLM(s).

        Returns:
            "text", "code", "both", or None.
        """
        ...

    def get_status(self) -> dict[str, Any]:
        """Return detailed status of all LLM slots.

        Returns:
            {
                "mode": "simultaneous" | "hot-swap" | "single",
                "text": {"loaded": True, "path": "...", "file_size_gb": 8.5},
                "code": {"loaded": False, "path": "...", "file_size_gb": 5.4},
                "load_multi_llm": False,
                "vram_free_gb": 12.3,
            }
        """
        ...

    def close(self) -> None:
        """Release all loaded LLMs and free VRAM.

        Calls Llama.close() on each loaded model.
        Safe to call multiple times.
        """
        ...
```

## Behavioral Contract

### Routing Decision Matrix

| `load_multi_llm` | VRAM Sufficient | `--llm` Override | Behavior |
|:-:|:-:|:-:|---|
| `true` | Yes | None | Both loaded. Auto-route based on chunk composition. |
| `true` | Yes | `"code"` | Both loaded. Force code LLM. |
| `true` | No | Any | Warning logged. Fall back to hot-swap mode. |
| `false` | N/A | None | Text LLM loaded. Use text LLM for all queries. Log suggestion for `--llm code` if code-heavy query detected. |
| `false` | N/A | `"code"` | Hot-swap: unload text LLM, load code LLM, answer, keep code LLM loaded. |
| `false` | N/A | `"text"` | Hot-swap back to text LLM if code LLM is currently loaded. |

### Chunk Composition Analysis

```python
def _analyze_chunk_composition(self, chunks: list[QueryResult]) -> str:
    """Determine if chunks are predominantly code or text.

    Counts chunks where 'language' payload field is present and non-None.

    Returns:
        "code" if >50% of chunks have code metadata.
        "text" otherwise (including ties — tiebreaker favors current LLM).
    """
    code_count = sum(1 for c in chunks if c.language is not None)
    if code_count > len(chunks) / 2:
        return "code"
    return "text"
```

### Hot-Swap Protocol

```
1. Acquire _lock
2. Log "Swapping LLM: {current} → {target}..."
3. Start timer
4. current_model.close()        # deterministic VRAM release
5. del current_model
6. gc.collect()                 # clear any ref cycles
7. Load new model: Llama(model_path=target_path, n_gpu_layers=-1, ...)
8. Update slot state
9. Stop timer, log duration
10. Release _lock
```

**Progress feedback**: Since `Llama()` constructor doesn't expose a progress callback in the high-level API, feedback is provided as:
- Pre-swap: Rich console message "Loading {name} LLM..." with spinner.
- Post-swap: Log message with duration: "Code LLM loaded in 3.2s".

### VRAM Estimation

```python
def _can_fit_both_llms(self) -> bool:
    """Check if both LLMs can fit in VRAM simultaneously.

    Formula: free_vram * 0.80 >= text_size + code_size + 2 * kv_cache_estimate

    kv_cache_estimate = n_ctx * 2 MB (empirical for 7-14B models)
    """
    ...
```

For RTX 4080 SUPER (16 GB):
- Phi-3-medium Q5_K_M: ~8.5 GB
- Qwen2.5-Coder-7B Q5_K_M: ~5.4 GB
- Combined weights: ~13.9 GB
- KV caches (2 × 8192 ctx × 2 MB): ~32 MB
- Overhead: ~500 MB
- **Total: ~14.4 GB** → fits in 16 GB but exceeds 80% safety margin (~12.8 GB)
- **Result**: `load_multi_llm=true` will likely fall back to hot-swap on 16 GB

### Thread Safety

- All public methods acquire `self._lock` (a `threading.Lock`).
- Only one operation (swap or generate) can occur at a time.
- `close()` is safe to call from any thread.

---

## Integration with Existing LLMClient

`LLMPool` **wraps** `LLMClient` instances OR uses `llama_cpp.Llama` directly. Two approaches:

**Option A: Wrap LLMClient** (preferred for consistency)
```python
# LLMPool creates LLMClient instances internally
self._text_client = LLMClient(model=text_model_path, n_gpu_layers=-1, ...)
self._code_client = LLMClient(model=code_model_path, n_gpu_layers=-1, ...)
```

The existing `LLMClient.generate()` method accepts chat messages, which is what `PromptBuilder.build()` produces. No changes to `LLMClient` are needed.

**Hot-swap**: `LLMClient` doesn't expose `.close()` because it wraps `Llama` internally. `LLMPool` needs access to the underlying `Llama` instance to call `.close()`. Options:
1. Add `close()` to `LLMClient` (delegates to `self._llm.close()`).
2. Have `LLMPool` hold `Llama` instances directly, bypassing `LLMClient`.

**Recommendation**: Add `close()` to `LLMClient`. It's a one-line addition with no breaking changes.

---

## Prompt Preset Auto-Coupling

`LLMPool` communicates the routing decision back to the caller, which then configures `PromptBuilder`:

```python
# In the query pipeline (cli/query.py or equivalent):
route = llm_pool.determine_route(retrieved_chunks, llm_override=args.llm)

if explicit_preset_override:
    preset = explicit_preset_override
elif route == "code":
    preset = "code"
else:
    preset = configured_preset  # default "balanced"

prompt_builder = PromptBuilder(preset_name=preset, ...)
messages = prompt_builder.build(query, retrieved_chunks)

response, llm_used = llm_pool.route_and_generate(messages, retrieved_chunks, llm_override=args.llm)
```

The auto-coupling is **not internal to LLMPool** — it's in the query pipeline coordinator. This keeps `LLMPool` focused on model lifecycle and `PromptBuilder` focused on prompt construction.
