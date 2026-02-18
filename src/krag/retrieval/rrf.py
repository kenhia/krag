"""Reciprocal Rank Fusion (RRF) for merging multi-model search results.

RRF is a rank-based fusion method that merges results from multiple
ranking systems. It uses rank positions (which are comparable across
models) rather than raw scores (which are not).

Reference: Cormack, Clarke, Buettcher (2009). "Reciprocal Rank Fusion
outperforms Condorcet and individual Rank Learning Methods."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class ScoredPointLike(Protocol):
    """Protocol for objects that have id, score, and payload."""

    id: Any
    score: float
    payload: dict[str, Any]


@dataclass
class RRFScoredPoint:
    """A result point with an RRF-computed score."""

    id: Any
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


def reciprocal_rank_fusion(
    result_lists: list[list[Any]],
    k: int = 60,
    limit: int = 10,
) -> list[RRFScoredPoint]:
    """Merge results from multiple vector spaces using RRF.

    RRF score for a document d across N result lists:
        RRF(d) = Σ 1/(k + rank_i(d))  for each list i where d appears

    Args:
        result_lists: List of result lists (one per embedding model).
            Each element must have .id, .score, and .payload attributes.
        k: Ranking constant (default 60, from original RRF paper).
        limit: Max results to return after fusion.

    Returns:
        Merged and re-ranked results as RRFScoredPoint objects.
    """
    if not result_lists:
        return []

    scores: dict[str, float] = {}
    point_map: dict[str, Any] = {}

    for results in result_lists:
        for rank, point in enumerate(results):
            pid = str(point.id)
            # RRF formula: rank is 1-based (rank 0 → rank+1=1)
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
            # Keep the first occurrence (highest-scoring version)
            if pid not in point_map:
                point_map[pid] = point

    # Sort by RRF score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Build results with RRF scores
    merged: list[RRFScoredPoint] = []
    for pid, rrf_score in ranked[:limit]:
        original = point_map[pid]
        merged.append(
            RRFScoredPoint(
                id=original.id,
                score=rrf_score,
                payload=getattr(original, "payload", {}),
            )
        )

    logger.debug(
        "RRF merge: %d input lists → %d unique docs → %d returned",
        len(result_lists),
        len(scores),
        len(merged),
    )
    return merged
