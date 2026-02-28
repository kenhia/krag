"""Tests for per-chunk target_collection routing in the indexer (T009, T010).

T009: When chunks have target_collection in payload, vectors route to correct collections.
T010: When target_collection is absent, fallback to route_file() per-file routing.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_indexer_with_collection_manager():
    """Create a minimal Indexer with a mocked CollectionManager."""
    from krag.orchestration.indexer import Indexer

    indexer = Indexer.__new__(Indexer)
    indexer.collection_manager = MagicMock()
    indexer.plugin_registry = None
    indexer.plugin_context = None
    indexer.vector_store = MagicMock()
    indexer.indexed_files = {}
    return indexer


class TestPerChunkRouting:
    """Per-chunk target_collection routing in index_full() / index_incremental()."""

    def test_vectors_with_target_collection_route_to_correct_collections(self) -> None:
        """T009: Chunks with target_collection split to correct collections."""
        # Simulate vectors with target_collection in payload
        vectors = [
            {
                "id": "v1",
                "vector": [0.1] * 10,
                "payload": {
                    "file_path": "obsidian://gratch/note.md",
                    "target_collection": "docs",
                    "content_type": "prose",
                },
            },
            {
                "id": "v2",
                "vector": [0.2] * 10,
                "payload": {
                    "file_path": "obsidian://gratch/note.md",
                    "target_collection": "code",
                    "content_type": "code",
                    "language": "python",
                },
            },
            {
                "id": "v3",
                "vector": [0.3] * 10,
                "payload": {
                    "file_path": "obsidian://gratch/note.md",
                    "target_collection": "docs",
                    "content_type": "prose",
                },
            },
        ]

        # Route using the helper
        from krag.orchestration.indexer import _route_vectors_by_chunk

        fallback_collection = "text"
        routed = _route_vectors_by_chunk(vectors, fallback_collection)

        assert "docs" in routed
        assert "code" in routed
        assert len(routed["docs"]) == 2
        assert len(routed["code"]) == 1

        # target_collection should be popped from payload
        for coll_vectors in routed.values():
            for vec in coll_vectors:
                assert "target_collection" not in vec["payload"]

    def test_vectors_without_target_collection_use_fallback(self) -> None:
        """T010: Chunks without target_collection use fallback collection."""
        vectors = [
            {
                "id": "v1",
                "vector": [0.1] * 10,
                "payload": {
                    "file_path": "/some/file.py",
                    "content_type": "code",
                },
            },
            {
                "id": "v2",
                "vector": [0.2] * 10,
                "payload": {
                    "file_path": "/some/file.py",
                    "content_type": "code",
                },
            },
        ]

        from krag.orchestration.indexer import _route_vectors_by_chunk

        fallback_collection = "code"
        routed = _route_vectors_by_chunk(vectors, fallback_collection)

        assert "code" in routed
        assert len(routed["code"]) == 2

    def test_mixed_vectors_some_with_some_without_target(self) -> None:
        """Vectors where some have target_collection and some don't."""
        vectors = [
            {
                "id": "v1",
                "vector": [0.1] * 10,
                "payload": {
                    "file_path": "obsidian://gratch/note.md",
                    "target_collection": "code",
                    "language": "python",
                },
            },
            {
                "id": "v2",
                "vector": [0.2] * 10,
                "payload": {
                    "file_path": "obsidian://gratch/note.md",
                    # No target_collection
                },
            },
        ]

        from krag.orchestration.indexer import _route_vectors_by_chunk

        fallback = "docs"
        routed = _route_vectors_by_chunk(vectors, fallback)

        assert len(routed["code"]) == 1
        assert len(routed["docs"]) == 1

    def test_empty_vectors_returns_empty(self) -> None:
        from krag.orchestration.indexer import _route_vectors_by_chunk

        routed = _route_vectors_by_chunk([], "docs")
        assert routed == {}
