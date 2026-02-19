# Contract: Retriever Boost Scaling

**Module**: `src/krag/retrieval/retriever.py`

## Score-Aware Boost Weights

```python
# Cosine similarity range (0.0–1.0)
_KEYWORD_BOOST_WEIGHT_COSINE = 0.05
_METADATA_BOOST_WEIGHT_COSINE = 0.08

# RRF score range (~0.01–0.03)
_KEYWORD_BOOST_WEIGHT_RRF = 0.002
_METADATA_BOOST_WEIGHT_RRF = 0.003
```

## Boost Application

```python
def _apply_boosts(
    results: list[QueryResult],
    query: str,
    is_rrf: bool,
) -> list[QueryResult]:
    """Apply keyword and metadata boosts with score-range-aware weights.

    Args:
        results: Retrieval results to boost.
        query: Original query string for keyword extraction.
        is_rrf: True if scores are RRF-fused (use smaller weights).

    Returns:
        Results with adjusted scores, re-sorted by score descending.

    Invariant:
        Boosts must not change the relative ordering of top results
        by more than ±2 positions compared to unmodified scores.
    """
```

## Payload-to-Result Helper

```python
def _payload_to_query_result(
    point_id: str | int,
    score: float,
    rank: int,
    payload: dict,
) -> QueryResult | None:
    """Convert a Qdrant point payload to a QueryResult.

    Returns None if the payload is invalid (missing/empty file_path),
    logging a warning. Does NOT raise exceptions for individual bad results.
    """
```
