"""Unit tests for stop_command --json flag (T015/US3).

Verifies that `krag stop --json` outputs valid JSON including
the kragd-not-running error case.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from krag_cli.commands.service import stop_command

runner = CliRunner()


def _invoke_stop(*args: str):
    """Invoke stop_command via Typer test runner."""
    import typer

    app = typer.Typer()
    app.command()(stop_command)
    return runner.invoke(app, list(args))


class TestStopJson:
    """stop_command --json output tests."""

    def test_json_flag_successful_stop(self) -> None:
        """--json should output JSON when kragd is stopped successfully."""
        with (
            patch("kragd.pid.read_pid") as mock_read_pid,
            patch("kragd.pid.is_pid_alive") as mock_alive,
            patch("kragd.pid.get_pid_path") as mock_path,
            patch("os.kill") as mock_kill,  # noqa: F841
        ):
            mock_path.return_value = "/tmp/test.pid"
            mock_read_pid.return_value = 12345
            mock_alive.return_value = True

            result = _invoke_stop("--json")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["status"] == "stopped" or "pid" in data

    def test_json_flag_not_running(self) -> None:
        """--json should output JSON error when kragd is not running."""
        with (
            patch("kragd.pid.read_pid") as mock_read_pid,
            patch("kragd.pid.get_pid_path") as mock_path,
            patch("krag_cli.commands.service._try_http_shutdown") as mock_http,
        ):
            mock_path.return_value = "/tmp/test.pid"
            mock_read_pid.return_value = None
            # _try_http_shutdown is called as fallback
            mock_http.return_value = None

            result = _invoke_stop("--json")
            data = json.loads(result.output)
            assert data.get("status") in ("not_running", "error") or "error" in data

    def test_json_flag_stale_pid(self) -> None:
        """--json should output JSON when PID file exists but process is dead."""
        with (
            patch("kragd.pid.read_pid") as mock_read_pid,
            patch("kragd.pid.is_pid_alive") as mock_alive,
            patch("kragd.pid.get_pid_path") as mock_path,
            patch("kragd.pid.remove_pid") as mock_remove,  # noqa: F841
        ):
            mock_path.return_value = "/tmp/test.pid"
            mock_read_pid.return_value = 99999
            mock_alive.return_value = False

            result = _invoke_stop("--json")
            data = json.loads(result.output)
            assert "status" in data

    def test_without_json_uses_rich_output(self) -> None:
        """Without --json, output should be human-readable."""
        with (
            patch("kragd.pid.read_pid") as mock_read_pid,
            patch("kragd.pid.is_pid_alive") as mock_alive,
            patch("kragd.pid.get_pid_path") as mock_path,
            patch("os.kill"),
        ):
            mock_path.return_value = "/tmp/test.pid"
            mock_read_pid.return_value = 12345
            mock_alive.return_value = True

            result = _invoke_stop()
            assert result.exit_code == 0
            with __import__("pytest").raises(json.JSONDecodeError):
                json.loads(result.output)
