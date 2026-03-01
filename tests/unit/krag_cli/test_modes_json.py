"""Unit tests for modes_list/modes_show --json flag (T013/US3).

Verifies that `krag modes list --json` and `krag modes show <name> --json`
output valid JSON.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from krag_cli.commands.modes import modes_app

runner = CliRunner()


def _invoke_modes(*args: str):
    """Invoke modes sub-app via Typer test runner."""
    return runner.invoke(modes_app, list(args))


def _mock_client():
    """Patch KragClient and read_service_config together."""
    return (
        patch("krag_cli.client.KragClient"),
        patch("krag_cli.config.read_service_config", return_value=("localhost", 8742)),
    )


class TestModesListJson:
    """modes list --json output tests."""

    def test_json_flag_outputs_valid_json(self) -> None:
        """--json should output parseable JSON with modes list."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._get.return_value = {
                "modes": [
                    {
                        "name": "default",
                        "description": "Default mode",
                        "collections": ["main"],
                        "llm_slot": "primary",
                        "preset": "rag",
                    }
                ]
            }
            MockClient.return_value = mock

            result = _invoke_modes("list", "--json")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "modes" in data
            assert len(data["modes"]) == 1

    def test_json_flag_empty_modes(self) -> None:
        """--json with no modes should output JSON with empty list."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._get.return_value = {"modes": []}
            MockClient.return_value = mock

            result = _invoke_modes("list", "--json")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["modes"] == []

    def test_without_json_uses_table(self) -> None:
        """Without --json, modes list should output a Rich table (not JSON)."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._get.return_value = {
                "modes": [
                    {
                        "name": "default",
                        "description": "Default mode",
                        "collections": ["main"],
                        "llm_slot": "primary",
                        "preset": "rag",
                    }
                ]
            }
            MockClient.return_value = mock

            result = _invoke_modes("list")
            assert result.exit_code == 0
            with __import__("pytest").raises(json.JSONDecodeError):
                json.loads(result.output)


class TestModesShowJson:
    """modes show --json output tests."""

    def test_json_flag_outputs_valid_json(self) -> None:
        """--json should output parseable JSON with mode details."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._get.return_value = {
                "name": "default",
                "description": "Default mode",
                "collections": {"main": 1.0},
                "llm_slot": "primary",
                "preset": "rag",
                "top_k": 10,
                "similarity_threshold": 0.5,
                "critic_enabled": False,
                "critic_threshold": 3,
            }
            MockClient.return_value = mock

            result = _invoke_modes("show", "default", "--json")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["name"] == "default"

    def test_json_flag_nonexistent_mode(self) -> None:
        """--json should output JSON error for nonexistent mode."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._get.side_effect = RuntimeError("Server error: Mode 'bogus' not found")
            MockClient.return_value = mock

            result = _invoke_modes("show", "bogus", "--json")
            data = json.loads(result.output)
            assert "error" in data
