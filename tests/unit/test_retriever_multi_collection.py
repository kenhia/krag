"""Unit tests for multi-model multi-collection retrieval (US2).

Tests that _multi_collection_retrieve() uses all embedding models when
is_multi_model is True, performs two-level RRF, and tracks composite keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

from krag.retrieval.retriever import Retriever

# ── Helpers ──────────────────────────────────────────────────────────────


@dataclass
class FakeScoredPoint:
    """Mimics _NamedSearchResult from qdrant_impl."""

    id: Any
    score: float
    payload: dict[str, Any]


def _result(
    chunk_id: str,
    score: float,
    content: str = "some content",
    file_path: str = "/test/file.py",
) -> dict:
    """Build a search() result dict."""
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


def _named_result(
    chunk_id: str,
    score: float,
    content: str = "some content",
    file_path: str = "/test/file.py",
) -> FakeScoredPoint:
    """Build a search_named() result object."""
    return FakeScoredPoint(
        id=chunk_id,
        score=score,
        payload={
            "content": content,
            "file_path": file_path,
            "chunk_index": 0,
            "file_type": "code",
        },
    )


@dataclass
class FakeCollectionStore:
    name: str
    collection_name: str
    vector_size: int
    vector_store: Any


def _make_collection_manager(
    stores_config: dict[str, dict],
) -> MagicMock:
    """Create a mock CollectionManager.

    Args:
        stores_config: Mapping of collection name → config dict with:
            - "search_results": list[dict] for search()
            - "search_named_results": dict[str, list] for search_named()
            - "has_named_vectors": bool (whether search_named is supported)
    """
    manager = MagicMock()
    manager.stores = {}

    for coll_name, config in stores_config.items():
        vs = MagicMock()
        vs.search = MagicMock(return_value=config.get("search_results", []))

        named_results = config.get("search_named_results", {})
        vs.search_named = MagicMock(
            side_effect=lambda vec, vector_name, limit=10, _nr=named_results: _nr.get(
                vector_name, []
            )
        )

        # The is_named_vectors property — used to check if collection has named vectors
        vs.is_named_vectors = config.get("has_named_vectors", False)
        # Make hasattr(vs, 'search_named') return True
        vs.search_named.__name__ = "search_named"

        store = FakeCollectionStore(
            name=coll_name,
            collection_name=f"krag_{coll_name}",
            vector_size=384,
            vector_store=vs,
        )
        manager.stores[coll_name] = store

    manager.get_store = MagicMock(side_effect=lambda k: manager.stores[k])
    return manager


def _make_embedding_gen() -> MagicMock:
    gen = MagicMock()
    gen.generate_single = MagicMock(return_value=[0.1] * 384)
    return gen


def _make_orchestrator(multi_model: bool = True) -> MagicMock:
    orch = MagicMock()
    orch.is_multi_model = multi_model
    orch.embed_query = MagicMock(
        return_value={
            "text": [0.1] * 384,
            "code-embeddings": [0.2] * 384,
        }
    )
    return orch


# ── T008: Multi-model multi-collection retrieval ────────────────────────


class TestMultiModelMultiCollection:
    """When is_multi_model is True, _multi_collection_retrieve should use
    embed_query and search_named per vector space per collection."""

    def test_embed_query_called_when_multi_model(self):
        """embed_query() should be called instead of generate_single()."""
        orch = _make_orchestrator(multi_model=True)
        gen = _make_embedding_gen()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("c1", 0.9)],
                        "code-embeddings": [_named_result("c2", 0.8)],
                    },
                },
            }
        )
        retriever = Retriever(
            vector_store=cm.stores["code"].vector_store,
            embedding_generator=gen,
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0},
        )
        orch.embed_query.assert_called_once_with("test")
        gen.generate_single.assert_not_called()

    def test_search_named_invoked_per_space_per_collection(self):
        """search_named() should be called for each vector space in each collection."""
        orch = _make_orchestrator()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("c1", 0.9)],
                        "code-embeddings": [_named_result("c2", 0.8)],
                    },
                },
                "tests": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("t1", 0.85)],
                        "code-embeddings": [_named_result("t2", 0.75)],
                    },
                },
            }
        )
        retriever = Retriever(
            vector_store=cm.stores["code"].vector_store,
            embedding_generator=_make_embedding_gen(),
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )
        # Each collection should have search_named called for each vector space
        code_vs = cm.stores["code"].vector_store
        tests_vs = cm.stores["tests"].vector_store
        assert code_vs.search_named.call_count == 2
        assert tests_vs.search_named.call_count == 2

    def test_composite_keys_in_per_space_counts(self):
        """_last_per_space_counts should have 'collection:space' composite keys."""
        orch = _make_orchestrator()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("c1", 0.9), _named_result("c2", 0.8)],
                        "code-embeddings": [_named_result("c3", 0.7)],
                    },
                },
                "tests": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("t1", 0.85)],
                        "code-embeddings": [],
                    },
                },
            }
        )
        retriever = Retriever(
            vector_store=cm.stores["code"].vector_store,
            embedding_generator=_make_embedding_gen(),
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )
        counts = retriever._last_per_space_counts
        assert "code:text" in counts
        assert "code:code-embeddings" in counts
        assert "tests:text" in counts
        assert "tests:code-embeddings" in counts
        assert counts["code:text"] == 2
        assert counts["code:code-embeddings"] == 1
        assert counts["tests:text"] == 1
        assert counts["tests:code-embeddings"] == 0

    def test_results_merged_via_two_level_rrf(self):
        """Results should be merged via inner RRF per collection then outer weighted RRF."""
        orch = _make_orchestrator()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("c1", 0.9)],
                        "code-embeddings": [_named_result("c1", 0.85)],  # same doc
                    },
                },
                "tests": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("t1", 0.8)],
                        "code-embeddings": [_named_result("t2", 0.7)],
                    },
                },
            }
        )
        retriever = Retriever(
            vector_store=cm.stores["code"].vector_store,
            embedding_generator=_make_embedding_gen(),
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        results = retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0, "tests": 0.5},
        )
        # Should produce results from both collections
        assert len(results) > 0
        collections_in_results = {r.collection for r in results}
        assert "code" in collections_in_results or "tests" in collections_in_results

    def test_single_model_path_unchanged_when_not_multi_model(self):
        """When is_multi_model is False, should use generate_single and search()."""
        orch = _make_orchestrator(multi_model=False)
        gen = _make_embedding_gen()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": False,
                    "search_results": [_result("c1", 0.9)],
                },
            }
        )
        retriever = Retriever(
            vector_store=cm.stores["code"].vector_store,
            embedding_generator=gen,
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0},
        )
        gen.generate_single.assert_called_once()
        orch.embed_query.assert_not_called()
        # Should have simple collection name key, not composite
        assert "code" in retriever._last_per_space_counts


# ── T009: Graceful degradation ──────────────────────────────────────────


class TestMultiModelGracefulDegradation:
    """Graceful fallback when collections lack named vectors or searches fail."""

    def test_collection_without_named_vectors_falls_back_to_search(self):
        """A collection without named vectors should use search() (unnamed)."""
        orch = _make_orchestrator()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("c1", 0.9)],
                        "code-embeddings": [_named_result("c2", 0.8)],
                    },
                },
                "docs": {
                    "has_named_vectors": False,
                    "search_results": [_result("d1", 0.7)],
                },
            }
        )
        retriever = Retriever(
            vector_store=cm.stores["code"].vector_store,
            embedding_generator=_make_embedding_gen(),
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0, "docs": 0.3},
        )
        # 'docs' should have used search() not search_named()
        docs_vs = cm.stores["docs"].vector_store
        docs_vs.search.assert_called_once()
        docs_vs.search_named.assert_not_called()
        # 'code' should have used search_named()
        code_vs = cm.stores["code"].vector_store
        assert code_vs.search_named.call_count == 2

    def test_search_named_exception_logged_and_count_zero(self):
        """search_named() exception should be logged, count recorded as 0."""
        orch = _make_orchestrator()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("c1", 0.9)],
                    },
                },
            }
        )
        # Make search_named raise for 'code-embeddings' but work for 'text'
        code_vs = cm.stores["code"].vector_store
        original_side_effect = code_vs.search_named.side_effect

        def selective_fail(vec, vector_name, limit=10):
            if vector_name == "code-embeddings":
                raise ValueError(f"Vector space '{vector_name}' not found")
            return original_side_effect(vec, vector_name, limit)

        code_vs.search_named = MagicMock(side_effect=selective_fail)

        retriever = Retriever(
            vector_store=code_vs,
            embedding_generator=_make_embedding_gen(),
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        results = retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0},
        )
        counts = retriever._last_per_space_counts
        assert counts["code:code-embeddings"] == 0
        assert counts["code:text"] == 1
        # Should still return results from the successful space
        assert len(results) > 0

    def test_mixed_named_and_unnamed_collections(self):
        """Multi-model collections mixed with single-vector collections."""
        orch = _make_orchestrator()
        cm = _make_collection_manager(
            {
                "code": {
                    "has_named_vectors": True,
                    "search_named_results": {
                        "text": [_named_result("c1", 0.9)],
                        "code-embeddings": [_named_result("c2", 0.8)],
                    },
                },
                "docs": {
                    "has_named_vectors": False,
                    "search_results": [_result("d1", 0.7)],
                },
            }
        )
        retriever = Retriever(
            vector_store=cm.stores["code"].vector_store,
            embedding_generator=_make_embedding_gen(),
            embedding_orchestrator=orch,
            collection_manager=cm,
        )
        retriever._multi_collection_retrieve(
            query="test",
            fetch_limit=10,
            target_collections={"code": 1.0, "docs": 0.3},
        )
        counts = retriever._last_per_space_counts
        # code should have composite keys
        assert "code:text" in counts
        assert "code:code-embeddings" in counts
        # docs should have simple key (fallback)
        assert "docs" in counts
        # collections_searched should include both
        assert "code" in retriever._last_collections_searched
        assert "docs" in retriever._last_collections_searched
