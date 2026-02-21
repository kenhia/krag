"""Integration tests for direct mode — US8 (T052).

Verify krag-direct entry point works in-process without kragd.
"""

from __future__ import annotations

import subprocess
import sys


class TestDirectModeEntryPoint:
    """Tests verifying krag-direct works independently of kragd."""

    def test_entry_point_configured(self) -> None:
        """krag-direct entry point is configured in pyproject.toml."""
        from importlib.metadata import entry_points

        eps = entry_points(group="console_scripts")
        names = [ep.name for ep in eps]
        assert "krag-direct" in names, "krag-direct console_scripts entry point must exist"

    def test_entry_point_target_module(self) -> None:
        """krag-direct maps to krag.cli.main:app."""
        from importlib.metadata import entry_points

        eps = entry_points(group="console_scripts")
        krag_direct = next(ep for ep in eps if ep.name == "krag-direct")
        assert krag_direct.value == "krag.cli.main:app"

    def test_direct_cli_app_importable(self) -> None:
        """krag.cli.main.app is importable and is a Typer app."""
        from krag.cli.main import app

        assert app is not None
        # Typer apps have a registered_callback or similar attributes
        assert hasattr(app, "registered_commands") or hasattr(app, "info")

    def test_direct_cli_has_query_command(self) -> None:
        """krag-direct has a query command."""
        from krag.cli.main import app

        command_names = [cmd.name or cmd.callback.__name__ for cmd in app.registered_commands]
        # Also check sub-apps
        group_names = [g.typer_instance.info.name or "" for g in app.registered_groups]
        all_names = command_names + group_names
        assert any("query" in name for name in all_names), (
            f"'query' command not found in: {all_names}"
        )

    def test_direct_cli_has_index_command(self) -> None:
        """krag-direct has an index command."""
        from krag.cli.main import app

        command_names = [cmd.name or cmd.callback.__name__ for cmd in app.registered_commands]
        assert any("index" in name for name in command_names), (
            f"'index' command not found in: {command_names}"
        )

    def test_direct_cli_has_config_subapp(self) -> None:
        """krag-direct has a config sub-app."""
        from krag.cli.main import app

        group_names = [g.typer_instance.info.name or "" for g in app.registered_groups]
        assert "config" in group_names, f"'config' group not found in: {group_names}"

    def test_direct_cli_has_plugin_subapp(self) -> None:
        """krag-direct has a plugin sub-app."""
        from krag.cli.main import app

        group_names = [g.typer_instance.info.name or "" for g in app.registered_groups]
        assert "plugin" in group_names, f"'plugin' group not found in: {group_names}"

    def test_direct_mode_does_not_import_kragd(self) -> None:
        """krag-direct does not import kragd — fully independent."""
        import importlib

        # Import the direct CLI module
        mod = importlib.import_module("krag.cli.main")
        # Check that kragd is not in the module's namespace
        source = mod.__file__
        assert source is not None
        with open(source) as f:
            content = f.read()
        assert "import kragd" not in content, "krag.cli.main must not import kragd"
        assert "from kragd" not in content, "krag.cli.main must not import from kragd"

    def test_direct_mode_help_runs(self) -> None:
        """krag-direct --help executes without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "krag.cli.main", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Usage" in result.stdout or "usage" in result.stdout.lower()
