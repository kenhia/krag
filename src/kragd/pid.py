"""PID file utilities for kragd service lifecycle.

T028: Write, read, stale detection, and removal of PID files.
Uses XDG runtime directory for PID file storage.
"""

from __future__ import annotations

import os
from pathlib import Path


def write_pid(pid_path: Path, pid: int | None = None) -> None:
    """Write a PID file.

    Args:
        pid_path: Path to write the PID file.
        pid: Process ID to write. Defaults to current process.
    """
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(pid if pid is not None else os.getpid()))


def read_pid(pid_path: Path) -> int | None:
    """Read a PID from a PID file.

    Args:
        pid_path: Path to the PID file.

    Returns:
        The PID as an integer, or None if file missing/invalid.
    """
    if not pid_path.exists():
        return None
    try:
        content = pid_path.read_text().strip()
        if not content:
            return None
        return int(content)
    except (ValueError, OSError):
        return None


def is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive.

    Uses ``os.kill(pid, 0)`` which sends no signal but checks existence.

    Args:
        pid: Process ID to check.

    Returns:
        True if the process exists, False otherwise.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True
    except OSError:
        return False


def remove_pid(pid_path: Path) -> None:
    """Remove a PID file.

    Safe to call when the file does not exist.

    Args:
        pid_path: Path to the PID file.
    """
    pid_path.unlink(missing_ok=True)


def get_pid_path() -> Path:
    """Get the default PID file path for kragd.

    Uses the krag XDG runtime directory.

    Returns:
        Path to ``kragd.pid`` in the krag runtime directory.
    """
    from krag.config.xdg import get_krag_runtime_dir

    return get_krag_runtime_dir() / "kragd.pid"
