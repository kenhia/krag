"""Integration test: incremental indexing with multi-collection.

Verifies that add/modify/delete file operations update the correct
collection in the multi-collection setup.
"""

from __future__ import annotations

from pathlib import Path

from krag.routing.collection_router import CollectionRouter
from krag.routing.rules import (
    COLLECTION_CODE,
    COLLECTION_DOCS,
    COLLECTION_TEXT,
)
from krag.storage.collection_manager import CollectionManager


class TestMultiCollectionIncremental:
    """Incremental operations on multi-collection stores."""

    def test_add_file_to_correct_collection(self, tmp_path: Path) -> None:
        """Adding a new file upserts to the routed collection only."""
        manager = CollectionManager(
            storage_path=tmp_path / "qdrant",
            vector_size=4,
            router=CollectionRouter(),
        )

        try:
            # Add a code file
            collection = manager.route_file(Path("src/new_module.py"), plugin_name=None)
            assert collection == COLLECTION_CODE

            store = manager.get_store(collection)
            store.vector_store.upsert(
                [
                    {
                        "id": "new_chunk_001",
                        "vector": [0.1, 0.2, 0.3, 0.4],
                        "payload": {
                            "content": "def new_function(): pass",
                            "file_path": "/src/new_module.py",
                            "file_type": "py",
                            "chunk_index": 0,
                        },
                    }
                ]
            )

            assert store.vector_store.get_stats()["count"] == 1
        finally:
            manager.close()

    def test_delete_from_correct_collection(self, tmp_path: Path) -> None:
        """Deleting a file removes vectors from its collection only."""
        manager = CollectionManager(
            storage_path=tmp_path / "qdrant",
            vector_size=4,
            router=CollectionRouter(),
        )

        try:
            # Insert into code
            code_store = manager.get_store(COLLECTION_CODE)
            code_store.vector_store.upsert(
                [
                    {
                        "id": "to_delete_001",
                        "vector": [0.1, 0.2, 0.3, 0.4],
                        "payload": {
                            "content": "def old(): pass",
                            "file_path": "/src/old.py",
                            "file_type": "py",
                            "chunk_index": 0,
                        },
                    }
                ]
            )
            assert code_store.vector_store.get_stats()["count"] == 1

            # Insert into docs
            docs_store = manager.get_store(COLLECTION_DOCS)
            docs_store.vector_store.upsert(
                [
                    {
                        "id": "doc_keep_001",
                        "vector": [0.5, 0.6, 0.7, 0.8],
                        "payload": {
                            "content": "# Keep this",
                            "file_path": "/docs/keep.md",
                            "file_type": "md",
                            "chunk_index": 0,
                        },
                    }
                ]
            )

            # Delete the code file by filter
            code_store.vector_store.delete_by_filter({"file_path": "/src/old.py"})

            # Code should be empty, docs should still have 1
            assert code_store.vector_store.get_stats()["count"] == 0
            assert docs_store.vector_store.get_stats()["count"] == 1
        finally:
            manager.close()

    def test_modify_updates_correct_collection(self, tmp_path: Path) -> None:
        """Modifying a file re-upserts to the same collection."""
        manager = CollectionManager(
            storage_path=tmp_path / "qdrant",
            vector_size=4,
            router=CollectionRouter(),
        )

        try:
            # Insert original
            collection = manager.route_file(Path("config.toml"), plugin_name=None)
            assert collection == COLLECTION_TEXT
            store = manager.get_store(collection)

            store.vector_store.upsert(
                [
                    {
                        "id": "config_001",
                        "vector": [0.1, 0.2, 0.3, 0.4],
                        "payload": {
                            "content": "old_config = true",
                            "file_path": "/config.toml",
                            "file_type": "toml",
                            "chunk_index": 0,
                        },
                    }
                ]
            )

            # Re-upsert with updated content (same id = modify)
            store.vector_store.upsert(
                [
                    {
                        "id": "config_001",
                        "vector": [0.4, 0.3, 0.2, 0.1],
                        "payload": {
                            "content": "new_config = true",
                            "file_path": "/config.toml",
                            "file_type": "toml",
                            "chunk_index": 0,
                        },
                    }
                ]
            )

            # Still just 1 vector (upserted, not duplicated)
            assert store.vector_store.get_stats()["count"] == 1
        finally:
            manager.close()

    def test_file_type_change_routing(self, tmp_path: Path) -> None:
        """Router correctly re-routes when the same relative path has diff extensions."""
        router = CollectionRouter()

        # A .py file routes to code
        assert router.route(Path("src/module.py"), ".py", plugin_name=None) == COLLECTION_CODE
        # A .md file routes to docs
        assert router.route(Path("docs/module.md"), ".md", plugin_name=None) == COLLECTION_DOCS
        # A .json file routes to text
        assert router.route(Path("data/module.json"), ".json", plugin_name=None) == COLLECTION_TEXT
