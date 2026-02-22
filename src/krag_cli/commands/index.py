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
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for indexing to complete"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Trigger indexing on kragd.

    Returns immediately by default. Use --wait to poll until complete.
    """
    import json
    import time

    from krag_cli.main import _get_client

    if full:
        mode = "full"

    client = _get_client(host, port)
    try:
        payload: dict[str, Any] = {"mode": mode, "dry_run": dry_run}
        if directory:
            payload["directories"] = list(directory)
        if file_type:
            payload["file_types"] = list(file_type)
        if exclude:
            payload["exclude_patterns"] = list(exclude)

        result = client.post("/index", json=payload)

        if output_json and not wait:
            console.print(json.dumps(result, indent=2))
            return

        status = result.get("status", "unknown")
        job_id = result.get("job_id", "")

        if status == "running":
            console.print(
                f"[yellow]Indexing started[/yellow] ({mode} mode)"
            )
            if job_id:
                console.print(f"[dim]Job {job_id}[/dim]")

            if not wait:
                console.print(
                    "[dim]Use 'krag index-status' to check progress, "
                    "or 'krag index --wait' to wait for completion.[/dim]"
                )
                return

            # Poll for completion
            console.print("[dim]Waiting for indexing to complete...[/dim]")
            poll_interval = 5.0
            while True:
                time.sleep(poll_interval)
                try:
                    status_result = client._get("/index/status")
                    # Handle list response (multiple results)
                    if isinstance(status_result, list):
                        status_result = status_result[-1]
                    current_status = status_result.get("status", "unknown")
                    if current_status in ("completed", "failed"):
                        if output_json:
                            console.print(json.dumps(status_result, indent=2))
                        else:
                            _display_index_result(status_result)
                        return
                    # Still running — show progress dot
                    scanned = status_result.get("files_scanned", 0)
                    processed = status_result.get("files_processed", 0)
                    if scanned > 0:
                        console.print(
                            f"[dim]  ...indexing in progress "
                            f"({processed}/{scanned} files processed)[/dim]"
                        )
                    else:
                        console.print("[dim]  ...indexing in progress[/dim]")
                except Exception:
                    console.print("[dim]  ...waiting (server busy)[/dim]")
        else:
            # Completed synchronously (shouldn't happen with new design, but handle it)
            if output_json:
                console.print(json.dumps(result, indent=2))
            else:
                _display_index_result(result)

    except (ConnectionError, RuntimeError) as exc:
        import logging

        logging.getLogger(__name__).debug("Index request failed", exc_info=True)
        console.print(f"[red]Fatal:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


def index_status_command(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Show the status of indexing jobs."""
    import json

    from krag_cli.main import _get_client

    client = _get_client(host, port)
    try:
        result = client._get("/index/status")

        if output_json:
            console.print(json.dumps(result, indent=2))
            return

        # Handle single result (dict) or multiple results (list)
        if isinstance(result, list):
            for i, job in enumerate(result):
                if i > 0:
                    console.print()  # blank line between jobs
                _display_index_result(job)
        else:
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

    job_id = result.get("job_id", "")
    if job_id and job_id != "none":
        console.print(f"[dim]Job {job_id}[/dim]")

    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Files Scanned", str(result.get("files_scanned", 0)))
    table.add_row("Files Processed", str(result.get("files_processed", 0)))
    skipped_unchanged = result.get("files_skipped_unchanged", 0)
    skipped_other = result.get("files_skipped_other", 0)
    skipped_total = result.get("files_skipped", skipped_unchanged + skipped_other)
    if skipped_unchanged or skipped_other:
        table.add_row("Skipped (no change)", str(skipped_unchanged))
        table.add_row("Skipped (other)", str(skipped_other))
    else:
        table.add_row("Files Skipped", str(skipped_total))
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
