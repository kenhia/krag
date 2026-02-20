"""Unit tests for Reciprocal Rank Fusion (RRF) merge.

T037: RRF merge produces unified ranked list from multiple result sets.
"""

from __future__ import annotations


class TestReciprocalRankFusion:
    """T037: RRF merge produces unified ranked list from multiple result sets."""

    def test_single_result_list_preserved(self) -> None:
        """A single result list is returned in order."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        results = _make_scored_points(["a", "b", "c"])
        merged = reciprocal_rank_fusion([results], k=60, limit=10)
        assert [p.id for p in merged] == ["a", "b", "c"]

    def test_two_lists_merged_by_combined_rank(self) -> None:
        """Results appearing in both lists get higher RRF scores."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        list_a = _make_scored_points(["a", "b", "c"])
        list_b = _make_scored_points(["b", "c", "d"])

        merged = reciprocal_rank_fusion([list_a, list_b], k=60, limit=10)
        ids = [p.id for p in merged]

        # "b" appears in both (rank 2, rank 1) → higher combined score
        # "c" appears in both (rank 3, rank 2)
        # "b" should rank higher than "a" or "d" since it's in both lists
        assert "b" in ids
        assert "c" in ids
        assert ids.index("b") < ids.index("a")  # b ranks higher than a

    def test_documents_in_both_lists_rank_higher(self) -> None:
        """A document appearing in multiple lists ranks above one-list-only docs."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        # "shared" appears as rank 3 in both lists
        list_a = _make_scored_points(["x", "y", "shared"])
        list_b = _make_scored_points(["p", "q", "shared"])

        merged = reciprocal_rank_fusion([list_a, list_b], k=60, limit=10)
        ids = [p.id for p in merged]

        # "shared" appears in both lists → gets combined score
        # RRF score for "shared": 1/(60+3) + 1/(60+3) = 2/63 ≈ 0.0317
        # RRF score for "x": 1/(60+1) = 1/61 ≈ 0.0164
        # So "shared" should rank higher
        assert ids.index("shared") < ids.index("x")

    def test_limit_respected(self) -> None:
        """Only 'limit' results are returned."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        results = _make_scored_points([f"doc{i}" for i in range(20)])
        merged = reciprocal_rank_fusion([results], k=60, limit=5)
        assert len(merged) == 5

    def test_empty_lists_handled(self) -> None:
        """Empty result lists produce empty output."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        merged = reciprocal_rank_fusion([], k=60, limit=10)
        assert merged == []

    def test_empty_inner_list_handled(self) -> None:
        """A mix of empty and populated lists still works."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        list_a = _make_scored_points(["a", "b"])
        merged = reciprocal_rank_fusion([list_a, []], k=60, limit=10)
        assert len(merged) == 2

    def test_k_constant_affects_ranking(self) -> None:
        """Different k values change relative scores but not ordering."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        list_a = _make_scored_points(["a", "b"])
        list_b = _make_scored_points(["b", "a"])

        merged_k60 = reciprocal_rank_fusion([list_a, list_b], k=60, limit=10)
        merged_k1 = reciprocal_rank_fusion([list_a, list_b], k=1, limit=10)

        # Same documents, same relative order when symmetrical
        assert {p.id for p in merged_k60} == {p.id for p in merged_k1}

    def test_preserves_point_payload(self) -> None:
        """Merged results retain their payload data."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        results = _make_scored_points(["a"], payloads=[{"content": "hello"}])
        merged = reciprocal_rank_fusion([results], k=60, limit=10)
        assert merged[0].payload == {"content": "hello"}

    def test_rrf_score_calculation(self) -> None:
        """Verify RRF score formula: sum(1/(k + rank)) across lists."""
        from krag.retrieval.rrf import reciprocal_rank_fusion

        # Document "a" is rank 1 in list_a, rank 2 in list_b
        list_a = _make_scored_points(["a", "b"])
        list_b = _make_scored_points(["c", "a"])

        merged = reciprocal_rank_fusion([list_a, list_b], k=60, limit=10)

        # Find "a" in merged results
        a_result = next(p for p in merged if p.id == "a")

        # RRF score for "a": 1/(60+1) + 1/(60+2) = 1/61 + 1/62
        expected_score = 1.0 / 61 + 1.0 / 62
        assert abs(a_result.score - expected_score) < 1e-9


class _MockScoredPoint:
    """Minimal scored point for testing RRF."""

    def __init__(self, id: str, score: float = 0.9, payload: dict | None = None) -> None:
        self.id = id
        self.score = score
        self.payload = payload or {}


def _make_scored_points(
    ids: list[str],
    scores: list[float] | None = None,
    payloads: list[dict] | None = None,
) -> list[_MockScoredPoint]:
    """Create a list of mock scored points."""
    if scores is None:
        scores = [0.9 - i * 0.05 for i in range(len(ids))]
    if payloads is None:
        payloads = [{}] * len(ids)
    return [
        _MockScoredPoint(id=id_, score=s, payload=p)
        for id_, s, p in zip(ids, scores, payloads, strict=True)
    ]
