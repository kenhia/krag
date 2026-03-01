"""CLI start and stop commands for kragd service lifecycle.

T032: `krag start` delegates to kragd, `krag stop` reads PID and sends SIGTERM.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys

import typer
from rich.console import Console

console = Console()


def start_command(
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    host: str | None = typer.Option(None, "--host", help="Bind host"),
    port: int | None = typer.Option(None, "--port", help="Bind port"),
    daemon: bool = typer.Option(True, "--daemon/--no-daemon", help="Run as background daemon"),
) -> None:
    """Start the kragd service."""
    # Check if already running
    from kragd.pid import get_pid_path, is_pid_alive, read_pid

    pid_path = get_pid_path()
    existing_pid = read_pid(pid_path)
    if existing_pid is not None and is_pid_alive(existing_pid):
        console.print(f"[yellow]kragd is already running[/yellow] (PID {existing_pid})")
        raise typer.Exit(0)

    # Build kragd command
    cmd = [sys.executable, "-m", "kragd"]
    if config:
        cmd.extend(["--config", config])
    if host:
        cmd.extend(["--host", host])
    if port:
        cmd.extend(["--port", str(port)])
    if daemon:
        cmd.append("--daemon")

    if daemon:
        # Start as background process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        console.print(f"[green]kragd starting[/green] (PID {process.pid})")
    else:
        # Run in foreground (blocking)
        console.print("[green]Starting kragd in foreground...[/green]")
        try:
            subprocess.run(cmd, check=True)
        except KeyboardInterrupt:
            console.print("\n[yellow]kragd stopped[/yellow]")
        except subprocess.CalledProcessError as exc:
            console.print(f"[red]kragd exited with code {exc.returncode}[/red]")
            raise typer.Exit(exc.returncode) from exc


def stop_command(
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
    force: bool = typer.Option(False, "--force", "-f", help="Force kill with SIGKILL"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Stop the kragd service."""
    import json

    from kragd.pid import get_pid_path, is_pid_alive, read_pid, remove_pid

    pid_path = get_pid_path()
    pid = read_pid(pid_path)

    if pid is None:
        # Try HTTP shutdown as fallback
        if output_json:
            _try_http_shutdown(host, port)
            console.print(json.dumps({"status": "not_running"}))
        else:
            _try_http_shutdown(host, port)
        return

    if not is_pid_alive(pid):
        remove_pid(pid_path)
        if output_json:
            console.print(json.dumps({"status": "stale_pid", "pid": pid}))
        else:
            console.print("[yellow]kragd is not running[/yellow] (stale PID file removed)")
        return

    # Send signal
    sig = signal.SIGKILL if force else signal.SIGTERM
    sig_name = "SIGKILL" if force else "SIGTERM"

    try:
        os.kill(pid, sig)
        if output_json:
            console.print(json.dumps({"status": "stopped", "pid": pid, "signal": sig_name}))
        else:
            console.print(f"[green]Sent {sig_name} to kragd[/green] (PID {pid})")
    except ProcessLookupError:
        if output_json:
            console.print(json.dumps({"status": "already_stopped", "pid": pid}))
        else:
            console.print("[yellow]kragd already stopped[/yellow]")
        remove_pid(pid_path)
    except PermissionError as exc:
        if output_json:
            console.print(
                json.dumps({"status": "error", "error": f"Permission denied for PID {pid}"})
            )
        else:
            console.print(f"[red]Permission denied:[/red] Cannot signal PID {pid}")
        raise typer.Exit(1) from exc


def _try_http_shutdown(host: str | None, port: int | None) -> None:
    """Attempt HTTP-based shutdown when no PID file exists."""
    try:
        from krag_cli.client import KragClient
        from krag_cli.config import read_service_config

        if host is None or port is None:
            cfg_host, cfg_port = read_service_config()
            host = host or cfg_host
            port = port or cfg_port

        client = KragClient(host=host, port=port, timeout=5.0)
        try:
            client.shutdown()
            console.print("[green]Shutdown signal sent[/green]")
        except ConnectionError:
            console.print("[yellow]kragd is not running[/yellow] (no PID file, not reachable)")
        finally:
            client.close()
    except Exception:
        console.print("[yellow]kragd is not running[/yellow]")
