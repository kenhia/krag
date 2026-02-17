# Contract: Embedding Orchestrator

## Interface

```python
class EmbeddingOrchestrator:
    """Manages multiple embedding models for plugin-declared routing.

    Wraps one or more EmbeddingGenerator instances, each associated with
    a named vector space in Qdrant. Routes files to the correct model
    during indexing and embeds queries with all active models during retrieval.
    """

    def __init__(
        self,
        default_model: str = "BAAI/bge-base-en-v1.5",
        device: str = "cpu",
        additional_models: dict[str, str] | None = None,
    ) -> None:
        """Initialize with default model and optional additional models.

        Args:
            default_model: HuggingFace model name for the default (text) embedder.
            device: Device for model loading ("cpu", "cuda", "cuda:0").
            additional_models: Mapping of vector_name → model_name for additional
                embedding models. E.g., {"code": "jinaai/jina-embeddings-v2-base-code"}.

        Raises:
            ValueError: If any model has a different vector dimension than the default.
            RuntimeError: If VRAM insufficient for simultaneous loading (logs warning,
                falls back to sequential mode).

        Post-conditions:
            - self._models["text"] is always loaded (the default model).
            - Additional models are loaded if VRAM permits.
            - All models have the same vector dimension.
        """
        ...

    def embed_chunks(
        self,
        chunks: list["TextChunk"],
        vector_name: str = "text",
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Embed chunks using the specified model.

        Args:
            chunks: List of TextChunk objects to embed.
            vector_name: Which embedding model to use ("text", "code", etc.).
            batch_size: Batch size for embedding generation.

        Returns:
            List of embedding vectors (one per chunk).

        Raises:
            KeyError: If vector_name is not a loaded model.
        """
        ...

    def embed_query(self, query: str) -> dict[str, list[float]]:
        """Embed a query with ALL active embedding models.

        Used during retrieval to search all vector spaces.

        Args:
            query: User query string.

        Returns:
            Dict mapping vector_name to embedding vector.
            E.g., {"text": [...], "code": [...]}.
            Only includes models that are currently loaded.
        """
        ...

    def get_vector_config(self) -> dict[str, "VectorParams"]:
        """Return Qdrant-compatible vectors_config for collection creation.

        Returns:
            Dict mapping vector_name to VectorParams.
            E.g., {"text": VectorParams(size=768, distance=COSINE),
                    "code": VectorParams(size=768, distance=COSINE)}.
        """
        ...

    def get_active_vector_names(self) -> list[str]:
        """Return names of all currently loaded vector spaces.

        Returns:
            List of vector names, e.g., ["text", "code"].
            Always includes "text" (the default).
        """
        ...

    def get_model_info(self) -> dict[str, dict[str, Any]]:
        """Return info about all managed models.

        Returns:
            {
                "text": {"model_name": "BAAI/bge-base-en-v1.5", "dimension": 768, "device": "cuda"},
                "code": {"model_name": "jinaai/jina-embeddings-v2-base-code", "dimension": 768, "device": "cuda"},
            }
        """
        ...

    @property
    def dimension(self) -> int:
        """Return the common vector dimension for all models."""
        ...

    @property
    def is_multi_model(self) -> bool:
        """Return True if more than one model is loaded."""
        ...
```

## Behavioral Contract

### Initialization

1. The default ("text") model is **always loaded**. If it fails, raise immediately.
2. Additional models are loaded opportunistically:
   - Check VRAM via `torch.cuda.mem_get_info()` before loading.
   - If VRAM insufficient, log a warning and skip (don't crash).
   - The orchestrator still functions with only the text model.
3. All models must have the **same vector dimension**. If dimensions differ, raise `ValueError` at construction time.

### Indexing Flow

1. Caller (IndexingOrchestrator) determines `vector_name` per file based on the plugin's `get_embedding_model()`:
   - Plugin returns model name → orchestrator looks up which `vector_name` uses that model.
   - Plugin returns `None` → use `"text"` (default).
2. `embed_chunks(chunks, vector_name="code")` embeds with the code model.
3. Caller upserts to Qdrant with `vector={vector_name: embedding}` (named vector).

### Query Flow

1. `embed_query(query)` embeds with **all loaded models** simultaneously.
2. Returns a dict: `{"text": text_embedding, "code": code_embedding}`.
3. Caller uses both embeddings to search Qdrant via `query_batch_points`.
4. Results are merged via Reciprocal Rank Fusion (RRF).

### Sequential Fallback (VRAM-constrained)

When VRAM is insufficient for simultaneous embedding models during indexing:

1. Load model A → embed all files for model A → unload model A.
2. Load model B → embed all files for model B → unload model B.
3. Log total time per pass.

This fallback is **transparent to the caller** — `embed_chunks()` works the same way.

---

## Integration with QdrantVectorStore

### Collection Schema

The orchestrator dictates the Qdrant collection's vector configuration:

```python
# Single-model (backward compatible):
vectors_config = VectorParams(size=768, distance=Distance.COSINE)

# Multi-model (named vectors):
vectors_config = {
    "text": VectorParams(size=768, distance=Distance.COSINE),
    "code": VectorParams(size=768, distance=Distance.COSINE),
}
```

### Search

```python
# Multi-model search (single Qdrant call):
from qdrant_client.models import QueryRequest

responses = client.query_batch_points(
    collection_name="krag_embeddings",
    requests=[
        QueryRequest(query=text_vec, using="text", limit=top_k, with_payload=True),
        QueryRequest(query=code_vec, using="code", limit=top_k, with_payload=True),
    ],
)
```

### Score Merging — Reciprocal Rank Fusion (RRF)

```python
def reciprocal_rank_fusion(
    result_lists: list[list[ScoredPoint]],
    k: int = 60,
    limit: int = 10,
) -> list[ScoredPoint]:
    """Merge results from multiple vector spaces using RRF.

    RRF score for a document d across N result lists:
    RRF(d) = Σ 1/(k + rank_i(d))  for each list i where d appears

    Args:
        result_lists: List of result lists (one per embedding model).
        k: Ranking constant (default 60, from original RRF paper).
        limit: Max results to return after fusion.

    Returns:
        Merged and re-ranked results.
    """
    ...
```

**Why RRF over min-max normalization**: See [research.md](../research.md#r5-score-merging-strategy--spec-deviation).

---

## VRAM Budget Management

```python
def _check_vram_budget(self, model_name: str) -> bool:
    """Check if there's enough VRAM to load an additional model.

    Uses torch.cuda.mem_get_info() for accurate post-context-init free VRAM.
    Estimates model VRAM need as ~2x model file size (weights + buffers).
    Applies 20% safety margin.

    Returns:
        True if model can fit, False otherwise.
    """
    ...
```

### Estimation Formula

$$\text{can\_fit} = \text{free\_vram} \times 0.8 \geq \text{model\_file\_size} \times 2$$

The factor of 2 accounts for SentenceTransformer overhead (tokenizer, pooling layers, buffers). For embedding models (~300-700 MB), this is conservative.
