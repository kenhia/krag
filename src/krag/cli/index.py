"""Index command for CLI - manages document indexing."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from krag.cli.utils import exit_with_code
from krag.config.settings import ConfigManager
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
        True,
        "--full/--incremental",
        help="Full reindex or incremental update",
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

    Examples:

        # Index using configuration
        krag index

        # Index specific directories
        krag index --dir ~/Documents --dir ~/Code

        # Incremental update
        krag index --incremental

        # Dry run to see what would be indexed
        krag index --dry-run

        # Index only specific file types
        krag index --type .py --type .md
    """
    try:
        # Load configuration
        config_manager = ConfigManager()
        config_path = Path.home() / ".config" / "krag" / "config.yaml"

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
        console.print("[cyan]Initializing indexing pipeline...[/cyan]")
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

        # Progress tracking
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("files"),
            TimeElapsedColumn(),
            console=console,
        )

        # Track progress state
        progress_task_id = None

        def progress_callback(current: int, total: int, stage: str) -> None:
            """Update progress bar."""
            nonlocal progress_task_id

            if progress_task_id is None:
                progress_task_id = progress.add_task(f"[cyan]{stage}[/cyan]", total=total)
            else:
                progress.update(
                    progress_task_id,
                    completed=current,
                    description=f"[cyan]{stage}[/cyan]",
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


def _display_results(result: dict, full: bool) -> None:
    """Display indexing results summary.

    Args:
        result: Result dictionary from orchestrator
        full: Whether this was a full reindex
    """
    console.print("\n" + "=" * 60)
    console.print("[bold green]Indexing Complete![/bold green]")
    console.print("=" * 60 + "\n")

    # Create results table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Files discovered", str(result.get("files_discovered", 0)))
    table.add_row("Files processed", str(result.get("files_processed", 0)))

    if not full and "files_skipped" in result:
        table.add_row("Files skipped", str(result["files_skipped"]))

    table.add_row("Chunks created", str(result.get("chunks_created", 0)))
    table.add_row("Embeddings generated", str(result.get("embeddings_generated", 0)))
    table.add_row("Vectors stored", str(result.get("vectors_stored", 0)))

    error_count = result.get("errors", 0)
    if error_count > 0:
        table.add_row("Errors", f"[red]{error_count}[/red]")

    console.print(table)

    # Display errors if any
    if error_count > 0:
        console.print(f"\n[yellow]Encountered {error_count} errors:[/yellow]\n")

        error_details = result.get("error_details", [])
        for i, error in enumerate(error_details[:10], 1):  # Show first 10
            file_path = error.get("file", error.get("directory", "unknown"))
            stage = error.get("stage", "unknown")
            error_msg = error.get("error", "unknown error")
            console.print(f"  {i}. [red]{file_path}[/red] ({stage}): {error_msg}")

        if len(error_details) > 10:
            console.print(f"\n  ... and {len(error_details) - 10} more errors")

    console.print()
