"""Obsidian vault file type handler implementation."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from krag.plugins.interfaces import FileTypeHandler

from krag_plugin_obsidian.config import ObsidianConfig

logger = logging.getLogger(__name__)

# Frontmatter delimiters — ``---`` on its own line
_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class ObsidianFileTypeHandler(FileTypeHandler):
    """Handler for Obsidian vault markdown files.

    Claims ``.md`` files under configured vault paths, splits mixed content
    (prose vs fenced code blocks) into separate collections, and stores
    results under virtual ``obsidian://`` path prefixes.
    """

    def __init__(self) -> None:
        self.vault_paths: dict[str, Path] = {}
        self._context: Any | None = None

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "obsidian"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_api_version(self) -> str:
        return "1.0"

    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown"]

    # ------------------------------------------------------------------
    # Lifecycle (T032, T034)
    # ------------------------------------------------------------------

    def config_schema(self) -> type[BaseModel] | None:
        """Return Pydantic model class for validating plugin-specific settings."""
        return ObsidianConfig

    def initialize(
        self,
        config: dict[str, Any] | None = None,
        context: Any | None = None,
    ) -> None:
        """Parse vaults config, resolve paths, warn on missing directories.

        Args:
            config: Plugin-specific configuration dict (may contain
                ``vaults`` key mapping vault names to filesystem paths).
            context: Optional :class:`PluginContext` for core services.
        """
        self._context = context
        self.vault_paths = {}

        if config is None:
            logger.debug("Obsidian plugin initialized with no config")
            return

        raw_vaults: dict[str, str] = config.get("vaults", {})
        for vault_name, raw_path in raw_vaults.items():
            resolved = Path(raw_path).expanduser().resolve()
            if resolved.is_dir():
                self.vault_paths[vault_name] = resolved
            else:
                logger.warning(
                    "Obsidian vault '%s' path does not exist or is not a directory: %s",
                    vault_name,
                    resolved,
                )

        # Load bundled lexicon entries if context provides a lexicon store
        self._load_lexicon()

        vault_names = ", ".join(sorted(self.vault_paths)) or "(none)"
        logger.info(
            "Obsidian plugin initialized with %d vault(s): %s",
            len(self.vault_paths),
            vault_names,
        )

    def cleanup(self) -> None:
        """Clean up plugin resources."""
        self.vault_paths.clear()
        self._context = None
        logger.debug("Obsidian plugin cleanup complete")

    # ------------------------------------------------------------------
    # Path-based claiming (T033)
    # ------------------------------------------------------------------

    def claims_file(self, file_path: Path) -> bool:
        """Claim ownership of ``.md`` / ``.markdown`` files under vault paths.

        Uses path-prefix checks only — no file I/O. Returns ``False`` for
        non-markdown extensions even if the file is under a vault path.

        Args:
            file_path: Absolute path to the candidate file.

        Returns:
            ``True`` if the file is a markdown file under a configured vault.
        """
        if not self.vault_paths:
            return False

        # Only claim markdown extensions
        if file_path.suffix.lower() not in (".md", ".markdown"):
            return False

        try:
            resolved = file_path.resolve()
        except (OSError, ValueError):
            return False

        for vault_path in self.vault_paths.values():
            try:
                resolved.relative_to(vault_path)
                return True
            except ValueError:
                continue

        return False

    # ------------------------------------------------------------------
    # Text / metadata extraction (T035, T036)
    # ------------------------------------------------------------------

    def extract_text(self, file_path: Path) -> str:
        """Read a ``.md`` file, strip YAML frontmatter, return body text.

        Args:
            file_path: Path to the Markdown file.

        Returns:
            Body text with frontmatter removed.

        Raises:
            FileNotFoundError: If file does not exist.
            PermissionError: If file cannot be read.
            UnicodeDecodeError: If file encoding is invalid.
        """
        content = file_path.read_text(encoding="utf-8")
        body = self._remove_frontmatter(content)
        return body.strip()

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Parse YAML frontmatter and add vault metadata.

        Args:
            file_path: Path to the Markdown file.

        Returns:
            Dict with frontmatter fields plus ``vault_name`` and
            ``virtual_path`` when the file belongs to a configured vault.
        """
        content = file_path.read_text(encoding="utf-8")
        metadata: dict[str, Any] = {}

        fm = self._parse_frontmatter(content, file_path)
        if fm:
            metadata.update(fm)

        # Default title from filename if not in frontmatter
        if "title" not in metadata:
            metadata["title"] = file_path.stem

        # Add vault-specific fields
        vault_info = self._resolve_vault(file_path)
        if vault_info is not None:
            vault_name, virtual_path = vault_info
            metadata["vault_name"] = vault_name
            metadata["virtual_path"] = virtual_path

        return metadata

    # ------------------------------------------------------------------
    # Chunking strategy (T038)
    # ------------------------------------------------------------------

    def get_chunking_strategy(self) -> Any | None:
        """Return chunking strategy for Obsidian files.

        Returns ``None`` to use krag's default chunker for Phase 3.
        A custom ``ObsidianChunker`` will be returned in Phase 4.
        """
        return None

    # ------------------------------------------------------------------
    # Vault resolution (T037)
    # ------------------------------------------------------------------

    def _resolve_vault(self, file_path: Path) -> tuple[str, str] | None:
        """Find which vault a file belongs to and compute its virtual path.

        Args:
            file_path: Absolute path to the file.

        Returns:
            ``(vault_name, virtual_path)`` tuple, or ``None`` if the file
            is not under any configured vault.  The virtual path has the
            form ``obsidian://<vault_name>/<relative_path>``.
        """
        try:
            resolved = file_path.resolve()
        except (OSError, ValueError):
            return None

        for vault_name, vault_path in self.vault_paths.items():
            try:
                relative = resolved.relative_to(vault_path)
                # Use POSIX separators for the virtual path
                virtual = f"obsidian://{vault_name}/{relative.as_posix()}"
                return vault_name, virtual
            except ValueError:
                continue

        return None

    # ------------------------------------------------------------------
    # Private helpers — frontmatter parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _remove_frontmatter(content: str) -> str:
        """Remove YAML frontmatter delimited by ``---``."""
        return _FM_PATTERN.sub("", content, count=1)

    @staticmethod
    def _parse_frontmatter(
        content: str,
        file_path: Path | None = None,
    ) -> dict[str, Any] | None:
        """Parse YAML frontmatter from content."""
        match = _FM_PATTERN.match(content)
        if not match:
            return None

        try:
            parsed = yaml.safe_load(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except yaml.YAMLError as e:
            location = f" in {file_path}" if file_path else ""
            logger.warning("Failed to parse YAML frontmatter%s: %s", location, e)

        return None

    # ------------------------------------------------------------------
    # Lexicon helpers
    # ------------------------------------------------------------------

    def _load_lexicon(self) -> None:
        """Load bundled lexicon.json and merge into the lexicon store."""
        lexicon_path = Path(__file__).parent / "lexicon.json"
        if not lexicon_path.is_file():
            return

        try:
            entries: dict[str, str] = json.loads(lexicon_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load Obsidian lexicon: %s", e)
            return

        # If context exposes a lexicon_store, merge entries
        if self._context is not None and hasattr(self._context, "lexicon_store"):
            store = self._context.lexicon_store
            if hasattr(store, "merge_entries"):
                added = store.merge_entries(entries, source="obsidian")
                logger.debug("Merged %d Obsidian lexicon entries", added)
