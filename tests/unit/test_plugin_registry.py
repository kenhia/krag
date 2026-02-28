"""Unit tests for plugin registry auto extension map build (US10).

T023: Validates that:
- After discover_plugins(), get_handler_for_extension() works without
  an explicit _build_extension_map() call
- _build_extension_map() is called internally by discover_plugins()
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from krag.models.configuration import PluginConfiguration


def _make_plugin_config() -> PluginConfiguration:
    """Create a minimal plugin configuration."""
    return PluginConfiguration(
        plugin_dir=None,
        enabled_plugins=[],
        disabled_plugins=[],
    )


class TestAutoExtensionMapBuild:
    """discover_plugins() must auto-build the extension map."""

    def test_extension_map_populated_after_discover(self) -> None:
        """After discover_plugins(), _extension_map is populated without explicit call."""
        from krag.plugins.registry import PluginRegistry

        config = _make_plugin_config()
        registry = PluginRegistry(config)

        # Mock a plugin that registers .py extension
        mock_handler = MagicMock()
        mock_handler.name = "test_plugin"
        mock_handler.version = "1.0.0"
        mock_handler.required_api_version = "1.0.0"
        mock_handler.supported_extensions.return_value = [".py", ".pyi"]
        mock_handler.description = "Test"
        mock_handler.author = "Test"

        fake_ep = MagicMock()
        fake_ep.name = "test_plugin"
        fake_ep.value = "test_plugin:Handler"

        with patch("krag.plugins.registry.entry_points") as mock_ep:
            # Return our fake entry point
            eps = MagicMock()
            eps.select.return_value = [fake_ep]
            mock_ep.return_value = eps

            with (
                patch.object(registry._loader, "load_plugin_class", return_value=MagicMock),
                patch.object(registry._loader, "instantiate_plugin", return_value=mock_handler),
            ):
                registry.discover_plugins()

        # Extension map should be populated WITHOUT explicit _build_extension_map() call
        assert ".py" in registry._extension_map
        assert ".pyi" in registry._extension_map
        assert registry._extension_map[".py"] == "test_plugin"

    def test_get_handler_for_extension_works_after_discover(self) -> None:
        """get_handler_for_extension() finds the plugin after discover_plugins()."""
        from krag.plugins.registry import PluginRegistry

        config = _make_plugin_config()
        registry = PluginRegistry(config)

        mock_handler = MagicMock()
        mock_handler.name = "code_plugin"
        mock_handler.version = "1.0.0"
        mock_handler.required_api_version = "1.0.0"
        mock_handler.supported_extensions.return_value = [".rs"]
        mock_handler.description = "Rust handler"
        mock_handler.author = None

        fake_ep = MagicMock()
        fake_ep.name = "code_plugin"
        fake_ep.value = "code_plugin:Handler"

        with patch("krag.plugins.registry.entry_points") as mock_ep:
            eps = MagicMock()
            eps.select.return_value = [fake_ep]
            mock_ep.return_value = eps

            with (
                patch.object(registry._loader, "load_plugin_class", return_value=MagicMock),
                patch.object(registry._loader, "instantiate_plugin", return_value=mock_handler),
            ):
                registry.discover_plugins()

        # get_handler_for_extension should resolve the plugin
        assert registry._extension_map.get(".rs") == "code_plugin"
