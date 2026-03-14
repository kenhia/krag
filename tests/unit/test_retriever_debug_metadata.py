"""Unit tests for _multi_collection_retrieve() debug metadata (US1).

Verifies that _last_per_space_counts and _last_collections_searched are
correctly populated during multi-collection retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

from krag.retrieval.retriever import Retriever

# ── Helpers ──────────────────────────────────────────────────────────────


def _result(
    chunk_id: str,
    score: float,
    content: str = "some content",
    file_path: str = "/test/file.py",
) -> dict:
    """Build a search result dict."""
    return {
        "id": chunk_id,
        "score": score,
        "payload": {
            "content": content,
            "file_path": file_path,
            "chunk_index": 0,
            "file_type": "code",
        },
    }


@dataclass
class FakeCollectionStore:
    name: str
    collection_name: str
    vector_size: int
    vector_store: Any


def _make_collection_manager(stores: dict[str, list[dict]]) -> MagicMock:
    """Create a mock CollectionManager with named stores.

    Args:
        stores: Mapping of collection name → search result list.
    """
    manager = MagicMock()
    manager.stores = {}
    for coll_name, results in stores.items():
        vs = MagicMock()
        vs.search = MagicMock(return_value=results)
        store = FakeCollectionStore(
            name=coll_name,
            collection_name=f"krag_{coll_name}",
            vector_size=384,
            vector_store=vs,
        )
        manager.stores[coll_name] = store
    manager.get_store = MagicMock(side_effect=lambda k: manager.stores[k])
    return manager


def _make_embedding() -> MagicMock:
    gen = MagicMock()
    gen.generate_single = MagicMock(return_value=[0.1] * 384)
    return gen


def _make_retriever(stores: dict[str, list[dict]]) -> Retriever:
    """Build a Retriever wired to a fake collection manager."""
    cm = _make_collection_manager(stores)
    first_store = next(iter(cm.stores.values()))
    return Retriever(
        vector_store=first_store.vector_store,
        embedding_generator=_make_embedding(),
        collection_manager=cm,
    )


# ── T002: _last_per_space_counts ────────────────────────────────────────


class TestLastPerSpaceCounts:
    """_multi_collection_retrieve populates _last_per_space_counts with
    collection-name keys."""

    def test_two_collections_with_results(self):
        """Two collections should produce per-collection keys."""
        retriever = _make_retriever(
            {
                "code": [_result("c1", 0.9), _result("c2", 0.8)],
                "tests": [_result("t1", 0.85)],
            }
        )
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )
        counts = retriever._last_per_space_counts
        assert "code" in counts
        assert "tests" in counts
        assert counts["code"] == 2
        assert counts["tests"] == 1

    def test_zero_result_collection_appears_with_zero(self):
        """A collection returning no results should still appear with 0."""
        retriever = _make_retriever(
            {
                "code": [_result("c1", 0.9)],
                "tests": [],
            }
        )
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )
        counts = retriever._last_per_space_counts
        assert "code" in counts
        assert "tests" in counts
        assert counts["code"] == 1
        assert counts["tests"] == 0

    def test_unknown_collection_skipped(self):
        """A collection name not in the manager raises KeyError and is skipped."""
        retriever = _make_retriever(
            {
                "code": [_result("c1", 0.9)],
            }
        )
        # "missing" is not in our stores — get_store will raise KeyError
        retriever.collection_manager.get_store = MagicMock(
            side_effect=lambda k: (
                retriever.collection_manager.stores[k]
                if k in retriever.collection_manager.stores
                else (_ for _ in ()).throw(KeyError(k))
            )
        )
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=10,
            target_collections={"code": 1.0, "missing": 0.5},
        )
        counts = retriever._last_per_space_counts
        assert "code" in counts
        assert "missing" not in counts

    def test_counts_sum_matches_total(self):
        """Sum of per-collection counts should equal the total results."""
        retriever = _make_retriever(
            {
                "code": [_result(f"c{i}", 0.9 - i * 0.01) for i in range(5)],
                "tests": [_result(f"t{i}", 0.8 - i * 0.01) for i in range(3)],
                "docs": [_result(f"d{i}", 0.7 - i * 0.01) for i in range(2)],
            }
        )
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=20,
            target_collections={"code": 1.0, "tests": 0.5, "docs": 0.3},
        )
        counts = retriever._last_per_space_counts
        assert sum(counts.values()) == 10


# ── T003: _last_collections_searched ────────────────────────────────────


class TestLastCollectionsSearched:
    """_multi_collection_retrieve populates _last_collections_searched
    with all attempted collection names."""

    def test_all_resolved_collections_present(self):
        """All successfully resolved collections should appear."""
        retriever = _make_retriever(
            {
                "code": [_result("c1", 0.9)],
                "tests": [_result("t1", 0.8)],
            }
        )
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )
        searched = retriever._last_collections_searched
        assert "code" in searched
        assert "tests" in searched
        assert len(searched) == 2

    def test_zero_result_collection_still_present(self):
        """A collection with 0 results should still appear in the list."""
        retriever = _make_retriever(
            {
                "code": [_result("c1", 0.9)],
                "tests": [],
            }
        )
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )
        searched = retriever._last_collections_searched
        assert "code" in searched
        assert "tests" in searched

    def test_unknown_collection_excluded(self):
        """A collection that raises KeyError should NOT appear."""
        retriever = _make_retriever(
            {
                "code": [_result("c1", 0.9)],
            }
        )
        retriever.collection_manager.get_store = MagicMock(
            side_effect=lambda k: (
                retriever.collection_manager.stores[k]
                if k in retriever.collection_manager.stores
                else (_ for _ in ()).throw(KeyError(k))
            )
        )
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=10,
            target_collections={"code": 1.0, "missing": 0.5},
        )
        searched = retriever._last_collections_searched
        assert "code" in searched
        assert "missing" not in searched

    def test_order_matches_attempt_order(self):
        """Collections should appear in the order they were attempted."""
        retriever = _make_retriever(
            {
                "code": [_result("c1", 0.9)],
                "tests": [_result("t1", 0.8)],
                "docs": [_result("d1", 0.7)],
            }
        )
        target = {"code": 1.0, "tests": 0.5, "docs": 0.3}
        retriever._multi_collection_retrieve(
            query="test query",
            fetch_limit=10,
            target_collections=target,
        )
        searched = retriever._last_collections_searched
        assert searched == list(target.keys())
