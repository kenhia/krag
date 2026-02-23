"""ModeRegistry — central store for named ModeConfigurations.

The registry loads built-in modes from ``krag/modes/builtin/`` on startup
and optionally merges user-defined modes from a configurable directory.

Typical usage::

    from krag.modes.mode_registry import ModeRegistry

    registry = ModeRegistry()
    registry.load_builtins()
    registry.load_user_modes(Path("~/.config/krag/modes"))

    mode = registry.get("code")
"""

from __future__ import annotations

import logging
from pathlib import Path

from krag.models.configuration import ModeConfiguration
from krag.modes.mode_loader import ModeLoader

logger = logging.getLogger(__name__)

# Built-in modes ship inside the package.
_BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"


class ModeRegistry:
    """Case-insensitive registry for ModeConfigurations."""

    def __init__(self) -> None:
        self._modes: dict[str, ModeConfiguration] = {}

    # ── Registration ───────────────────────────────────────────────────

    def register(self, mode: ModeConfiguration) -> None:
        """Register (or replace) a mode by its lowercased name."""
        key = mode.name.lower()
        if key in self._modes:
            logger.info("Replacing mode '%s'", key)
        self._modes[key] = mode

    # ── Lookup ─────────────────────────────────────────────────────────

    def get(self, name: str) -> ModeConfiguration:
        """Return the mode for *name* (case-insensitive).

        Raises:
            ValueError: If the name is not registered.
        """
        key = name.lower()
        mode = self._modes.get(key)
        if mode is None:
            available = ", ".join(sorted(self._modes)) or "(none)"
            raise ValueError(f"Unknown mode '{name}'. Available modes: {available}")
        return mode

    def list_modes(self) -> list[ModeConfiguration]:
        """Return all registered modes sorted by name."""
        return sorted(self._modes.values(), key=lambda m: m.name)

    # ── Bulk loading ───────────────────────────────────────────────────

    def load_builtins(self) -> None:
        """Load all modes from the package's ``builtin/`` directory."""
        if not _BUILTIN_DIR.is_dir():
            logger.warning("Built-in modes directory missing: %s", _BUILTIN_DIR)
            return

        for mode in ModeLoader.load_directory(_BUILTIN_DIR):
            self.register(mode)

        logger.info(
            "Loaded %d built-in mode(s): %s",
            len(self._modes),
            ", ".join(sorted(self._modes)),
        )

    def load_user_modes(self, directory: Path) -> None:
        """Load user modes from *directory*, overriding builtins if names clash."""
        if not directory.is_dir():
            logger.debug("User modes directory does not exist: %s", directory)
            return

        for mode in ModeLoader.load_directory(directory):
            self.register(mode)

        logger.info("Loaded user modes from %s", directory)

    # ── Introspection ──────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._modes)

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._modes
