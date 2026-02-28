"""Unit tests for query / debug-query CLI error handling.

Verifies that an invalid --mode (or any ValueError from the client) shows a
clean ``Error: …`` message instead of a Python traceback.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from krag_cli.main import app

runner = CliRunner()

_INVALID_MODE_MSG = (
    "Request validation failed: Unknown mode 'bogus'. "
    "Available modes: code, default, docs, obsidian"
)


# ── helper ────────────────────────────────────────────────────────────────────


def _make_mock_client_class(side_effect: Exception) -> MagicMock:
    """Return a KragClient class mock whose methods raise *side_effect*."""
    mock_instance = MagicMock()
    mock_instance.query.side_effect = side_effect
    mock_instance.retrieve.side_effect = side_effect
    mock_instance.post.side_effect = side_effect

    mock_class = MagicMock(return_value=mock_instance)
    return mock_class


# ── query command ─────────────────────────────────────────────────────────────


class TestQueryCommandValueError:
    """krag query with invalid --mode shows clean error, exit 1."""

    @patch("krag_cli.client.KragClient")
    @patch("krag_cli.config.read_service_config", return_value=("localhost", 11435))
    def test_invalid_mode_exits_with_error_message(
        self, _mock_cfg: MagicMock, mock_client_class: MagicMock
    ) -> None:
        """ValueError from client is displayed as 'Error: ...' and exits 1."""
        mock_client_class.return_value = _make_mock_client_class(
            ValueError(_INVALID_MODE_MSG)
        ).return_value

        result = runner.invoke(app, ["query", "hello", "--mode", "bogus"])

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Unknown mode" in result.output

    @patch("krag_cli.client.KragClient")
    @patch("krag_cli.config.read_service_config", return_value=("localhost", 11435))
    def test_invalid_mode_no_traceback(
        self, _mock_cfg: MagicMock, mock_client_class: MagicMock
    ) -> None:
        """ValueError does not produce a Python traceback in the output."""
        mock_client_class.return_value = _make_mock_client_class(
            ValueError(_INVALID_MODE_MSG)
        ).return_value

        result = runner.invoke(app, ["query", "hello", "--mode", "bogus"])

        assert "Traceback" not in result.output
        assert "ValueError" not in result.output

    @patch("krag_cli.client.KragClient")
    @patch("krag_cli.config.read_service_config", return_value=("localhost", 11435))
    def test_invalid_mode_no_synthesis_exits_cleanly(
        self, _mock_cfg: MagicMock, mock_client_class: MagicMock
    ) -> None:
        """ValueError during --no-synthesis retrieve is also caught cleanly."""
        mock_instance = MagicMock()
        mock_instance.retrieve.side_effect = ValueError(_INVALID_MODE_MSG)
        mock_client_class.return_value = mock_instance

        result = runner.invoke(app, ["query", "hello", "--mode", "bogus", "--no-synthesis"])

        assert result.exit_code == 1
        assert "Error:" in result.output


# ── debug query command ───────────────────────────────────────────────────────


class TestDebugQueryCommandValueError:
    """krag debug query with invalid --mode shows clean error, exit 1."""

    @patch("krag_cli.main._get_client")
    def test_invalid_mode_exits_with_error_message(self, mock_get_client: MagicMock) -> None:
        """ValueError from debug client is displayed as 'Error: ...' and exits 1."""
        mock_client = MagicMock()
        mock_client.post.side_effect = ValueError(_INVALID_MODE_MSG)
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["debug", "query", "hello", "--mode", "bogus"])

        assert result.exit_code == 1
        assert "Error:" in result.output
        assert "Unknown mode" in result.output

    @patch("krag_cli.main._get_client")
    def test_invalid_mode_no_traceback(self, mock_get_client: MagicMock) -> None:
        """ValueError in debug query does not leak a Python traceback."""
        mock_client = MagicMock()
        mock_client.post.side_effect = ValueError(_INVALID_MODE_MSG)
        mock_get_client.return_value = mock_client

        result = runner.invoke(app, ["debug", "query", "hello", "--mode", "bogus"])

        assert "Traceback" not in result.output
        assert "ValueError" not in result.output
