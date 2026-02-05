"""Incremental indexing logic for change detection and file categorization."""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from krag.models.file_metadata import FileMetadata

logger = logging.getLogger(__name__)


class FileChangeType(StrEnum):
    """Types of file changes detected during incremental indexing."""

    NEW = "new"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


@dataclass
class FileChange:
    """Represents a detected change to a file."""

    file_path: Path
    change_type: FileChangeType
    needs_indexing: bool
    previous_hash: str | None = None
    current_hash: str | None = None


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file contents.

    Args:
        file_path: Path to file to hash

    Returns:
        Hex string of SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 64KB chunks for memory efficiency
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class ChangeDetector:
    """Detects changes between current files and previously indexed metadata."""

    def __init__(self, storage_path: Path):
        """Initialize change detector.

        Args:
            storage_path: Path to metadata storage
        """
        self.storage_path = storage_path
        logger.info(f"Initialized ChangeDetector with storage: {storage_path}")

    def detect_change(self, file_path: Path, previous_metadata: FileMetadata | None) -> FileChange:
        """Detect what type of change occurred to a file.

        Args:
            file_path: Path to file to check
            previous_metadata: Previously stored metadata, or None if new file

        Returns:
            FileChange describing the detected change
        """
        # Case 1: File doesn't exist but has previous metadata -> DELETED
        if not file_path.exists():
            if previous_metadata is not None:
                return FileChange(
                    file_path=file_path,
                    change_type=FileChangeType.DELETED,
                    needs_indexing=False,
                    previous_hash=previous_metadata.content_hash,
                    current_hash=None,
                )
            # File doesn't exist and no previous metadata -> shouldn't happen
            raise ValueError(f"File doesn't exist and has no previous metadata: {file_path}")

        # Case 2: File exists but no previous metadata -> NEW
        if previous_metadata is None:
            current_hash = compute_file_hash(file_path)
            return FileChange(
                file_path=file_path,
                change_type=FileChangeType.NEW,
                needs_indexing=True,
                previous_hash=None,
                current_hash=current_hash,
            )

        # Case 3: File exists with previous metadata -> check for changes
        current_stat = file_path.stat()
        current_mtime = datetime.fromtimestamp(current_stat.st_mtime, tz=UTC)

        # Quick check: if mtime hasn't changed, file is likely unchanged
        # Use a small tolerance for filesystem timestamp precision
        mtime_diff = abs((current_mtime - previous_metadata.modification_time).total_seconds())

        if mtime_diff < 0.001:  # Less than 1ms difference
            # Modification time unchanged, file is likely unchanged
            return FileChange(
                file_path=file_path,
                change_type=FileChangeType.UNCHANGED,
                needs_indexing=False,
                previous_hash=previous_metadata.content_hash,
                current_hash=previous_metadata.content_hash,
            )

        # Modification time changed, compute hash to verify actual content change
        current_hash = compute_file_hash(file_path)

        if current_hash == previous_metadata.content_hash:
            # Hash matches despite mtime change (e.g., file moved or touched)
            return FileChange(
                file_path=file_path,
                change_type=FileChangeType.UNCHANGED,
                needs_indexing=False,
                previous_hash=current_hash,
                current_hash=current_hash,
            )

        # Hash different -> file was actually modified
        return FileChange(
            file_path=file_path,
            change_type=FileChangeType.MODIFIED,
            needs_indexing=True,
            previous_hash=previous_metadata.content_hash,
            current_hash=current_hash,
        )

    def categorize_changes(
        self, current_files: list[Path], previous_metadata: dict[str, FileMetadata]
    ) -> dict[str, list[FileChange]]:
        """Categorize all file changes.

        Args:
            current_files: List of files currently discovered
            previous_metadata: Dict mapping file paths to previous metadata

        Returns:
            Dict with keys: 'new', 'modified', 'deleted', 'unchanged'
            Each value is a list of FileChange objects
        """
        categorized = {
            "new": [],
            "modified": [],
            "deleted": [],
            "unchanged": [],
        }

        # Track which previous files we've seen
        seen_previous_files = set()

        # Check each current file
        for file_path in current_files:
            file_key = str(file_path)
            previous = previous_metadata.get(file_key)

            change = self.detect_change(file_path, previous)

            # Add to appropriate category
            if change.change_type == FileChangeType.NEW:
                categorized["new"].append(change)
            elif change.change_type == FileChangeType.MODIFIED:
                categorized["modified"].append(change)
            elif change.change_type == FileChangeType.UNCHANGED:
                categorized["unchanged"].append(change)

            if previous is not None:
                seen_previous_files.add(file_key)

        # Find deleted files (in previous metadata but not in current files)
        for file_key, metadata in previous_metadata.items():
            if file_key not in seen_previous_files:
                deleted_change = FileChange(
                    file_path=metadata.file_path,
                    change_type=FileChangeType.DELETED,
                    needs_indexing=False,
                    previous_hash=metadata.content_hash,
                    current_hash=None,
                )
                categorized["deleted"].append(deleted_change)

        logger.info(
            f"Change categorization: {len(categorized['new'])} new, "
            f"{len(categorized['modified'])} modified, "
            f"{len(categorized['deleted'])} deleted, "
            f"{len(categorized['unchanged'])} unchanged"
        )

        return categorized
