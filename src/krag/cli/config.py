"""Configuration management CLI commands."""

import os
import subprocess
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from krag.cli.utils import exit_with_code
from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir

# Create config subcommand app
config_app = typer.Typer(
    name="config",
    help="Manage krag configuration",
    add_completion=False,
)

console = Console()


@config_app.command(name="validate")
def config_validate(
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file path (default: auto-detect in XDG config dir)",
    ),
) -> None:
    """Validate configuration file.

    Checks configuration file for errors and reports validation issues.
    Verifies all required fields, data types, and constraints.

    Examples:

        # Validate default config
        krag config validate

        # Validate specific config file
        krag config validate --config /path/to/config.toml
    """
    config_manager = ConfigManager()

    # Auto-detect config if not specified
    if config_path is None:
        config_dir = get_krag_config_dir()
        # Try TOML first, then YAML
        if (config_dir / "config.toml").exists():
            config_path = config_dir / "config.toml"
        elif (config_dir / "config.yaml").exists():
            config_path = config_dir / "config.yaml"
        else:
            console.print("[red]No configuration file found[/red]")
            console.print(f"Expected: {config_dir / 'config.toml'}")
            console.print("Run: krag init")
            exit_with_code(1)

    # Check if file exists
    if not config_path.exists():
        console.print(f"[red]Configuration file not found: {config_path}[/red]")
        exit_with_code(1)

    console.print(f"[cyan]Validating configuration:[/cyan] {config_path}")

    try:
        # Load and validate
        config = config_manager.load(config_path)
        is_valid, error_message = config_manager.validate(config)

        if not is_valid:
            console.print("\n[red]✗ Validation failed:[/red]\n")
            console.print(f"  {error_message}")
            exit_with_code(1)
        else:
            console.print("\n[green]✓ Configuration is valid[/green]")

            # Display summary
            console.print("\n[cyan]Configuration Summary:[/cyan]")
            console.print(f"  Format: {config_path.suffix.upper()}")
            console.print(f"  Directories: {len(config.directory_paths)} configured")
            console.print(f"  File types: {len(config.supported_file_types)} supported")
            console.print(f"  Exclusions: {len(config.exclusion_patterns)} patterns")
            console.print(f"  Chunk size: {config.chunk_size} characters")
            console.print(f"  Embedding model: {config.embedding_model}")

    except ValidationError as e:
        console.print("\n[red]Validation errors:[/red]\n")
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            console.print(f"  • {field}: {message}")
        exit_with_code(1)
    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")
        exit_with_code(1)


@config_app.command(name="show")
def config_show(
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file path (default: auto-detect in XDG config dir)",
    ),
) -> None:
    """Display current configuration.

    Shows all configuration settings in a formatted table.

    Examples:

        # Show default config
        krag config show

        # Show specific config file
        krag config show --config /path/to/config.toml
    """
    config_manager = ConfigManager()

    # Auto-detect config if not specified
    if config_path is None:
        config_dir = get_krag_config_dir()
        if (config_dir / "config.toml").exists():
            config_path = config_dir / "config.toml"
        elif (config_dir / "config.yaml").exists():
            config_path = config_dir / "config.yaml"
        else:
            console.print("[red]No configuration file found[/red]")
            console.print(f"Expected: {config_dir / 'config.toml'}")
            console.print("Run: krag init")
            exit_with_code(1)

    if not config_path.exists():
        console.print(f"[red]Configuration file not found: {config_path}[/red]")
        exit_with_code(1)

    try:
        config = config_manager.load(config_path)

        console.print(f"\n[cyan]Configuration:[/cyan] {config_path}\n")

        # Directories
        table = Table(title="Directories", show_header=True)
        table.add_column("Path", style="cyan")
        for path in config.directory_paths:
            table.add_row(str(path))
        console.print(table)
        console.print()

        # File Processing
        table = Table(title="File Processing", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Supported file types", ", ".join(config.supported_file_types))
        table.add_row("Exclusion patterns", ", ".join(config.exclusion_patterns))
        console.print(table)
        console.print()

        # Text Processing
        table = Table(title="Text Processing", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Chunk size", str(config.chunk_size))
        table.add_row("Chunk overlap", str(config.chunk_overlap))
        console.print(table)
        console.print()

        # Embeddings
        table = Table(title="Embeddings", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Model", config.embedding_model)
        table.add_row("Batch size", str(config.embedding_batch_size))
        table.add_row("Device", config.embedding_device)
        console.print(table)
        console.print()

        # Vector Store
        table = Table(title="Vector Store", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Path", str(config.vector_store_path))
        table.add_row("Distance metric", config.distance_metric)
        console.print(table)
        console.print()

        # LLM
        table = Table(title="LLM (Language Model)", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Model", config.llm_model)
        table.add_row("Context size", str(config.llm_context_size))
        table.add_row("Threads", str(config.llm_num_threads))
        table.add_row("Temperature", str(config.llm_temperature))
        console.print(table)
        console.print()

        # Query
        table = Table(title="Query", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Top K results", str(config.top_k))
        console.print(table)

    except Exception as e:
        console.print(f"[red]Error reading configuration: {e}[/red]")
        exit_with_code(1)


@config_app.command(name="edit")
def config_edit(
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file path (default: auto-detect in XDG config dir)",
    ),
    editor: str | None = typer.Option(
        None,
        "--editor",
        "-e",
        help="Editor to use (default: $EDITOR or nano)",
    ),
) -> None:
    """Open configuration file in editor.

    Opens the configuration file in your default editor or a specified editor.
    Defaults to $EDITOR environment variable, falls back to nano.

    Examples:

        # Edit default config with default editor
        krag config edit

        # Edit with specific editor
        krag config edit --editor vim

        # Edit specific config file
        krag config edit --config /path/to/config.toml
    """
    # Auto-detect config if not specified
    if config_path is None:
        config_dir = get_krag_config_dir()
        if (config_dir / "config.toml").exists():
            config_path = config_dir / "config.toml"
        elif (config_dir / "config.yaml").exists():
            config_path = config_dir / "config.yaml"
        else:
            console.print("[red]No configuration file found[/red]")
            console.print(f"Expected: {config_dir / 'config.toml'}")
            console.print("Run: krag init")
            exit_with_code(1)

    if not config_path.exists():
        console.print(f"[red]Configuration file not found: {config_path}[/red]")
        exit_with_code(1)

    # Determine editor
    if editor is None:
        editor = os.environ.get("EDITOR")
        if editor is None:
            # Try common editors
            for fallback in ["nano", "vim", "vi"]:
                try:
                    subprocess.run(["which", fallback], capture_output=True, check=True)
                    editor = fallback
                    break
                except subprocess.CalledProcessError:
                    continue

            if editor is None:
                console.print("[red]No editor found[/red]")
                console.print("Set $EDITOR environment variable or use --editor")
                exit_with_code(1)

    console.print(f"[cyan]Opening configuration in {editor}:[/cyan] {config_path}")

    try:
        subprocess.run([editor, str(config_path)], check=True)
        console.print("\n[green]Configuration file closed[/green]")
        console.print("[cyan]Tip:[/cyan] Run 'krag config validate' to check for errors")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error opening editor: {e}[/red]")
        exit_with_code(1)
    except FileNotFoundError:
        console.print(f"[red]Editor not found: {editor}[/red]")
        console.print("Try a different editor with --editor")
        exit_with_code(1)
