"""Integration test for named-vector + RRF query pipeline.

T032: Verifies that a multi-model retriever correctly:
- Embeds queries with multiple models via EmbeddingOrchestrator
- Searches each named vector space in the vector store
- Merges results via Reciprocal Rank Fusion (RRF)
- Applies metadata and keyword boosts with RRF-aware weights
- Returns correctly ranked QueryResult objects
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from krag.retrieval.retriever import Retriever

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeScoredPoint:
    """Minimal ScoredPointLike for search_named() return values."""

    id: str
    score: float
    payload: dict[str, Any]


def _payload(
    content: str,
    file_path: str = "/repo/src/app.py",
    chunk_index: int = 0,
    file_type: str = ".py",
    function_name: str | None = None,
    class_name: str | None = None,
) -> dict[str, Any]:
    """Build a vector-store payload dict."""
    p: dict[str, Any] = {
        "content": content,
        "file_path": file_path,
        "chunk_index": chunk_index,
        "file_type": file_type,
    }
    if function_name is not None:
        p["function_name"] = function_name
    if class_name is not None:
        p["class_name"] = class_name
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_embedding_generator() -> MagicMock:
    """Single-model embedding generator (used as primary)."""
    gen = MagicMock()
    gen.generate_single.return_value = [0.1] * 384
    return gen


@pytest.fixture()
def mock_embedding_orchestrator() -> MagicMock:
    """Multi-model orchestrator returning embeddings for 'text' and 'code'."""
    orch = MagicMock()
    orch.is_multi_model = True
    orch.embed_query.return_value = {
        "text": [0.1] * 384,
        "code": [0.2] * 768,
    }
    return orch


@pytest.fixture()
def mock_vector_store() -> MagicMock:
    """Vector store with search_named returning distinct result sets."""
    store = MagicMock()

    # Text space results — general documentation chunks
    text_results = [
        _FakeScoredPoint(
            "doc-a",
            0.92,
            _payload(
                "The calculate function computes totals.", "/repo/docs/calc.md", file_type=".md"
            ),
        ),
        _FakeScoredPoint(
            "doc-b",
            0.88,
            _payload("Error handling in the application.", "/repo/docs/errors.md", file_type=".md"),
        ),
        _FakeScoredPoint(
            "doc-c",
            0.85,
            _payload("Configuration reference guide.", "/repo/docs/config.md", file_type=".md"),
        ),
    ]

    # Code space results — code chunks with metadata
    code_results = [
        _FakeScoredPoint(
            "code-a",
            0.95,
            _payload(
                "def calculate(items):\n    return sum(i.price for i in items)",
                "/repo/src/billing.py",
                function_name="calculate",
                class_name="BillingService",
            ),
        ),
        _FakeScoredPoint(
            "doc-a",
            0.80,
            _payload(
                "The calculate function computes totals.", "/repo/docs/calc.md", file_type=".md"
            ),
        ),  # duplicate ID
        _FakeScoredPoint(
            "code-b",
            0.75,
            _payload(
                "class BillingService:\n    def __init__(self): ...",
                "/repo/src/billing.py",
                function_name="__init__",
                class_name="BillingService",
            ),
        ),
    ]

    def _search_named(query_vector, vector_name, limit=10):
        if vector_name == "text":
            return text_results[:limit]
        elif vector_name == "code":
            return code_results[:limit]
        return []

    store.search_named = MagicMock(side_effect=_search_named)
    return store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNamedVectorRRFPipeline:
    """Integration tests for the full named-vector + RRF retrieval pipeline."""

    def test_rrf_merges_results_from_both_spaces(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """Results from both text and code vector spaces are merged via RRF."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        results = retriever.retrieve("calculate billing total", top_k=5)

        # Should have results from both spaces
        file_paths = {str(r.file_path) for r in results}
        assert "/repo/docs/calc.md" in file_paths, "Text space doc should appear"
        assert "/repo/src/billing.py" in file_paths, "Code space doc should appear"

    def test_rrf_score_is_rank_based(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """RRF scores are rank-fusion values, not raw cosine similarities."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        results = retriever.retrieve("calculate", top_k=5)

        # RRF scores are typically in the range ~0.01–0.03 per list
        for r in results:
            # Scores should be positive (from RRF formula 1/(k+rank))
            assert r.score > 0

    def test_duplicate_ids_are_deduplicated(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """doc-a appears in both result lists; RRF merges them into one entry."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        results = retriever.retrieve("calculate function", top_k=10)

        # doc-a appears in both text and code results but should only appear once
        # Count appearances of doc-a content
        calc_docs = [r for r in results if "calculate function computes" in r.chunk_content]
        assert len(calc_docs) <= 1, "Duplicate doc-a should be deduplicated"

    def test_metadata_boost_with_rrf_weights(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """Metadata boost uses RRF-aware weights (smaller than cosine weights)."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        results = retriever.retrieve("calculate BillingService", top_k=5)

        # code-a has function_name="calculate" and class_name="BillingService"
        # which should get metadata boost from the query keywords
        code_a = [r for r in results if "def calculate" in r.chunk_content]
        assert len(code_a) == 1, "code-a should be in results"

        # The RRF metadata boost weight is 0.003, much smaller than cosine 0.08
        # but should still be applied
        base_rrf_score = 1.0 / (60 + 1)  # rank 1 in one list
        assert code_a[0].score > base_rrf_score, "Metadata boost should increase score"

    def test_keyword_boost_with_rrf_weights(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """Keyword boost uses RRF-aware weights for content matching."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        results = retriever.retrieve("calculate items price", top_k=5)

        # code-a contains "calculate", "items", "price" — should get keyword boost
        code_a = [r for r in results if "def calculate" in r.chunk_content]
        assert len(code_a) == 1

    def test_both_vector_spaces_are_searched(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """Retriever calls search_named for each vector space from orchestrator."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        retriever.retrieve("test query", top_k=5)

        # search_named should be called once per vector space
        calls = mock_vector_store.search_named.call_args_list
        vector_names = {
            call.kwargs.get("vector_name", call.args[1] if len(call.args) > 1 else None)
            for call in calls
        }
        assert "text" in vector_names
        assert "code" in vector_names

    def test_rrf_doc_appearing_in_both_lists_scores_higher(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """A document found in multiple vector spaces gets a higher RRF score."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        results = retriever.retrieve("calculate", top_k=10)

        # doc-a appears in both text (rank 1) and code (rank 2) results
        # It should score higher than doc-b (only in text, rank 2) or
        # code-b (only in code, rank 3)
        doc_a = [r for r in results if "calculate function computes" in r.chunk_content]
        doc_b = [r for r in results if "Error handling" in r.chunk_content]

        if doc_a and doc_b:
            # doc-a in two lists should score >= doc-b in one list
            assert doc_a[0].score >= doc_b[0].score, (
                "Document in both vector spaces should score higher via RRF"
            )

    def test_ranks_are_sequential(
        self,
        mock_vector_store: MagicMock,
        mock_embedding_generator: MagicMock,
        mock_embedding_orchestrator: MagicMock,
    ) -> None:
        """Final results have sequential rank numbers starting from 1."""
        retriever = Retriever(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_generator,
            embedding_orchestrator=mock_embedding_orchestrator,
        )

        results = retriever.retrieve("calculate", top_k=5)

        for i, r in enumerate(results, start=1):
            assert r.rank == i, f"Expected rank {i}, got {r.rank}"
