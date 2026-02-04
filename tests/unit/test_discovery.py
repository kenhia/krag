"""Unit tests for FileScanner.

Tests file discovery functionality.
Should FAIL until FileScanner is implemented.
"""

from pathlib import Path

import pytest


class TestFileScanner:
    """Unit tests for FileScanner class."""

    def test_file_scanner_initialization(self) -> None:
        """Test FileScanner can be initialized with directory paths."""
        from krag.discovery.scanner import FileScanner

        scanner = FileScanner(directory_paths=[Path("/tmp")])

        assert scanner.directory_paths == [Path("/tmp")]

    def test_scan_finds_files_in_directory(self, tmp_path: Path) -> None:
        """Test scan method finds files in specified directory."""
        from krag.discovery.scanner import FileScanner

        # Create test files
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content")
        (test_dir / "file2.md").write_text("# Header")

        scanner = FileScanner(directory_paths=[test_dir])
        files = scanner.scan()

        assert len(files) == 2, "Should find both files"
        file_names = {f.file_path.name for f in files}
        assert "file1.txt" in file_names
        assert "file2.md" in file_names

    def test_scan_recursive_finds_nested_files(self, tmp_path: Path) -> None:
        """Test scan finds files in subdirectories."""
        from krag.discovery.scanner import FileScanner

        # Create nested structure
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "root.txt").write_text("root")

        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")

        scanner = FileScanner(directory_paths=[test_dir])
        files = scanner.scan()

        assert len(files) == 2, "Should find files recursively"

    def test_scan_respects_file_type_filter(self, tmp_path: Path) -> None:
        """Test scan only returns specified file types."""
        from krag.discovery.scanner import FileScanner

        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "doc.txt").write_text("text")
        (test_dir / "code.py").write_text("# code")
        (test_dir / "image.jpg").write_bytes(b"image")

        scanner = FileScanner(directory_paths=[test_dir], supported_file_types=[".txt", ".py"])
        files = scanner.scan()

        assert len(files) == 2, "Should only find .txt and .py files"
        extensions = {f.file_path.suffix for f in files}
        assert extensions == {".txt", ".py"}

    def test_scan_excludes_patterns(self, tmp_path: Path) -> None:
        """Test scan excludes files matching exclusion patterns."""
        from krag.discovery.scanner import FileScanner

        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "include.txt").write_text("include")
        (test_dir / "exclude.txt").write_text("exclude")

        # Create __pycache__ directory
        pycache = test_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "cache.pyc").write_bytes(b"cache")

        scanner = FileScanner(
            directory_paths=[test_dir],
            exclusion_patterns=["*exclude*", "__pycache__"],
        )
        files = scanner.scan()

        assert len(files) == 1, "Should exclude matching files"
        assert files[0].file_path.name == "include.txt"

    def test_scan_handles_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test scan handles non-existent directories gracefully."""
        from krag.discovery.scanner import FileScanner

        scanner = FileScanner(directory_paths=[Path("/nonexistent")])

        # Should not crash, return empty or raise informative error
        try:
            files = scanner.scan()
            assert isinstance(files, list), "Should return list even if directory missing"
        except FileNotFoundError as e:
            assert "nonexistent" in str(e).lower(), "Error should mention missing directory"

    def test_scan_handles_permission_denied(self, tmp_path: Path) -> None:
        """Test scan handles permission denied errors."""
        from krag.discovery.scanner import FileScanner

        # Create directory with no read permissions
        test_dir = tmp_path / "restricted"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        try:
            test_dir.chmod(0o000)  # Remove all permissions

            scanner = FileScanner(directory_paths=[test_dir])
            files = scanner.scan()

            # Should handle gracefully, possibly returning empty list
            assert isinstance(files, list), "Should handle permission errors gracefully"

        finally:
            test_dir.chmod(0o755)  # Restore permissions for cleanup

    def test_scan_returns_file_metadata(self, tmp_path: Path) -> None:
        """Test scan returns FileMetadata objects with required fields."""
        from krag.discovery.scanner import FileScanner
        from krag.models.file_metadata import FileMetadata

        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        scanner = FileScanner(directory_paths=[test_dir])
        files = scanner.scan()

        assert len(files) == 1
        file_meta = files[0]

        # Should return FileMetadata objects
        assert isinstance(file_meta, FileMetadata), "Should return FileMetadata objects"
        assert file_meta.file_path.exists(), "FileMetadata should have valid path"
        assert file_meta.file_size > 0, "FileMetadata should have file size"
        assert file_meta.file_type in ["text", "code", "markdown"], "Should detect file type"

    def test_scan_handles_symlinks(self, tmp_path: Path) -> None:
        """Test scan handles symbolic links appropriately."""
        from krag.discovery.scanner import FileScanner

        test_dir = tmp_path / "test"
        test_dir.mkdir()
        real_file = test_dir / "real.txt"
        real_file.write_text("content")

        # Create symlink
        symlink = test_dir / "link.txt"
        try:
            symlink.symlink_to(real_file)
        except OSError:
            pytest.skip("Symlinks not supported on this system")

        scanner = FileScanner(directory_paths=[test_dir], follow_symlinks=True)
        files = scanner.scan()

        # Should include symlink (or its target)
        assert len(files) >= 1, "Should handle symlinks"

    def test_scan_multiple_directories(self, tmp_path: Path) -> None:
        """Test scan handles multiple directory paths."""
        from krag.discovery.scanner import FileScanner

        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "file1.txt").write_text("content1")

        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "file2.txt").write_text("content2")

        scanner = FileScanner(directory_paths=[dir1, dir2])
        files = scanner.scan()

        assert len(files) == 2, "Should scan all specified directories"
        file_names = {f.file_path.name for f in files}
        assert file_names == {"file1.txt", "file2.txt"}

    def test_scan_large_directory_performance(self, tmp_path: Path) -> None:
        """Test scan performs reasonably with many files."""
        import time

        from krag.discovery.scanner import FileScanner

        test_dir = tmp_path / "large"
        test_dir.mkdir()

        # Create 100 files
        for i in range(100):
            (test_dir / f"file{i}.txt").write_text(f"content {i}")

        scanner = FileScanner(directory_paths=[test_dir])

        start = time.time()
        files = scanner.scan()
        elapsed = time.time() - start

        assert len(files) == 100, "Should find all files"
        assert elapsed < 2.0, "Should complete in reasonable time (< 2 seconds)"
