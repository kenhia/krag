"""Integration tests for FileMetadata persistence across CLI invocations."""

from pathlib import Path

from krag.models.configuration import Configuration
from krag.orchestration.indexer import IndexingOrchestrator


class TestMetadataPersistence:
    """Test that metadata persists between separate IndexingOrchestrator instances."""

    def test_metadata_persists_across_instances(self, tmp_path: Path):
        """Test that indexed file metadata persists when creating new orchestrator."""
        # Create test corpus
        corpus_dir = tmp_path / "corpus"
        corpus_dir.mkdir()

        (corpus_dir / "doc1.txt").write_text("This is document 1.")
        (corpus_dir / "doc2.txt").write_text("This is document 2.")

        vector_store_path = tmp_path / "vector_store"
        vector_store_path.mkdir()

        config = Configuration(
            directory_paths=[corpus_dir],
            vector_store_path=vector_store_path,
        )

        # First indexing session
        with IndexingOrchestrator(config) as orchestrator1:
            job1 = orchestrator1.index_full()
            assert job1.files_processed == 2
            assert len(orchestrator1.indexed_files) == 2

        # Verify metadata file was created
        metadata_path = vector_store_path / "metadata.json"
        assert metadata_path.exists(), "Metadata file should be created"

        # Second indexing session (new orchestrator instance)
        with IndexingOrchestrator(config) as orchestrator2:
            # Should load 2 files from metadata
            assert len(orchestrator2.indexed_files) == 2, "Should load previous metadata"

            # Run incremental - should skip unchanged files
            job2 = orchestrator2.index_incremental()
            assert job2.files_skipped == 2, "Both files should be skipped (unchanged)"
            assert job2.files_added == 0
            assert job2.files_modified == 0

    def test_incremental_detects_new_files_after_restart(self, tmp_path: Path):
        """Test that new files are detected after restarting orchestrator."""
        corpus_dir = tmp_path / "corpus"
        corpus_dir.mkdir()

        (corpus_dir / "doc1.txt").write_text("This is document 1.")

        vector_store_path = tmp_path / "vector_store"
        vector_store_path.mkdir()

        config = Configuration(
            directory_paths=[corpus_dir],
            vector_store_path=vector_store_path,
        )

        # First session: index 1 file
        with IndexingOrchestrator(config) as orchestrator1:
            job1 = orchestrator1.index_full()
            assert job1.files_processed == 1

        # Add new file between sessions
        (corpus_dir / "doc2.txt").write_text("This is document 2.")

        # Second session: should detect new file
        with IndexingOrchestrator(config) as orchestrator2:
            assert len(orchestrator2.indexed_files) == 1, "Should load 1 file from metadata"

            job2 = orchestrator2.index_incremental()
            assert job2.files_added == 1, "Should detect new file"
            assert job2.files_skipped == 1, "Should skip unchanged file"
            assert job2.files_processed == 1

    def test_incremental_detects_modified_files_after_restart(self, tmp_path: Path):
        """Test that modified files are detected after restarting orchestrator."""
        corpus_dir = tmp_path / "corpus"
        corpus_dir.mkdir()

        doc_path = corpus_dir / "doc1.txt"
        doc_path.write_text("Original content.")

        vector_store_path = tmp_path / "vector_store"
        vector_store_path.mkdir()

        config = Configuration(
            directory_paths=[corpus_dir],
            vector_store_path=vector_store_path,
        )

        # First session: index file
        with IndexingOrchestrator(config) as orchestrator1:
            job1 = orchestrator1.index_full()
            assert job1.files_processed == 1

        # Modify file between sessions
        import time

        time.sleep(0.1)  # Ensure modification time changes
        doc_path.write_text("Modified content with new text.")

        # Second session: should detect modification
        with IndexingOrchestrator(config) as orchestrator2:
            assert len(orchestrator2.indexed_files) == 1

            job2 = orchestrator2.index_incremental()
            assert job2.files_modified == 1, "Should detect modified file"
            assert job2.files_processed == 1

    def test_incremental_detects_deleted_files_after_restart(self, tmp_path: Path):
        """Test that deleted files are detected after restarting orchestrator."""
        corpus_dir = tmp_path / "corpus"
        corpus_dir.mkdir()

        doc1_path = corpus_dir / "doc1.txt"
        doc2_path = corpus_dir / "doc2.txt"

        doc1_path.write_text("Document 1.")
        doc2_path.write_text("Document 2.")

        vector_store_path = tmp_path / "vector_store"
        vector_store_path.mkdir()

        config = Configuration(
            directory_paths=[corpus_dir],
            vector_store_path=vector_store_path,
        )

        # First session: index 2 files
        with IndexingOrchestrator(config) as orchestrator1:
            job1 = orchestrator1.index_full()
            assert job1.files_processed == 2

        # Delete one file between sessions
        doc2_path.unlink()

        # Second session: should detect deletion
        with IndexingOrchestrator(config) as orchestrator2:
            assert len(orchestrator2.indexed_files) == 2

            job2 = orchestrator2.index_incremental()
            assert job2.files_deleted == 1, "Should detect deleted file"
            assert job2.files_skipped == 1, "Should skip unchanged file"

    def test_metadata_handles_corrupt_file_gracefully(self, tmp_path: Path):
        """Test that corrupt metadata file is handled gracefully."""
        corpus_dir = tmp_path / "corpus"
        corpus_dir.mkdir()

        (corpus_dir / "doc1.txt").write_text("Document 1.")

        vector_store_path = tmp_path / "vector_store"
        vector_store_path.mkdir()

        # Create corrupt metadata file
        metadata_path = vector_store_path / "metadata.json"
        metadata_path.write_text("{invalid json content")

        config = Configuration(
            directory_paths=[corpus_dir],
            vector_store_path=vector_store_path,
        )

        # Should handle corrupt metadata gracefully and start fresh
        with IndexingOrchestrator(config) as orchestrator:
            assert len(orchestrator.indexed_files) == 0, "Should start with empty state"

            job = orchestrator.index_full()
            assert job.files_processed == 1

    def test_metadata_missing_creates_new_file(self, tmp_path: Path):
        """Test that missing metadata file is created on first run."""
        corpus_dir = tmp_path / "corpus"
        corpus_dir.mkdir()

        (corpus_dir / "doc1.txt").write_text("Document 1.")

        vector_store_path = tmp_path / "vector_store"
        vector_store_path.mkdir()

        config = Configuration(
            directory_paths=[corpus_dir],
            vector_store_path=vector_store_path,
        )

        metadata_path = vector_store_path / "metadata.json"
        assert not metadata_path.exists(), "Metadata should not exist yet"

        # First run should create metadata
        with IndexingOrchestrator(config) as orchestrator:
            job = orchestrator.index_full()
            assert job.files_processed == 1

        assert metadata_path.exists(), "Metadata should be created"
        assert metadata_path.stat().st_size > 0, "Metadata should not be empty"
