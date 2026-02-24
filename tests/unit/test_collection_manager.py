"""Unit tests for CollectionManager lifecycle.

Tests cover:
- Creation with shared QdrantClient
- get_store / get_all_stores accessors
- close() releases the shared client
- Router integration (routes files to correct stores)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from krag.routing.collection_router import CollectionRouter
from krag.routing.rules import (
    ALL_COLLECTIONS,
    COLLECTION_CODE,
    COLLECTION_DOCS,
    COLLECTION_TESTS,
    COLLECTION_TEXT,
    qdrant_collection_name,
)
from krag.storage.collection_manager import CollectionManager, CollectionStore


class TestCollectionStoreDataclass:
    """CollectionStore value object tests."""

    def test_fields(self) -> None:
        store = CollectionStore(
            name=COLLECTION_CODE,
            collection_name=qdrant_collection_name(COLLECTION_CODE),
            vector_size=768,
            vector_store=MagicMock(),
        )
        assert store.name == "code"
        assert store.collection_name == "krag_code"
        assert store.vector_size == 768
        assert store.vector_store is not None

    def test_immutable(self) -> None:
        store = CollectionStore(
            name=COLLECTION_CODE,
            collection_name=qdrant_collection_name(COLLECTION_CODE),
            vector_size=768,
            vector_store=MagicMock(),
        )
        with pytest.raises(AttributeError):
            store.name = "other"  # type: ignore[misc]


class TestCollectionManagerCreate:
    """CollectionManager construction and store creation."""

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_creates_four_stores(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        # 4 stores created (one per collection)
        assert len(manager.stores) == 4
        for name in ALL_COLLECTIONS:
            assert name in manager.stores

        manager.close()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_shared_client(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        # All QdrantVectorStore instances receive the same client
        calls = mock_vs_cls.call_args_list
        assert len(calls) == 4
        for call in calls:
            assert call.kwargs.get("client") is mock_client

        manager.close()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_collection_naming(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        calls = mock_vs_cls.call_args_list
        collection_names = {call.kwargs["collection_name"] for call in calls}
        assert collection_names == {"krag_code", "krag_tests", "krag_docs", "krag_text"}

        manager.close()


class TestCollectionManagerAccessors:
    """get_store and get_all_stores accessors."""

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_get_store_valid(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        store = manager.get_store(COLLECTION_CODE)
        assert store is not None
        assert store.name == COLLECTION_CODE

        manager.close()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_get_store_invalid(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        with pytest.raises(KeyError):
            manager.get_store("nonexistent")

        manager.close()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_get_all_stores(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        stores = manager.get_all_stores()
        assert len(stores) == 4
        names = {s.name for s in stores}
        assert names == ALL_COLLECTIONS

        manager.close()


class TestCollectionManagerClose:
    """close() releases the shared client."""

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_close_closes_client(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        manager.close()
        mock_client.close.assert_called_once()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_close_idempotent(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        manager.close()
        manager.close()
        # Only one close call
        mock_client.close.assert_called_once()


class TestCollectionManagerRouting:
    """Router integration — route_file delegates to CollectionRouter."""

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_route_file_to_code(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        collection = manager.route_file(Path("src/main.py"), plugin_name=None)
        assert collection == COLLECTION_CODE

        manager.close()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_route_file_to_tests(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        collection = manager.route_file(Path("tests/test_main.py"), plugin_name=None)
        assert collection == COLLECTION_TESTS

        manager.close()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_route_file_to_docs(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        collection = manager.route_file(Path("docs/guide.md"), plugin_name=None)
        assert collection == COLLECTION_DOCS

        manager.close()

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_route_file_returns_store(
        self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        mock_client_cls.return_value = MagicMock()

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        collection = manager.route_file(Path("config.json"), plugin_name=None)
        assert collection == COLLECTION_TEXT
        # Can get the store for this collection
        store = manager.get_store(collection)
        assert store.name == COLLECTION_TEXT

        manager.close()


class TestCollectionManagerStats:
    """Per-collection stats aggregation."""

    @patch("krag.storage.collection_manager.QdrantClient")
    @patch("krag.storage.collection_manager.QdrantVectorStore")
    def test_get_all_stats(self, mock_vs_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        mock_client_cls.return_value = MagicMock()

        # Each mock vector store returns stats
        mock_stores = {}
        for name in ALL_COLLECTIONS:
            mock_store = MagicMock()
            mock_store.get_stats.return_value = {
                "collection_name": qdrant_collection_name(name),
                "count": 10,
                "status": "green",
            }
            mock_stores[name] = mock_store

        mock_vs_cls.side_effect = lambda **kwargs: mock_stores.get(
            kwargs["collection_name"].replace("krag_", ""), MagicMock()
        )

        manager = CollectionManager(
            storage_path=Path("/tmp/qdrant"),
            vector_size=768,
            router=CollectionRouter(),
        )

        # Manually set stores with our mocks
        for name in ALL_COLLECTIONS:
            manager.stores[name] = CollectionStore(
                name=name,
                collection_name=qdrant_collection_name(name),
                vector_size=768,
                vector_store=mock_stores[name],
            )

        stats = manager.get_all_stats()
        assert len(stats) == 4
        for name in ALL_COLLECTIONS:
            assert name in stats
            assert stats[name]["count"] == 10

        manager.close()
