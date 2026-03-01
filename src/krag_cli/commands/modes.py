"""CLI modes commands for the krag service-backed client.

Delegates to GET /modes and GET /modes/{name} on kragd.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

modes_app = typer.Typer(
    name="modes",
    help="List and inspect retrieval modes",
    no_args_is_help=True,
)

console = Console()


@modes_app.command(name="list")
def modes_list(
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List all available retrieval modes from the kragd service."""
    import json

    from krag_cli.client import KragClient
    from krag_cli.config import read_service_config

    if host is None or port is None:
        cfg_host, cfg_port = read_service_config()
        host = host or cfg_host
        port = port or cfg_port

    client = KragClient(host=host, port=port)
    try:
        resp = client._get("/modes")

        if output_json:
            console.print(json.dumps(resp, indent=2))
            return

        modes = resp.get("modes", [])

        if not modes:
            console.print("[yellow]No modes registered.[/yellow]")
            raise typer.Exit(0)

        table = Table(title="Retrieval Modes")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description")
        table.add_column("Collections", style="green")
        table.add_column("LLM", style="magenta")
        table.add_column("Preset", style="blue")

        for m in modes:
            colls = ", ".join(m.get("collections", []))
            table.add_row(
                m["name"],
                m.get("description", "") or "—",
                colls,
                m.get("llm_slot", ""),
                m.get("preset", ""),
            )

        console.print(table)
    except ConnectionError as exc:
        if output_json:
            console.print(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


@modes_app.command(name="show")
def modes_show(
    name: str = typer.Argument(..., help="Mode name"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Show full details for a specific mode from the kragd service."""
    import json

    from krag_cli.client import KragClient
    from krag_cli.config import read_service_config

    if host is None or port is None:
        cfg_host, cfg_port = read_service_config()
        host = host or cfg_host
        port = port or cfg_port

    client = KragClient(host=host, port=port)
    try:
        mode = client._get(f"/modes/{name}")

        if output_json:
            console.print(json.dumps(mode, indent=2))
            return

        console.print(f"\n[bold cyan]{mode['name']}[/bold cyan]")
        desc = mode.get("description", "")
        if desc:
            console.print(f"  {desc}\n")
        else:
            console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="dim")
        table.add_column("Value")

        colls = mode.get("collections", {})
        if isinstance(colls, dict):
            colls_str = ", ".join(f"{k}: {v}" for k, v in sorted(colls.items()))
        else:
            colls_str = ", ".join(colls)
        table.add_row("Collections", colls_str)
        table.add_row("LLM slot", mode.get("llm_slot", ""))
        table.add_row("Preset", mode.get("preset", ""))
        table.add_row("top_k", str(mode.get("top_k", "")))
        table.add_row("similarity_threshold", str(mode.get("similarity_threshold", "")))
        table.add_row("Critic enabled", str(mode.get("critic_enabled", "")))
        table.add_row("Critic threshold", str(mode.get("critic_threshold", "")))

        console.print(table)
        console.print()
    except ConnectionError as exc:
        if output_json:
            console.print(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except RuntimeError as exc:
        if output_json:
            console.print(json.dumps({"error": str(exc)}))
            raise typer.Exit(1) from exc
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()
