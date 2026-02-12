"""Unit tests for PluginContext.

Tests PluginContext initialization, attribute access, and service availability.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from krag.embeddings.generator import EmbeddingGenerator
from krag.extraction.chunker import TextChunker
from krag.plugins.context import PluginContext
from krag.storage.vector_store import VectorStore


@pytest.fixture
def mock_embedding_generator():
    """Create a mock EmbeddingGenerator."""
    return MagicMock(spec=EmbeddingGenerator)


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore."""
    return MagicMock(spec=VectorStore)


@pytest.fixture
def mock_chunker():
    """Create a mock TextChunker."""
    return MagicMock(spec=TextChunker)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_report_callback():
    """Create a mock report_indexing_failure callback."""
    return MagicMock()


@pytest.fixture
def context(
    mock_embedding_generator, mock_vector_store, mock_chunker, mock_logger, mock_report_callback
):
    """Create a PluginContext with all mocks."""
    return PluginContext(
        embedding_generator=mock_embedding_generator,
        vector_store=mock_vector_store,
        chunker=mock_chunker,
        logger=mock_logger,
        report_indexing_failure=mock_report_callback,
    )


class TestContextInitialization:
    """Test PluginContext initialization."""

    def test_context_initializes_with_all_services(
        self,
        mock_embedding_generator,
        mock_vector_store,
        mock_chunker,
        mock_logger,
        mock_report_callback,
    ):
        """PluginContext should initialize with all provided services."""
        context = PluginContext(
            embedding_generator=mock_embedding_generator,
            vector_store=mock_vector_store,
            chunker=mock_chunker,
            logger=mock_logger,
            report_indexing_failure=mock_report_callback,
        )

        assert context.embedding_generator is mock_embedding_generator
        assert context.vector_store is mock_vector_store
        assert context.chunker is mock_chunker
        assert context.logger is mock_logger
        assert context.report_indexing_failure is mock_report_callback

    def test_context_stores_references_not_copies(
        self,
        mock_embedding_generator,
        mock_vector_store,
        mock_chunker,
        mock_logger,
        mock_report_callback,
    ):
        """PluginContext should store references to services, not copies."""
        context = PluginContext(
            embedding_generator=mock_embedding_generator,
            vector_store=mock_vector_store,
            chunker=mock_chunker,
            logger=mock_logger,
            report_indexing_failure=mock_report_callback,
        )

        # Verify references are identical
        assert context.embedding_generator is mock_embedding_generator
        assert context.vector_store is mock_vector_store


class TestAttributeAccess:
    """Test attribute access on PluginContext."""

    def test_can_access_embedding_generator(self, context):
        """Plugins should be able to access embedding_generator."""
        generator = context.embedding_generator

        assert generator is not None

    def test_can_access_vector_store(self, context):
        """Plugins should be able to access vector_store."""
        store = context.vector_store

        assert store is not None

    def test_can_access_chunker(self, context):
        """Plugins should be able to access chunker."""
        chunker = context.chunker

        assert chunker is not None
        assert hasattr(chunker, "chunk")

    def test_can_access_logger(self, context):
        """Plugins should be able to access logger."""
        logger = context.logger

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_can_access_report_callback(self, context):
        """Plugins should be able to access report_indexing_failure callback."""
        callback = context.report_indexing_failure

        assert callback is not None
        assert callable(callback)


class TestServiceUsage:
    """Test using services through PluginContext."""

    def test_can_call_embedding_generator(self, context, mock_embedding_generator):
        """Plugins should be able to call embedding generator through context."""
        mock_embedding_generator.generate_single.return_value = [0.1, 0.2, 0.3]

        result = context.embedding_generator.generate_single("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_embedding_generator.generate_single.assert_called_once_with("test text")

    def test_can_call_chunker(self, context, mock_chunker):
        """Plugins should be able to call chunker through context."""
        mock_chunk = MagicMock()
        mock_chunker.chunk.return_value = [mock_chunk]

        result = context.chunker.chunk("test text", Path("/tmp/test.txt"))

        assert len(result) == 1
        mock_chunker.chunk.assert_called_once()

    def test_can_call_logger(self, context, mock_logger):
        """Plugins should be able to log messages through context."""
        context.logger.info("Test message")
        context.logger.warning("Warning message")
        context.logger.error("Error message")

        mock_logger.info.assert_called_once_with("Test message")
        mock_logger.warning.assert_called_once_with("Warning message")
        mock_logger.error.assert_called_once_with("Error message")

    def test_can_call_report_callback(self, context, mock_report_callback):
        """Plugins should be able to report failures through context."""
        test_path = Path("/tmp/failed.txt")
        error_msg = "File is corrupted"

        context.report_indexing_failure(test_path, error_msg)

        mock_report_callback.assert_called_once_with(test_path, error_msg)


class TestRealInstanceCompatibility:
    """Test compatibility with real service instances."""

    def test_context_works_with_real_logger(
        self, mock_embedding_generator, mock_vector_store, mock_chunker, mock_report_callback
    ):
        """PluginContext should work with real logger instance."""
        real_logger = logging.getLogger("test_plugin")

        context = PluginContext(
            embedding_generator=mock_embedding_generator,
            vector_store=mock_vector_store,
            chunker=mock_chunker,
            logger=real_logger,
            report_indexing_failure=mock_report_callback,
        )

        # Should be able to use real logger
        assert context.logger is real_logger
        # Should not raise exception
        context.logger.info("Test message")

    def test_context_works_with_real_chunker(
        self, mock_embedding_generator, mock_vector_store, mock_logger, mock_report_callback
    ):
        """PluginContext should work with real TextChunker instance."""
        real_chunker = TextChunker(chunk_size=500, chunk_overlap=100)

        context = PluginContext(
            embedding_generator=mock_embedding_generator,
            vector_store=mock_vector_store,
            chunker=real_chunker,
            logger=mock_logger,
            report_indexing_failure=mock_report_callback,
        )

        assert context.chunker is real_chunker
        assert context.chunker.chunk_size == 500


class TestContextImmutability:
    """Test that context attributes can be reassigned (no immutability enforced)."""

    def test_can_reassign_attributes(self, context):
        """Context attributes are not immutable (by design for flexibility)."""
        new_logger = MagicMock(spec=logging.Logger)

        # Should be able to reassign
        context.logger = new_logger

        assert context.logger is new_logger

    def test_can_add_custom_attributes(self, context):
        """Plugins can add custom attributes to context (Python allows it)."""
        # This is allowed but not recommended
        context.custom_data = "test"

        assert hasattr(context, "custom_data")
        assert context.custom_data == "test"


class TestContextInPluginScenario:
    """Test context usage in realistic plugin scenarios."""

    def test_plugin_can_use_context_for_extraction(self, context, mock_chunker):
        """Plugin should be able to use context services during extraction."""
        mock_chunk = MagicMock()
        mock_chunk.text = "chunk text"
        mock_chunker.chunk.return_value = [mock_chunk]

        # Simulate plugin using context
        text = "Extracted text content"
        chunks = context.chunker.chunk(text, Path("/tmp/file.txt"))

        assert len(chunks) == 1
        assert chunks[0].text == "chunk text"

    def test_plugin_can_report_failures(self, context, mock_report_callback):
        """Plugin should be able to report indexing failures."""
        failed_file = Path("/tmp/corrupted.pdf")
        error_message = "PDF structure is invalid"

        context.report_indexing_failure(failed_file, error_message)

        mock_report_callback.assert_called_once_with(failed_file, error_message)

    def test_plugin_can_log_progress(self, context, mock_logger):
        """Plugin should be able to log progress during operation."""
        context.logger.info("Starting extraction")
        context.logger.debug("Processing page 1")
        context.logger.info("Extraction complete")

        assert mock_logger.info.call_count == 2
        assert mock_logger.debug.call_count == 1


class TestContextLifecycle:
    """Test context lifecycle and cleanup."""

    def test_context_survives_service_method_calls(self, context, mock_chunker):
        """Context should remain valid after service method calls."""
        mock_chunker.chunk.return_value = []

        # Call service multiple times
        context.chunker.chunk("text1", Path("/tmp/file1.txt"))
        context.chunker.chunk("text2", Path("/tmp/file2.txt"))

        # Context should still be valid
        assert context.chunker is mock_chunker
        assert mock_chunker.chunk.call_count == 2

    def test_context_cleanup_not_automatic(self, context):
        """Context does not automatically clean up (plugin responsibility)."""
        # Context doesn't implement cleanup - it's just a data holder
        assert not hasattr(context, "cleanup")
        assert not hasattr(context, "__del__")
