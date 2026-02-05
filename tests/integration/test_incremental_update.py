"""Integration tests for incremental indexing functionality.

Tests verify that incremental indexing correctly detects:
- New files to add
- Modified files to re-index
- Deleted files to remove
- Unchanged files to skip
"""

import time
from pathlib import Path

import pytest

from krag.models.configuration import Configuration
from krag.models.indexing_job import JobType
from krag.orchestration.indexer import IndexingOrchestrator


@pytest.fixture
def test_corpus_dir(tmp_path: Path) -> Path:
    """Create a temporary test corpus directory."""
    corpus = tmp_path / "test_corpus"
    corpus.mkdir()
    return corpus


@pytest.fixture
def config(test_corpus_dir: Path, tmp_path: Path) -> Configuration:
    """Create test configuration."""
    return Configuration(
        directory_paths=[test_corpus_dir],
        vector_store_path=tmp_path / "storage",
        chunk_size=128,
        chunk_overlap=20,
    )


@pytest.fixture
def orchestrator(config: Configuration) -> IndexingOrchestrator:
    """Create indexing orchestrator."""
    return IndexingOrchestrator(config)


class TestIncrementalIndexing:
    """Test incremental indexing functionality."""

    def test_new_files_are_indexed(self, test_corpus_dir: Path, orchestrator: IndexingOrchestrator):
        """Test that new files are detected and indexed during incremental update."""
        # Initial indexing with 2 files
        (test_corpus_dir / "file1.txt").write_text("Initial content for file 1")
        (test_corpus_dir / "file2.txt").write_text("Initial content for file 2")

        # Run full index
        job1 = orchestrator.index_full()
        assert job1.job_type == JobType.FULL
        assert job1.files_processed == 2
        assert job1.files_discovered == 2

        # Add a new file
        time.sleep(0.1)  # Ensure timestamp difference
        (test_corpus_dir / "file3.txt").write_text("New content in file 3")

        # Run incremental index
        job2 = orchestrator.index_incremental()
        assert job2.job_type == JobType.INCREMENTAL
        assert job2.files_discovered == 3  # Total files found
        assert job2.files_processed == 1  # Only new file processed
        assert job2.files_skipped == 2  # Two unchanged files

    def test_modified_files_are_reindexed(
        self, test_corpus_dir: Path, orchestrator: IndexingOrchestrator
    ):
        """Test that modified files are detected and re-indexed."""
        # Initial indexing
        file1 = test_corpus_dir / "file1.txt"
        file2 = test_corpus_dir / "file2.txt"
        file1.write_text("Original content 1")
        file2.write_text("Original content 2")

        job1 = orchestrator.index_full()
        assert job1.files_processed == 2

        # Modify one file
        time.sleep(0.1)  # Ensure timestamp difference
        file1.write_text("Modified content 1 - completely different")

        # Run incremental index
        job2 = orchestrator.index_incremental()
        assert job2.files_processed == 1  # Only modified file
        assert job2.files_skipped == 1  # One unchanged file

    def test_deleted_files_are_removed_from_index(
        self, test_corpus_dir: Path, orchestrator: IndexingOrchestrator
    ):
        """Test that deleted files are removed from the vector store."""
        # Initial indexing with 3 files
        (test_corpus_dir / "file1.txt").write_text("Content 1")
        (test_corpus_dir / "file2.txt").write_text("Content 2")
        file3 = test_corpus_dir / "file3.txt"
        file3.write_text("Content 3")

        job1 = orchestrator.index_full()
        assert job1.files_processed == 3

        # Get initial vector count
        from krag.storage.qdrant_impl import QdrantVectorStore

        vector_store = QdrantVectorStore(
            storage_path=orchestrator.config.vector_store_path,
            collection_name=orchestrator.config.collection_name,
        )
        initial_stats = vector_store.get_stats()
        initial_count = initial_stats["vector_count"]
        assert initial_count > 0

        # Delete one file
        file3.unlink()

        # Run incremental index
        job2 = orchestrator.index_incremental()
        assert job2.files_discovered == 2  # Only 2 files remain

        # Verify vector store updated (vectors for deleted file removed)
        updated_stats = vector_store.get_stats()
        updated_count = updated_stats["vector_count"]
        assert updated_count < initial_count, "Deleted file vectors should be removed"

    def test_unchanged_files_are_skipped(
        self, test_corpus_dir: Path, orchestrator: IndexingOrchestrator
    ):
        """Test that unchanged files are not reprocessed."""
        # Initial indexing
        (test_corpus_dir / "file1.txt").write_text("Content 1")
        (test_corpus_dir / "file2.txt").write_text("Content 2")
        (test_corpus_dir / "file3.txt").write_text("Content 3")

        job1 = orchestrator.index_full()
        assert job1.files_processed == 3

        # Run incremental without changes
        job2 = orchestrator.index_incremental()
        assert job2.files_discovered == 3
        assert job2.files_processed == 0  # Nothing changed
        assert job2.files_skipped == 3  # All files skipped

    def test_mixed_changes_are_handled_correctly(
        self, test_corpus_dir: Path, orchestrator: IndexingOrchestrator
    ):
        """Test combination of new, modified, deleted, and unchanged files."""
        # Initial indexing with 3 files
        file1 = test_corpus_dir / "file1.txt"
        file2 = test_corpus_dir / "file2.txt"
        file3 = test_corpus_dir / "file3.txt"

        file1.write_text("Content 1")
        file2.write_text("Content 2")
        file3.write_text("Content 3")

        job1 = orchestrator.index_full()
        assert job1.files_processed == 3

        # Make mixed changes
        time.sleep(0.1)
        file1.write_text("Modified content 1")  # Modified
        file3.unlink()  # Deleted
        (test_corpus_dir / "file4.txt").write_text("New content 4")  # New
        # file2 unchanged

        # Run incremental index
        job2 = orchestrator.index_incremental()
        assert job2.files_discovered == 3  # file1, file2, file4 (file3 deleted)
        assert job2.files_processed == 2  # file1 (modified) + file4 (new)
        assert job2.files_skipped == 1  # file2 (unchanged)

    def test_incremental_faster_than_full_reindex(
        self, test_corpus_dir: Path, orchestrator: IndexingOrchestrator
    ):
        """Test that incremental indexing is significantly faster than full re-index."""
        # Create a larger corpus
        for i in range(20):
            (test_corpus_dir / f"file{i}.txt").write_text(f"Content for file {i}" * 50)

        # Full index
        import time as time_module

        start = time_module.time()
        job1 = orchestrator.index_full()
        full_duration = time_module.time() - start
        assert job1.files_processed == 20

        # Modify just one file
        time.sleep(0.1)
        (test_corpus_dir / "file0.txt").write_text("Modified content")

        # Incremental index
        start = time_module.time()
        job2 = orchestrator.index_incremental()
        incremental_duration = time_module.time() - start

        assert job2.files_processed == 1
        # Incremental should be significantly faster
        # Allow some overhead, but should be at least 5x faster for 1/20 files
        assert incremental_duration < full_duration / 3, (
            f"Incremental indexing should be much faster than full re-index. "
            f"Full: {full_duration:.2f}s, Incremental: {incremental_duration:.2f}s"
        )
