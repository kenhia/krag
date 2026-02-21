"""CLI index command.

T048: `krag index` with --full, --dir, --type, --exclude, --dry-run flags
and Rich stats display.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def index_command(
    mode: str = typer.Option("incremental", "--mode", "-m", help="full or incremental"),
    full: bool = typer.Option(
        False, "--full", "-f", help="Run full reindex (shortcut for --mode full)"
    ),
    directory: list[str] | None = typer.Option(None, "--dir", "-d", help="Override directories"),
    file_type: list[str] | None = typer.Option(None, "--type", "-t", help="Filter file extensions"),
    exclude: list[str] | None = typer.Option(None, "--exclude", "-e", help="Exclusion patterns"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without indexing"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Trigger indexing on kragd.

    Uses already-loaded embedding models for efficient re-indexing.
    """
    import json

    from krag_cli.main import _get_client

    if full:
        mode = "full"

    client = _get_client(host, port, timeout=600.0)
    try:
        payload: dict[str, Any] = {"mode": mode, "dry_run": dry_run}
        if directory:
            payload["directories"] = list(directory)
        if file_type:
            payload["file_types"] = list(file_type)
        if exclude:
            payload["exclude_patterns"] = list(exclude)

        result = client.post("/index", json=payload)

        if output_json:
            console.print(json.dumps(result, indent=2))
            return

        _display_index_result(result)

    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


def index_status_command(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Show the status of the last indexing job."""
    import json

    from krag_cli.main import _get_client

    client = _get_client(host, port)
    try:
        result = client._get("/index/status")

        if output_json:
            console.print(json.dumps(result, indent=2))
            return

        _display_index_result(result)

    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


def _display_index_result(result: dict[str, Any]) -> None:
    """Display indexing results as a Rich table."""
    status = result.get("status", "unknown")
    mode = result.get("mode", "unknown")
    dry_run = result.get("dry_run", False)

    status_color = "green" if status == "completed" else "red" if status == "failed" else "yellow"
    title = f"Indexing {'(dry run) ' if dry_run else ''}{status}"

    console.print(f"\n[{status_color}]{title}[/{status_color}] ({mode} mode)")

    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Job ID", result.get("job_id", ""))
    table.add_row("Files Scanned", str(result.get("files_scanned", 0)))
    table.add_row("Files Processed", str(result.get("files_processed", 0)))
    table.add_row("Files Skipped", str(result.get("files_skipped", 0)))
    table.add_row("Files Errored", str(result.get("files_errored", 0)))
    table.add_row("Chunks Created", str(result.get("chunks_created", 0)))
    table.add_row("Vectors Stored", str(result.get("vectors_stored", 0)))
    table.add_row("Duration", f"{result.get('duration_seconds', 0):.1f}s")

    console.print(table)

    # Display errors if any
    errors = result.get("errors", [])
    if errors:
        console.print(f"\n[red]Errors ({len(errors)}):[/red]")
        for err in errors:
            console.print(
                f"  [dim]{err.get('file_path', '')}[/dim]: {err.get('error_message', '')}"
            )
