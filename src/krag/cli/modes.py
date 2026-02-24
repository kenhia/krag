"""CLI commands for listing and showing retrieval modes.

Works for both krag-direct (calls ModeRegistry directly) and
the service-backed krag CLI (delegates from krag_cli.commands.modes).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

modes_app = typer.Typer(
    name="modes",
    help="List and inspect retrieval modes",
    no_args_is_help=True,
)

console = Console()


def _build_registry(config_path: Path | None = None):
    """Build a ModeRegistry from builtins + user config."""
    from krag.modes.mode_registry import ModeRegistry

    registry = ModeRegistry()
    registry.load_builtins()

    # Try to load user modes from config
    try:
        from krag.config.settings import ConfigManager

        if config_path:
            config = ConfigManager.load(config_path)
        else:
            config = ConfigManager.find_and_load()
        if config.modes_dir:
            registry.load_user_modes(config.modes_dir)
    except Exception:
        pass

    return registry


@modes_app.command(name="list")
def modes_list(
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
) -> None:
    """List all available retrieval modes."""
    registry = _build_registry(config_path)
    modes = registry.list_modes()

    if not modes:
        console.print("[yellow]No modes registered.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Retrieval Modes")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Collections", style="green")
    table.add_column("LLM", style="magenta")
    table.add_column("Preset", style="blue")
    table.add_column("top_k", justify="right")

    for m in modes:
        colls = ", ".join(sorted(m.collections.keys()))
        table.add_row(
            m.name,
            m.description or "—",
            colls,
            m.llm_slot,
            m.preset,
            str(m.top_k),
        )

    console.print(table)


@modes_app.command(name="show")
def modes_show(
    name: str = typer.Argument(..., help="Mode name to display"),
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
) -> None:
    """Show full details for a specific mode."""
    registry = _build_registry(config_path)

    try:
        mode = registry.get(name)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"\n[bold cyan]{mode.name}[/bold cyan]")
    if mode.description:
        console.print(f"  {mode.description}\n")
    else:
        console.print()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    # Collections with weights
    colls = ", ".join(f"{k}: {v}" for k, v in sorted(mode.collections.items()))
    table.add_row("Collections", colls)
    table.add_row("LLM slot", mode.llm_slot)
    table.add_row("Preset", mode.preset)
    table.add_row("top_k", str(mode.top_k))
    table.add_row("similarity_threshold", str(mode.similarity_threshold))
    table.add_row("Critic enabled", str(mode.critic_enabled))
    table.add_row("Critic threshold", str(mode.critic_threshold))

    console.print(table)
    console.print()
