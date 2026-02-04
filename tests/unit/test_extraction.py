"""Unit tests for TextExtractor.

Tests text extraction from files.
Should FAIL until TextExtractor is implemented.
"""

from pathlib import Path

import pytest


class TestTextExtractor:
    """Unit tests for TextExtractor class."""

    def test_text_extractor_initialization(self) -> None:
        """Test TextExtractor can be initialized."""
        from krag.extraction.text_extractor import TextExtractor

        extractor = TextExtractor()
        assert extractor is not None

    def test_extract_from_text_file(self, tmp_path: Path) -> None:
        """Test extracting text from plain text file."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "test.txt"
        content = "This is test content."
        test_file.write_text(content)

        extractor = TextExtractor()
        extracted = extractor.extract(test_file)

        assert extracted == content, "Should extract exact text content"

    def test_extract_from_markdown_file(self, tmp_path: Path) -> None:
        """Test extracting text from markdown file."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "test.md"
        content = "# Header\n\nThis is **bold** text."
        test_file.write_text(content)

        extractor = TextExtractor()
        extracted = extractor.extract(test_file)

        assert "Header" in extracted, "Should extract header text"
        assert "bold" in extracted, "Should extract formatted text"

    def test_extract_from_python_file(self, tmp_path: Path) -> None:
        """Test extracting text from Python source file."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "test.py"
        content = 'def hello():\n    """Docstring"""\n    print("Hello")'
        test_file.write_text(content)

        extractor = TextExtractor()
        extracted = extractor.extract(test_file)

        assert "def hello" in extracted, "Should extract function definition"
        assert "Docstring" in extracted, "Should extract docstring"

    def test_detect_encoding_utf8(self, tmp_path: Path) -> None:
        """Test detecting UTF-8 encoding."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "utf8.txt"
        test_file.write_text("Hello 世界", encoding="utf-8")

        extractor = TextExtractor()
        encoding = extractor.detect_encoding(test_file)

        assert encoding.lower() in ["utf-8", "utf8", "ascii"], "Should detect UTF-8"

    def test_detect_encoding_latin1(self, tmp_path: Path) -> None:
        """Test detecting Latin-1 encoding."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "latin1.txt"
        test_file.write_bytes("Café".encode("latin-1"))

        extractor = TextExtractor()
        encoding = extractor.detect_encoding(test_file)

        assert encoding is not None, "Should detect encoding"

    def test_extract_handles_large_file(self, tmp_path: Path) -> None:
        """Test extraction respects file size limits."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "large.txt"
        # Create 10MB file
        large_content = "x" * (10 * 1024 * 1024)
        test_file.write_text(large_content)

        extractor = TextExtractor(max_file_size_mb=5)

        try:
            extracted = extractor.extract(test_file)
            # Should either truncate or raise error
            assert len(extracted) <= 5 * 1024 * 1024, (
                "Should respect max file size"
            )  # or raise ValueError
        except ValueError as e:
            assert "size" in str(e).lower(), "Should mention file size in error"

    def test_extract_handles_binary_file(self, tmp_path: Path) -> None:
        """Test extraction handles binary files gracefully."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

        extractor = TextExtractor()

        try:
            extracted = extractor.extract(test_file)
            # Should return empty or raise error
            assert isinstance(extracted, str), "Should return string type"
        except (UnicodeDecodeError, ValueError):
            # Expected - binary file can't be decoded
            assert True, "Should raise error for binary file"

    def test_extract_handles_empty_file(self, tmp_path: Path) -> None:
        """Test extraction handles empty files."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        extractor = TextExtractor()
        extracted = extractor.extract(test_file)

        assert extracted == "", "Should return empty string for empty file"

    def test_extract_handles_nonexistent_file(self, tmp_path: Path) -> None:
        """Test extraction handles non-existent files."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "nonexistent.txt"

        extractor = TextExtractor()

        with pytest.raises(FileNotFoundError):
            extractor.extract(test_file)

    def test_extract_handles_unicode_content(self, tmp_path: Path) -> None:
        """Test extraction handles various Unicode characters."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "unicode.txt"
        content = "Hello 世界 🚀 Café naïve"
        test_file.write_text(content, encoding="utf-8")

        extractor = TextExtractor()
        extracted = extractor.extract(test_file)

        assert extracted == content, "Should preserve Unicode characters"

    def test_extract_strips_excess_whitespace(self, tmp_path: Path) -> None:
        """Test extraction normalizes whitespace."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "whitespace.txt"
        content = "Line 1\n\n\n\nLine 2\t\t\tTabbed"
        test_file.write_text(content)

        extractor = TextExtractor(normalize_whitespace=True)
        extracted = extractor.extract(test_file)

        # Should normalize excessive whitespace
        assert "\n\n\n\n" not in extracted, "Should reduce excessive newlines"

    def test_extract_preserves_code_formatting(self, tmp_path: Path) -> None:
        """Test extraction preserves code indentation."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "code.py"
        content = "def func():\n    if True:\n        return 1"
        test_file.write_text(content)

        extractor = TextExtractor(preserve_formatting=True)
        extracted = extractor.extract(test_file)

        # Should preserve indentation
        assert "    if True:" in extracted, "Should preserve code indentation"

    def test_extract_handles_special_characters(self, tmp_path: Path) -> None:
        """Test extraction handles special/control characters."""
        from krag.extraction.text_extractor import TextExtractor

        test_file = tmp_path / "special.txt"
        content = "Text with\r\nWindows line endings\x00and null bytes"
        test_file.write_text(content, errors="ignore")

        extractor = TextExtractor()
        extracted = extractor.extract(test_file)

        # Should handle or strip problematic characters
        assert isinstance(extracted, str), "Should return valid string"
