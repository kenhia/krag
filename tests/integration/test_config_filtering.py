"""Integration tests for configuration-based filtering."""

from pathlib import Path

import pytest

from krag.discovery.scanner import FileScanner
from krag.models.configuration import Configuration


class TestConfigurationBasedFiltering:
    """Test that configuration controls file discovery and processing."""

    @pytest.fixture
    def test_directory(self, tmp_path: Path) -> Path:
        """Create a test directory with various file types."""
        # Create Python files
        (tmp_path / "script.py").write_text("print('hello')")
        (tmp_path / "module.py").write_text("def func(): pass")

        # Create text files
        (tmp_path / "readme.txt").write_text("README content")
        (tmp_path / "notes.md").write_text("# Notes")

        # Create files that should be excluded
        (tmp_path / "compiled.pyc").write_text("binary")
        (tmp_path / "temp.tmp").write_text("temporary")

        # Create __pycache__ directory
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.pyc").write_text("cached")

        # Create node_modules directory
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.js").write_text("module.exports = {}")

        return tmp_path

    def test_scanner_respects_file_type_filters(self, test_directory: Path) -> None:
        """Test that FileScanner only finds files matching supported types."""
        # Only scan for Python files
        config = Configuration(
            directory_paths=[test_directory],
            supported_file_types=[".py"],
        )

        scanner = FileScanner(
            directory_paths=config.directory_paths,
            supported_file_types=config.supported_file_types,
            exclusion_patterns=config.exclusion_patterns,
        )

        files = scanner.scan()

        # Should only find .py files
        found_files = [f.file_path.name for f in files]
        assert "script.py" in found_files
        assert "module.py" in found_files
        assert "readme.txt" not in found_files
        assert "notes.md" not in found_files

    def test_scanner_respects_exclusion_patterns(self, test_directory: Path) -> None:
        """Test that FileScanner excludes files matching patterns."""
        config = Configuration(
            directory_paths=[test_directory],
            supported_file_types=[".py", ".txt", ".md", ".pyc", ".tmp"],
            exclusion_patterns=["*.pyc", "*.tmp", "**/__pycache__/**", "**/node_modules/**"],
        )

        scanner = FileScanner(
            directory_paths=config.directory_paths,
            supported_file_types=config.supported_file_types,
            exclusion_patterns=config.exclusion_patterns,
        )

        files = scanner.scan()
        found_files = [f.file_path.name for f in files]

        # Should find regular files
        assert "script.py" in found_files
        assert "readme.txt" in found_files
        assert "notes.md" in found_files

        # Should exclude based on patterns
        assert "compiled.pyc" not in found_files
        assert "temp.tmp" not in found_files
        assert "cached.pyc" not in found_files
        assert "package.js" not in found_files

    def test_scanner_with_multiple_file_types(self, test_directory: Path) -> None:
        """Test scanner with multiple supported file types."""
        config = Configuration(
            directory_paths=[test_directory],
            supported_file_types=[".py", ".md"],
        )

        scanner = FileScanner(
            directory_paths=config.directory_paths,
            supported_file_types=config.supported_file_types,
            exclusion_patterns=config.exclusion_patterns,
        )

        files = scanner.scan()
        found_files = [f.file_path.name for f in files]

        # Should find both .py and .md files
        assert "script.py" in found_files
        assert "module.py" in found_files
        assert "notes.md" in found_files

        # Should not find .txt files
        assert "readme.txt" not in found_files

    def test_scanner_with_custom_exclusions(self, test_directory: Path) -> None:
        """Test scanner with custom exclusion patterns."""
        # Create additional test files
        (test_directory / "keep.py").write_text("# keep this")
        (test_directory / "skip_this.py").write_text("# skip this")
        (test_directory / "skip_that.py").write_text("# skip that")

        config = Configuration(
            directory_paths=[test_directory],
            supported_file_types=[".py"],
            exclusion_patterns=["skip_*.py"],  # Custom pattern
        )

        scanner = FileScanner(
            directory_paths=config.directory_paths,
            supported_file_types=config.supported_file_types,
            exclusion_patterns=config.exclusion_patterns,
        )

        files = scanner.scan()
        found_files = [f.file_path.name for f in files]

        # Should find files not matching skip pattern
        assert "keep.py" in found_files
        assert "script.py" in found_files

        # Should exclude files matching skip pattern
        assert "skip_this.py" not in found_files
        assert "skip_that.py" not in found_files

    def test_default_exclusions_work(self, test_directory: Path) -> None:
        """Test that default exclusion patterns work correctly."""
        config = Configuration(
            directory_paths=[test_directory],
            # Use default exclusion patterns
        )

        scanner = FileScanner(
            directory_paths=config.directory_paths,
            supported_file_types=config.supported_file_types,
            exclusion_patterns=config.exclusion_patterns,
        )

        files = scanner.scan()
        found_paths = [str(f.file_path.relative_to(test_directory)) for f in files]

        # Should not find files in excluded directories
        assert not any("__pycache__" in p for p in found_paths)
        assert not any("node_modules" in p for p in found_paths)

    def test_multiple_directories_with_different_content(self, tmp_path: Path) -> None:
        """Test scanning multiple directories with configuration."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create different files in each directory
        (dir1 / "file1.py").write_text("dir1 python")
        (dir1 / "file1.txt").write_text("dir1 text")
        (dir2 / "file2.py").write_text("dir2 python")
        (dir2 / "file2.md").write_text("dir2 markdown")

        config = Configuration(
            directory_paths=[dir1, dir2],
            supported_file_types=[".py", ".md"],  # Only Python and Markdown
        )

        scanner = FileScanner(
            directory_paths=config.directory_paths,
            supported_file_types=config.supported_file_types,
            exclusion_patterns=config.exclusion_patterns,
        )

        files = scanner.scan()
        found_files = [f.file_path.name for f in files]

        # Should find .py and .md files from both directories
        assert "file1.py" in found_files
        assert "file2.py" in found_files
        assert "file2.md" in found_files

        # Should not find .txt files
        assert "file1.txt" not in found_files
