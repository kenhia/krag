"""Unit tests for PID file utilities.

T026: Test write, read, stale detection via os.kill, and removal.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch


class TestWritePid:
    """Test writing PID files."""

    def test_write_pid_creates_file(self, tmp_path: Path) -> None:
        """write_pid() creates a PID file at the specified path."""
        from kragd.pid import write_pid

        pid_file = tmp_path / "kragd.pid"
        write_pid(pid_file)
        assert pid_file.exists()

    def test_write_pid_contains_current_pid(self, tmp_path: Path) -> None:
        """PID file contains the current process PID."""
        from kragd.pid import write_pid

        pid_file = tmp_path / "kragd.pid"
        write_pid(pid_file)
        content = pid_file.read_text().strip()
        assert content == str(os.getpid())

    def test_write_pid_creates_parent_dirs(self, tmp_path: Path) -> None:
        """write_pid() creates parent directories if needed."""
        from kragd.pid import write_pid

        pid_file = tmp_path / "sub" / "dir" / "kragd.pid"
        write_pid(pid_file)
        assert pid_file.exists()

    def test_write_pid_overwrites_existing(self, tmp_path: Path) -> None:
        """write_pid() overwrites an existing PID file."""
        from kragd.pid import write_pid

        pid_file = tmp_path / "kragd.pid"
        pid_file.write_text("12345")
        write_pid(pid_file)
        content = pid_file.read_text().strip()
        assert content == str(os.getpid())

    def test_write_pid_custom_pid(self, tmp_path: Path) -> None:
        """write_pid() accepts an explicit PID value."""
        from kragd.pid import write_pid

        pid_file = tmp_path / "kragd.pid"
        write_pid(pid_file, pid=99999)
        content = pid_file.read_text().strip()
        assert content == "99999"


class TestReadPid:
    """Test reading PID files."""

    def test_read_pid_returns_pid(self, tmp_path: Path) -> None:
        """read_pid() returns the PID from the file."""
        from kragd.pid import read_pid

        pid_file = tmp_path / "kragd.pid"
        pid_file.write_text("12345\n")
        assert read_pid(pid_file) == 12345

    def test_read_pid_missing_file(self, tmp_path: Path) -> None:
        """read_pid() returns None when file does not exist."""
        from kragd.pid import read_pid

        pid_file = tmp_path / "nonexistent.pid"
        assert read_pid(pid_file) is None

    def test_read_pid_empty_file(self, tmp_path: Path) -> None:
        """read_pid() returns None for empty PID file."""
        from kragd.pid import read_pid

        pid_file = tmp_path / "kragd.pid"
        pid_file.write_text("")
        assert read_pid(pid_file) is None

    def test_read_pid_invalid_content(self, tmp_path: Path) -> None:
        """read_pid() returns None for non-numeric PID file."""
        from kragd.pid import read_pid

        pid_file = tmp_path / "kragd.pid"
        pid_file.write_text("not-a-pid")
        assert read_pid(pid_file) is None

    def test_read_pid_strips_whitespace(self, tmp_path: Path) -> None:
        """read_pid() handles whitespace around PID."""
        from kragd.pid import read_pid

        pid_file = tmp_path / "kragd.pid"
        pid_file.write_text("  42  \n")
        assert read_pid(pid_file) == 42


class TestIsPidAlive:
    """Test PID liveness detection."""

    def test_is_pid_alive_current_process(self) -> None:
        """is_pid_alive() returns True for current process."""
        from kragd.pid import is_pid_alive

        assert is_pid_alive(os.getpid()) is True

    def test_is_pid_alive_nonexistent_pid(self) -> None:
        """is_pid_alive() returns False for non-existent PID."""
        from kragd.pid import is_pid_alive

        # Use a very high PID that's unlikely to exist
        assert is_pid_alive(4_000_000) is False

    def test_is_pid_alive_negative_pid(self) -> None:
        """is_pid_alive() returns False for negative PID."""
        from kragd.pid import is_pid_alive

        assert is_pid_alive(-1) is False

    def test_is_pid_alive_zero(self) -> None:
        """is_pid_alive() returns False for PID 0."""
        from kragd.pid import is_pid_alive

        assert is_pid_alive(0) is False

    @patch("os.kill")
    def test_is_pid_alive_uses_signal_0(self, mock_kill) -> None:
        """is_pid_alive() uses signal 0 (no-op) to probe."""
        from kragd.pid import is_pid_alive

        mock_kill.return_value = None
        is_pid_alive(12345)
        mock_kill.assert_called_once_with(12345, 0)


class TestRemovePid:
    """Test PID file removal."""

    def test_remove_pid_deletes_file(self, tmp_path: Path) -> None:
        """remove_pid() deletes the PID file."""
        from kragd.pid import remove_pid

        pid_file = tmp_path / "kragd.pid"
        pid_file.write_text("12345")
        remove_pid(pid_file)
        assert not pid_file.exists()

    def test_remove_pid_missing_file_no_error(self, tmp_path: Path) -> None:
        """remove_pid() does not raise when file is missing."""
        from kragd.pid import remove_pid

        pid_file = tmp_path / "nonexistent.pid"
        remove_pid(pid_file)  # Should not raise


class TestGetPidPath:
    """Test PID file path construction."""

    def test_get_pid_path_returns_path_object(self) -> None:
        """get_pid_path() returns a Path object."""
        from kragd.pid import get_pid_path

        result = get_pid_path()
        assert isinstance(result, Path)

    def test_get_pid_path_ends_with_pid(self) -> None:
        """get_pid_path() returns path ending in 'kragd.pid'."""
        from kragd.pid import get_pid_path

        result = get_pid_path()
        assert result.name == "kragd.pid"

    def test_get_pid_path_in_runtime_dir(self) -> None:
        """get_pid_path() uses krag runtime directory."""
        from kragd.pid import get_pid_path

        result = get_pid_path()
        assert "krag" in str(result).lower()


class TestStaleDetection:
    """Test stale PID file detection (PID file exists, process is dead)."""

    def test_stale_pid_file_detected(self, tmp_path: Path) -> None:
        """Stale PID (file exists, process dead) is detectable."""
        from kragd.pid import is_pid_alive, read_pid

        pid_file = tmp_path / "kragd.pid"
        pid_file.write_text("4000000")  # Very unlikely to be alive

        pid = read_pid(pid_file)
        assert pid is not None
        assert is_pid_alive(pid) is False

    def test_live_pid_file_detected(self, tmp_path: Path) -> None:
        """Live PID (current process) is correctly identified."""
        from kragd.pid import is_pid_alive, read_pid, write_pid

        pid_file = tmp_path / "kragd.pid"
        write_pid(pid_file)

        pid = read_pid(pid_file)
        assert pid is not None
        assert is_pid_alive(pid) is True
