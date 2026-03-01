"""Unit tests for health_command --json flag (T012/US3).

Verifies that `krag health --json` outputs valid JSON.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from krag_cli.commands.status import health_command

runner = CliRunner()


def _invoke_health(*args: str):
    """Invoke health_command via Typer test runner."""
    import typer

    app = typer.Typer()
    app.command()(health_command)
    return runner.invoke(app, list(args))


def _mock_client():
    """Patch KragClient and read_service_config together."""
    return (
        patch("krag_cli.client.KragClient"),
        patch("krag_cli.config.read_service_config", return_value=("localhost", 8742)),
    )


class TestHealthJson:
    """health_command --json output tests."""

    def test_json_flag_outputs_valid_json(self) -> None:
        """--json should output parseable JSON with status and version."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock.health.return_value = True
            mock._get.return_value = {"status": "healthy", "version": "1.0.0"}
            MockClient.return_value = mock

            result = _invoke_health("--json")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["status"] == "healthy"

    def test_json_flag_healthy_has_status_field(self) -> None:
        """JSON output must include 'status' key."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock.health.return_value = True
            mock._get.return_value = {"status": "healthy", "version": "1.0.0"}
            MockClient.return_value = mock

            result = _invoke_health("--json")
            data = json.loads(result.output)
            assert "status" in data

    def test_json_flag_not_responding(self) -> None:
        """--json should output JSON error when kragd is unreachable."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock.health.return_value = False
            mock._get.side_effect = ConnectionError("unreachable")
            MockClient.return_value = mock

            result = _invoke_health("--json")
            data = json.loads(result.output)
            assert data["status"] == "error" or "error" in data

    def test_without_json_flag_uses_rich_output(self) -> None:
        """Without --json, output should be human-readable (not JSON)."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock.health.return_value = True
            MockClient.return_value = mock

            result = _invoke_health()
            assert result.exit_code == 0
            # Should NOT be valid JSON
            with __import__("pytest").raises(json.JSONDecodeError):
                json.loads(result.output)
