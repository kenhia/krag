"""Unit tests for lexicon_refresh --json flag (T014/US3).

Verifies that `krag lexicon refresh --json` outputs valid JSON.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from krag_cli.commands.lexicon import lexicon_refresh

runner = CliRunner()


def _invoke_lexicon(*args: str):
    """Invoke lexicon_refresh via Typer test runner."""
    import typer

    app = typer.Typer()
    app.command()(lexicon_refresh)
    return runner.invoke(app, list(args))


def _mock_client():
    """Patch KragClient and read_service_config together."""
    return (
        patch("krag_cli.client.KragClient"),
        patch("krag_cli.config.read_service_config", return_value=("localhost", 8742)),
    )


class TestLexiconRefreshJson:
    """lexicon refresh --json output tests."""

    def test_json_flag_outputs_valid_json(self) -> None:
        """--json should output parseable JSON with entries and status."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._post.return_value = {"entries": 42, "status": "reloaded"}
            MockClient.return_value = mock

            result = _invoke_lexicon("--json")
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["entries"] == 42
            assert data["status"] == "reloaded"

    def test_json_flag_has_entries_field(self) -> None:
        """JSON output must include 'entries' key."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._post.return_value = {"entries": 100, "status": "reloaded"}
            MockClient.return_value = mock

            result = _invoke_lexicon("--json")
            data = json.loads(result.output)
            assert "entries" in data

    def test_without_json_uses_rich_output(self) -> None:
        """Without --json, output should be human-readable (not JSON)."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._post.return_value = {"entries": 42, "status": "reloaded"}
            MockClient.return_value = mock

            result = _invoke_lexicon()
            assert result.exit_code == 0
            with __import__("pytest").raises(json.JSONDecodeError):
                json.loads(result.output)

    def test_json_flag_error_case(self) -> None:
        """--json should output JSON error when refresh fails."""
        mc, msc = _mock_client()
        with mc as MockClient, msc:
            mock = MagicMock()
            mock._post.side_effect = Exception("No lexicon configured")
            MockClient.return_value = mock

            result = _invoke_lexicon("--json")
            data = json.loads(result.output)
            assert "error" in data
