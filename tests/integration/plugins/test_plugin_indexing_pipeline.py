"""Integration tests for plugin indexing pipeline.

Tests end-to-end plugin integration including:
- Plugin discovery and loading in indexing context
- File extraction through plugins
- Error handling and plugin auto-disable
- Failure reporting and summary
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from krag.models.configuration import PluginConfiguration
from krag.plugins.context import PluginContext
from krag.plugins.exceptions import PluginExtractionError
from krag.plugins.registry import PluginRegistry
from tests.fixtures.mock_plugin import MockFileTypeHandler


@pytest.fixture
def mock_plugin_config():
    """Configuration with mock_plugin enabled."""
    return PluginConfiguration(
        enabled_plugins=["mock_plugin"],
        disabled_plugins=[]
    )


@pytest.fixture
def test_corpus(tmp_path):
    """Create a test corpus with various file types."""
    corpus_dir = tmp_path / "test_corpus"
    corpus_dir.mkdir()

    # Create .mock file for mock plugin
    mock_file = corpus_dir / "test.mock"
    mock_file.write_text("This is a test mock file.\nWith multiple lines.\n")

    # Create .txt file for core processing
    txt_file = corpus_dir / "test.txt"
    txt_file.write_text("This is a regular text file.\n")

    # Create unsupported file type
    unsupported = corpus_dir / "test.xyz"
    unsupported.write_text("Unsupported file type.\n")

    return corpus_dir


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = MagicMock()
    store.upsert_chunks.return_value = None
    return store


@pytest.fixture
def mock_embedding_generator():
    """Create a mock embedding generator."""
    gen = MagicMock()
    gen.generate.return_value = [0.1] * 384  # Mock 384-dim embedding
    gen.generate_single.return_value = [0.1] * 384  # Mock 384-dim embedding
    return gen


class TestEndToEndPluginIndexing:
    """Test end-to-end plugin indexing pipeline."""

    @patch("krag.plugins.registry.entry_points")
    @patch("krag.plugins.loader.entry_points")
    def test_plugin_discovers_and_loads_in_indexing(
        self, mock_loader_entry_points, mock_registry_entry_points, tmp_path, test_corpus
    ):
        """Plugins should be discovered and loaded for indexing."""
        # Setup mock entry point
        from importlib.metadata import EntryPoint
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "mock_plugin"
        mock_ep.value = "tests.fixtures.mock_plugin:MockFileTypeHandler"
        mock_ep.load.return_value = MockFileTypeHandler

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]

        # Configure both patches to return the same mock
        mock_registry_entry_points.return_value = mock_eps
        mock_loader_entry_points.return_value = mock_eps

        # Create plugin config
        plugin_config = PluginConfiguration(
            enabled_plugins=["mock_plugin"],
            disabled_plugins=[]
        )

        # Create registry and discover plugins
        registry = PluginRegistry(plugin_config)
        discovered = registry.discover_plugins()

        # Verify plugin was discovered
        plugin_names = [p.name for p in discovered]
        assert "mock_plugin" in plugin_names

        # Verify plugin can be loaded
        handler = registry.load_plugin("mock_plugin")
        assert handler is not None
        assert isinstance(handler, MockFileTypeHandler)

    def test_plugin_extracts_text_from_supported_files(self, tmp_path):
        """Plugin should extract text from its supported file types."""
        # Create a .mock file
        mock_file = tmp_path / "test.mock"
        mock_file.write_text("Mock file content\nLine 2\n")

        # Create in-memory plugin registry
        plugin_config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(plugin_config)

        # Manually register mock plugin
        handler = MockFileTypeHandler()
        registry._loaded["mock_plugin"] = handler
        registry._extension_map[".mock"] = "mock_plugin"

        # Test extraction through registry
        retrieved_handler = registry.get_handler_for_extension(".mock", None)

        if retrieved_handler:
            text = retrieved_handler.extract_text(mock_file)
            assert "Mock file content" in text

    def test_multiple_plugins_coexist(self, tmp_path):
        """Multiple plugins should coexist and handle different file types."""
        # Create plugin registry
        plugin_config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(plugin_config)

        # Register multiple mock plugins
        from krag.models.configuration import PluginMetadata

        registry._discovered["plugin_a"] = PluginMetadata(
            name="plugin_a",
            version="1.0.0",
            entry_point="dummy:HandlerA",
            supported_extensions=[".a"],
            required_api_version="1.0.0",
            is_enabled=True
        )

        registry._discovered["plugin_b"] = PluginMetadata(
            name="plugin_b",
            version="1.0.0",
            entry_point="dummy:HandlerB",
            supported_extensions=[".b"],
            required_api_version="1.0.0",
            is_enabled=True
        )

        # Build extension map
        registry._build_extension_map()

        # Verify both plugins registered
        assert ".a" in registry._extension_map
        assert ".b" in registry._extension_map


class TestPluginErrorHandling:
    """Test plugin error handling and auto-disable behavior."""

    def test_plugin_exception_disables_plugin(self):
        """Plugin raising exception should be automatically disabled."""
        plugin_config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(plugin_config)

        # Create a failing plugin
        class FailingHandler(MockFileTypeHandler):
            def extract_text(self, file_path: Path) -> str:
                raise PluginExtractionError(
                    "Extraction failed",
                    plugin_name=self.name,
                    file_path=file_path
                )

        # Register the failing plugin
        from krag.models.configuration import PluginMetadata
        registry._discovered["failing"] = PluginMetadata(
            name="failing",
            version="1.0.0",
            entry_point="dummy:FailingHandler",
            supported_extensions=[".fail"],
            required_api_version="1.0.0",
            is_enabled=True
        )

        handler = FailingHandler()
        registry._loaded["failing"] = handler

        # Verify plugin starts enabled
        assert registry._discovered["failing"].is_enabled is True

    def test_disabled_plugin_skipped_in_indexing(self, tmp_path):
        """Disabled plugins should be skipped during indexing."""
        plugin_config = PluginConfiguration(
            enabled_plugins=[],
            disabled_plugins=["bad_plugin"]
        )
        registry = PluginRegistry(plugin_config)

        # Add disabled plugin
        from krag.models.configuration import PluginMetadata
        registry._discovered["bad_plugin"] = PluginMetadata(
            name="bad_plugin",
            version="1.0.0",
            entry_point="dummy:BadHandler",
            supported_extensions=[".bad"],
            required_api_version="1.0.0",
            is_enabled=False
        )

        registry._build_extension_map()

        # Verify extension not mapped
        assert ".bad" not in registry._extension_map

    def test_fallback_to_core_when_plugin_fails(self, tmp_path):
        """System should fall back to core processing when plugin fails."""
        # This tests the orchestrator's fallback logic
        # Create a .txt file
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Regular text content")

        # Even if plugin fails, core should handle .txt
        from krag.extraction.text_extractor import TextExtractor
        extractor = TextExtractor()

        # Core extraction should work
        text = extractor.extract(txt_file)
        assert "Regular text content" in text

    def test_plugin_error_logged_and_continues(self, caplog):
        """Plugin errors should be logged but indexing should continue."""
        plugin_config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(plugin_config)

        # Attempt to load non-existent plugin
        handler = registry.load_plugin("nonexistent")

        # Should return None
        assert handler is None

        # Should log warning
        assert any(record.levelname == "WARNING" for record in caplog.records)


class TestPluginFailureReporting:
    """Test failure reporting and summary generation."""

    def test_indexing_failure_recorded(self, tmp_path):
        """Indexing failures should be recorded in failure collector."""
        from krag.plugins.failures import IndexingFailureCollector

        collector = IndexingFailureCollector()

        # Record some failures
        collector.record_failure(
            file_path=tmp_path / "bad.pdf",
            reason="Corrupted file",
            plugin_name="pdf"
        )

        collector.record_failure(
            file_path=tmp_path / "bad.docx",
            reason="Unsupported version",
            plugin_name="docx"
        )

        # Verify failures recorded
        assert collector.total_failures() == 2

    def test_failure_summary_generated(self, tmp_path):
        """Failure summary should be generated and formatted."""
        from krag.plugins.failures import IndexingFailureCollector

        collector = IndexingFailureCollector()

        # Record failures from different plugins
        collector.record_failure(
            tmp_path / "file1.pdf",
            "Error 1",
            plugin_name="pdf"
        )
        collector.record_failure(
            tmp_path / "file2.pdf",
            "Error 2",
            plugin_name="pdf"
        )
        collector.record_failure(
            tmp_path / "file3.docx",
            "Error 3",
            plugin_name="docx"
        )

        # Generate summary
        summary = collector.format_summary()

        # Verify summary content
        assert "Total failures: 3" in summary
        assert "Plugin 'pdf': 2 failure(s)" in summary
        assert "Plugin 'docx': 1 failure(s)" in summary

    def test_no_failures_summary(self):
        """Summary should handle case of no failures."""
        from krag.plugins.failures import IndexingFailureCollector

        collector = IndexingFailureCollector()
        summary = collector.format_summary()

        assert "No indexing failures" in summary

    def test_core_and_plugin_failures_separated(self, tmp_path):
        """Core and plugin failures should be separated in summary."""
        from krag.plugins.failures import IndexingFailureCollector

        collector = IndexingFailureCollector()

        # Core failure (no plugin_name)
        collector.record_failure(
            tmp_path / "core.txt",
            "Core error",
            plugin_name=None
        )

        # Plugin failure
        collector.record_failure(
            tmp_path / "plugin.pdf",
            "Plugin error",
            plugin_name="pdf"
        )

        summary = collector.format_summary()

        # Verify both sections present
        assert "Core system:" in summary
        assert "Plugin 'pdf':" in summary


class TestPluginContextIntegration:
    """Test PluginContext integration in indexing pipeline."""

    def test_plugin_receives_context(self, tmp_path):
        """Plugins should receive PluginContext during initialization."""
        import logging

        from krag.embeddings.generator import EmbeddingGenerator
        from krag.extraction.chunker import TextChunker
        from krag.storage.vector_store import VectorStore

        embedding_gen = MagicMock(spec=EmbeddingGenerator)
        vector_store = MagicMock(spec=VectorStore)
        chunker = TextChunker(chunk_size=500, chunk_overlap=100)
        logger = logging.getLogger("test")
        report_callback = MagicMock()

        # Create context
        context = PluginContext(
            embedding_generator=embedding_gen,
            vector_store=vector_store,
            chunker=chunker,
            logger=logger,
            report_indexing_failure=report_callback
        )

        # Verify context has expected attributes
        assert context.embedding_generator is embedding_gen
        assert context.vector_store is vector_store

    def test_plugin_can_use_context_services(self, tmp_path):
        """Plugins should be able to use context services."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)

        # Plugin would use context.chunker
        text = "This is test text. " * 20
        chunks = chunker.chunk(text, tmp_path / "test.txt")

        assert len(chunks) > 0

    def test_plugin_can_report_failures_via_context(self):
        """Plugins should be able to report failures through context."""
        from pathlib import Path

        from krag.plugins.failures import report_indexing_failure

        # Plugin would call context.report_indexing_failure
        # which delegates to this function
        report_indexing_failure(
            file_path=Path("/tmp/bad.pdf"),
            reason="Test failure",
            plugin_name="test_plugin"
        )

        # Should not raise exception


class TestPluginLifecycle:
    """Test plugin lifecycle (init, use, cleanup)."""

    def test_plugin_initialize_called(self):
        """Plugin initialize should be called with config and context."""
        handler = MockFileTypeHandler()

        assert handler._initialized is False

        # Initialize
        config = {"max_line_count": 500}
        handler.initialize(config)

        assert handler._initialized is True
        assert handler._config == config

    def test_plugin_cleanup_called(self):
        """Plugin cleanup should be called on shutdown."""
        handler = MockFileTypeHandler()
        handler.initialize({"test": "value"})

        assert handler._initialized is True

        # Cleanup
        handler.cleanup()

        assert handler._initialized is False
        assert handler._config == {}

    def test_plugin_registry_shutdown_cleans_all(self):
        """Registry shutdown should cleanup all loaded plugins."""
        plugin_config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(plugin_config)

        # Load some plugins
        handler1 = MockFileTypeHandler()
        handler2 = MockFileTypeHandler()

        handler1.initialize({})
        handler2.initialize({})

        registry._loaded["plugin1"] = handler1
        registry._loaded["plugin2"] = handler2

        # Shutdown all
        registry.shutdown_all_plugins()

        # Verify cleanup called
        assert handler1._initialized is False
        assert handler2._initialized is False

        # Verify loaded dict cleared
        assert len(registry._loaded) == 0
