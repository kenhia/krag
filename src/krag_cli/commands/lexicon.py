"""CLI lexicon commands for the krag service-backed client.

Delegates to POST /lexicon/refresh on kragd.
"""

from __future__ import annotations

import typer
from rich.console import Console

lexicon_app = typer.Typer(
    name="lexicon",
    help="Manage the domain lexicon",
    no_args_is_help=True,
)

console = Console()


@lexicon_app.command(name="refresh")
def lexicon_refresh(
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Reload the domain lexicon from disk."""
    from krag_cli.client import KragClient
    from krag_cli.config import read_service_config

    if host is None or port is None:
        cfg_host, cfg_port = read_service_config()
        host = host or cfg_host
        port = port or cfg_port

    client = KragClient(host=host, port=port)
    try:
        resp = client._post("/lexicon/refresh", {})
        entries = resp.get("entries", 0)
        status = resp.get("status", "unknown")
        console.print(f"[green]Lexicon {status}[/green]: {entries} entries loaded")
    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        detail = str(exc)
        if "400" in detail or "No lexicon" in detail:
            console.print("[red]Error:[/red] No lexicon configured on the service")
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()
