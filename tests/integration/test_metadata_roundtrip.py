"""Integration test for metadata round-trip with vector store (US1).

T017: Validates metadata persistence across full indexing cycles:
- Index directory A, save metadata
- Load metadata, index directory B
- Verify entries from A are preserved in the loaded + saved state
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from krag.models.file_metadata import FileMetadata


class TestMetadataRoundTrip:
    """Metadata round-trip: save → load → save preserves cross-directory entries."""

    def test_save_load_save_preserves_all_entries(self, tmp_path: Path) -> None:
        """Save metadata, load it, add new entries, save again — all entries present."""
        from unittest.mock import MagicMock, patch

        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        # Create real files so they won't be pruned
        dir_a = tmp_path / "dir_a"
        dir_a.mkdir()
        file_a = dir_a / "module_a.py"
        file_a.write_text("# module a")

        dir_b = tmp_path / "dir_b"
        dir_b.mkdir()
        file_b = dir_b / "module_b.py"
        file_b.write_text("# module b")

        # --- Cycle 1: Save metadata for file_a ---
        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch1 = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch1.indexed_files = {
                str(file_a): FileMetadata(
                    file_path=file_a,
                    file_size=file_a.stat().st_size,
                    modification_time=datetime.fromtimestamp(file_a.stat().st_mtime),
                    file_type=".py",
                    content_hash="hash_a",
                    last_indexed_at=datetime(2025, 1, 1),
                    chunk_count=3,
                ),
            }
            orch1.vector_store = MagicMock()
            orch1.vector_store.storage_path = storage_dir
            orch1._save_metadata()

        # Verify file saved
        saved1 = json.loads((storage_dir / "metadata.json").read_text())
        assert len(saved1) == 1
        assert saved1[0]["file_path"] == str(file_a)

        # --- Cycle 2: Load metadata, add file_b, save ---
        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch2 = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch2.indexed_files = {}
            orch2.config = None
            orch2.directory_paths = [dir_b]  # Only dir_b in scope now
            orch2.vector_store = MagicMock()
            orch2.vector_store.storage_path = storage_dir

            orch2._load_metadata()

            # file_a must be loaded despite dir_b being the current directory
            assert str(file_a) in orch2.indexed_files

            # Now add file_b (simulating index_full processing)
            orch2.indexed_files[str(file_b)] = FileMetadata(
                file_path=file_b,
                file_size=file_b.stat().st_size,
                modification_time=datetime.fromtimestamp(file_b.stat().st_mtime),
                file_type=".py",
                content_hash="hash_b",
                last_indexed_at=datetime(2025, 6, 1),
                chunk_count=4,
            )

            orch2._save_metadata()

        # --- Verify: Both entries saved ---
        saved2 = json.loads((storage_dir / "metadata.json").read_text())
        saved_paths = {e["file_path"] for e in saved2}
        assert str(file_a) in saved_paths
        assert str(file_b) in saved_paths
        assert len(saved2) == 2

    def test_stale_file_pruned_on_round_trip(self, tmp_path: Path) -> None:
        """Files that no longer exist get pruned on save, even if loaded."""
        from unittest.mock import MagicMock, patch

        from krag.orchestration.indexer import IndexingOrchestrator

        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        # Create file, save metadata, then delete the file
        ephemeral = tmp_path / "ephemeral.py"
        ephemeral.write_text("# temp")

        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch1 = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch1.indexed_files = {
                str(ephemeral): FileMetadata(
                    file_path=ephemeral,
                    file_size=10,
                    modification_time=datetime(2025, 1, 1),
                    file_type=".py",
                    content_hash="ephemeral_hash",
                    chunk_count=1,
                ),
            }
            orch1.vector_store = MagicMock()
            orch1.vector_store.storage_path = storage_dir
            orch1._save_metadata()

        # Delete the file
        ephemeral.unlink()

        # Load and re-save
        with patch.object(IndexingOrchestrator, "__init__", lambda self: None):
            orch2 = IndexingOrchestrator.__new__(IndexingOrchestrator)
            orch2.indexed_files = {}
            orch2.config = None
            orch2.directory_paths = [tmp_path]
            orch2.vector_store = MagicMock()
            orch2.vector_store.storage_path = storage_dir

            orch2._load_metadata()
            # Entry is loaded (it existed when saved)
            assert str(ephemeral) in orch2.indexed_files

            # Save triggers pruning
            orch2._save_metadata()

        # After save, stale entry is gone from both file and dict
        saved = json.loads((storage_dir / "metadata.json").read_text())
        assert len(saved) == 0
        assert str(ephemeral) not in orch2.indexed_files
