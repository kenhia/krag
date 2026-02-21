"""krag CLI that delegates to kragd via HTTP.

This is the ``krag`` entry point when the service architecture is active.
Commands like ``query`` and ``index`` send requests to kragd.  Management
sub-apps (config, plugin, gpu, log) are re-exported from the existing
``krag.cli`` package unchanged.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

# Suppress verbose output from transformers library before importing anything else
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import typer
from rich.console import Console

from krag import __version__

if TYPE_CHECKING:
    from krag_cli.client import KragClient

console = Console()

app = typer.Typer(
    name="krag",
    help="krag — local RAG assistant (service-backed CLI)",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


# ── Delegated management sub-apps (unchanged from krag.cli) ──

from krag.cli.config import config_app  # noqa: E402
from krag.cli.gpu import gpu_app  # noqa: E402
from krag.cli.log import log_app  # noqa: E402
from krag.cli.plugin import plugin_app  # noqa: E402

app.add_typer(config_app, name="config")
app.add_typer(plugin_app, name="plugin")
app.add_typer(gpu_app, name="gpu")
app.add_typer(log_app, name="log")


# ── helpers ─────────────────────────────────────


def _get_client(
    host: str | None = None,
    port: int | None = None,
    timeout: float = 60.0,
) -> KragClient:
    """Create a KragClient, reading config if host/port not specified."""
    from krag_cli.client import KragClient
    from krag_cli.config import read_service_config

    if host is None or port is None:
        cfg_host, cfg_port = read_service_config()
        host = host or cfg_host
        port = port or cfg_port

    return KragClient(host=host, port=port, timeout=timeout)


# ── version callback ───────────────────────────


def _version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"krag version {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """krag — local RAG assistant."""


# ── query command (from commands module) ───────

from krag_cli.commands.debug import debug_app  # noqa: E402
from krag_cli.commands.query import query_command  # noqa: E402

app.command(name="query")(query_command)
app.add_typer(debug_app, name="debug")


# ── index command (from commands module) ───────

from krag_cli.commands.index import index_command, index_status_command  # noqa: E402

app.command(name="index")(index_command)
app.command(name="index-status")(index_status_command)


# ── status and health commands (from commands module) ──

from krag_cli.commands.status import health_command, status_command  # noqa: E402

app.command(name="status")(status_command)
app.command(name="health")(health_command)


# ── start and stop commands (from commands module) ──

from krag_cli.commands.service import start_command, stop_command  # noqa: E402

app.command(name="start")(start_command)
app.command(name="stop")(stop_command)


# ── shutdown command (backward compat, delegates to stop) ──


@app.command()
def shutdown(
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Send shutdown signal to kragd."""
    client = _get_client(host, port)
    try:
        client.shutdown()
        console.print("[green]Shutdown signal sent[/green]")
    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()
