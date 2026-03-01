"""CLI status and health commands.

T031: Rich-formatted status display with LLM slots, VRAM, uptime.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def status_command(
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Show kragd service status with model info, VRAM, and uptime."""
    import json

    from krag_cli.client import KragClient
    from krag_cli.config import read_service_config

    if host is None or port is None:
        cfg_host, cfg_port = read_service_config()
        host = host or cfg_host
        port = port or cfg_port

    client = KragClient(host=host, port=port)
    try:
        data = client.status()

        if output_json:
            console.print(json.dumps(data, indent=2))
            return

        # Header
        version = data.get("version", "?")
        uptime = data.get("uptime_seconds", 0)
        uptime_str = _format_uptime(uptime)
        console.print(
            f"\n[bold green]kragd[/bold green] v{version}  [dim]uptime: {uptime_str}[/dim]\n"
        )

        # LLM table
        llm_slots = data.get("llm", {})
        if llm_slots:
            table = Table(title="LLM Slots", show_header=True, header_style="bold cyan")
            table.add_column("Slot", style="bold")
            table.add_column("Model")
            table.add_column("Loaded")
            table.add_column("Primary")
            table.add_column("Idle Timeout")

            for slot_name, slot in llm_slots.items():
                loaded = "[green]yes[/green]" if slot.get("loaded") else "[dim]no[/dim]"
                primary = "[yellow]★[/yellow]" if slot.get("primary") else ""
                model = slot.get("model", "—") or "—"
                timeout = str(slot.get("idle_timeout_s", "—") or "—")
                table.add_row(slot_name, model, loaded, primary, timeout)

            console.print(table)
            console.print()

        # Embedding models
        models = data.get("embedding_models", [])
        if models:
            console.print(f"[bold]Embeddings:[/bold] {', '.join(models)}")

        # Vector store
        vs = data.get("vector_store", {})
        spaces = vs.get("named_spaces", [])
        spaces_str = f" (spaces: {', '.join(spaces)})" if spaces else ""
        console.print(
            f"[bold]Vectors:[/bold] {vs.get('total_vectors', 0):,} "
            f"in [cyan]{vs.get('collection', '?')}[/cyan]{spaces_str}"
        )

        # VRAM
        vram = data.get("vram")
        if vram:
            console.print(
                f"[bold]VRAM:[/bold] {vram.get('used_mb', 0):,}MB / "
                f"{vram.get('total_mb', 0):,}MB "
                f"({vram.get('free_mb', 0):,}MB free)"
            )

        console.print()

    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


def health_command(
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Check if kragd is running and healthy."""
    import json

    from krag_cli.client import KragClient
    from krag_cli.config import read_service_config

    if host is None or port is None:
        cfg_host, cfg_port = read_service_config()
        host = host or cfg_host
        port = port or cfg_port

    client = KragClient(host=host, port=port)
    try:
        if output_json:
            try:
                data = client._get("/health")
                console.print(json.dumps(data, indent=2))
            except Exception:
                console.print(json.dumps({"status": "error", "error": "kragd is not responding"}))
                raise typer.Exit(1) from None
            return

        if client.health():
            console.print("[green]kragd is healthy[/green]")
        else:
            console.print("[red]kragd is not responding[/red]")
            raise typer.Exit(1)
    except ConnectionError as exc:
        if output_json:
            console.print(json.dumps({"status": "error", "error": str(exc)}))
        else:
            console.print("[red]kragd is not responding[/red]")
        raise typer.Exit(1) from exc
    finally:
        client.close()


def _format_uptime(seconds: float) -> str:
    """Format uptime seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"
