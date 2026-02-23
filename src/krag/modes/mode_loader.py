"""ModeLoader — parse and validate TOML mode files into ModeConfiguration.

This module reads mode definition files in TOML format, maps their sections
to ModeConfiguration fields, and validates the result using Pydantic.

Typical usage::

    from krag.modes.mode_loader import ModeLoader
    mode = ModeLoader.load(Path("modes/code.toml"))
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from krag.models.configuration import ModeConfiguration

logger = logging.getLogger(__name__)


class ModeLoader:
    """Parse TOML files into validated ModeConfiguration instances."""

    @staticmethod
    def load(path: Path) -> ModeConfiguration:
        """Load a single mode TOML file and return a ModeConfiguration.

        Args:
            path: Path to a ``.toml`` file.

        Returns:
            A validated ModeConfiguration.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the TOML is malformed or fails validation.
        """
        if not path.exists():
            raise FileNotFoundError(f"Mode file not found: {path}")

        try:
            raw = path.read_text(encoding="utf-8")
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"TOML parse error in {path}: {exc}") from exc

        # ── Extract [mode] section (required) ──────────────────────────
        mode_section = data.get("mode")
        if mode_section is None:
            raise ValueError(f"Missing required [mode] section in {path}")
        if "name" not in mode_section:
            raise ValueError(f"Missing required 'name' field in [mode] section of {path}")

        # ── Build flat kwargs for ModeConfiguration ────────────────────
        kwargs: dict[str, object] = {
            "name": mode_section["name"],
        }

        if "description" in mode_section:
            kwargs["description"] = mode_section["description"]

        # [collections] → collections dict
        collections = data.get("collections")
        if collections is not None:
            kwargs["collections"] = dict(collections)

        # [llm] → llm_slot
        llm_section = data.get("llm")
        if llm_section is not None and "slot" in llm_section:
            kwargs["llm_slot"] = llm_section["slot"]

        # [prompt] → preset
        prompt_section = data.get("prompt")
        if prompt_section is not None and "preset" in prompt_section:
            kwargs["preset"] = prompt_section["preset"]

        # [retrieval] → top_k, similarity_threshold
        retrieval = data.get("retrieval")
        if retrieval is not None:
            if "top_k" in retrieval:
                kwargs["top_k"] = retrieval["top_k"]
            if "similarity_threshold" in retrieval:
                kwargs["similarity_threshold"] = retrieval["similarity_threshold"]

        # [critic] → critic_enabled, critic_threshold
        critic = data.get("critic")
        if critic is not None:
            if "enabled" in critic:
                kwargs["critic_enabled"] = critic["enabled"]
            if "threshold" in critic:
                kwargs["critic_threshold"] = critic["threshold"]

        # ── Construct & validate via Pydantic ──────────────────────────
        try:
            return ModeConfiguration(**kwargs)  # type: ignore[arg-type]
        except Exception as exc:
            raise ValueError(f"Validation failed for mode '{kwargs.get('name')}': {exc}") from exc

    @staticmethod
    def load_directory(directory: Path) -> list[ModeConfiguration]:
        """Load all valid ``.toml`` files from *directory*.

        Invalid files are logged and skipped — they do not cause a fatal error.

        Args:
            directory: Folder containing mode TOML files.

        Returns:
            List of successfully loaded ModeConfigurations.
        """
        if not directory.is_dir():
            logger.warning("Mode directory does not exist: %s", directory)
            return []

        modes: list[ModeConfiguration] = []
        for toml_file in sorted(directory.glob("*.toml")):
            try:
                modes.append(ModeLoader.load(toml_file))
            except (ValueError, FileNotFoundError) as exc:
                logger.warning("Skipping invalid mode file %s: %s", toml_file, exc)

        return modes
