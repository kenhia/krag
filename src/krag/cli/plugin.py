"""Plugin management CLI commands."""

import subprocess
from pathlib import Path

import tomli_w
import typer
from rich.console import Console
from rich.table import Table

from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir
from krag.models.configuration import Configuration
from krag.plugins.registry import PluginRegistry

# Create Typer app for plugin commands
plugin_app = typer.Typer(
    name="plugin",
    help="Manage krag file type plugins",
)

console = Console()


def _get_config_path() -> Path | None:
    """Get the configuration file path (auto-detect TOML or YAML)."""
    config_dir = get_krag_config_dir()
    # Try TOML first, then YAML
    if (config_dir / "config.toml").exists():
        return config_dir / "config.toml"
    elif (config_dir / "config.yaml").exists():
        return config_dir / "config.yaml"
    return None


def _save_config_toml(config: Configuration, config_path: Path) -> None:
    """Save configuration to TOML file with proper section structure."""
    toml_dict = {
        "directories": {
            "paths": [str(p) for p in config.directory_paths],
            "exclusion_patterns": config.exclusion_patterns,
            "follow_symlinks": config.follow_symlinks,
            "supported_file_types": config.supported_file_types,
            "max_file_size_mb": config.max_file_size_mb,
            "skip_binary_files": config.skip_binary_files,
        },
        "embedding": {
            "model": config.embedding_model,
            "batch_size": config.embedding_batch_size,
            "device": config.embedding_device,
        },
        "chunking": {
            "size": config.chunk_size,
            "overlap": config.chunk_overlap,
        },
        "vector_store": {
            "path": str(config.vector_store_path),
            "collection_name": config.collection_name,
            "distance_metric": config.distance_metric,
        },
        "retrieval": {
            "top_k": config.top_k,
        },
        "llm": {
            "model": config.llm_model,
            "context_size": config.llm_context_size,
            "num_threads": config.llm_num_threads,
            "temperature": config.llm_temperature,
        },
        "path_reductions": {
            "aliases": config.path_aliases,
        },
        "plugins": {
            "enabled": config.plugins.enabled_plugins,
            "disabled": config.plugins.disabled_plugins,
        },
    }

    # Add per-plugin settings sections
    for plugin_name, settings in config.plugins.plugin_settings.items():
        toml_dict[f"plugins.{plugin_name}"] = settings

    with open(config_path, "wb") as f:
        tomli_w.dump(toml_dict, f)


@plugin_app.command("list")
def list_plugins(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed plugin information",
    ),
) -> None:
    """List all installed and configured plugins.

    Shows plugin names, status (enabled/disabled), supported file extensions,
    and version information.

    Examples:
        krag plugin list
        krag plugin list --verbose
    """
    try:
        # Load configuration
        config_path = _get_config_path()
        if config_path is None:
            console.print("[red]No configuration file found[/red]")
            console.print("Run: krag init")
            raise typer.Exit(1)

        config = ConfigManager.load(config_path)

        # Create plugin configuration from config
        plugin_cfg = config.plugins

        # Discover plugins
        registry = PluginRegistry(plugin_cfg)
        registry.discover_plugins()

        plugins = registry.list_plugins()

        if not plugins:
            console.print("[yellow]No plugins found.[/yellow]")
            console.print("\nInstall plugins with: uv pip install <plugin-package>")
            console.print("Or create your own: See docs/plugin-development.md")
            return

        # Create table
        table = Table(title="Installed Plugins")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Version", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Extensions", style="yellow")

        if verbose:
            table.add_column("Entry Point", style="dim")

        for plugin in plugins:
            status = "✓ enabled" if plugin.is_enabled else "✗ disabled"
            extensions = ", ".join(plugin.supported_extensions)

            if verbose:
                entry_point = plugin.entry_point if plugin.entry_point else "N/A"
                table.add_row(
                    plugin.name,
                    plugin.version,
                    status,
                    extensions,
                    entry_point,
                )
            else:
                table.add_row(
                    plugin.name,
                    plugin.version,
                    status,
                    extensions,
                )

        console.print(table)

        # Summary
        enabled_count = sum(1 for p in plugins if p.is_enabled)
        disabled_count = len(plugins) - enabled_count
        console.print(
            f"\n[dim]{len(plugins)} plugin(s) installed: "
            f"{enabled_count} enabled, {disabled_count} disabled[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error listing plugins: {e}[/red]")
        raise typer.Exit(code=1) from e


@plugin_app.command("info")
def plugin_info(
    name: str = typer.Argument(..., help="Plugin name to show information for"),
) -> None:
    """Show detailed information about a specific plugin.

    Displays plugin metadata, configuration schema, supported extensions,
    and current configuration values.

    Examples:
        krag plugin info markdown
        krag plugin info logs
    """
    try:
        # Load configuration
        config_path = _get_config_path()
        if config_path is None:
            console.print("[red]No configuration file found[/red]")
            console.print("Run: krag init")
            raise typer.Exit(1)

        config = ConfigManager.load(config_path)

        # Discover plugins
        registry = PluginRegistry(config.plugins)
        registry.discover_plugins()

        # Find plugin
        plugins = registry.list_plugins()
        plugin_metadata = None
        for p in plugins:
            if p.name == name:
                plugin_metadata = p
                break

        if not plugin_metadata:
            console.print(f"[red]Plugin '{name}' not found.[/red]")
            console.print("\nAvailable plugins:")
            for p in plugins:
                console.print(f"  - {p.name}")
            raise typer.Exit(code=1)

        # Display plugin information
        console.print(f"\n[bold cyan]Plugin: {plugin_metadata.name}[/bold cyan]")
        console.print(f"Version: {plugin_metadata.version}")
        console.print(f"Required API Version: {plugin_metadata.required_api_version}")

        status = "enabled" if plugin_metadata.is_enabled else "disabled"
        status_color = "green" if plugin_metadata.is_enabled else "yellow"
        console.print(f"Status: [{status_color}]{status}[/{status_color}]")

        console.print("\nSupported Extensions:")
        for ext in plugin_metadata.supported_extensions:
            console.print(f"  • {ext}")

        if plugin_metadata.entry_point:
            console.print(f"\nEntry Point: {plugin_metadata.entry_point}")

        # Show description if available
        if plugin_metadata.description:
            console.print(f"Description: {plugin_metadata.description}")

        # Show author if available
        if plugin_metadata.author:
            console.print(f"Author: {plugin_metadata.author}")

        # Show current configuration
        current_config = config.plugins.plugin_settings.get(name, {})
        if current_config:
            console.print("\n[bold]Current Configuration:[/bold]")
            for key, value in current_config.items():
                console.print(f"  {key}: {value}")
        else:
            console.print("\n[dim]No configuration set (using defaults)[/dim]")

        if plugin_metadata.load_error:
            console.print(f"\n[red]Load Error: {plugin_metadata.load_error}[/red]")

    except Exception as e:
        console.print(f"[red]Error getting plugin info: {e}[/red]")
        raise typer.Exit(code=1) from e


@plugin_app.command("validate")
def validate_plugins() -> None:
    """Validate all configured plugins for compatibility.

    Checks plugin API versions, dependencies, and configuration validity.
    Reports any issues that might prevent plugins from loading.

    Examples:
        krag plugin validate
    """
    try:
        # Load configuration
        config_path = _get_config_path()
        if config_path is None:
            console.print("[red]No configuration file found[/red]")
            console.print("Run: krag init")
            raise typer.Exit(1)

        config = ConfigManager.load(config_path)

        # Discover plugins
        registry = PluginRegistry(config.plugins)
        registry.discover_plugins()

        plugins = registry.list_plugins()

        if not plugins:
            console.print("[yellow]No plugins to validate.[/yellow]")
            return

        console.print(f"[bold]Validating {len(plugins)} plugin(s)...[/bold]\n")

        errors = 0
        warnings = 0

        for plugin in plugins:
            # Check for load errors
            if plugin.load_error:
                console.print(f"[red]✗ {plugin.name}: {plugin.load_error}[/red]")
                errors += 1
                continue

            # Check if disabled
            if not plugin.is_enabled:
                console.print(f"[yellow]⚠ {plugin.name}: disabled[/yellow]")
                warnings += 1
                continue

            # Plugin looks good
            console.print(f"[green]✓ {plugin.name}: OK[/green]")

        # Summary
        console.print()
        if errors == 0 and warnings == 0:
            console.print("[green]All plugins valid! ✓[/green]")
        else:
            if errors > 0:
                console.print(f"[red]{errors} error(s) found[/red]")
            if warnings > 0:
                console.print(f"[yellow]{warnings} warning(s) found[/yellow]")

            if errors > 0:
                raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]Error validating plugins: {e}[/red]")
        raise typer.Exit(code=1) from e


@plugin_app.command("enable")
def enable_plugin(
    name: str = typer.Argument(..., help="Plugin name to enable"),
) -> None:
    """Enable a disabled plugin.

    Adds the plugin to the enabled list and removes it from the disabled list
    in configuration. The plugin will be loaded on next index/query operation.

    Examples:
        krag plugin enable markdown
        krag plugin enable logs
    """
    try:
        # Load configuration
        config_path = _get_config_path()
        if config_path is None:
            console.print("[red]No configuration file found[/red]")
            console.print("Run: krag init")
            raise typer.Exit(1)

        config = ConfigManager.load(config_path)

        # Check if already enabled
        if name in config.plugins.enabled_plugins:
            console.print(f"[yellow]Plugin '{name}' is already enabled.[/yellow]")
            return

        # Remove from disabled, add to enabled
        if name in config.plugins.disabled_plugins:
            config.plugins.disabled_plugins.remove(name)

        if name not in config.plugins.enabled_plugins:
            config.plugins.enabled_plugins.append(name)

        # Save configuration (only TOML supported for now)
        if config_path.suffix.lower() == ".toml":
            _save_config_toml(config, config_path)
        else:
            console.print(
                "[yellow]Warning: Saving YAML configs not yet supported. Please edit manually.[/yellow]"
            )
            return

        console.print(f"[green]✓ Plugin '{name}' enabled successfully.[/green]")

    except Exception as e:
        console.print(f"[red]Error enabling plugin: {e}[/red]")
        raise typer.Exit(code=1) from e


@plugin_app.command("disable")
def disable_plugin(
    name: str = typer.Argument(..., help="Plugin name to disable"),
) -> None:
    """Disable an enabled plugin.

    Removes the plugin from the enabled list and adds it to the disabled list
    in configuration. The plugin will not be loaded until re-enabled.

    Examples:
        krag plugin disable markdown
        krag plugin disable logs
    """
    try:
        # Load configuration
        config_path = _get_config_path()
        if config_path is None:
            console.print("[red]No configuration file found[/red]")
            console.print("Run: krag init")
            raise typer.Exit(1)

        config = ConfigManager.load(config_path)

        # Check if already disabled
        if name in config.plugins.disabled_plugins:
            console.print(f"[yellow]Plugin '{name}' is already disabled.[/yellow]")
            return

        # Remove from enabled, add to disabled
        if name in config.plugins.enabled_plugins:
            config.plugins.enabled_plugins.remove(name)

        if name not in config.plugins.disabled_plugins:
            config.plugins.disabled_plugins.append(name)

        # Save configuration (only TOML supported for now)
        if config_path.suffix.lower() == ".toml":
            _save_config_toml(config, config_path)
        else:
            console.print(
                "[yellow]Warning: Saving YAML configs not yet supported. Please edit manually.[/yellow]"
            )
            return

        console.print(f"[green]✓ Plugin '{name}' disabled successfully.[/green]")

    except Exception as e:
        console.print(f"[red]Error disabling plugin: {e}[/red]")
        raise typer.Exit(code=1) from e


@plugin_app.command("install")
def install_plugin(
    path: Path | None = typer.Option(
        None,
        "--editable",
        "-e",
        help="Install plugin from local path in editable mode",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    package: str | None = typer.Argument(
        None,
        help="Package name to install from PyPI",
    ),
) -> None:
    """Install a plugin package.

    Installs a plugin using uv pip. Use --editable/-e for local development.

    Examples:
        # Install from PyPI
        krag plugin install krag-plugin-pdf

        # Install from local path in editable mode
        krag plugin install -e ./my-plugin

        # Or use uv pip directly
        uv pip install krag-plugin-markdown
    """
    if not path and not package:
        console.print("[red]Error: Specify either --editable PATH or PACKAGE name.[/red]")
        console.print("\nExamples:")
        console.print("  krag plugin install krag-plugin-pdf")
        console.print("  krag plugin install -e ./my-plugin")
        raise typer.Exit(code=1)

    try:
        if path:
            # Install in editable mode
            console.print(f"[bold]Installing plugin from {path} in editable mode...[/bold]")
            cmd = ["uv", "pip", "install", "-e", str(path)]
        else:
            # Install from PyPI
            console.print(f"[bold]Installing plugin package: {package}[/bold]")
            cmd = ["uv", "pip", "install", package]

        # Run installation
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            console.print("[red]Installation failed:[/red]")
            console.print(result.stderr)
            raise typer.Exit(code=1)

        console.print("[green]✓ Plugin installed successfully.[/green]")
        console.print("\nRun 'krag plugin list' to see available plugins.")

    except FileNotFoundError:
        console.print(
            "[red]Error: 'uv' not found. Please install uv first:[/red]\n"
            "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        )
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red]Error installing plugin: {e}[/red]")
        raise typer.Exit(code=1) from e
