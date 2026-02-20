"""Log management CLI commands."""

import shutil

import typer
from rich.console import Console

from krag.config.logging import get_log_file_path

log_app = typer.Typer(
    name="log",
    help="Log file management",
    add_completion=False,
)

console = Console()

_MAX_BACKUPS = 5


@log_app.command(name="rotate")
def rotate() -> None:
    """Archive the current log file and start fresh.

    Shifts existing backups: krag.log.4 → krag.log.5, ..., krag.log → krag.log.1.
    Creates a new empty krag.log. Maximum 5 backup files.

    Examples:

        krag log rotate
    """
    log_file = get_log_file_path()

    if not log_file.exists():
        console.print("[yellow]No log file to rotate[/yellow]")
        return

    # Shift existing backups (5 → delete, 4 → 5, ... , 1 → 2)
    for i in range(_MAX_BACKUPS, 0, -1):
        backup = log_file.with_suffix(f".log.{i}")
        if i == _MAX_BACKUPS and backup.exists():
            backup.unlink()
        elif backup.exists():
            backup.rename(log_file.with_suffix(f".log.{i + 1}"))

    # Rotate current log → .1
    shutil.move(str(log_file), str(log_file.with_suffix(".log.1")))

    # Create fresh empty log
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.touch()

    console.print(f"Log rotated: {log_file.with_suffix('.log.1')}")


@log_app.command(name="clear")
def clear() -> None:
    """Truncate the current log file to zero bytes.

    Examples:

        krag log clear
    """
    log_file = get_log_file_path()

    if not log_file.exists():
        console.print("[yellow]No log file found[/yellow]")
        return

    log_file.write_text("")
    console.print(f"Log cleared: {log_file}")


@log_app.command(name="path")
def path() -> None:
    """Print the absolute path to the current log file.

    Examples:

        krag log path
    """
    log_file = get_log_file_path()
    suffix = "(exists)" if log_file.exists() else "(not found)"
    console.print(f"{log_file} {suffix}")
