"""Unit tests for PluginLoader.

Tests plugin class loading, instantiation, API compatibility checking,
initialization, and cleanup.
"""

from importlib.metadata import EntryPoint
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from krag.plugins.context import PluginContext
from krag.plugins.exceptions import (
    PluginAPIVersionError,
    PluginDependencyError,
    PluginLoadError,
)
from krag.plugins.interfaces import FileTypeHandler
from krag.plugins.loader import PluginLoader, _parse_semver
from tests.fixtures.mock_plugin import MockFileTypeHandler


@pytest.fixture
def loader():
    """Create a PluginLoader instance."""
    return PluginLoader(api_version="1.0.0")


@pytest.fixture
def plugin_context(tmp_path):
    """Create a PluginContext for testing."""
    import logging

    from krag.embeddings.generator import EmbeddingGenerator
    from krag.extraction.chunker import TextChunker
    from krag.storage.vector_store import VectorStore

    embedding_gen = MagicMock(spec=EmbeddingGenerator)
    vector_store = MagicMock(spec=VectorStore)
    chunker = TextChunker(chunk_size=1000, chunk_overlap=200)
    logger = logging.getLogger("test")
    report_callback = MagicMock()

    return PluginContext(
        embedding_generator=embedding_gen,
        vector_store=vector_store,
        chunker=chunker,
        logger=logger,
        report_indexing_failure=report_callback,
    )


class TestSemverParsing:
    """Test semantic version parsing."""

    def test_parse_semver_valid_version(self):
        """_parse_semver should parse valid semver strings."""
        major, minor, patch = _parse_semver("1.2.3")

        assert major == 1
        assert minor == 2
        assert patch == 3

    def test_parse_semver_strips_prerelease(self):
        """_parse_semver should strip pre-release identifiers."""
        major, minor, patch = _parse_semver("2.0.0-beta.1")

        assert major == 2
        assert minor == 0
        assert patch == 0

    def test_parse_semver_strips_build_metadata(self):
        """_parse_semver should strip build metadata."""
        major, minor, patch = _parse_semver("1.5.2+build.123")

        assert major == 1
        assert minor == 5
        assert patch == 2

    def test_parse_semver_invalid_format_raises_error(self):
        """_parse_semver should raise ValueError for invalid format."""
        with pytest.raises(ValueError) as exc_info:
            _parse_semver("1")

        assert "Invalid semver format" in str(exc_info.value)

    def test_parse_semver_two_part_version(self):
        """_parse_semver should accept two-part versions like '1.0'."""
        major, minor, patch = _parse_semver("1.2")

        assert major == 1
        assert minor == 2
        assert patch == 0

    def test_parse_semver_non_numeric_raises_error(self):
        """_parse_semver should raise ValueError for non-numeric versions."""
        with pytest.raises(ValueError) as exc_info:
            _parse_semver("1.a.3")

        assert "Invalid semver format" in str(exc_info.value)


class TestLoaderInitialization:
    """Test PluginLoader initialization."""

    def test_loader_initializes_with_api_version(self):
        """PluginLoader should initialize with provided API version."""
        loader = PluginLoader(api_version="1.2.3")

        assert loader._api_version == "1.2.3"
        assert loader._api_major == 1

    def test_loader_parses_api_version(self):
        """PluginLoader should parse major version from API version."""
        loader = PluginLoader(api_version="2.5.1")

        assert loader._api_major == 2


class TestAPICompatibility:
    """Test API version compatibility checking."""

    def test_check_api_compatibility_accepts_same_major(self, loader):
        """check_api_compatibility should accept same major version."""
        # Should not raise exception
        loader.check_api_compatibility("1.5.0", "test_plugin")
        loader.check_api_compatibility("1.0.0", "test_plugin")
        loader.check_api_compatibility("1.99.99", "test_plugin")

    def test_check_api_compatibility_rejects_different_major(self, loader):
        """check_api_compatibility should reject different major version."""
        with pytest.raises(PluginAPIVersionError) as exc_info:
            loader.check_api_compatibility("2.0.0", "test_plugin")

        assert "test_plugin" in str(exc_info.value)
        assert "incompatible" in str(exc_info.value).lower()

    def test_check_api_compatibility_handles_invalid_version(self, loader):
        """check_api_compatibility should raise error for invalid version format."""
        with pytest.raises(PluginAPIVersionError) as exc_info:
            loader.check_api_compatibility("invalid", "test_plugin")

        assert "invalid" in str(exc_info.value).lower()
        assert "test_plugin" in str(exc_info.value)

    def test_check_api_compatibility_accepts_prerelease(self, loader):
        """check_api_compatibility should accept pre-release versions with same major."""
        # Should not raise exception
        loader.check_api_compatibility("1.0.0-alpha", "test_plugin")
        loader.check_api_compatibility("1.5.0-beta.2", "test_plugin")


class TestPluginClassLoading:
    """Test plugin class loading from entry points."""

    @patch("krag.plugins.loader.entry_points")
    def test_load_plugin_class_finds_entry_point(self, mock_entry_points, loader):
        """load_plugin_class should find and load plugin from entry point."""
        # Create mock entry point
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "mock_plugin"
        mock_ep.value = "tests.fixtures.mock_plugin:MockFileTypeHandler"
        mock_ep.load.return_value = MockFileTypeHandler

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps

        handler_class = loader.load_plugin_class("mock_plugin")

        assert handler_class == MockFileTypeHandler
        mock_ep.load.assert_called_once()

    @patch("krag.plugins.loader.entry_points")
    def test_load_plugin_class_handles_legacy_api(self, mock_entry_points, loader):
        """load_plugin_class should handle legacy entry_points API."""
        # Create mock entry point
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "mock_plugin"
        mock_ep.value = "tests.fixtures.mock_plugin:MockFileTypeHandler"
        mock_ep.load.return_value = MockFileTypeHandler

        mock_eps = {"krag.plugins": [mock_ep]}
        mock_entry_points.return_value = mock_eps

        handler_class = loader.load_plugin_class("mock_plugin")

        assert handler_class == MockFileTypeHandler

    @patch("krag.plugins.loader.entry_points")
    def test_load_plugin_class_raises_for_missing_plugin(self, mock_entry_points, loader):
        """load_plugin_class should raise PluginLoadError for missing plugin."""
        mock_eps = MagicMock()
        mock_eps.select.return_value = []
        mock_entry_points.return_value = mock_eps

        with pytest.raises(PluginLoadError) as exc_info:
            loader.load_plugin_class("nonexistent")

        assert "No entry point found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    @patch("krag.plugins.loader.entry_points")
    def test_load_plugin_class_validates_handler_subclass(self, mock_entry_points, loader):
        """load_plugin_class should validate that loaded class is FileTypeHandler subclass."""

        # Create mock entry point that loads wrong class
        class NotAHandler:
            pass

        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "bad_plugin"
        mock_ep.value = "nonexistent.module:NotAHandler"
        mock_ep.load.return_value = NotAHandler

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps

        with pytest.raises(PluginLoadError) as exc_info:
            loader.load_plugin_class("bad_plugin")

        assert "does not point to a FileTypeHandler subclass" in str(exc_info.value)

    @patch("krag.plugins.loader.entry_points")
    def test_load_plugin_class_handles_import_error(self, mock_entry_points, loader):
        """load_plugin_class should handle ImportError for missing modules."""
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "missing_deps"
        mock_ep.value = "nonexistent_package.module:Handler"
        mock_ep.load.side_effect = ImportError("No module named 'nonexistent_package'")

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps

        with pytest.raises(PluginDependencyError) as exc_info:
            loader.load_plugin_class("missing_deps")

        assert "missing dependencies" in str(exc_info.value).lower()
        assert "missing_deps" in str(exc_info.value)

    @patch("krag.plugins.loader.entry_points")
    def test_load_plugin_class_handles_general_import_error(self, mock_entry_points, loader):
        """load_plugin_class should handle general ImportError as PluginLoadError."""
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "broken_import"
        mock_ep.value = "broken.module:Handler"
        mock_ep.load.side_effect = ImportError("Syntax error in module")

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps

        with pytest.raises(PluginLoadError) as exc_info:
            loader.load_plugin_class("broken_import")

        assert "Failed to import" in str(exc_info.value)

    @patch("krag.plugins.loader.entry_points")
    def test_load_plugin_class_handles_unexpected_errors(self, mock_entry_points, loader):
        """load_plugin_class should handle unexpected errors gracefully."""
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "bad_plugin"
        mock_ep.value = "dummy.module:Handler"
        mock_ep.load.side_effect = RuntimeError("Unexpected error")

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps

        with pytest.raises(PluginLoadError) as exc_info:
            loader.load_plugin_class("bad_plugin")

        assert "Unexpected error" in str(exc_info.value)


class TestPluginInstantiation:
    """Test plugin handler instantiation."""

    def test_instantiate_plugin_creates_instance(self, loader):
        """instantiate_plugin should create handler instance."""
        handler = loader.instantiate_plugin(MockFileTypeHandler)

        assert isinstance(handler, MockFileTypeHandler)
        assert handler.name == "mock_plugin"

    def test_instantiate_plugin_handles_instantiation_errors(self, loader):
        """instantiate_plugin should handle errors during instantiation."""

        class BadHandler(FileTypeHandler):
            def __init__(self):
                raise ValueError("Cannot instantiate")

            @property
            def name(self) -> str:
                return "bad"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

        with pytest.raises(PluginLoadError) as exc_info:
            loader.instantiate_plugin(BadHandler)

        assert "Failed to instantiate" in str(exc_info.value)


class TestPluginInitialization:
    """Test plugin initialization with configuration."""

    def test_initialize_plugin_calls_initialize(self, loader, plugin_context):
        """initialize_plugin should call handler's initialize method."""
        handler = MockFileTypeHandler()
        config = {"max_line_count": 500}

        loader.initialize_plugin(handler, config, plugin_context)

        assert handler._initialized is True
        assert handler._config == config

    def test_initialize_plugin_passes_context_if_supported(self, loader, plugin_context):
        """initialize_plugin should pass context to initialize if parameter exists."""
        handler = MockFileTypeHandler()
        config = {}

        # Mock plugin has context parameter
        loader.initialize_plugin(handler, config, plugin_context)

        # Should not raise exception
        assert handler._initialized is True

    def test_initialize_plugin_works_without_context_parameter(self, loader):
        """initialize_plugin should work with plugins that don't accept context."""

        class SimpleHandler(FileTypeHandler):
            def __init__(self):
                self.initialized = False
                self.config = {}

            def initialize(self, config):
                """Initialize without context parameter."""
                self.initialized = True
                self.config = config

            @property
            def name(self) -> str:
                return "simple"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".simple"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict:
                return {}

        handler = SimpleHandler()
        config = {"key": "value"}

        loader.initialize_plugin(handler, config, None)

        assert handler.initialized is True
        assert handler.config == config

    def test_initialize_plugin_handles_initialization_errors(self, loader, plugin_context):
        """initialize_plugin should handle errors during initialization."""

        class FailingHandler(FileTypeHandler):
            def __init__(self):
                pass

            def initialize(self, config, context=None):
                raise RuntimeError("Initialization failed")

            @property
            def name(self) -> str:
                return "failing"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".fail"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict:
                return {}

        handler = FailingHandler()

        with pytest.raises(PluginLoadError) as exc_info:
            loader.initialize_plugin(handler, {}, plugin_context)

        assert "Failed to initialize" in str(exc_info.value)
        assert "failing" in str(exc_info.value)


class TestPluginCleanup:
    """Test plugin cleanup and resource management."""

    def test_cleanup_plugin_calls_cleanup(self, loader):
        """cleanup_plugin should call handler's cleanup method."""
        handler = MockFileTypeHandler()
        handler._initialized = True
        handler._config = {"test": "value"}

        loader.cleanup_plugin(handler)

        assert handler._initialized is False
        assert handler._config == {}

    def test_cleanup_plugin_handles_errors_gracefully(self, loader):
        """cleanup_plugin should not raise exceptions on cleanup errors."""

        class FailingCleanupHandler(FileTypeHandler):
            def __init__(self):
                pass

            def cleanup(self):
                raise RuntimeError("Cleanup failed")

            @property
            def name(self) -> str:
                return "failing_cleanup"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".fail"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict:
                return {}

        handler = FailingCleanupHandler()

        # Should not raise exception
        loader.cleanup_plugin(handler)

    def test_cleanup_plugin_logs_errors(self, loader, caplog):
        """cleanup_plugin should log errors during cleanup."""

        class FailingCleanupHandler(FileTypeHandler):
            def __init__(self):
                pass

            def cleanup(self):
                raise RuntimeError("Cleanup failed")

            @property
            def name(self) -> str:
                return "failing_cleanup"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".fail"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict:
                return {}

        handler = FailingCleanupHandler()

        loader.cleanup_plugin(handler)

        # Check that error was logged
        assert any("Error during cleanup" in record.message for record in caplog.records)
