"""File scanner for discovering files to index."""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from krag.models.file_metadata import FileMetadata, IndexingStatus

if TYPE_CHECKING:
    from krag.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


class FileScanner:
    """Scans directories to discover files for indexing.

    Recursively finds files matching criteria (file types, exclusion patterns).
    """

    def __init__(
        self,
        directory_paths: list[Path],
        supported_file_types: list[str] | None = None,
        exclusion_patterns: list[str] | None = None,
        follow_symlinks: bool = False,
        plugin_registry: "PluginRegistry | None" = None,
    ):
        """Initialize file scanner.

        Args:
            directory_paths: Directories to scan
            supported_file_types: File extensions to include (e.g. ['.txt', '.md'])
            exclusion_patterns: Glob patterns to exclude (e.g. ['*.pyc', '__pycache__'])
            follow_symlinks: Whether to follow symbolic links
            plugin_registry: Optional plugin registry to get additional extensions from
        """
        self.directory_paths = [Path(p) for p in directory_paths]
        self.supported_file_types = supported_file_types or [
            ".txt",
            ".md",
            ".py",
            ".js",
            ".java",
            ".cpp",
            ".c",
            ".rs",
            ".go",
        ]

        # Merge plugin extensions if registry provided
        if plugin_registry is not None:
            plugin_extensions = plugin_registry.get_supported_extensions()
            # Add plugin extensions that aren't already in the list
            for ext in plugin_extensions:
                ext_lower = ext.lower()
                if ext_lower not in [e.lower() for e in self.supported_file_types]:
                    self.supported_file_types.append(ext_lower)
            if plugin_extensions:
                logger.debug(
                    f"Added {len(plugin_extensions)} extensions from plugins: {plugin_extensions}"
                )

        self.exclusion_patterns = exclusion_patterns or [
            ".*",  # Hidden files (starting with .)
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "*.pyc",
            "*.so",
            "*.dylib",
            "*.dll",
        ]
        self.follow_symlinks = follow_symlinks

    def scan(self) -> list[FileMetadata]:
        """Scan all configured directories for files.

        Returns:
            List of FileMetadata objects for discovered files
        """
        all_files = []

        for directory in self.directory_paths:
            try:
                if not directory.exists():
                    logger.warning(f"Directory does not exist: {directory}")
                    continue

                if not directory.is_dir():
                    logger.warning(f"Path is not a directory: {directory}")
                    continue

                files = self._scan_directory(directory)
                all_files.extend(files)

            except PermissionError as e:
                logger.error(f"Permission denied accessing {directory}: {e}")
            except Exception as e:
                logger.error(f"Error scanning {directory}: {e}")

        logger.info(f"Discovered {len(all_files)} files")
        return all_files

    def _scan_directory(self, directory: Path) -> list[FileMetadata]:
        """Recursively scan a single directory.

        Args:
            directory: Directory path to scan

        Returns:
            List of FileMetadata objects
        """
        files = []

        try:
            for item in directory.rglob("*"):
                # Handle symlinks
                if item.is_symlink() and not self.follow_symlinks:
                    continue

                # Skip directories
                if item.is_dir():
                    continue

                # Check exclusion patterns
                if self._is_excluded(item):
                    continue

                # Check file type
                if item.suffix not in self.supported_file_types:
                    continue

                # Check permissions
                try:
                    if not item.exists() or not item.is_file():
                        continue

                    # Create FileMetadata
                    file_meta = self._create_metadata(item)
                    files.append(file_meta)

                except (PermissionError, OSError) as e:
                    logger.debug(f"Skipping {item}: {e}")
                    continue

        except PermissionError as e:
            logger.error(f"Permission denied scanning {directory}: {e}")

        return files

    def _is_excluded(self, path: Path) -> bool:
        """Check if path matches exclusion patterns.

        Args:
            path: File path to check

        Returns:
            True if path should be excluded
        """
        # Check if file/directory name starts with dot (hidden)
        if path.name.startswith(".") and not path.name.startswith(".."):
            return True

        # Check each part of the path against patterns
        for pattern in self.exclusion_patterns:
            # Skip the .* pattern as we handled it above
            if pattern == ".*":
                continue

            # Check glob match
            if path.match(pattern):
                return True

            # Check if any parent directory matches pattern
            pattern_clean = pattern.strip("*").strip("/")
            for parent in path.parents:
                if parent.name == pattern_clean:
                    return True

        return False

    def _create_metadata(self, file_path: Path) -> FileMetadata:
        """Create FileMetadata object for a file.

        Args:
            file_path: Path to file

        Returns:
            FileMetadata object
        """
        stat = file_path.stat()

        # Detect file type
        file_type = self._detect_file_type(file_path)

        # Compute content hash
        content_hash = self._compute_hash(file_path)

        return FileMetadata(
            file_path=file_path.resolve(),
            file_size=stat.st_size,
            file_type=file_type,
            modification_time=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            content_hash=content_hash,
            indexing_status=IndexingStatus.PENDING,
        )

    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type from extension.

        Args:
            file_path: Path to file

        Returns:
            File type string
        """
        extension = file_path.suffix.lower()

        # Code files
        code_extensions = {".py", ".js", ".java", ".cpp", ".c", ".rs", ".go", ".ts", ".jsx", ".tsx"}
        if extension in code_extensions:
            return "code"

        # Markdown
        if extension in {".md", ".markdown"}:
            return "markdown"

        # Plain text
        if extension in {".txt", ".log", ".csv"}:
            return "text"

        # Default
        return "text"

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file content.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of SHA-256 hash
        """
        sha256_hash = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
        except Exception as e:
            logger.warning(f"Error computing hash for {file_path}: {e}")
            return ""

        return sha256_hash.hexdigest()
