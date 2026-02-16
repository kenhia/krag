# Contract: Retriever

**Module**: `src/krag/retrieval/retriever.py`  
**Status**: Modified (threshold filtering + enhanced logging)

## Interface

```python
class Retriever:
    """Retrieves relevant chunks with similarity threshold filtering."""

    def __init__(
        self,
        vector_store: Any,
        embedding_generator: Any,
    ) -> None: ...

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
    ) -> list[QueryResult]:
        """Retrieve most relevant chunks for a query.

        Args:
            query: User query string
            top_k: Number of candidates to fetch from vector store
            similarity_threshold: Minimum cosine similarity score (0.0-1.0).
                Chunks below this threshold are excluded from results.

        Returns:
            List of QueryResult objects that meet the threshold,
            ranked by relevance. May be empty if no chunks qualify.
        """
        ...
```

## Behavioral Contract

- Fetches `top_k` candidates from vector store WITHOUT threshold filtering.
- Applies `similarity_threshold` as a post-retrieval filter in Python.
- Returns only chunks with `score >= similarity_threshold`.
- May return fewer than `top_k` results (including zero) if chunks don't meet threshold.
- Debug logging (FR-008, FR-013): logs each retrieved chunk with score, source file, and whether it passed/failed the threshold filter.
- Logs summary: "Retrieved {n}, kept {m} after threshold {t}" at INFO level.
