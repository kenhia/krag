"""Unit tests for incremental indexing logic.

Tests focus on change detection, file categorization, and hash-based comparison.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from krag.models.file_metadata import FileMetadata, IndexingStatus
from krag.orchestration.incremental import (
    ChangeDetector,
    FileChange,
    FileChangeType,
    compute_file_hash,
)


class TestFileHashing:
    """Test file content hashing for change detection."""

    def test_compute_file_hash_returns_consistent_hash(self, tmp_path: Path):
        """Test that same content produces same hash."""
        file = tmp_path / "test.txt"
        content = "This is test content for hashing"
        file.write_text(content)

        hash1 = compute_file_hash(file)
        hash2 = compute_file_hash(file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters

    def test_compute_file_hash_detects_content_changes(self, tmp_path: Path):
        """Test that different content produces different hash."""
        file = tmp_path / "test.txt"

        file.write_text("Original content")
        hash1 = compute_file_hash(file)

        file.write_text("Modified content")
        hash2 = compute_file_hash(file)

        assert hash1 != hash2

    def test_compute_file_hash_handles_binary_files(self, tmp_path: Path):
        """Test hashing works with binary files."""
        file = tmp_path / "test.bin"
        file.write_bytes(b"\\x00\\x01\\x02\\x03\\xFF\\xFE\\xFD")

        hash1 = compute_file_hash(file)
        assert isinstance(hash1, str)
        assert len(hash1) == 64


class TestChangeDetector:
    """Test file change detection logic."""

    @pytest.fixture
    def detector(self, tmp_path: Path) -> ChangeDetector:
        """Create change detector instance."""
        storage_path = tmp_path / "storage"
        storage_path.mkdir()
        return ChangeDetector(storage_path=storage_path)

    def test_new_file_is_detected(self, detector: ChangeDetector, tmp_path: Path):
        """Test that a file with no previous metadata is detected as new."""
        file = tmp_path / "new_file.txt"
        file.write_text("New content")

        # No previous metadata
        change = detector.detect_change(file, previous_metadata=None)

        assert change.change_type == FileChangeType.NEW
        assert change.file_path == file
        assert change.needs_indexing is True

    def test_deleted_file_is_detected(self, detector: ChangeDetector, tmp_path: Path):
        """Test that a missing file with previous metadata is detected as deleted."""
        file = tmp_path / "deleted_file.txt"

        # Previous metadata exists but file doesn't
        previous_meta = FileMetadata(
            file_path=file,
            file_size=100,
            modification_time=datetime.now(),
            file_type="txt",
            status=IndexingStatus.COMPLETED,
            content_hash="abc123",
        )

        change = detector.detect_change(file, previous_metadata=previous_meta)

        assert change.change_type == FileChangeType.DELETED
        assert change.file_path == file
        assert change.needs_indexing is False

    def test_modified_file_is_detected(self, detector: ChangeDetector, tmp_path: Path):
        """Test that a file with changed modification time is detected as modified."""
        file = tmp_path / "modified_file.txt"
        file.write_text("Original content")

        # Create previous metadata with old timestamp
        old_time = datetime.now() - timedelta(hours=1)
        previous_meta = FileMetadata(
            file_path=file,
            file_size=100,
            modification_time=old_time,
            file_type="txt",
            status=IndexingStatus.COMPLETED,
            content_hash=compute_file_hash(file),  # Hash of original content
        )

        # Modify file
        import time

        time.sleep(0.01)
        file.write_text("Modified content")

        change = detector.detect_change(file, previous_metadata=previous_meta)

        assert change.change_type == FileChangeType.MODIFIED
        assert change.file_path == file
        assert change.needs_indexing is True

    def test_unchanged_file_is_detected(self, detector: ChangeDetector, tmp_path: Path):
        """Test that a file with same mtime and hash is detected as unchanged."""
        file = tmp_path / "unchanged_file.txt"
        file.write_text("Stable content")

        # Get current file stats
        stat = file.stat()
        current_time = datetime.fromtimestamp(stat.st_mtime)
        current_hash = compute_file_hash(file)

        # Create previous metadata matching current state
        previous_meta = FileMetadata(
            file_path=file,
            file_size=stat.st_size,
            modification_time=current_time,
            file_type="txt",
            status=IndexingStatus.COMPLETED,
            content_hash=current_hash,
        )

        change = detector.detect_change(file, previous_metadata=previous_meta)

        assert change.change_type == FileChangeType.UNCHANGED
        assert change.file_path == file
        assert change.needs_indexing is False

    def test_categorize_changes(self, detector: ChangeDetector, tmp_path: Path):
        """Test categorization of multiple file changes."""
        # Create files with different change types
        new_file = tmp_path / "new.txt"
        modified_file = tmp_path / "modified.txt"
        unchanged_file = tmp_path / "unchanged.txt"
        deleted_file = tmp_path / "deleted.txt"

        new_file.write_text("New")
        modified_file.write_text("Modified")
        unchanged_file.write_text("Unchanged")

        # Create previous metadata
        old_time = datetime.now() - timedelta(hours=1)
        previous_metadata = {
            str(modified_file): FileMetadata(
                file_path=modified_file,
                file_size=8,
                modification_time=old_time,
                file_type="txt",
                status=IndexingStatus.COMPLETED,
                content_hash="old_hash",
            ),
            str(unchanged_file): FileMetadata(
                file_path=unchanged_file,
                file_size=9,
                modification_time=datetime.fromtimestamp(unchanged_file.stat().st_mtime),
                file_type="txt",
                status=IndexingStatus.COMPLETED,
                content_hash=compute_file_hash(unchanged_file),
            ),
            str(deleted_file): FileMetadata(
                file_path=deleted_file,
                file_size=7,
                modification_time=old_time,
                file_type="txt",
                status=IndexingStatus.COMPLETED,
                content_hash="deleted_hash",
            ),
        }

        current_files = [new_file, modified_file, unchanged_file]

        categorized = detector.categorize_changes(current_files, previous_metadata)

        assert len(categorized["new"]) == 1
        assert categorized["new"][0].file_path == new_file

        assert len(categorized["modified"]) == 1
        assert categorized["modified"][0].file_path == modified_file

        assert len(categorized["unchanged"]) == 1
        assert categorized["unchanged"][0].file_path == unchanged_file

        assert len(categorized["deleted"]) == 1
        assert categorized["deleted"][0].file_path == deleted_file


class TestFileChangeType:
    """Test FileChangeType enum."""

    def test_enum_values(self):
        """Test that FileChangeType enum has expected values."""
        assert FileChangeType.NEW.value == "new"
        assert FileChangeType.MODIFIED.value == "modified"
        assert FileChangeType.DELETED.value == "deleted"
        assert FileChangeType.UNCHANGED.value == "unchanged"


class TestFileChange:
    """Test FileChange dataclass."""

    def test_file_change_creation(self, tmp_path: Path):
        """Test creating FileChange instances."""
        file = tmp_path / "test.txt"
        file.write_text("test")

        change = FileChange(
            file_path=file,
            change_type=FileChangeType.NEW,
            needs_indexing=True,
            previous_hash=None,
            current_hash="abc123",
        )

        assert change.file_path == file
        assert change.change_type == FileChangeType.NEW
        assert change.needs_indexing is True
        assert change.previous_hash is None
        assert change.current_hash == "abc123"
