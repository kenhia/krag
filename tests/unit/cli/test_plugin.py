"""Unit tests for plugin CLI commands.

Tests the plugin management CLI commands (list, info, validate, enable, disable, install).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from krag.cli.main import app
from krag.models.configuration import Configuration, PluginConfiguration, PluginMetadata

runner = CliRunner()


@pytest.fixture
def mock_config(tmp_path):
    """Mock configuration with plugin settings."""
    config_path = tmp_path / "config.toml"
    config = Configuration(
        directory_paths=[Path.home() / "Documents"],
        plugins=PluginConfiguration(
            enabled_plugins=["markdown"],
            disabled_plugins=[],
        ),
    )
    return config, config_path


@pytest.fixture
def mock_plugin_metadata():
    """Mock plugin metadata for testing."""
    return [
        PluginMetadata(
            name="markdown",
            version="0.1.0",
            entry_point="krag_plugin_markdown.handler:MarkdownFileTypeHandler",
            supported_extensions=[".md", ".markdown"],
            required_api_version="1.0.0",
            is_enabled=True,
        ),
        PluginMetadata(
            name="logs",
            version="0.2.0",
            entry_point="krag_plugin_logs.handler:LogFileHandler",
            supported_extensions=[".log"],
            required_api_version="1.0.0",
            is_enabled=True,
        ),
    ]


class TestPluginList:
    """Tests for `krag plugin list` command."""

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.plugins.registry.PluginRegistry")
    def test_list_plugins_basic(
        self,
        mock_registry_class,
        mock_load,
        mock_get_config_path,
        mock_config,
        mock_plugin_metadata,
        tmp_path,
    ):
        """Test listing plugins shows basic information."""
        config, config_path = mock_config
        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        # Mock registry
        mock_registry = MagicMock()
        mock_registry.list_plugins.return_value = mock_plugin_metadata
        mock_registry_class.return_value = mock_registry

        result = runner.invoke(app, ["plugin", "list"])

        assert result.exit_code == 0
        assert "markdown" in result.stdout
        assert "logs" in result.stdout
        assert "2 plugin(s) installed" in result.stdout

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.plugins.registry.PluginRegistry")
    def test_list_plugins_verbose(
        self,
        mock_registry_class,
        mock_load,
        mock_get_config_path,
        mock_config,
        mock_plugin_metadata,
        tmp_path,
    ):
        """Test listing plugins with verbose flag shows entry points."""
        config, config_path = mock_config
        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        mock_registry = MagicMock()
        mock_registry.list_plugins.return_value = mock_plugin_metadata
        mock_registry_class.return_value = mock_registry

        result = runner.invoke(app, ["plugin", "list", "--verbose"])

        assert result.exit_code == 0
        assert "Entry Point" in result.stdout
        assert "krag_plugin_markdown.handler:MarkdownFileTypeHandler" in result.stdout

    @patch("krag.cli.plugin._get_config_path")
    def test_list_plugins_no_config(self, mock_get_config_path):
        """Test listing plugins when no config exists."""
        mock_get_config_path.return_value = None

        result = runner.invoke(app, ["plugin", "list"])

        assert result.exit_code == 1
        assert "No configuration file found" in result.stdout


class TestPluginInfo:
    """Tests for `krag plugin info` command."""

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.plugins.registry.PluginRegistry")
    def test_plugin_info_success(
        self,
        mock_registry_class,
        mock_load,
        mock_get_config_path,
        mock_config,
        mock_plugin_metadata,
        tmp_path,
    ):
        """Test showing plugin information."""
        config, config_path = mock_config
        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        mock_registry = MagicMock()
        mock_registry.list_plugins.return_value = mock_plugin_metadata
        mock_registry_class.return_value = mock_registry

        result = runner.invoke(app, ["plugin", "info", "markdown"])

        assert result.exit_code == 0
        assert "Plugin: markdown" in result.stdout
        assert "Version: 0.1.0" in result.stdout
        assert "Required API Version: 1.0.0" in result.stdout
        assert ".md" in result.stdout

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.plugins.registry.PluginRegistry")
    def test_plugin_info_not_found(
        self,
        mock_registry_class,
        mock_load,
        mock_get_config_path,
        mock_config,
        mock_plugin_metadata,
        tmp_path,
    ):
        """Test showing info for non-existent plugin."""
        config, config_path = mock_config
        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        mock_registry = MagicMock()
        mock_registry.list_plugins.return_value = mock_plugin_metadata
        mock_registry_class.return_value = mock_registry

        result = runner.invoke(app, ["plugin", "info", "nonexistent"])

        assert result.exit_code == 1
        assert "Plugin 'nonexistent' not found" in result.stdout


class TestPluginValidate:
    """Tests for `krag plugin validate` command."""

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.plugins.registry.PluginRegistry")
    def test_validate_all_plugins_ok(
        self,
        mock_registry_class,
        mock_load,
        mock_get_config_path,
        mock_config,
        mock_plugin_metadata,
        tmp_path,
    ):
        """Test validating plugins when all are OK."""
        config, config_path = mock_config
        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        mock_registry = MagicMock()
        mock_registry.list_plugins.return_value = mock_plugin_metadata
        mock_registry_class.return_value = mock_registry

        result = runner.invoke(app, ["plugin", "validate"])

        assert result.exit_code == 0
        assert "All plugins valid" in result.stdout

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.plugins.registry.PluginRegistry")
    def test_validate_with_errors(
        self, mock_registry_class, mock_load, mock_get_config_path, mock_config, tmp_path
    ):
        """Test validating plugins when some have errors."""
        config, config_path = mock_config
        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        # Create plugin with load error
        error_plugin = PluginMetadata(
            name="broken",
            version="0.1.0",
            entry_point="broken:Handler",
            supported_extensions=[".broken"],
            required_api_version="1.0.0",
            is_enabled=True,
            load_error="Failed to import module",
        )

        mock_registry = MagicMock()
        mock_registry.list_plugins.return_value = [error_plugin]
        mock_registry_class.return_value = mock_registry

        result = runner.invoke(app, ["plugin", "validate"])

        assert result.exit_code == 1
        assert "broken" in result.stdout
        assert "Failed to import module" in result.stdout


class TestPluginEnableDisable:
    """Tests for `krag plugin enable` and `krag plugin disable` commands."""

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.cli.plugin._save_config_toml")
    def test_enable_plugin(self, mock_save, mock_load, mock_get_config_path, mock_config, tmp_path):
        """Test enabling a disabled plugin."""
        config, config_path = mock_config
        config_path = tmp_path / "config.toml"
        config.plugins.disabled_plugins = ["markdown"]
        config.plugins.enabled_plugins = []

        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        result = runner.invoke(app, ["plugin", "enable", "markdown"])

        assert result.exit_code == 0
        assert "enabled successfully" in result.stdout
        assert "markdown" in config.plugins.enabled_plugins
        assert "markdown" not in config.plugins.disabled_plugins
        mock_save.assert_called_once()

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    @patch("krag.cli.plugin._save_config_toml")
    def test_disable_plugin(
        self, mock_save, mock_load, mock_get_config_path, mock_config, tmp_path
    ):
        """Test disabling an enabled plugin."""
        config, config_path = mock_config
        config_path = tmp_path / "config.toml"
        config.plugins.enabled_plugins = ["markdown"]
        config.plugins.disabled_plugins = []

        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        result = runner.invoke(app, ["plugin", "disable", "markdown"])

        assert result.exit_code == 0
        assert "disabled successfully" in result.stdout
        assert "markdown" not in config.plugins.enabled_plugins
        assert "markdown" in config.plugins.disabled_plugins
        mock_save.assert_called_once()

    @patch("krag.cli.plugin._get_config_path")
    @patch("krag.config.settings.ConfigManager.load")
    def test_enable_already_enabled(self, mock_load, mock_get_config_path, mock_config, tmp_path):
        """Test enabling an already enabled plugin."""
        config, config_path = mock_config
        config.plugins.enabled_plugins = ["markdown"]

        mock_get_config_path.return_value = config_path
        mock_load.return_value = config

        result = runner.invoke(app, ["plugin", "enable", "markdown"])

        assert result.exit_code == 0
        assert "already enabled" in result.stdout


class TestPluginInstall:
    """Tests for `krag plugin install` command."""

    @patch("subprocess.run")
    def test_install_plugin_package(self, mock_run):
        """Test installing a plugin from PyPI."""
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["plugin", "install", "krag-plugin-markdown"])

        assert result.exit_code == 0
        assert "successfully" in result.stdout
        mock_run.assert_called_once()
        # Check that uv pip install was called
        args = mock_run.call_args[0][0]
        assert "uv" in args
        assert "pip" in args
        assert "install" in args
        assert "krag-plugin-markdown" in args

    @patch("subprocess.run")
    def test_install_plugin_editable(self, mock_run):
        """Test installing a plugin in editable mode."""
        mock_run.return_value = MagicMock(returncode=0)

        result = runner.invoke(app, ["plugin", "install", "--editable", "./my-plugin"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        # Check that -e flag was included
        args = mock_run.call_args[0][0]
        assert "-e" in args
        assert "./my-plugin" in args

    @patch("subprocess.run")
    def test_install_plugin_failure(self, mock_run):
        """Test handling installation failure."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error message")

        result = runner.invoke(app, ["plugin", "install", "nonexistent-plugin"])

        assert result.exit_code == 1
        assert "Failed" in result.stdout
