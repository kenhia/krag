"""Integration tests for example plugins with actual file indexing.

Tests that markdown and log file plugins work correctly in the full indexing pipeline.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from krag.embeddings.generator import EmbeddingGenerator
from krag.extraction.chunker import TextChunker
from krag.models.configuration import PluginConfiguration
from krag.plugins.context import PluginContext
from krag.plugins.registry import PluginRegistry
from krag.storage.vector_store import VectorStore


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def plugin_registry():
    """Create plugin registry with example plugins enabled."""
    config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
    registry = PluginRegistry(config)
    registry.discover_plugins()
    return registry


@pytest.fixture
def mock_embedding_generator():
    """Create a mock EmbeddingGenerator."""
    return MagicMock(spec=EmbeddingGenerator)


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore."""
    return MagicMock(spec=VectorStore)


@pytest.fixture
def mock_plugin_context(mock_vector_store, mock_embedding_generator):
    """Create mock plugin context for testing."""
    import logging

    chunker = TextChunker()
    logger = logging.getLogger(__name__)
    report_callback = MagicMock()

    return PluginContext(
        embedding_generator=mock_embedding_generator,
        vector_store=mock_vector_store,
        chunker=chunker,
        logger=logger,
        report_indexing_failure=report_callback,
    )


class TestMarkdownPluginIntegration:
    """Integration tests for markdown plugin."""

    def test_markdown_plugin_discovered(self, plugin_registry):
        """Test that markdown plugin is discovered."""
        plugins = plugin_registry.list_plugins()
        plugin_names = [p.name for p in plugins]
        assert "markdown" in plugin_names

    def test_markdown_plugin_direct_usage(self, temp_dir):
        """Test markdown plugin with direct instantiation."""
        from krag_plugin_markdown.handler import MarkdownFileTypeHandler

        # Create test markdown file
        md_file = temp_dir / "test.md"
        md_file.write_text(
            """---
title: Test Document
author: Test Author
---

# Introduction

This is a **test** document with *formatting*.

## Section

- List item 1
- List item 2

[Link text](https://example.com)
"""
        )

        handler = MarkdownFileTypeHandler()
        text = handler.extract_text(md_file)

        # Should contain content without Markdown syntax
        assert "Introduction" in text
        assert "test document" in text
        assert "List item 1" in text

        # Should not contain Markdown syntax
        assert "**" not in text
        assert "*" not in text or text.count("*") == 0  # Allow if stripped
        assert "---" not in text
        assert "[Link text]" not in text

    def test_markdown_plugin_metadata(self, temp_dir):
        """Test markdown metadata extraction."""
        from krag_plugin_markdown.handler import MarkdownFileTypeHandler

        md_file = temp_dir / "test.md"
        md_file.write_text(
            """---
title: Integration Test
author: Test Suite
tags:
  - test
  - integration
---

# Content
"""
        )

        handler = MarkdownFileTypeHandler()
        metadata = handler.extract_metadata(md_file)

        assert metadata["title"] == "Integration Test"
        assert metadata["author"] == "Test Suite"
        assert metadata["tags"] == ["test", "integration"]

    def test_markdown_plugin_extensions(self):
        """Test that markdown plugin handles correct extensions."""
        from krag_plugin_markdown.handler import MarkdownFileTypeHandler

        handler = MarkdownFileTypeHandler()
        assert handler.can_handle_file(Path("test.md"))
        assert handler.can_handle_file(Path("test.markdown"))
        assert not handler.can_handle_file(Path("test.txt"))
        assert not handler.can_handle_file(Path("test.log"))


class TestLogPluginIntegration:
    """Integration tests for log file plugin."""

    def test_log_plugin_discovered(self, plugin_registry):
        """Test that log plugin is discovered."""
        plugins = plugin_registry.list_plugins()
        plugin_names = [p.name for p in plugins]
        assert "logs" in plugin_names

    def test_log_plugin_loads(self, plugin_registry, mock_plugin_context):
        """Test that log plugin can be loaded."""
        handler = plugin_registry.load_plugin("logs", mock_plugin_context)
        assert handler is not None
        assert handler.name == "logs"

    def test_log_plugin_extracts_text(self, plugin_registry, mock_plugin_context, temp_dir):
        """Test log text extraction with real file."""
        log_file = temp_dir / "test.log"
        log_file.write_text(
            """2024-02-11 10:00:00 INFO Application started
2024-02-11 10:00:05 INFO Database connected
2024-02-11 10:00:10 ERROR Connection timeout
    at org.example.Service.connect(Service.java:123)
    at org.example.App.main(App.java:45)
2024-02-11 10:00:15 INFO Retry successful
"""
        )

        handler = plugin_registry.load_plugin("logs", mock_plugin_context)
        text = handler.extract_text(log_file)

        assert "Application started" in text
        assert "Database connected" in text
        assert "Connection timeout" in text
        assert "Service.java:123" in text

    def test_log_plugin_extracts_metadata(self, plugin_registry, mock_plugin_context, temp_dir):
        """Test log metadata extraction with real file."""
        log_file = temp_dir / "application.log"
        log_file.write_text(
            """2024-02-11 10:00:00 INFO Starting
2024-02-11 10:00:05 DEBUG Details
2024-02-11 10:00:10 WARN Warning message
2024-02-11 10:00:15 ERROR Error message
2024-02-11 10:00:20 INFO Complete
"""
        )

        handler = plugin_registry.load_plugin("logs", mock_plugin_context)
        metadata = handler.extract_metadata(log_file)

        assert metadata["source"] == "application"
        assert "log_levels" in metadata
        assert metadata["log_levels"]["INFO"] == 2
        assert metadata["log_levels"]["ERROR"] == 1
        assert metadata["log_levels"]["WARN"] == 1
        assert "time_range_start" in metadata
        assert "time_range_end" in metadata

    def test_log_plugin_custom_chunking(self, plugin_registry, mock_plugin_context, temp_dir):
        """Test that log plugin uses custom chunking strategy."""
        handler = plugin_registry.load_plugin("logs", mock_plugin_context)
        chunker = handler.get_chunking_strategy()

        assert chunker is not None
        # Verify it's the custom LogFileChunker
        assert type(chunker).__name__ == "LogFileChunker"
        assert hasattr(chunker, "chunk_window_minutes")
        assert hasattr(chunker, "max_entries_per_chunk")

    def test_log_plugin_chunks_by_time_windows(
        self, plugin_registry, mock_plugin_context, temp_dir
    ):
        """Test that log chunking groups entries by time windows."""
        log_file = temp_dir / "test.log"
        log_file.write_text(
            """2024-02-11 10:00:00 INFO Entry 1
2024-02-11 10:02:00 INFO Entry 2
2024-02-11 10:04:00 INFO Entry 3
2024-02-11 10:06:00 INFO Entry 4
2024-02-11 10:08:00 INFO Entry 5
"""
        )

        handler = plugin_registry.load_plugin("logs", mock_plugin_context)
        text = handler.extract_text(log_file)
        chunker = handler.get_chunking_strategy()

        chunks = chunker.chunk_text(text)

        # Should create multiple chunks based on 5-minute windows
        assert len(chunks) >= 2
        # Each chunk should have metadata with time ranges
        for chunk in chunks:
            assert "metadata" in chunk
            if "entry_count" in chunk["metadata"] and chunk["metadata"]["entry_count"] > 0:
                assert "time_range_start" in chunk["metadata"]
                assert "time_range_end" in chunk["metadata"]

    def test_log_plugin_handles_extensions(self, plugin_registry, mock_plugin_context):
        """Test that log plugin handles correct extensions."""
        handler = plugin_registry.load_plugin("logs", mock_plugin_context)
        assert handler.can_handle_file(Path("test.log"))
        assert not handler.can_handle_file(Path("test.txt"))
        assert not handler.can_handle_file(Path("test.md"))


class TestExamplePluginsCoexistence:
    """Test that both example plugins work together."""

    def test_both_plugins_load(self, plugin_registry, mock_plugin_context):
        """Test that both plugins can be loaded simultaneously."""
        md_handler = plugin_registry.load_plugin("markdown", mock_plugin_context)
        log_handler = plugin_registry.load_plugin("logs", mock_plugin_context)

        assert md_handler is not None
        assert log_handler is not None
        assert md_handler.name != log_handler.name

    def test_both_plugins_handle_different_extensions(self, plugin_registry, mock_plugin_context):
        """Test that plugins have distinct extension handling."""
        md_handler = plugin_registry.load_plugin("markdown", mock_plugin_context)
        log_handler = plugin_registry.load_plugin("logs", mock_plugin_context)

        assert md_handler.can_handle_file(Path("test.md"))
        assert not log_handler.can_handle_file(Path("test.md"))

        assert log_handler.can_handle_file(Path("test.log"))
        assert not md_handler.can_handle_file(Path("test.log"))

    def test_extension_resolution(self, plugin_registry):
        """Test that registry correctly maps extensions to plugins."""
        # Get extension mapping
        md_extensions = plugin_registry.get_plugins_by_extension(".md")
        log_extensions = plugin_registry.get_plugins_by_extension(".log")

        # Markdown file should map to markdown plugin
        assert any(p.name == "markdown" for p in md_extensions)

        # Log file should map to logs plugin
        assert any(p.name == "logs" for p in log_extensions)
