"""Configuration management CLI commands."""

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from krag.cli.utils import exit_with_code
from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir

if TYPE_CHECKING:
    from krag.models.configuration import Configuration

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
            # Provide actionable hints for common path issues
            if error_message and (
                "not writable" in error_message or "permission denied" in error_message.lower()
            ):
                console.print("\n[yellow]Hint:[/yellow] Check directory ownership and permissions.")
                console.print("  For shared /krag paths, ensure your user is in the 'krag' group:")
                console.print("    sudo usermod -aG krag $USER")
                console.print("    newgrp krag")
            elif error_message and "does not exist" in error_message and "Storage" in error_message:
                console.print("\n[yellow]Hint:[/yellow] The parent directory does not exist.")
                console.print("  Create it with: sudo mkdir -p <path>")
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

            # Show storage paths summary
            console.print("\n[cyan]Storage Paths:[/cyan]")
            console.print(f"  Vector store: {config.vector_store_path}")
            console.print(f"  Model cache:  {config.model_cache_path}")
            console.print(f"  Corpus cache: {config.corpus_cache_path}")
            console.print(f"  Logs:         {config.logs_path}")

            # Show GPU summary
            if config.llm_n_gpu_layers != 0:
                gpu_desc = (
                    "full offload"
                    if config.llm_n_gpu_layers == -1
                    else f"{config.llm_n_gpu_layers} layers"
                )
                console.print(f"\n[cyan]GPU:[/cyan] {gpu_desc}")

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
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Show configuration in Rich table format",
    ),
    paths_only: bool = typer.Option(
        False,
        "--paths-only",
        help="Show only storage paths",
    ),
    gpu_only: bool = typer.Option(
        False,
        "--gpu-only",
        help="Show only GPU/LLM configuration",
    ),
) -> None:
    """Display current configuration.

    Shows all configuration settings in dotted key=value format (grep-friendly).
    Use --pretty for Rich table display.

    Examples:

        # Show config (dotted format, pipe-friendly)
        krag config show

        # Show config in Rich tables
        krag config show --pretty

        # Filter with grep
        krag config show | grep llm

        # Show only storage paths
        krag config show --paths-only

        # Show only GPU configuration
        krag config show --gpu-only

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

        # --paths-only and --gpu-only always use pretty tables
        if paths_only:
            console.print(f"\n[cyan]Configuration:[/cyan] {config_path}\n")
            _show_storage_paths(config)
            return

        if gpu_only:
            console.print(f"\n[cyan]Configuration:[/cyan] {config_path}\n")
            _show_gpu_config(config)
            return

        if not pretty:
            _show_dotted(config_path)
            return

        console.print(f"\n[cyan]Configuration:[/cyan] {config_path}\n")

        # Directories
        table = Table(title="Directories", show_header=True)
        table.add_column("Path", style="cyan")
        for path in config.directory_paths:
            table.add_row(str(path))
        console.print(table)
        console.print()

        # Storage Paths
        _show_storage_paths(config)
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

        # LLM (includes GPU)
        _show_gpu_config(config)
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


def _flatten_toml(prefix: str, obj: dict, out: list[tuple[str, str]]) -> None:
    """Recursively flatten a TOML dict into dotted key-value pairs."""
    for key, value in obj.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _flatten_toml(full, value, out)
        else:
            out.append((full, str(value)))


def _show_dotted(config_path: Path) -> None:
    """Display configuration in flat dotted format (grep-friendly).

    Reads the raw TOML file and flattens it so the output matches
    the on-disk structure rather than the resolved Configuration model.
    """
    import tomllib

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    pairs: list[tuple[str, str]] = []
    _flatten_toml("", data, pairs)

    for key, value in pairs:
        print(f'{key} = "{value}"')


def _show_storage_paths(config: "Configuration") -> None:
    """Display storage paths table."""
    from krag.config.xdg import get_krag_cache_dir, get_krag_state_dir

    table = Table(title="Storage Paths", show_header=True)
    table.add_column("Path Type", style="cyan")
    table.add_column("Location", style="white")
    table.add_column("Source", style="dim")
    table.add_column("Status", style="white")

    # Determine source and status for each path
    cache_dir = get_krag_cache_dir()
    state_dir = get_krag_state_dir()

    paths = [
        ("Vector Store", config.vector_store_path, cache_dir / "storage"),
        ("Model Cache", config.model_cache_path, cache_dir / "models"),
        ("Corpus Cache", config.corpus_cache_path, cache_dir / "corpus"),
        ("Logs", config.logs_path, state_dir / "logs"),
    ]

    for label, actual_path, default_path in paths:
        source = "default (XDG)" if actual_path == default_path else "config"
        status = "[green]exists[/green]" if actual_path.exists() else "[yellow]pending[/yellow]"
        table.add_row(label, str(actual_path), source, status)

    console.print(table)


def _show_gpu_config(config: "Configuration") -> None:
    """Display GPU/LLM configuration table."""
    table = Table(title="LLM (Language Model)", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Model", config.llm_model)
    table.add_row("Context size", str(config.llm_context_size))
    table.add_row("Threads", str(config.llm_num_threads))
    table.add_row("Temperature", str(config.llm_temperature))

    # GPU status
    gpu_desc = str(config.llm_n_gpu_layers)
    if config.llm_n_gpu_layers == 0:
        gpu_desc += " (CPU only)"
    elif config.llm_n_gpu_layers == -1:
        gpu_desc += " (full GPU offload)"
    else:
        gpu_desc += f" (partial: {config.llm_n_gpu_layers} layers on GPU)"
    table.add_row("GPU layers", gpu_desc)

    # Try to detect GPU availability
    try:
        import torch

        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            table.add_row("CUDA status", f"[green]Available[/green] ({device_name})")
        else:
            table.add_row("CUDA status", "[yellow]Not available[/yellow]")
    except ImportError:
        table.add_row("CUDA status", "[dim]torch not installed[/dim]")

    console.print(table)


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
