"""Main CLI application using Typer."""

import json
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from krag.cli.index import index_command
from krag.cli.query import query_command
from krag.cli.utils import exit_with_code
from krag.config.logging import setup_logging
from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir, migrate_from_legacy, should_migrate_from_legacy

# Create Typer app
app = typer.Typer(
    name="krag",
    help="Personal RAG system for querying local knowledge base",
    add_completion=False,
)

# Add commands
app.command(name="query")(query_command)
app.command(name="index")(index_command)

# Console for rich output
console = Console()


@app.callback()
def main_callback(
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
) -> None:
    """Initialize configuration for krag.

    Creates a default configuration file with sensible defaults.
    By default, creates TOML format in XDG_CONFIG_HOME/krag/config.toml
    (typically ~/.config/krag/config.toml). Use --yaml for legacy YAML format.
    Edit the file to customize directories, models, and other settings.

    Examples:

        # Initialize with default TOML config
        krag init

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

        # Create default config in requested format
        format_type = "yaml" if yaml else "toml"
        config = config_manager.create_default(config_path, format=format_type)
        console.print(
            f"[green]Created {format_type.upper()} configuration at {config_path}[/green]\n"
        )

        # Display key settings
        console.print("[cyan]Default Settings:[/cyan]")
        console.print(f"  Directories: {config.directory_paths}")
        console.print(f"  Embedding model: {config.embedding_model}")
        console.print(f"  Vector store: {config.vector_store_path}")
        console.print(f"  LLM model: {config.llm_model_path or 'Not configured'}")

        console.print(f"\n[cyan]Edit configuration:[/cyan] {config_path}")
        console.print("[cyan]Then run:[/cyan] krag index --dir /path/to/documents")

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


# Config subcommand group
config_app = typer.Typer(help="Manage configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show(
    config_path: Path = typer.Option(
        Path.home() / ".krag" / "config.yaml",
        "--config",
        "-c",
        help="Configuration file path",
    ),
) -> None:
    """Display current configuration.

    Shows all configuration settings in a readable format.

    Examples:

        # Show configuration
        krag config show

        # Show custom config
        krag config show --config /path/to/config.yaml
    """
    try:
        config_manager = ConfigManager()
        try:
            config = config_manager.load(config_path)
        except FileNotFoundError:
            console.print("[red]Configuration not found. Run 'krag init' first.[/red]")
            exit_with_code(1)

        # Display as formatted JSON
        config_dict = config.model_dump()
        console.print_json(json.dumps(config_dict, indent=2, default=str))

    except Exception as e:
        console.print(f"[red]Failed to show configuration: {e}[/red]")
        exit_with_code(1)


@config_app.command("validate")
def config_validate(
    config_path: Path = typer.Option(
        Path.home() / ".krag" / "config.yaml",
        "--config",
        "-c",
        help="Configuration file path",
    ),
) -> None:
    """Validate configuration file.

    Checks that the configuration file is valid and all
    required fields are present with correct types.

    Examples:

        # Validate configuration
        krag config validate

        # Validate custom config
        krag config validate --config /path/to/config.yaml
    """
    try:
        config_manager = ConfigManager()

        if not config_path.exists():
            console.print(f"[red]Configuration file not found: {config_path}[/red]")
            exit_with_code(1)

        # Try to load and validate
        try:
            config = config_manager.load(config_path)
            config_manager.validate(config)
            console.print("[green]✓ Configuration is valid[/green]")

            # Show warnings for missing directories
            missing = []
            for dir_path in config.directory_paths:
                if not dir_path.exists():
                    missing.append(str(dir_path))

            if missing:
                console.print(
                    f"\n[yellow]Warning: {len(missing)} configured directories do not exist:[/yellow]"
                )
                for dir_path in missing:
                    console.print(f"  - {dir_path}")

        except Exception as e:
            console.print(f"[red]✗ Configuration is invalid: {e}[/red]")
            exit_with_code(1)

    except Exception as e:
        console.print(f"[red]Failed to validate configuration: {e}[/red]")
        exit_with_code(1)


@config_app.command("edit")
def config_edit(
    config_path: Path = typer.Option(
        Path.home() / ".krag" / "config.yaml",
        "--config",
        "-c",
        help="Configuration file path",
    ),
    editor: str = typer.Option(
        None,
        "--editor",
        "-e",
        help="Editor to use (default: $EDITOR env var)",
        envvar="EDITOR",
    ),
) -> None:
    """Edit configuration file in default editor.

    Opens the configuration file in your default text editor.
    Uses $EDITOR environment variable or falls back to nano/vim.

    Examples:

        # Edit with default editor
        krag config edit

        # Edit with specific editor
        krag config edit --editor vim

        # Edit custom config
        krag config edit --config /path/to/config.yaml
    """
    try:
        if not config_path.exists():
            console.print(f"[red]Configuration file not found: {config_path}[/red]")
            console.print("Run 'krag init' to create it first.")
            exit_with_code(1)

        # Determine editor
        if not editor:
            # Try common editors
            for fallback in ["nano", "vim", "vi"]:
                try:
                    subprocess.run(
                        ["which", fallback],
                        check=True,
                        capture_output=True,
                    )
                    editor = fallback
                    break
                except subprocess.CalledProcessError:
                    continue

        if not editor:
            console.print("[red]No editor found. Set $EDITOR or use --editor[/red]")
            exit_with_code(1)

        # Open editor
        console.print(f"[cyan]Opening {config_path} in {editor}...[/cyan]")
        subprocess.run([editor, str(config_path)], check=True)

        # Validate after edit
        console.print("\n[cyan]Validating configuration...[/cyan]")
        config_manager = ConfigManager()
        try:
            config = config_manager.load(config_path)
            config_manager.validate(config)
            console.print("[green]✓ Configuration is valid[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Configuration may be invalid: {e}[/yellow]")

    except subprocess.CalledProcessError:
        console.print("[red]Editor exited with error[/red]")
        exit_with_code(1)
    except Exception as e:
        console.print(f"[red]Failed to edit configuration: {e}[/red]")
        exit_with_code(1)


if __name__ == "__main__":
    app()
