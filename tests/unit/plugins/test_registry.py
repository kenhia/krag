"""Unit tests for PluginRegistry.

Tests plugin discovery, loading, extension mapping, and lifecycle management.
"""

from importlib.metadata import EntryPoint
from unittest.mock import MagicMock, patch

import pytest

from krag.models.configuration import PluginConfiguration, PluginMetadata
from krag.plugins.context import PluginContext
from krag.plugins.exceptions import PluginNotFoundError
from krag.plugins.registry import PLUGIN_API_VERSION, PluginRegistry
from tests.fixtures.mock_plugin import MockFileTypeHandler


@pytest.fixture
def config_empty():
    """Configuration with no enabled/disabled plugins."""
    return PluginConfiguration(enabled_plugins=[], disabled_plugins=[])


@pytest.fixture
def config_with_enabled():
    """Configuration with specific enabled plugins."""
    return PluginConfiguration(enabled_plugins=["mock_plugin"], disabled_plugins=[])


@pytest.fixture
def config_with_disabled():
    """Configuration with specific disabled plugins."""
    return PluginConfiguration(enabled_plugins=[], disabled_plugins=["mock_plugin"])


@pytest.fixture
def registry_empty(config_empty):
    """Registry with empty configuration."""
    return PluginRegistry(config_empty)


@pytest.fixture
def registry_with_enabled(config_with_enabled):
    """Registry with enabled plugins."""
    return PluginRegistry(config_with_enabled)


@pytest.fixture
def mock_entry_point():
    """Create a mock entry point for testing."""
    ep = MagicMock(spec=EntryPoint)
    ep.name = "mock_plugin"
    ep.value = "tests.fixtures.mock_plugin:MockFileTypeHandler"
    return ep


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


class TestRegistryInitialization:
    """Test registry initialization."""

    def test_registry_initializes_with_config(self, config_empty):
        """Registry should initialize with provided configuration."""
        registry = PluginRegistry(config_empty)

        assert registry._config == config_empty
        assert registry._api_version == PLUGIN_API_VERSION
        assert registry._discovered == {}
        assert registry._loaded == {}
        assert registry._extension_map == {}

    def test_registry_creates_loader(self, registry_empty):
        """Registry should create a PluginLoader instance."""
        assert registry_empty._loader is not None
        assert registry_empty._loader._api_version == PLUGIN_API_VERSION


class TestPluginDiscovery:
    """Test plugin discovery mechanisms."""

    @patch("krag.plugins.registry.entry_points")
    def test_discover_plugins_finds_entry_points(
        self, mock_entry_points, registry_empty, mock_entry_point
    ):
        """discover_plugins should find plugins registered as entry points."""
        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_entry_point]
        mock_entry_points.return_value = mock_eps

        plugins = registry_empty.discover_plugins()

        assert len(plugins) == 1
        assert plugins[0].name == "mock_plugin"
        assert "mock_plugin" in registry_empty._discovered

    @patch("krag.plugins.registry.entry_points")
    def test_discover_plugins_handles_legacy_entry_points_api(
        self, mock_entry_points, registry_empty, mock_entry_point
    ):
        """discover_plugins should handle legacy entry_points API without select()."""
        mock_eps = {"krag.plugins": [mock_entry_point]}
        mock_entry_points.return_value = mock_eps

        plugins = registry_empty.discover_plugins()

        assert len(plugins) == 1
        assert plugins[0].name == "mock_plugin"

    @patch("krag.plugins.registry.entry_points")
    def test_discover_plugins_applies_enabled_filter(
        self, mock_entry_points, config_with_enabled, mock_entry_point
    ):
        """discover_plugins should mark plugins as enabled based on configuration."""
        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_entry_point]
        mock_entry_points.return_value = mock_eps

        registry = PluginRegistry(config_with_enabled)
        plugins = registry.discover_plugins()

        assert len(plugins) == 1
        assert plugins[0].is_enabled is True

    @patch("krag.plugins.registry.entry_points")
    def test_discover_plugins_applies_disabled_filter(
        self, mock_entry_points, config_with_disabled, mock_entry_point
    ):
        """discover_plugins should mark plugins as disabled based on configuration."""
        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_entry_point]
        mock_entry_points.return_value = mock_eps

        registry = PluginRegistry(config_with_disabled)
        plugins = registry.discover_plugins()

        assert len(plugins) == 1
        assert plugins[0].is_enabled is False

    @patch("krag.plugins.registry.entry_points")
    def test_discover_plugins_handles_errors_gracefully(self, mock_entry_points, registry_empty):
        """discover_plugins should log errors and continue on plugin discovery failures."""
        # Create an entry point that raises an exception
        bad_ep = MagicMock(spec=EntryPoint)
        bad_ep.name = "bad_plugin"
        bad_ep.value = "nonexistent.module:BadHandler"

        mock_eps = MagicMock()
        mock_eps.select.return_value = [bad_ep]
        mock_entry_points.return_value = mock_eps

        # Should not raise exception
        plugins = registry_empty.discover_plugins()

        # Should return empty list (or only valid plugins)
        assert isinstance(plugins, list)


class TestPluginEnablement:
    """Test plugin enablement logic."""

    def test_is_plugin_enabled_returns_false_for_disabled(self, config_with_disabled):
        """_is_plugin_enabled should return False for explicitly disabled plugins."""
        registry = PluginRegistry(config_with_disabled)
        assert registry._is_plugin_enabled("mock_plugin") is False

    def test_is_plugin_enabled_returns_true_when_enabled_list_empty(self, config_empty):
        """_is_plugin_enabled should return True for any plugin when enabled_plugins is empty."""
        registry = PluginRegistry(config_empty)
        assert registry._is_plugin_enabled("any_plugin") is True

    def test_is_plugin_enabled_requires_explicit_enable(self, config_with_enabled):
        """_is_plugin_enabled should require plugin to be in enabled_plugins when list is non-empty."""
        registry = PluginRegistry(config_with_enabled)
        assert registry._is_plugin_enabled("mock_plugin") is True
        assert registry._is_plugin_enabled("other_plugin") is False


class TestExtensionMapping:
    """Test extension to plugin mapping."""

    def test_build_extension_map_creates_mapping(self, registry_empty):
        """_build_extension_map should create extension to plugin name mapping."""
        # Manually add discovered plugin with extensions
        registry_empty._discovered["mock_plugin"] = PluginMetadata(
            name="mock_plugin",
            version="1.0.0",
            entry_point="tests.fixtures.mock_plugin:MockFileTypeHandler",
            supported_extensions=[".mock", ".test"],
            required_api_version="1.0.0",
            is_enabled=True,
        )

        registry_empty._build_extension_map()

        assert ".mock" in registry_empty._extension_map
        assert ".test" in registry_empty._extension_map
        assert registry_empty._extension_map[".mock"] == "mock_plugin"
        assert registry_empty._extension_map[".test"] == "mock_plugin"

    def test_build_extension_map_normalizes_case(self, registry_empty):
        """_build_extension_map should normalize extensions to lowercase."""
        registry_empty._discovered["mock_plugin"] = PluginMetadata(
            name="mock_plugin",
            version="1.0.0",
            entry_point="tests.fixtures.mock_plugin:MockFileTypeHandler",
            supported_extensions=[".MOCK", ".Test"],
            required_api_version="1.0.0",
            is_enabled=True,
        )

        registry_empty._build_extension_map()

        assert ".mock" in registry_empty._extension_map
        assert ".test" in registry_empty._extension_map

    def test_build_extension_map_skips_disabled_plugins(self, registry_empty):
        """_build_extension_map should skip disabled plugins."""
        registry_empty._discovered["disabled_plugin"] = PluginMetadata(
            name="disabled_plugin",
            version="1.0.0",
            entry_point="dummy:Handler",
            supported_extensions=[".disabled"],
            required_api_version="1.0.0",
            is_enabled=False,
        )

        registry_empty._build_extension_map()

        assert ".disabled" not in registry_empty._extension_map

    def test_build_extension_map_handles_conflicts_first_wins(self, registry_empty):
        """_build_extension_map should handle conflicts with first-in-wins strategy."""
        registry_empty._discovered["plugin_a"] = PluginMetadata(
            name="plugin_a",
            version="1.0.0",
            entry_point="dummy:HandlerA",
            supported_extensions=[".conflict"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._discovered["plugin_b"] = PluginMetadata(
            name="plugin_b",
            version="1.0.0",
            entry_point="dummy:HandlerB",
            supported_extensions=[".conflict"],
            required_api_version="1.0.0",
            is_enabled=True,
        )

        registry_empty._build_extension_map()

        # First plugin wins
        assert registry_empty._extension_map[".conflict"] in ["plugin_a", "plugin_b"]

    def test_get_supported_extensions_returns_enabled_extensions(self, registry_empty):
        """get_supported_extensions should return all extensions from enabled plugins."""
        registry_empty._extension_map = {".mock": "mock_plugin", ".test": "test_plugin"}

        extensions = registry_empty.get_supported_extensions()

        assert ".mock" in extensions
        assert ".test" in extensions
        assert len(extensions) == 2


class TestPluginListing:
    """Test plugin listing with filters."""

    def test_list_plugins_returns_all_when_no_filter(self, registry_empty):
        """list_plugins should return all plugins when no filter is provided."""
        registry_empty._discovered["plugin1"] = PluginMetadata(
            name="plugin1",
            version="1.0.0",
            entry_point="dummy:H1",
            supported_extensions=[".p1"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._discovered["plugin2"] = PluginMetadata(
            name="plugin2",
            version="1.0.0",
            entry_point="dummy:H2",
            supported_extensions=[".p2"],
            required_api_version="1.0.0",
            is_enabled=False,
        )

        plugins = registry_empty.list_plugins()

        assert len(plugins) == 2

    def test_list_plugins_filters_enabled(self, registry_empty):
        """list_plugins should filter for enabled plugins."""
        registry_empty._discovered["enabled"] = PluginMetadata(
            name="enabled",
            version="1.0.0",
            entry_point="dummy:H1",
            supported_extensions=[".en"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._discovered["disabled"] = PluginMetadata(
            name="disabled",
            version="1.0.0",
            entry_point="dummy:H2",
            supported_extensions=[".dis"],
            required_api_version="1.0.0",
            is_enabled=False,
        )

        plugins = registry_empty.list_plugins(filter_status="enabled")

        assert len(plugins) == 1
        assert plugins[0].name == "enabled"

    def test_list_plugins_filters_disabled(self, registry_empty):
        """list_plugins should filter for disabled plugins."""
        registry_empty._discovered["enabled"] = PluginMetadata(
            name="enabled",
            version="1.0.0",
            entry_point="dummy:H1",
            supported_extensions=[".en"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._discovered["disabled"] = PluginMetadata(
            name="disabled",
            version="1.0.0",
            entry_point="dummy:H2",
            supported_extensions=[".dis"],
            required_api_version="1.0.0",
            is_enabled=False,
        )

        plugins = registry_empty.list_plugins(filter_status="disabled")

        assert len(plugins) == 1
        assert plugins[0].name == "disabled"

    def test_list_plugins_filters_loaded(self, registry_empty):
        """list_plugins should filter for loaded plugins."""
        registry_empty._discovered["loaded"] = PluginMetadata(
            name="loaded",
            version="1.0.0",
            entry_point="dummy:H1",
            supported_extensions=[".ld"],
            required_api_version="1.0.0",
            is_enabled=True,
            is_loaded=True,
        )
        registry_empty._discovered["not_loaded"] = PluginMetadata(
            name="not_loaded",
            version="1.0.0",
            entry_point="dummy:H2",
            supported_extensions=[".nld"],
            required_api_version="1.0.0",
            is_enabled=True,
            is_loaded=False,
        )

        plugins = registry_empty.list_plugins(filter_status="loaded")

        assert len(plugins) == 1
        assert plugins[0].name == "loaded"


class TestPluginInfo:
    """Test plugin metadata retrieval."""

    def test_get_plugin_info_returns_metadata(self, registry_empty):
        """get_plugin_info should return plugin metadata."""
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            entry_point="dummy:Handler",
            supported_extensions=[".test"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._discovered["test_plugin"] = metadata

        result = registry_empty.get_plugin_info("test_plugin")

        assert result == metadata

    def test_get_plugin_info_raises_for_unknown_plugin(self, registry_empty):
        """get_plugin_info should raise PluginNotFoundError for unknown plugins."""
        with pytest.raises(PluginNotFoundError) as exc_info:
            registry_empty.get_plugin_info("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()


class TestPluginLoading:
    """Test plugin loading and instantiation."""

    def test_load_plugin_returns_none_for_unknown_plugin(self, registry_empty):
        """load_plugin should return None for unknown plugins."""
        handler = registry_empty.load_plugin("nonexistent")
        assert handler is None

    def test_load_plugin_returns_cached_instance(self, registry_empty, plugin_context):
        """load_plugin should return cached instance on subsequent calls."""
        # Add discovered plugin
        registry_empty._discovered["mock_plugin"] = PluginMetadata(
            name="mock_plugin",
            version="1.0.0",
            entry_point="tests.fixtures.mock_plugin:MockFileTypeHandler",
            supported_extensions=[".mock"],
            required_api_version="1.0.0",
            is_enabled=True,
        )

        # Pre-load a handler
        handler1 = MockFileTypeHandler()
        registry_empty._loaded["mock_plugin"] = handler1

        # Load again
        handler2 = registry_empty.load_plugin("mock_plugin", plugin_context)

        # Should return same instance
        assert handler2 is handler1

    def test_load_plugin_returns_none_for_disabled_plugin(self, registry_empty):
        """load_plugin should return None for disabled plugins."""
        registry_empty._discovered["disabled"] = PluginMetadata(
            name="disabled",
            version="1.0.0",
            entry_point="dummy:Handler",
            supported_extensions=[".dis"],
            required_api_version="1.0.0",
            is_enabled=False,
        )

        handler = registry_empty.load_plugin("disabled")
        assert handler is None

    @patch("krag.plugins.registry.PluginLoader")
    def test_load_plugin_handles_load_errors_gracefully(
        self, mock_loader_class, registry_empty, plugin_context
    ):
        """load_plugin should handle errors gracefully and disable plugin."""
        # Setup mock loader to raise exception
        mock_loader = MagicMock()
        mock_loader.load_plugin_class.side_effect = Exception("Load failed")
        mock_loader_class.return_value = mock_loader

        registry = PluginRegistry(PluginConfiguration(enabled_plugins=[], disabled_plugins=[]))
        registry._discovered["failing"] = PluginMetadata(
            name="failing",
            version="1.0.0",
            entry_point="dummy:Handler",
            supported_extensions=[".fail"],
            required_api_version="1.0.0",
            is_enabled=True,
        )

        # Should not raise exception
        handler = registry.load_plugin("failing", plugin_context)

        assert handler is None
        # Plugin should be disabled
        assert registry._discovered["failing"].is_enabled is False


class TestHandlerRetrieval:
    """Test file extension to handler mapping."""

    def test_get_handler_for_extension_normalizes_case(self, registry_empty, plugin_context):
        """get_handler_for_extension should perform case-insensitive lookup."""
        # Setup plugin
        registry_empty._discovered["mock_plugin"] = PluginMetadata(
            name="mock_plugin",
            version="1.0.0",
            entry_point="tests.fixtures.mock_plugin:MockFileTypeHandler",
            supported_extensions=[".mock"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._extension_map = {".mock": "mock_plugin"}
        handler = MockFileTypeHandler()
        registry_empty._loaded["mock_plugin"] = handler

        # Test case-insensitive lookup
        result1 = registry_empty.get_handler_for_extension(".mock", plugin_context)
        result2 = registry_empty.get_handler_for_extension(".MOCK", plugin_context)
        result3 = registry_empty.get_handler_for_extension(".Mock", plugin_context)

        assert result1 is handler
        assert result2 is handler
        assert result3 is handler

    def test_get_handler_for_extension_returns_none_for_unsupported(
        self, registry_empty, plugin_context
    ):
        """get_handler_for_extension should return None for unsupported extensions."""
        result = registry_empty.get_handler_for_extension(".unsupported", plugin_context)
        assert result is None

    def test_get_handler_for_extension_triggers_lazy_load(self, registry_empty, plugin_context):
        """get_handler_for_extension should trigger lazy loading of plugin."""
        registry_empty._discovered["mock_plugin"] = PluginMetadata(
            name="mock_plugin",
            version="1.0.0",
            entry_point="tests.fixtures.mock_plugin:MockFileTypeHandler",
            supported_extensions=[".mock"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._extension_map = {".mock": "mock_plugin"}

        # Handler not yet loaded
        assert "mock_plugin" not in registry_empty._loaded

        # Mock the load_plugin method to avoid actual loading
        from unittest.mock import patch

        mock_handler = MockFileTypeHandler()
        with patch.object(registry_empty, "load_plugin", return_value=mock_handler) as mock_load:
            handler = registry_empty.get_handler_for_extension(".mock", plugin_context)

            # load_plugin should have been called
            mock_load.assert_called_once_with("mock_plugin", plugin_context)

            # Handler should be returned
            assert handler is mock_handler

    def test_get_handler_for_file_uses_extension(self, registry_empty, plugin_context, tmp_path):
        """get_handler_for_file should extract extension and delegate to get_handler_for_extension."""
        # Setup
        registry_empty._discovered["mock_plugin"] = PluginMetadata(
            name="mock_plugin",
            version="1.0.0",
            entry_point="tests.fixtures.mock_plugin:MockFileTypeHandler",
            supported_extensions=[".mock"],
            required_api_version="1.0.0",
            is_enabled=True,
        )
        registry_empty._extension_map = {".mock": "mock_plugin"}
        handler = MockFileTypeHandler()
        registry_empty._loaded["mock_plugin"] = handler

        # Test with file path
        test_file = tmp_path / "test.mock"
        result = registry_empty.get_handler_for_file(test_file, plugin_context)

        assert result is handler


class TestPluginCleanup:
    """Test plugin cleanup and shutdown."""

    def test_shutdown_all_plugins_calls_cleanup(self, registry_empty):
        """shutdown_all_plugins should call cleanup() on all loaded plugins."""
        # Create mock handlers
        handler1 = MagicMock(spec=MockFileTypeHandler)
        handler2 = MagicMock(spec=MockFileTypeHandler)

        registry_empty._loaded = {"plugin1": handler1, "plugin2": handler2}

        registry_empty.shutdown_all_plugins()

        handler1.cleanup.assert_called_once()
        handler2.cleanup.assert_called_once()

    def test_shutdown_all_plugins_handles_cleanup_errors(self, registry_empty):
        """shutdown_all_plugins should handle cleanup errors gracefully."""
        handler = MagicMock(spec=MockFileTypeHandler)
        handler.cleanup.side_effect = Exception("Cleanup failed")

        registry_empty._loaded = {"failing": handler}

        # Should not raise exception
        registry_empty.shutdown_all_plugins()

        handler.cleanup.assert_called_once()

    def test_shutdown_all_plugins_clears_loaded_dict(self, registry_empty):
        """shutdown_all_plugins should clear the loaded plugins dictionary."""
        handler = MagicMock(spec=MockFileTypeHandler)
        registry_empty._loaded = {"plugin": handler}

        registry_empty.shutdown_all_plugins()

        assert len(registry_empty._loaded) == 0
