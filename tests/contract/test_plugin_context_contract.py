"""Contract tests for PluginContext API.

Verifies that PluginContext provides the required interface for plugins to
access krag's core services.
"""

import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

from krag.embeddings.generator import EmbeddingGenerator
from krag.extraction.chunker import TextChunker
from krag.plugins.context import PluginContext
from krag.storage.vector_store import VectorStore


@pytest.fixture
def mock_embedding_generator() -> Mock:
    """Create a mock embedding generator."""
    return Mock(spec=EmbeddingGenerator)


@pytest.fixture
def mock_vector_store() -> Mock:
    """Create a mock vector store."""
    return Mock(spec=VectorStore)


@pytest.fixture
def mock_chunker() -> Mock:
    """Create a mock text chunker."""
    return Mock(spec=TextChunker)


@pytest.fixture
def mock_logger() -> Mock:
    """Create a mock logger."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def mock_failure_callback() -> Mock:
    """Create a mock failure reporting callback."""
    return Mock()


@pytest.fixture
def plugin_context(
    mock_embedding_generator: Mock,
    mock_vector_store: Mock,
    mock_chunker: Mock,
    mock_logger: Mock,
    mock_failure_callback: Mock,
) -> PluginContext:
    """Create a PluginContext with all mocked dependencies."""
    return PluginContext(
        embedding_generator=mock_embedding_generator,
        vector_store=mock_vector_store,
        chunker=mock_chunker,
        logger=mock_logger,
        report_indexing_failure=mock_failure_callback,
    )


class TestPluginContextContract:
    """Contract tests for PluginContext API."""

    def test_context_has_embedding_generator(self, plugin_context: PluginContext) -> None:
        """Verify context provides embedding_generator attribute."""
        assert hasattr(plugin_context, "embedding_generator")
        assert plugin_context.embedding_generator is not None

    def test_context_has_vector_store(self, plugin_context: PluginContext) -> None:
        """Verify context provides vector_store attribute."""
        assert hasattr(plugin_context, "vector_store")
        assert plugin_context.vector_store is not None

    def test_context_has_chunker(self, plugin_context: PluginContext) -> None:
        """Verify context provides chunker attribute."""
        assert hasattr(plugin_context, "chunker")
        assert plugin_context.chunker is not None

    def test_context_has_logger(self, plugin_context: PluginContext) -> None:
        """Verify context provides logger attribute."""
        assert hasattr(plugin_context, "logger")
        assert plugin_context.logger is not None

    def test_context_has_report_indexing_failure(self, plugin_context: PluginContext) -> None:
        """Verify context provides report_indexing_failure callback."""
        assert hasattr(plugin_context, "report_indexing_failure")
        assert callable(plugin_context.report_indexing_failure)

    def test_report_indexing_failure_callable(
        self, plugin_context: PluginContext, mock_failure_callback: Mock
    ) -> None:
        """Verify report_indexing_failure can be called with file_path and reason."""
        test_path = Path("/test/file.txt")
        test_reason = "Test failure reason"

        plugin_context.report_indexing_failure(test_path, test_reason)

        mock_failure_callback.assert_called_once_with(test_path, test_reason)

    def test_context_initialization(
        self,
        mock_embedding_generator: Mock,
        mock_vector_store: Mock,
        mock_chunker: Mock,
        mock_logger: Mock,
        mock_failure_callback: Mock,
    ) -> None:
        """Verify PluginContext can be constructed with all required arguments."""
        context = PluginContext(
            embedding_generator=mock_embedding_generator,
            vector_store=mock_vector_store,
            chunker=mock_chunker,
            logger=mock_logger,
            report_indexing_failure=mock_failure_callback,
        )

        assert context.embedding_generator is mock_embedding_generator
        assert context.vector_store is mock_vector_store
        assert context.chunker is mock_chunker
        assert context.logger is mock_logger
        assert context.report_indexing_failure is mock_failure_callback
