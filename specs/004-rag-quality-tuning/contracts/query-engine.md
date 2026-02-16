# Contract: QueryEngine

**Module**: `src/krag/orchestration/query_engine.py`  
**Status**: Modified (preset integration + diagnostic logging)

## Interface

```python
@dataclass
class QueryResponse:
    """Response from query engine containing answer and sources."""
    answer: str
    sources: list[QueryResult]
    query: str
    prompt: str  # NEW: the complete prompt/messages sent to LLM (serialized)

class QueryEngine:
    """Orchestrates the complete query pipeline with preset support."""

    def __init__(
        self,
        vector_store: Any,
        embedding_generator: Any,
        llm_client: LLMClient,
        top_k: int = 5,
        max_context_length: int = 4000,
        path_aliases: list[str] | None = None,
        similarity_threshold: float = 0.3,
        preset_name: str = "balanced",
        system_prompt_override: str | None = None,
    ) -> None: ...

    def query(
        self,
        query_text: str,
        top_k: int | None = None,
    ) -> QueryResponse:
        """Execute complete query pipeline.

        Returns QueryResponse with answer, sources, query, and the
        serialized prompt that was sent to the LLM.
        """
        ...
```

## Behavioral Contract

- Passes `similarity_threshold` to `Retriever.retrieve()`.
- Passes `preset_name` and `system_prompt_override` to `PromptBuilder`.
- When retriever returns empty results (all below threshold): skips LLM call, returns "insufficient context" response.
- `QueryResponse.prompt` field contains the serialized messages list for diagnostic/eval use.
- Debug logging: logs retrieval count, threshold filter results, prompt size, and generation summary.
