"""Integration test: index mixed project → verify per-collection file distribution.

Creates a temporary directory with files of various types and verifies
that after indexing through the multi-collection pipeline, files land
in the correct Qdrant collections.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from krag.routing.collection_router import CollectionRouter
from krag.routing.rules import (
    COLLECTION_CODE,
    COLLECTION_DOCS,
    COLLECTION_TESTS,
    COLLECTION_TEXT,
    qdrant_collection_name,
)
from krag.storage.collection_manager import CollectionManager


@pytest.fixture
def mixed_project(tmp_path: Path) -> Path:
    """Create a mixed project with code, tests, docs, and config files."""
    # Code files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main(): pass")
    (tmp_path / "src" / "utils.js").write_text("function util() {}")

    # Test files
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_main(): assert True")
    (tmp_path / "tests" / "conftest.py").write_text("import pytest")

    # Doc files
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\nSome documentation")
    (tmp_path / "README.md").write_text("# Project\nReadme content")

    # Config/data files
    (tmp_path / "config.json").write_text('{"key": "value"}')
    (tmp_path / "settings.yaml").write_text("key: value")

    # Unknown extension (fallback)
    (tmp_path / "Makefile").write_text("all: build")

    return tmp_path


class TestMultiCollectionRouting:
    """Verify that CollectionRouter distributes files correctly."""

    def test_mixed_project_routing(self, mixed_project: Path) -> None:
        """Every file in the mixed project lands in the expected collection."""
        router = CollectionRouter()

        expected = {
            "src/main.py": COLLECTION_CODE,
            "src/utils.js": COLLECTION_CODE,
            "tests/test_main.py": COLLECTION_TESTS,
            "tests/conftest.py": COLLECTION_TESTS,
            "docs/guide.md": COLLECTION_DOCS,
            "README.md": COLLECTION_DOCS,
            "config.json": COLLECTION_TEXT,
            "settings.yaml": COLLECTION_TEXT,
            "Makefile": COLLECTION_TEXT,
        }

        for rel_path, expected_collection in expected.items():
            full_path = mixed_project / rel_path
            ext = full_path.suffix
            result = router.route(full_path, ext, plugin_name=None)
            assert result == expected_collection, (
                f"{rel_path}: expected {expected_collection}, got {result}"
            )


class TestMultiCollectionManagerLifecycle:
    """CollectionManager creates and closes stores correctly with real Qdrant."""

    def test_create_and_close(self, tmp_path: Path) -> None:
        """CollectionManager creates four collections and closes cleanly."""
        manager = CollectionManager(
            storage_path=tmp_path / "qdrant",
            vector_size=64,  # small dim for test speed
            router=CollectionRouter(),
        )

        try:
            # All 4 stores exist
            assert len(manager.stores) == 4
            for name in (COLLECTION_CODE, COLLECTION_TESTS, COLLECTION_DOCS, COLLECTION_TEXT):
                store = manager.get_store(name)
                assert store.collection_name == qdrant_collection_name(name)
        finally:
            manager.close()

    def test_upsert_to_routed_collection(self, tmp_path: Path) -> None:
        """Files can be upserted to their routed collection."""
        manager = CollectionManager(
            storage_path=tmp_path / "qdrant",
            vector_size=4,  # tiny dim for test speed
            router=CollectionRouter(),
        )

        try:
            # Route a Python source file
            collection = manager.route_file(Path("src/main.py"), plugin_name=None)
            assert collection == COLLECTION_CODE

            # Upsert a vector to the routed collection
            store = manager.get_store(collection)
            store.vector_store.upsert(
                [
                    {
                        "id": "chunk_001",
                        "vector": [0.1, 0.2, 0.3, 0.4],
                        "payload": {
                            "content": "def main(): pass",
                            "file_path": "/src/main.py",
                            "file_type": "py",
                            "chunk_index": 0,
                        },
                    }
                ]
            )

            # Verify it's in the code collection
            stats = store.vector_store.get_stats()
            assert stats["count"] >= 1

            # Verify other collections are empty
            for name in (COLLECTION_TESTS, COLLECTION_DOCS, COLLECTION_TEXT):
                other_stats = manager.get_store(name).vector_store.get_stats()
                assert other_stats["count"] == 0, f"{name} should be empty"

        finally:
            manager.close()

    def test_multiple_collections_populated(self, tmp_path: Path) -> None:
        """Multiple collections can be populated independently."""
        manager = CollectionManager(
            storage_path=tmp_path / "qdrant",
            vector_size=4,
            router=CollectionRouter(),
        )

        try:
            # Upsert to code collection
            code_store = manager.get_store(COLLECTION_CODE)
            code_store.vector_store.upsert(
                [
                    {
                        "id": "code_001",
                        "vector": [0.1, 0.2, 0.3, 0.4],
                        "payload": {
                            "content": "def main(): pass",
                            "file_path": "/src/main.py",
                            "file_type": "py",
                            "chunk_index": 0,
                        },
                    }
                ]
            )

            # Upsert to docs collection
            docs_store = manager.get_store(COLLECTION_DOCS)
            docs_store.vector_store.upsert(
                [
                    {
                        "id": "doc_001",
                        "vector": [0.5, 0.6, 0.7, 0.8],
                        "payload": {
                            "content": "# Guide",
                            "file_path": "/docs/guide.md",
                            "file_type": "md",
                            "chunk_index": 0,
                        },
                    }
                ]
            )

            # Verify counts
            assert code_store.vector_store.get_stats()["count"] == 1
            assert docs_store.vector_store.get_stats()["count"] == 1

            # Other collections should be empty
            assert manager.get_store(COLLECTION_TESTS).vector_store.get_stats()["count"] == 0
            assert manager.get_store(COLLECTION_TEXT).vector_store.get_stats()["count"] == 0

        finally:
            manager.close()

    def test_get_all_stats(self, tmp_path: Path) -> None:
        """get_all_stats returns per-collection statistics."""
        manager = CollectionManager(
            storage_path=tmp_path / "qdrant",
            vector_size=4,
            router=CollectionRouter(),
        )

        try:
            stats = manager.get_all_stats()
            assert len(stats) == 4
            for name in (COLLECTION_CODE, COLLECTION_TESTS, COLLECTION_DOCS, COLLECTION_TEXT):
                assert name in stats
                assert "count" in stats[name]
                assert stats[name]["count"] == 0  # empty initially
        finally:
            manager.close()
