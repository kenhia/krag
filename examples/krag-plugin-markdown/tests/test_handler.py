"""Unit tests for Markdown file type handler."""

from pathlib import Path

import pytest

from krag_plugin_markdown.handler import MarkdownFileTypeHandler


@pytest.fixture
def handler():
    """Create a MarkdownFileTypeHandler instance."""
    return MarkdownFileTypeHandler()


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestMarkdownFileTypeHandler:
    """Test suite for MarkdownFileTypeHandler."""

    def test_plugin_properties(self, handler):
        """Test plugin metadata properties."""
        assert handler.name == "markdown"
        assert handler.version == "1.0.0"
        assert handler.required_api_version == "1.0"

    def test_supported_extensions(self, handler):
        """Test supported file extensions."""
        extensions = handler.supported_extensions()
        assert ".md" in extensions
        assert ".markdown" in extensions
        assert len(extensions) == 2

    def test_extract_text_simple(self, handler, fixtures_dir):
        """Test text extraction from simple Markdown file."""
        file_path = fixtures_dir / "simple.md"
        text = handler.extract_text(file_path)

        # Should contain main content
        assert "Getting Started" in text
        assert "This is a simple paragraph" in text

        # Should not contain Markdown syntax
        assert "#" not in text
        assert "**" not in text
        assert "__" not in text

    def test_extract_text_with_frontmatter(self, handler, fixtures_dir):
        """Test text extraction removes frontmatter."""
        file_path = fixtures_dir / "with_frontmatter.md"
        text = handler.extract_text(file_path)

        # Should contain main content
        assert "Introduction" in text
        assert "This document has frontmatter" in text

        # Should not contain frontmatter
        assert "title:" not in text
        assert "author:" not in text
        assert "---" not in text

    def test_extract_text_strips_formatting(self, handler, fixtures_dir):
        """Test that Markdown formatting is stripped."""
        file_path = fixtures_dir / "formatted.md"
        text = handler.extract_text(file_path)

        # Should contain text without formatting
        assert "bold text" in text
        assert "italic text" in text
        assert "inline code" in text

        # Should not contain Markdown syntax
        assert "**bold" not in text
        assert "*italic" not in text
        assert "`inline" not in text

    def test_extract_text_handles_links(self, handler, fixtures_dir):
        """Test that links are converted to text."""
        file_path = fixtures_dir / "with_links.md"
        text = handler.extract_text(file_path)

        # Should contain link text
        assert "example link" in text
        assert "another link" in text

        # Should not contain URLs or Markdown syntax
        assert "http" not in text
        assert "[example" not in text
        assert "](http" not in text

    def test_extract_text_handles_lists(self, handler, fixtures_dir):
        """Test that list items are extracted."""
        file_path = fixtures_dir / "with_lists.md"
        text = handler.extract_text(file_path)

        # Should contain list items
        assert "First item" in text
        assert "Second item" in text
        assert "Third item" in text

        # Should not contain list markers
        lines = text.split("\n")
        assert not any(line.strip().startswith("-") for line in lines)
        assert not any(line.strip().startswith("*") for line in lines)
        assert not any(line.strip().startswith("1.") for line in lines)

    def test_extract_text_file_not_found(self, handler, tmp_path):
        """Test handling of missing file."""
        file_path = tmp_path / "nonexistent.md"
        with pytest.raises(FileNotFoundError):
            handler.extract_text(file_path)

    def test_extract_metadata_with_frontmatter(self, handler, fixtures_dir):
        """Test metadata extraction from YAML frontmatter."""
        from datetime import date

        file_path = fixtures_dir / "with_frontmatter.md"
        metadata = handler.extract_metadata(file_path)

        assert metadata["title"] == "Test Document"
        assert metadata["author"] == "Jane Doe"
        assert metadata["date"] == date(2024, 1, 15)  # YAML parses dates as date objects
        assert metadata["tags"] == ["test", "documentation"]
        assert metadata["category"] == "guides"

    def test_extract_metadata_without_frontmatter(self, handler, fixtures_dir):
        """Test metadata extraction when no frontmatter exists."""
        file_path = fixtures_dir / "simple.md"
        metadata = handler.extract_metadata(file_path)

        # Should use filename as title
        assert metadata["title"] == "simple"
        # Should not have other fields
        assert "author" not in metadata
        assert "date" not in metadata

    def test_extract_metadata_invalid_frontmatter(self, handler, fixtures_dir):
        """Test handling of invalid YAML frontmatter."""
        file_path = fixtures_dir / "invalid_frontmatter.md"
        metadata = handler.extract_metadata(file_path)

        # Should fall back to filename as title
        assert metadata["title"] == "invalid_frontmatter"

    def test_extract_metadata_file_not_found(self, handler, tmp_path):
        """Test handling of missing file."""
        file_path = tmp_path / "nonexistent.md"
        with pytest.raises(FileNotFoundError):
            handler.extract_metadata(file_path)

    def test_get_chunking_strategy(self, handler):
        """Test that default chunking strategy is used."""
        strategy = handler.get_chunking_strategy()
        assert strategy is None

    def test_initialize(self, handler):
        """Test plugin initialization."""
        # Should not raise any exceptions
        handler.initialize()

    def test_cleanup(self, handler):
        """Test plugin cleanup."""
        # Should not raise any exceptions
        handler.cleanup()

    def test_config_schema(self, handler):
        """Test configuration schema."""
        schema = handler.config_schema()
        assert schema is None

    def test_remove_frontmatter(self, handler):
        """Test frontmatter removal helper."""
        content = """---
title: Test
author: Jane
---

# Main Content

This is the body."""

        result = handler._remove_frontmatter(content)

        assert "---" not in result
        assert "title:" not in result
        assert "# Main Content" in result
        assert "This is the body." in result

    def test_parse_frontmatter(self, handler):
        """Test frontmatter parsing helper."""
        content = """---
title: Test Document
author: Jane Doe
tags:
  - test
  - docs
---

Main content here."""

        frontmatter = handler._parse_frontmatter(content)

        assert frontmatter is not None
        assert frontmatter["title"] == "Test Document"
        assert frontmatter["author"] == "Jane Doe"
        assert frontmatter["tags"] == ["test", "docs"]

    def test_parse_frontmatter_no_frontmatter(self, handler):
        """Test parsing when no frontmatter exists."""
        content = """# Main Content

No frontmatter here."""

        frontmatter = handler._parse_frontmatter(content)
        assert frontmatter is None

    def test_parse_frontmatter_invalid_yaml(self, handler):
        """Test handling of invalid YAML."""
        content = """---
title: Test
invalid: {{ yaml
---

Main content."""

        frontmatter = handler._parse_frontmatter(content)
        assert frontmatter is None

    def test_strip_markdown_headers(self, handler):
        """Test header stripping."""
        content = """# Header 1
## Header 2
### Header 3

Some content."""

        result = handler._strip_markdown(content)

        assert result == "Header 1\nHeader 2\nHeader 3\n\nSome content."

    def test_strip_markdown_formatting(self, handler):
        """Test formatting removal."""
        content = """This is **bold** and this is *italic*.
Also __bold__ and _italic_."""

        result = handler._strip_markdown(content)

        assert "**" not in result
        assert "*" not in result
        assert "__" not in result
        assert "_" not in result
        assert "bold" in result
        assert "italic" in result

    def test_strip_markdown_code_blocks(self, handler):
        """Test code block removal."""
        content = """Some text

```python
def hello():
    print("world")
```

More text."""

        result = handler._strip_markdown(content)

        assert "```" not in result
        assert "def hello" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_strip_markdown_links(self, handler):
        """Test link conversion."""
        content = "Check out [this link](https://example.com) for more info."

        result = handler._strip_markdown(content)

        assert "[" not in result
        assert "]" not in result
        assert "https" not in result
        assert "this link" in result

    def test_strip_markdown_images(self, handler):
        """Test image removal."""
        content = "Here's an image: ![Alt text](image.png)"

        result = handler._strip_markdown(content)

        assert "![" not in result
        assert "image.png" not in result
        assert "Alt text" in result
