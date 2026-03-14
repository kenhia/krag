"""Integration test for multi-model multi-collection retrieval (US2).

End-to-end test exercising the full retrieval pipeline with mocked Qdrant
to verify two collections × two vector spaces produces correct result
merge and debug metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

from krag.retrieval.retriever import Retriever

# ── Helpers ──────────────────────────────────────────────────────────────


@dataclass
class FakeScoredPoint:
    id: Any
    score: float
    payload: dict[str, Any]


@dataclass
class FakeCollectionStore:
    name: str
    collection_name: str
    vector_size: int
    vector_store: Any


def _make_payload(
    content: str = "chunk content",
    file_path: str = "/test/file.py",
) -> dict:
    return {
        "content": content,
        "file_path": file_path,
        "chunk_index": 0,
        "file_type": "code",
    }


class TestMultiModelMultiCollectionIntegration:
    """Full pipeline: two collections × two vector spaces, two-level RRF."""

    def test_end_to_end_merge_and_debug_metadata(self):
        """Two collections with two vector spaces each should produce merged
        results with composite debug metadata keys."""
        # Set up code collection: 3 results per space
        code_text_results = [
            FakeScoredPoint(
                id="c1", score=0.95, payload=_make_payload("code chunk 1", "/src/a.py")
            ),
            FakeScoredPoint(
                id="c2", score=0.90, payload=_make_payload("code chunk 2", "/src/b.py")
            ),
            FakeScoredPoint(
                id="c3", score=0.85, payload=_make_payload("code chunk 3", "/src/c.py")
            ),
        ]
        code_embed_results = [
            FakeScoredPoint(
                id="c1", score=0.92, payload=_make_payload("code chunk 1", "/src/a.py")
            ),
            FakeScoredPoint(
                id="c4", score=0.80, payload=_make_payload("code chunk 4", "/src/d.py")
            ),
        ]

        # Set up tests collection: 2 results per space
        tests_text_results = [
            FakeScoredPoint(
                id="t1", score=0.88, payload=_make_payload("test chunk 1", "/tests/x.py")
            ),
            FakeScoredPoint(
                id="t2", score=0.82, payload=_make_payload("test chunk 2", "/tests/y.py")
            ),
        ]
        tests_embed_results = [
            FakeScoredPoint(
                id="t1", score=0.86, payload=_make_payload("test chunk 1", "/tests/x.py")
            ),
        ]

        # Build vector stores
        code_vs = MagicMock()
        code_vs.is_named_vectors = True
        code_vs.search_named = MagicMock(
            side_effect=lambda vec, vector_name, limit=10: {
                "text": code_text_results,
                "code-embeddings": code_embed_results,
            }.get(vector_name, [])
        )

        tests_vs = MagicMock()
        tests_vs.is_named_vectors = True
        tests_vs.search_named = MagicMock(
            side_effect=lambda vec, vector_name, limit=10: {
                "text": tests_text_results,
                "code-embeddings": tests_embed_results,
            }.get(vector_name, [])
        )

        # Build collection manager
        cm = MagicMock()
        cm.stores = {
            "code": FakeCollectionStore("code", "krag_code", 384, code_vs),
            "tests": FakeCollectionStore("tests", "krag_tests", 384, tests_vs),
        }
        cm.get_store = MagicMock(side_effect=lambda k: cm.stores[k])

        # Build orchestrator (multi-model)
        orch = MagicMock()
        orch.is_multi_model = True
        orch.embed_query = MagicMock(
            return_value={
                "text": [0.1] * 384,
                "code-embeddings": [0.2] * 384,
            }
        )

        gen = MagicMock()
        gen.generate_single = MagicMock(return_value=[0.1] * 384)

        retriever = Retriever(
            vector_store=code_vs,
            embedding_generator=gen,
            embedding_orchestrator=orch,
            collection_manager=cm,
        )

        results = retriever._multi_collection_retrieve(
            query="find relevant code",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )

        # ── Result validation ──
        assert len(results) > 0, "Should return merged results"

        # All results should have collection tags
        for r in results:
            assert r.collection in ("code", "tests")

        # ── Debug metadata validation ──
        counts = retriever._last_per_space_counts
        assert "code:text" in counts
        assert "code:code-embeddings" in counts
        assert "tests:text" in counts
        assert "tests:code-embeddings" in counts

        # Counts should match the input data
        assert counts["code:text"] == 3
        assert counts["code:code-embeddings"] == 2
        assert counts["tests:text"] == 2
        assert counts["tests:code-embeddings"] == 1

        # Collections searched
        searched = retriever._last_collections_searched
        assert "code" in searched
        assert "tests" in searched

        # ── Verify embed_query was used (not generate_single) ──
        orch.embed_query.assert_called_once()
        gen.generate_single.assert_not_called()

        # ── Verify search_named was called for each space per collection ──
        assert code_vs.search_named.call_count == 2
        assert tests_vs.search_named.call_count == 2
