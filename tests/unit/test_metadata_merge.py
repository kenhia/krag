"""Unit tests for metadata merge across directory changes (US1).

T016: Validates that:
- _load_metadata() loads ALL entries unconditionally (no directory filter)
- index_full() preserves previously-loaded entries not touched by current run
- _save_metadata() prunes entries where file_path no longer exists on disk
- Cross-directory indexing: entries from prior directory remain after indexing a different one
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from krag.models.file_metadata import FileMetadata


def _make_metadata_entry(
    file_path: str,
    file_size: int = 100,
    file_type: str = ".py",
    content_hash: str = "abc123",
    chunk_count: int = 3,
) -> dict:
    """Create a serialized metadata entry (as stored in metadata.json)."""
    return {
        "file_path": file_path,
        "file_size": file_size,
        "modification_time": datetime(2025, 1, 1, 12, 0, 0).isoformat(),
        "file_type": file_type,
        "content_hash": content_hash,
        "last_indexed_at": datetime(2025, 1, 1, 12, 1, 0).isoformat(),
        "chunk_count": chunk_count,
    }


class TestLoadMetadataNoFilter:
    """_load_metadata() must load all entries unconditionally."""

    def test_loads_entries_outside_current_directory_paths(self, tmp_path: Path) -> None:
        """Entries from /other/dir are loaded even when directory_paths is /project."""
        from krag.orchestration.indexer import IndexingOrchestrator

        # Create metadata.json with entries from two different directories
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        metadata_path = storage_dir / "metadata.json"

        project_file = str(tmp_path / "project" / "main.py")
        other_file = str(tmp_path / "other" / "lib.py")

        metadata_path.write_text(
            json.dumps(
                [
                    _make_metadata_entry(project_file),
                    _make_metadata_entry(other_file),
                ]
            )
        )

        # Create orchestrator with directory_paths pointing only to /project
        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {}
            orch.config = None
            orch.directory_paths = [tmp_path / "project"]
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir

            orch._load_metadata()

        # Both entries must be loaded
        assert project_file in orch.indexed_files
        assert other_file in orch.indexed_files

    def test_loads_all_entries_count(self, tmp_path: Path) -> None:
        """All N entries in metadata.json are loaded regardless of directory."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        metadata_path = storage_dir / "metadata.json"

        entries = [_make_metadata_entry(f"/dir{i}/file{j}.py") for i in range(5) for j in range(3)]
        metadata_path.write_text(json.dumps(entries))

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {}
            orch.config = None
            orch.directory_paths = [Path("/dir0")]
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir

            orch._load_metadata()

        assert len(orch.indexed_files) == 15

    def test_empty_metadata_file_loads_nothing(self, tmp_path: Path) -> None:
        """Empty JSON array produces empty indexed_files."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        (storage_dir / "metadata.json").write_text("[]")

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {}
            orch.config = None
            orch.directory_paths = []
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir

            orch._load_metadata()

        assert len(orch.indexed_files) == 0

    def test_missing_metadata_file_starts_fresh(self, tmp_path: Path) -> None:
        """No metadata.json → empty indexed_files, no error."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {}
            orch.config = None
            orch.directory_paths = []
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir

            orch._load_metadata()

        assert len(orch.indexed_files) == 0


class TestMetadataMergePreservation:
    """index_full() must preserve previously-loaded entries not touched by current run."""

    def test_previously_loaded_entries_survive_full_index(self, tmp_path: Path) -> None:
        """Entries loaded from metadata.json persist after index_full() processes other files."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        # Pre-seed indexed_files with an entry from a different directory
        prior_key = "/other/dir/old_file.py"
        prior_metadata = FileMetadata(
            file_path=Path(prior_key),
            file_size=200,
            modification_time=datetime(2025, 1, 1),
            file_type=".py",
            content_hash="priorhash",
            last_indexed_at=datetime(2025, 1, 1),
            chunk_count=5,
        )

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {prior_key: prior_metadata}
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir
            orch.directory_paths = [tmp_path / "project"]
            orch.supported_file_types = [".py"]
            orch.exclusion_patterns = []
            orch.plugin_registry = None
            orch.plugin_context = None
            orch.chunking_resolver = None
            orch.failure_collector = None
            orch.collection_manager = None
            orch.config = None

            # FileScanner returns no files for /project (empty dir)
            with patch("krag.orchestration.indexer.FileScanner") as MockScanner:
                MockScanner.return_value.scan.return_value = []
                orch.index_full()

        # The prior entry must still be in indexed_files
        assert prior_key in orch.indexed_files
        assert orch.indexed_files[prior_key].content_hash == "priorhash"

    def test_current_run_overwrites_same_path(self, tmp_path: Path) -> None:
        """If the current run re-indexes a file, it overwrites the old metadata."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        file_key = str(tmp_path / "project" / "main.py")
        old_metadata = FileMetadata(
            file_path=Path(file_key),
            file_size=100,
            modification_time=datetime(2025, 1, 1),
            file_type=".py",
            content_hash="oldhash",
            last_indexed_at=datetime(2025, 1, 1),
            chunk_count=2,
        )
        new_metadata = FileMetadata(
            file_path=Path(file_key),
            file_size=200,
            modification_time=datetime(2025, 6, 1),
            file_type=".py",
            content_hash="newhash",
        )

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {file_key: old_metadata}
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir
            orch.directory_paths = [tmp_path / "project"]
            orch.supported_file_types = [".py"]
            orch.exclusion_patterns = []
            orch.plugin_registry = None
            orch.plugin_context = None
            orch.chunking_resolver = None
            orch.failure_collector = None
            orch.collection_manager = None
            orch.config = None

            # FileScanner returns the file, _process_file returns success
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.skipped = False
            mock_result.vectors = [{"id": "v1", "vector": [0.1], "payload": {}}]
            mock_result.chunk_count = 5
            mock_result.embeddings_created = 5

            with (
                patch("krag.orchestration.indexer.FileScanner") as MockScanner,
                patch.object(orch, "_process_file", return_value=mock_result),
                patch.object(orch, "_save_metadata"),
            ):
                MockScanner.return_value.scan.return_value = [new_metadata]
                orch.index_full()

        # The entry should be updated
        assert orch.indexed_files[file_key].content_hash == "newhash"
        assert orch.indexed_files[file_key].chunk_count == 5


class TestSaveMetadataPrunesStale:
    """_save_metadata() must remove entries where file_path no longer exists on disk."""

    def test_stale_entries_pruned_on_save(self, tmp_path: Path) -> None:
        """Files that no longer exist on disk are removed before saving."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        # Create one real file and one that doesn't exist
        real_file = tmp_path / "exists.py"
        real_file.write_text("# exists")
        stale_file = tmp_path / "deleted.py"  # does NOT exist

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {
                str(real_file): FileMetadata(
                    file_path=real_file,
                    file_size=10,
                    modification_time=datetime(2025, 1, 1),
                    file_type=".py",
                    content_hash="aaa",
                    chunk_count=1,
                ),
                str(stale_file): FileMetadata(
                    file_path=stale_file,
                    file_size=20,
                    modification_time=datetime(2025, 1, 1),
                    file_type=".py",
                    content_hash="bbb",
                    chunk_count=2,
                ),
            }
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir

            orch._save_metadata()

        # Read saved metadata
        saved = json.loads((storage_dir / "metadata.json").read_text())
        saved_paths = [e["file_path"] for e in saved]

        # Only the real file should be saved
        assert str(real_file) in saved_paths
        assert str(stale_file) not in saved_paths

    def test_all_entries_saved_when_all_exist(self, tmp_path: Path) -> None:
        """No pruning occurs when all files still exist."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text("# a")
        file_b.write_text("# b")

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {
                str(file_a): FileMetadata(
                    file_path=file_a,
                    file_size=10,
                    modification_time=datetime(2025, 1, 1),
                    file_type=".py",
                    content_hash="aaa",
                    chunk_count=1,
                ),
                str(file_b): FileMetadata(
                    file_path=file_b,
                    file_size=20,
                    modification_time=datetime(2025, 1, 1),
                    file_type=".py",
                    content_hash="bbb",
                    chunk_count=2,
                ),
            }
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir

            orch._save_metadata()

        saved = json.loads((storage_dir / "metadata.json").read_text())
        assert len(saved) == 2

    def test_stale_entries_removed_from_indexed_files_dict(self, tmp_path: Path) -> None:
        """After _save_metadata(), stale entries are removed from self.indexed_files too."""
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        stale_file = tmp_path / "gone.py"

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {
                str(stale_file): FileMetadata(
                    file_path=stale_file,
                    file_size=10,
                    modification_time=datetime(2025, 1, 1),
                    file_type=".py",
                    content_hash="aaa",
                    chunk_count=1,
                ),
            }
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir

            orch._save_metadata()

        assert str(stale_file) not in orch.indexed_files


class TestCrossDirectoryScenario:
    """End-to-end: index dir A, then index dir B — entries from A must persist."""

    def test_entries_from_first_directory_persist_after_second_index(self, tmp_path: Path) -> None:
        """Simulate: load metadata with dir_a entries, run index_full on dir_b.

        Entries from dir_a should remain in indexed_files after indexing dir_b.
        """
        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        # Simulate prior metadata from dir_a
        dir_a_file = str(tmp_path / "dir_a" / "module.py")
        metadata_json = json.dumps([_make_metadata_entry(dir_a_file)])
        (storage_dir / "metadata.json").write_text(metadata_json)

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch.indexed_files = {}
            orch.config = None
            orch.directory_paths = [tmp_path / "dir_b"]
            orch.vector_store = MagicMock()
            orch.vector_store.storage_path = storage_dir
            orch.supported_file_types = [".py"]
            orch.exclusion_patterns = []
            orch.plugin_registry = None
            orch.plugin_context = None
            orch.chunking_resolver = None
            orch.failure_collector = None
            orch.collection_manager = None

            # Load metadata (should get dir_a entry)
            orch._load_metadata()
            assert dir_a_file in orch.indexed_files

            # Run index_full on dir_b (no files found)
            with patch("krag.orchestration.indexer.FileScanner") as MockScanner:
                MockScanner.return_value.scan.return_value = []
                orch.index_full()

        # dir_a entry must survive
        assert dir_a_file in orch.indexed_files
        assert orch.indexed_files[dir_a_file].chunk_count == 3
