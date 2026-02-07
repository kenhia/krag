"""Main CLI application using Typer."""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from krag import __version__
from krag.cli.config import config_app
from krag.cli.index import index_command
from krag.cli.query import query_command
from krag.cli.utils import exit_with_code
from krag.config.logging import setup_logging
from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir, migrate_from_legacy, should_migrate_from_legacy


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console = Console()
        console.print(f"krag version {__version__}")
        raise typer.Exit()


# Create Typer app
app = typer.Typer(
    name="krag",
    help="Personal RAG system for querying local knowledge base",
    add_completion=False,
)

# Add commands
app.command(name="query")(query_command)
app.command(name="index")(index_command)
app.add_typer(config_app, name="config")

# Console for rich output
console = Console()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose (DEBUG level) logging",
    ),
    show_logs: bool = typer.Option(
        False,
        "--show-logs",
        help="Show application logs on console (INFO level)",
    ),
    legacy_paths: bool = typer.Option(
        False,
        "--legacy-paths",
        help="Use legacy ~/.krag directory structure instead of XDG paths",
    ),
) -> None:
    """Configure global options for krag CLI."""
    # Check for automatic migration from legacy paths
    if not legacy_paths and should_migrate_from_legacy():
        console.print("[yellow]Migrating from legacy ~/.krag to XDG directories...[/yellow]")
        migrations = migrate_from_legacy()
        if migrations:
            console.print("[green]Migration complete:[/green]")
            for old, new in migrations.items():
                console.print(f"  {old} → {new}")
            console.print(
                "\n[cyan]Tip:[/cyan] Use --legacy-paths flag if you need to revert to old structure\n"
            )

    setup_logging(show_logs=show_logs, verbose=verbose)


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Configuration file path (default: XDG_CONFIG_HOME/krag/config.toml)",
    ),
    yaml: bool = typer.Option(
        False,
        "--yaml",
        help="Create YAML configuration instead of TOML (legacy format)",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Prompt for directories and settings interactively",
    ),
) -> None:
    """Initialize configuration for krag.

    Creates a default configuration file with sensible defaults.
    By default, creates TOML format in XDG_CONFIG_HOME/krag/config.toml
    (typically ~/.config/krag/config.toml). Use --yaml for legacy YAML format.
    Edit the file to customize directories, models, and other settings.

    Examples:

        # Initialize with default TOML config
        krag init

        # Initialize interactively with prompts
        krag init --interactive

        # Initialize with legacy YAML format
        krag init --yaml

        # Force overwrite existing config
        krag init --force

        # Use custom config location
        krag init --config /path/to/config.toml
    """
    config_manager = ConfigManager()

    # Determine default config path if not specified
    if config_path is None:
        config_dir = get_krag_config_dir()
        if yaml:
            config_path = config_dir / "config.yaml"
        else:
            config_path = config_dir / "config.toml"

    # Validate extension matches format
    suffix = config_path.suffix.lower()
    if yaml and suffix != ".yaml" and suffix != ".yml":
        console.print(f"[yellow]Warning: --yaml specified but file has {suffix} extension[/yellow]")
    elif not yaml and suffix != ".toml":
        console.print(f"[yellow]Warning: TOML format but file has {suffix} extension[/yellow]")

    try:
        # Check if config exists
        if config_path.exists() and not force:
            console.print(f"[yellow]Configuration already exists at {config_path}[/yellow]")
            console.print("Use --force to overwrite")
            exit_with_code(1)

        # Remove existing config if force is enabled
        if config_path.exists() and force:
            config_path.unlink()
            console.print("[yellow]Removed existing configuration[/yellow]")

        # Interactive mode - prompt for directories
        directory_paths = []
        if interactive:
            console.print("\n[cyan]Configure directories to index[/cyan]\n")
            console.print(
                "Enter directories one at a time (press Enter with empty input to finish)"
            )

            while True:
                dir_input = typer.prompt(
                    "Directory path (or press Enter to finish)",
                    default="",
                    show_default=False,
                )

                if not dir_input.strip():
                    if not directory_paths:
                        # Need at least one directory
                        console.print("[yellow]At least one directory is required[/yellow]")
                        continue
                    break

                dir_path = Path(dir_input.strip()).expanduser().resolve()

                if not dir_path.exists():
                    console.print(f"[yellow]Warning: Directory does not exist: {dir_path}[/yellow]")
                    use_anyway = typer.confirm("Add it anyway?", default=False)
                    if not use_anyway:
                        continue

                if not dir_path.is_dir():
                    console.print(f"[red]Error: Not a directory: {dir_path}[/red]")
                    continue

                directory_paths.append(dir_path)
                console.print(f"[green]✓ Added: {dir_path}[/green]")

        # Create default config in requested format
        format_type = "yaml" if yaml else "toml"
        config = config_manager.create_default(config_path, format=format_type)

        # Update with interactive directories if provided
        if directory_paths:
            config.directory_paths = directory_paths
            # Save the updated config
            config_dict = config.model_dump(mode="json")
            if format_type == "toml":
                import tomli_w

                with open(config_path, "wb") as f:
                    tomli_w.dump(config_dict, f)
            else:
                import yaml

                with open(config_path, "w") as f:
                    yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)

        console.print(
            f"\n[green]Created {format_type.upper()} configuration at {config_path}[/green]\n"
        )

        # Display key settings
        console.print("[cyan]Configuration:[/cyan]")
        console.print(f"  Directories: {config.directory_paths}")
        console.print(f"  Embedding model: {config.embedding_model}")
        console.print(f"  Vector store: {config.vector_store_path}")
        console.print(f"  LLM model: {config.llm_model}")

        console.print("\n[cyan]Edit configuration:[/cyan] krag config edit")
        console.print("[cyan]Validate configuration:[/cyan] krag config validate")
        console.print("[cyan]Then run:[/cyan] krag index")

    except Exception as e:
        console.print(f"[red]Failed to create configuration: {e}[/red]")
        exit_with_code(1)


@app.command()
def migrate(
    yaml_path: Path = typer.Argument(
        ...,
        help="Path to existing YAML configuration file",
    ),
    toml_path: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Path for new TOML file (default: same location with .toml extension)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing TOML file",
    ),
) -> None:
    """Migrate YAML configuration to TOML format.

    Converts an existing YAML configuration file to the modern TOML format.
    The YAML file is not deleted - you can remove it manually after verification.

    Examples:

        # Migrate config.yaml to config.toml in same directory
        krag migrate ~/.krag/config.yaml

        # Specify custom output path
        krag migrate old.yaml --output new.toml

        # Overwrite existing TOML file
        krag migrate config.yaml --force
    """
    config_manager = ConfigManager()

    try:
        # Validate YAML file exists
        if not yaml_path.exists():
            console.print(f"[red]YAML configuration not found: {yaml_path}[/red]")
            exit_with_code(1)

        # Determine output path
        if toml_path is None:
            toml_path = yaml_path.with_suffix(".toml")

        # Check if TOML file exists
        if toml_path.exists() and not force:
            console.print(f"[yellow]TOML configuration already exists: {toml_path}[/yellow]")
            console.print("Use --force to overwrite")
            exit_with_code(1)

        # Remove existing TOML if force
        if toml_path.exists() and force:
            toml_path.unlink()

        # Perform migration
        console.print(f"[cyan]Migrating {yaml_path} → {toml_path}...[/cyan]")
        result_path = config_manager.migrate_yaml_to_toml(yaml_path, toml_path)

        console.print(f"[green]✓ Successfully migrated configuration to {result_path}[/green]\n")

        # Load and display the migrated config
        migrated_config = config_manager.load(result_path)
        console.print("[cyan]Migrated Settings:[/cyan]")
        console.print(f"  Directories: {migrated_config.directory_paths}")
        console.print(f"  Embedding model: {migrated_config.embedding_model}")
        console.print(f"  Vector store: {migrated_config.vector_store_path}")

        console.print(f"\n[yellow]Note:[/yellow] Original YAML file not deleted: {yaml_path}")
        console.print(
            "[cyan]Verify the TOML configuration, then you can remove the YAML file[/cyan]"
        )

    except Exception as e:
        console.print(f"[red]Failed to migrate configuration: {e}[/red]")
        exit_with_code(1)


@app.command()
def status(
    config_path: Path = typer.Option(
        Path.home() / ".krag" / "config.yaml",
        "--config",
        "-c",
        help="Configuration file path",
    ),
) -> None:
    """Show index statistics and system status.

    Displays information about the current index including
    number of documents, vectors, and storage usage.

    Examples:

        # Show status
        krag status

        # Use custom config
        krag status --config /path/to/config.yaml
    """
    try:
        # Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load(config_path)
        except FileNotFoundError:
            console.print("[red]Configuration not found. Run 'krag init' first.[/red]")
            exit_with_code(1)

        # Create table
        table = Table(title="KRAG System Status", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        # Configuration status
        table.add_row("Configuration", str(config_path))
        table.add_row(
            "Directories",
            ", ".join(str(d) for d in config.directory_paths) or "Not configured",
        )
        table.add_row("Embedding Model", config.embedding_model)

        # Vector store status
        try:
            from krag.storage.qdrant_impl import QdrantVectorStore

            vector_store = QdrantVectorStore(
                collection_name=config.collection_name,
                vector_size=384,  # Default for all-MiniLM-L6-v2
                storage_path=config.vector_store_path,
            )

            stats = vector_store.get_stats()
            table.add_row("Vector Store", str(config.vector_store_path or "In-memory"))
            table.add_row("Collection", stats["collection_name"])
            table.add_row("Indexed Vectors", str(stats["count"]))
            table.add_row("Status", stats["status"])

            vector_store.close()

        except Exception as e:
            table.add_row("Vector Store", f"[yellow]Not initialized: {e}[/yellow]")

        console.print(table)
        console.print(
            "\n[cyan]Run 'krag index' to index documents or 'krag query' to search.[/cyan]"
        )

    except Exception as e:
        console.print(f"[red]Failed to get status: {e}[/red]")
        exit_with_code(1)


@app.command()
def reset(
    config: bool = typer.Option(
        False,
        "--config",
        help="Remove configuration files",
    ),
    data: bool = typer.Option(
        False,
        "--data",
        help="Remove vector store and cache data",
    ),
    logs: bool = typer.Option(
        False,
        "--logs",
        help="Remove log files",
    ),
    all: bool = typer.Option(
        False,
        "--all",
        help="Remove everything (config, data, logs)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts",
    ),
) -> None:
    """Reset krag by removing data, configuration, or logs.

    This command removes krag files from XDG directories. Use with caution!

    Examples:

        # Remove only vector store data
        krag reset --data

        # Remove everything with confirmation
        krag reset --all

        # Remove config and data without prompts
        krag reset --config --data --yes
    """
    from krag.config.xdg import get_krag_cache_dir, get_krag_config_dir, get_krag_state_dir

    # Determine what to reset
    reset_config = config or all
    reset_data = data or all
    reset_logs = logs or all

    if not (reset_config or reset_data or reset_logs):
        console.print("[yellow]No reset options specified. Use --help to see options.[/yellow]")
        console.print("Examples:")
        console.print("  krag reset --data        # Remove vector store")
        console.print("  krag reset --all         # Remove everything")
        exit_with_code(1)

    # Show what will be removed
    console.print("\n[yellow]The following will be removed:[/yellow]\n")
    items_to_remove = []

    if reset_config:
        config_dir = get_krag_config_dir()
        console.print(f"  • Configuration: {config_dir}")
        items_to_remove.append(("Configuration", config_dir))

    if reset_data:
        cache_dir = get_krag_cache_dir()
        console.print(f"  • Data (vector store, models): {cache_dir}")
        items_to_remove.append(("Data", cache_dir))

    if reset_logs:
        state_dir = get_krag_state_dir()
        console.print(f"  • Logs: {state_dir / 'logs'}")
        items_to_remove.append(("Logs", state_dir / "logs"))

    # Confirm
    if not yes:
        console.print()
        confirm = typer.confirm("Are you sure you want to proceed?", default=False)
        if not confirm:
            console.print("[yellow]Reset cancelled[/yellow]")
            raise typer.Exit(0)

    # Perform removal
    import shutil

    console.print()
    for name, path in items_to_remove:
        try:
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                console.print(f"[green]✓ Removed {name}:[/green] {path}")
            else:
                console.print(f"[dim]• {name} not found:[/dim] {path}")
        except Exception as e:
            console.print(f"[red]✗ Failed to remove {name}: {e}[/red]")

    console.print("\n[green]Reset complete[/green]")
    console.print("[cyan]Run 'krag init' to reinitialize[/cyan]")


if __name__ == "__main__":
    app()
