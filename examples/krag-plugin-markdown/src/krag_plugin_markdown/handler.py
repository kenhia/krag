"""Markdown file type handler implementation."""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from krag.plugins.interfaces import FileTypeHandler

logger = logging.getLogger(__name__)


class MarkdownFileTypeHandler(FileTypeHandler):
    """Handler for Markdown files with YAML frontmatter support.

    This plugin demonstrates a simple file type handler that:
    - Extracts text by stripping Markdown syntax
    - Parses YAML frontmatter for metadata
    - Uses krag's default chunking strategy (returns None)
    """

    @property
    def name(self) -> str:
        """Plugin identifier."""
        return "markdown"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def required_api_version(self) -> str:
        """Required krag plugin API version."""
        return "1.0"

    def supported_extensions(self) -> list[str]:
        """Supported file extensions."""
        return [".md", ".markdown"]

    def extract_text(self, file_path: Path) -> str:
        """Extract text content from Markdown file.

        Strips Markdown syntax to produce clean, readable text suitable for
        semantic search and RAG applications.

        Args:
            file_path: Path to the Markdown file

        Returns:
            Cleaned text content with Markdown syntax removed

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be read
            UnicodeDecodeError: If file encoding is invalid
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(f"Markdown file not found: {file_path}")
            raise
        except PermissionError:
            logger.error(f"Permission denied reading Markdown file: {file_path}")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Invalid encoding in Markdown file {file_path}: {e}")
            raise

        # Remove frontmatter (will be parsed separately)
        content = self._remove_frontmatter(content)

        # Strip Markdown syntax
        text = self._strip_markdown(content)

        return text.strip()

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract metadata from YAML frontmatter.

        Parses YAML frontmatter at the beginning of Markdown files.
        If no frontmatter exists, returns basic file metadata.

        Args:
            file_path: Path to the Markdown file

        Returns:
            Dictionary containing metadata fields:
            - title: From frontmatter or filename
            - author: From frontmatter (optional)
            - date: From frontmatter (optional)
            - tags: From frontmatter (optional)
            - Any additional frontmatter fields

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be read
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(f"Markdown file not found: {file_path}")
            raise
        except PermissionError:
            logger.error(f"Permission denied reading Markdown file: {file_path}")
            raise

        metadata: dict[str, Any] = {}

        # Parse frontmatter
        frontmatter = self._parse_frontmatter(content)
        if frontmatter:
            metadata.update(frontmatter)

        # Add default title if not in frontmatter
        if "title" not in metadata:
            metadata["title"] = file_path.stem

        return metadata

    def get_chunking_strategy(self) -> None:
        """Return chunking strategy for Markdown files.

        Returns None to use krag's default TextChunker, which works well
        for Markdown content after syntax stripping.

        Returns:
            None to use default chunking
        """
        return None

    def initialize(self, config: dict[str, Any] | None = None, context: Any = None) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin-specific configuration (unused by this plugin)
            context: Plugin context (unused by this plugin)
        """
        logger.debug("Markdown plugin initialized")

    def cleanup(self) -> None:
        """Clean up plugin resources.

        No cleanup needed for this stateless plugin.
        """
        logger.debug("Markdown plugin cleanup complete")

    def config_schema(self) -> dict[str, Any] | None:
        """Return configuration schema for the plugin.

        This plugin requires no configuration.

        Returns:
            None (no configuration needed)
        """
        return None

    # Private helper methods

    def _remove_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from content.

        Args:
            content: Full Markdown content

        Returns:
            Content with frontmatter removed
        """
        # Match YAML frontmatter: ---\n...\n---
        pattern = r"^---\s*\n.*?\n---\s*\n"
        return re.sub(pattern, "", content, count=1, flags=re.DOTALL)

    def _parse_frontmatter(self, content: str) -> dict[str, Any] | None:
        """Parse YAML frontmatter from content.

        Args:
            content: Full Markdown content

        Returns:
            Dictionary of frontmatter fields or None if no frontmatter
        """
        # Match YAML frontmatter
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return None

        frontmatter_text = match.group(1)

        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if isinstance(frontmatter, dict):
                return frontmatter
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML frontmatter: {e}")

        return None

    def _strip_markdown(self, content: str) -> str:
        """Strip Markdown syntax from content.

        Removes common Markdown elements to produce clean text:
        - Headers (#, ##, etc.)
        - Bold/italic markers (**, *, _, __)
        - Links [text](url)
        - Images ![alt](url)
        - Code blocks (```, `)
        - Blockquotes (>)
        - Horizontal rules (---, ***)
        - List markers (-, *, 1.)

        Args:
            content: Markdown content

        Returns:
            Plain text with Markdown syntax removed
        """
        text = content

        # Remove code blocks (``` ... ```)
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

        # Remove inline code (` ... `)
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Remove images ![alt](url)
        text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", text)

        # Remove links [text](url) but keep text
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        # Remove headers (### Header)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # Remove bold/italic markers
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold**
        text = re.sub(r"\*([^*]+)\*", r"\1", text)  # *italic*
        text = re.sub(r"__([^_]+)__", r"\1", text)  # __bold__
        text = re.sub(r"_([^_]+)_", r"\1", text)  # _italic_

        # Remove blockquotes (> text)
        text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)

        # Remove horizontal rules (---, ***)
        text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

        # Remove list markers (-, *, 1.)
        text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)

        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        return text
