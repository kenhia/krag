"""kragd entry point — ``python -m kragd`` or the ``kragd`` console script.

Supports three run modes:
  kragd                  — foreground (default)
  kragd --daemon         — background with PID file
  kragd --reload         — development with auto-reload
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from rich.console import Console

from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir, get_krag_runtime_dir

console = Console()

app = typer.Typer(
    name="kragd",
    help="krag RAG service daemon",
    no_args_is_help=False,
    pretty_exceptions_enable=False,
)


def _find_config() -> Path:
    """Locate the krag config file using standard search order."""
    candidates = [
        Path("krag.toml"),
        get_krag_config_dir() / "config.toml",
        get_krag_config_dir() / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to XDG default — will be created if needed
    return get_krag_config_dir() / "config.toml"


def _write_pid(pid_path: Path) -> None:
    """Write current PID to file."""
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))


def _remove_pid(pid_path: Path) -> None:
    """Remove PID file if it exists."""
    try:
        pid_path.unlink(missing_ok=True)
    except OSError:
        pass


@app.callback(invoke_without_command=True)
def main(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to krag config file (default: auto-detect)"
    ),
    host: str | None = typer.Option(None, "--host", help="Override bind host"),
    port: int | None = typer.Option(None, "--port", help="Override bind port"),
    daemon: bool = typer.Option(False, "--daemon", help="Run in background (daemonize)"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Start the kragd service daemon."""
    # Locate config
    config_path = config or _find_config()
    if not config_path.exists():
        console.print(f"[red]Error:[/red] Config file not found: {config_path}")
        console.print("Run 'krag config init' to create a default configuration.")
        raise typer.Exit(1)

    loaded_config = ConfigManager.load(config_path)

    resolved_host = host or loaded_config.service.host
    resolved_port = port or loaded_config.service.port

    # PID file management
    pid_path = get_krag_runtime_dir() / "kragd.pid"

    if daemon:
        _daemonize(config_path, resolved_host, resolved_port, pid_path)
    else:
        _run_foreground(config_path, resolved_host, resolved_port, pid_path, reload=reload)


def _run_foreground(
    config_path: Path,
    host: str,
    port: int,
    pid_path: Path,
    *,
    reload: bool = False,
) -> None:
    """Run uvicorn in the foreground."""
    import uvicorn

    _write_pid(pid_path)

    # Set config path as env var so the app factory can pick it up
    os.environ["KRAGD_CONFIG_PATH"] = str(config_path)

    try:
        uvicorn.run(
            "kragd.app:create_app_from_env",
            host=host,
            port=port,
            reload=reload,
            factory=True,
        )
    finally:
        _remove_pid(pid_path)


def _daemonize(config_path: Path, host: str, port: int, pid_path: Path) -> None:
    """Fork and run in background."""
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "kragd",
        "--config",
        str(config_path),
        "--host",
        host,
        "--port",
        str(port),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    console.print(f"kragd started in background (PID {proc.pid})")
    console.print(f"  Listening on http://{host}:{port}")
    console.print(f"  PID file: {pid_path}")


if __name__ == "__main__":
    app()
