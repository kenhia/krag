"""Index command for CLI - manages document indexing."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from krag.cli.utils import exit_with_code
from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir
from krag.models.indexing_job import IndexingJob
from krag.orchestration.indexer import IndexingOrchestrator

logger = logging.getLogger(__name__)
console = Console()


def index_command(
    directories: list[Path] | None = typer.Option(
        None,
        "--dir",
        "-d",
        help="Directories to index (overrides config)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    full: bool = typer.Option(
        False,
        "--full/--incremental",
        help="Full reindex or incremental update (default: incremental)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be indexed without actually indexing",
    ),
    file_types: list[str] | None = typer.Option(
        None,
        "--type",
        "-t",
        help="File types to include (e.g., .py, .md)",
    ),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Patterns to exclude",
    ),
    vector_store_path: Path | None = typer.Option(
        None,
        "--vector-store",
        help="Path to vector store (overrides config)",
    ),
) -> None:
    """Index documents into the knowledge base.

    Scans specified directories for supported file types, extracts text,
    generates embeddings, and stores vectors for later retrieval.

    By default, performs incremental indexing (only processes new/modified files).

    Examples:

        # Incremental index using configuration (default)
        krag index

        # Full reindex from scratch
        krag index --full

        # Index specific directories
        krag index --dir ~/Documents --dir ~/Code

        # Dry run to see what would be indexed
        krag index --dry-run

        # Index only specific file types
        krag index --type .py --type .md
    """
    try:
        # Load configuration
        config_manager = ConfigManager()

        # Try TOML first (primary format), fall back to YAML (legacy)
        config_dir = get_krag_config_dir()
        config_toml = config_dir / "config.toml"
        config_yaml = config_dir / "config.yaml"

        if config_toml.exists():
            config_path = config_toml
        elif config_yaml.exists():
            config_path = config_yaml
        else:
            console.print("[red]Configuration not found. Run 'krag init' first.[/red]")
            exit_with_code(1)

        try:
            config = config_manager.load(config_path)
        except FileNotFoundError:
            console.print("[red]Configuration not found. Run 'krag init' first.[/red]")
            exit_with_code(1)

        # Override config with CLI arguments
        if directories:
            dirs_to_index = directories
        else:
            dirs_to_index = config.directory_paths

        if not dirs_to_index:
            console.print("[red]No directories specified to index.[/red]")
            console.print("Either specify --dir or configure directories in config.")
            exit_with_code(1)

        # Prepare orchestrator configuration
        vector_store = vector_store_path or config.vector_store_path
        supported_types = file_types or config.supported_file_types
        exclusion_patterns = exclude or config.exclusion_patterns

        # Dry run mode
        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")
            _perform_dry_run(dirs_to_index, supported_types, exclusion_patterns)
            return

        # Create orchestrator
        console.print("[cyan]Initializing indexing pipeline...[/cyan][dim](be patient)[/dim]")
        orchestrator = IndexingOrchestrator(
            directory_paths=dirs_to_index,
            vector_store_path=vector_store,
            supported_file_types=supported_types,
            exclusion_patterns=exclusion_patterns,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            collection_name=config.collection_name,
            embedding_model=config.embedding_model,
            device=config.embedding_device,
        )

        # Show configuration
        console.print(f"[cyan]Directories:[/cyan] {', '.join(str(d) for d in dirs_to_index)}")
        console.print(f"[cyan]Vector store:[/cyan] {vector_store or 'in-memory'}")
        console.print(f"[cyan]Mode:[/cyan] {'Full reindex' if full else 'Incremental'}\n")

        # Enhanced Progress tracking with ETA and completion count
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TextColumn("files"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        )

        # Track progress state and timing for rate calculation
        progress_task_id = None
        start_time = None

        def progress_callback(current: int, total: int, stage: str) -> None:
            """Update progress bar with enhanced information."""
            nonlocal progress_task_id, start_time

            if progress_task_id is None:
                progress_task_id = progress.add_task(f"[cyan]{stage}[/cyan]", total=total)
                start_time = progress.get_time()
            else:
                # Calculate processing rate if applicable
                if current > 0 and start_time:
                    elapsed = progress.get_time() - start_time
                    rate = current / elapsed if elapsed > 0 else 0
                    if rate > 1:
                        rate_text = f" ({rate:.1f}/sec)"
                    else:
                        rate_text = ""
                    description = f"[cyan]{stage}[/cyan]{rate_text}"
                else:
                    description = f"[cyan]{stage}[/cyan]"

                progress.update(
                    progress_task_id,
                    completed=current,
                    description=description,
                )

        # Run indexing
        with progress:
            if full:
                result = orchestrator.index_full(progress_callback=progress_callback)
            else:
                result = orchestrator.index_incremental(progress_callback=progress_callback)

        # Close orchestrator resources
        orchestrator.close()

        # Display results
        _display_results(result, full)

    except KeyboardInterrupt:
        console.print("\n[yellow]Indexing cancelled by user[/yellow]")
        exit_with_code(130)
    except Exception as e:
        logger.exception("Indexing failed")
        console.print(f"[red]Indexing failed: {e}[/red]")
        exit_with_code(1)


def _perform_dry_run(
    directories: list[Path],
    supported_types: list[str] | None,
    exclusion_patterns: list[str] | None,
) -> None:
    """Perform a dry run to show what would be indexed.

    Args:
        directories: Directories to scan
        supported_types: File types to include
        exclusion_patterns: Patterns to exclude
    """
    from krag.discovery.scanner import FileScanner

    console.print("[cyan]Scanning directories...[/cyan]\n")

    scanner = FileScanner(
        directory_paths=directories,
        supported_file_types=supported_types,
        exclusion_patterns=exclusion_patterns,
    )

    files = scanner.scan()

    # Display summary
    console.print(f"[green]Found {len(files)} files to index:[/green]\n")

    # Group by file type
    by_type: dict[str, int] = {}
    for file_meta in files:
        ext = file_meta.file_type
        by_type[ext] = by_type.get(ext, 0) + 1

    # Display table
    table = Table(title="Files by Type")
    table.add_column("Extension", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for ext, count in sorted(by_type.items()):
        table.add_row(ext, str(count))

    console.print(table)
    console.print(f"\n[cyan]Total:[/cyan] {len(files)} files")


def _display_results(result: IndexingJob, full: bool) -> None:
    """Display indexing results summary.

    Args:
        result: IndexingJob from orchestrator
        full: Whether this was a full reindex
    """
    console.print("\n" + "=" * 60)
    console.print("[bold green]Indexing Complete![/bold green]")
    console.print("=" * 60 + "\n")

    # Create results table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Files discovered", str(result.files_discovered))
    table.add_row("Files processed", str(result.files_processed))

    if not full:
        # Show incremental stats
        table.add_row("Files added", str(result.files_added))
        table.add_row("Files modified", str(result.files_modified))
        table.add_row("Files deleted", str(result.files_deleted))
        table.add_row("Files skipped", str(result.files_skipped))

    table.add_row("Chunks generated", str(result.chunks_generated))
    table.add_row("Embeddings created", str(result.embeddings_created))

    error_count = result.files_errored
    if error_count > 0:
        table.add_row("Errors", f"[red]{error_count}[/red]")

    console.print(table)

    # Display errors if any
    if error_count > 0:
        console.print(f"\n[yellow]Encountered {error_count} errors:[/yellow]\n")

        for i, error in enumerate(result.error_summary[:10], 1):  # Show first 10
            console.print(
                f"  {i}. [red]{error.file_path}[/red] ({error.error_type}): {error.error_message}"
            )

        if len(result.error_summary) > 10:
            console.print(f"\n  ... and {len(result.error_summary) - 10} more errors")

    console.print()
