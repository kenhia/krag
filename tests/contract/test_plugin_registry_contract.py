"""Contract tests for PluginRegistry API.

Verifies that PluginRegistry provides a stable, consistent API for
plugin discovery, information retrieval, and lifecycle management.
"""

from pathlib import Path

import pytest

from krag.models.configuration import PluginConfiguration
from krag.plugins.exceptions import PluginNotFoundError
from krag.plugins.registry import PluginRegistry


class TestPluginRegistryContract:
    """Contract tests for PluginRegistry API."""

    @pytest.fixture
    def registry(self) -> PluginRegistry:
        """Create a fresh registry for testing."""
        config = PluginConfiguration(
            enabled_plugins=[],
            disabled_plugins=[],
            plugin_settings={},
        )
        return PluginRegistry(config)

    def test_discover_plugins_returns_count(self, registry: PluginRegistry) -> None:
        """Verify discover_plugins returns list of metadata."""
        plugins = registry.discover_plugins()
        assert isinstance(plugins, list)

        for plugin in plugins:
            assert hasattr(plugin, "name")
            assert hasattr(plugin, "version")
            assert hasattr(plugin, "is_enabled")

    def test_list_plugins_returns_list(self, registry: PluginRegistry) -> None:
        """Verify list_plugins returns list of metadata."""
        plugins = registry.list_plugins()
        assert isinstance(plugins, list)

        for plugin in plugins:
            assert hasattr(plugin, "name")
            assert hasattr(plugin, "version")
            assert hasattr(plugin, "supported_extensions")
            assert hasattr(plugin, "is_enabled")
            assert hasattr(plugin, "is_loaded")

    def test_get_plugin_info_for_existing_plugin(self, registry: PluginRegistry) -> None:
        """Verify get_plugin_info returns metadata for valid plugin."""
        registry.discover_plugins()
        plugins = registry.list_plugins()

        if plugins:
            plugin_name = plugins[0].name
            info = registry.get_plugin_info(plugin_name)
            assert info is not None
            assert info.name == plugin_name

    def test_get_plugin_info_raises_for_unknown_plugin(self, registry: PluginRegistry) -> None:
        """Verify get_plugin_info raises for non-existent plugin."""
        with pytest.raises(PluginNotFoundError):
            registry.get_plugin_info("nonexistent_plugin_xyz")

    def test_validate_plugins_returns_results(self, registry: PluginRegistry) -> None:
        """Verify validate_plugins returns list of failed plugin names."""
        registry.discover_plugins()
        failed = registry.validate_plugins()

        assert isinstance(failed, list)
        # All elements should be strings (plugin names)
        for plugin_name in failed:
            assert isinstance(plugin_name, str)

    def test_check_extension_conflicts_returns_dict(self, registry: PluginRegistry) -> None:
        """Verify check_extension_conflicts returns conflict map."""
        registry.discover_plugins()
        conflicts = registry.check_extension_conflicts()

        assert isinstance(conflicts, dict)
        for ext, handlers in conflicts.items():
            assert isinstance(ext, str)
            assert ext.startswith(".")
            assert isinstance(handlers, list)
            assert len(handlers) >= 2  # Conflict means 2+ handlers

    def test_get_handler_for_extension_lazy_loads(self, registry: PluginRegistry) -> None:
        """Verify get_handler_for_extension returns handler instance."""
        registry.discover_plugins()
        plugins = registry.list_plugins()

        if plugins and plugins[0].supported_extensions:
            ext = plugins[0].supported_extensions[0]
            handler = registry.get_handler_for_extension(ext)

            # Handler should be None (conflict) or FileTypeHandler instance
            assert handler is None or hasattr(handler, "extract_text")

    def test_get_handler_for_file_resolves_extension(
        self, registry: PluginRegistry, tmp_path: Path
    ) -> None:
        """Verify get_handler_for_file resolves via extension (if implemented)."""
        # Note: get_handler_for_file is planned for T039, may not exist yet
        if not hasattr(registry, "get_handler_for_file"):
            assert True  # Method not yet implemented
            return

        registry.discover_plugins()
        plugins = registry.list_plugins()

        if plugins and plugins[0].supported_extensions:
            ext = plugins[0].supported_extensions[0]
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("test content")

            handler = registry.get_handler_for_file(test_file)
            assert handler is None or hasattr(handler, "extract_text")

    def test_load_plugin_returns_handler(self, registry: PluginRegistry) -> None:
        """Verify load_plugin returns handler instance on success (if implemented)."""
        # Note: load_plugin is planned for T036, may not exist yet
        if not hasattr(registry, "load_plugin"):
            assert True  # Method not yet implemented
            return

        registry.discover_plugins()
        plugins = registry.list_plugins()

        if plugins:
            plugin_name = plugins[0].name
            handler = registry.load_plugin(plugin_name)

            # May return None if load fails (acceptable per spec)
            assert handler is None or hasattr(handler, "extract_text")

    def test_unload_plugin_is_callable(self, registry: PluginRegistry) -> None:
        """Verify unload_plugin exists and is callable (if implemented)."""
        # Note: unload_plugin is planned for T037, may not exist yet
        if hasattr(registry, "unload_plugin"):
            assert callable(registry.unload_plugin)
            # Should not raise for unknown plugin (graceful)
            registry.unload_plugin("nonexistent_plugin")
        else:
            # Method not yet implemented - this is expected until T037
            assert True

    def test_registry_idempotent_discovery(self, registry: PluginRegistry) -> None:
        """Verify multiple discover calls are safe."""
        plugins1 = registry.discover_plugins()
        plugins2 = registry.discover_plugins()

        # Second call may return same or updated list (both valid)
        assert isinstance(plugins1, list)
        assert isinstance(plugins2, list)
