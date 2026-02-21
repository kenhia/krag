"""Configuration reader for krag_cli.

Reads host/port from the krag config file's [service] section so the CLI
knows where to connect to kragd.
"""

from __future__ import annotations

from pathlib import Path

from krag.config.settings import ConfigManager
from krag.config.xdg import get_krag_config_dir


def find_config() -> Path | None:
    """Locate the krag config file using standard search order.

    Returns:
        Path to config file, or None if not found.
    """
    candidates = [
        Path("krag.toml"),
        get_krag_config_dir() / "config.toml",
        get_krag_config_dir() / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def read_service_config(
    config_path: Path | None = None,
) -> tuple[str, int]:
    """Read service host/port from configuration.

    Args:
        config_path: Explicit config path, or None to auto-detect.

    Returns:
        Tuple of (host, port).
    """
    if config_path is None:
        config_path = find_config()

    if config_path is not None and config_path.exists():
        config = ConfigManager.load(config_path)
        return config.service.host, config.service.port

    # Defaults if no config found
    return "0.0.0.0", 8742
