"""Obsidian vault file type handler implementation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from krag.plugins.interfaces import FileTypeHandler

logger = logging.getLogger(__name__)


class ObsidianFileTypeHandler(FileTypeHandler):
    """Handler for Obsidian vault markdown files.

    Claims .md files under configured vault paths, splits mixed content
    (prose vs fenced code blocks) into separate collections, and stores
    results under virtual obsidian:// path prefixes.
    """

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

    def extract_text(self, file_path: Path) -> str:
        raise NotImplementedError("extract_text will be implemented in Phase 3")

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        raise NotImplementedError("extract_metadata will be implemented in Phase 3")
