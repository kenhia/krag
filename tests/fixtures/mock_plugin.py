"""Mock plugin fixture for testing.

Provides a simple FileTypeHandler implementation for use in tests.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from krag.plugins.exceptions import PluginExtractionError
from krag.plugins.interfaces import ChunkingStrategy, FileTypeHandler


class MockPluginConfig(BaseModel):
    """Configuration schema for mock plugin."""

    extract_metadata_enabled: bool = Field(default=True, description="Enable metadata extraction")
    max_line_count: int = Field(default=1000, description="Maximum lines to process")


class MockFileTypeHandler(FileTypeHandler):
    """Mock file type handler for testing.

    Handles `.mock` files, extracting simple text and metadata.
    """

    def __init__(self) -> None:
        """Initialize the mock handler."""
        self._config: dict[str, Any] = {}
        self._initialized = False

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "mock_plugin"

    @property
    def version(self) -> str:
        """Return the plugin version."""
        return "1.0.0"

    @property
    def required_api_version(self) -> str:
        """Return the required API version."""
        return "1.0.0"

    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return [".mock"]

    def extract_text(self, file_path: Path) -> str:
        """Extract text from a .mock file.

        Args:
            file_path: Path to the file to extract text from

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If file does not exist
            PluginExtractionError: If extraction fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            text = file_path.read_text(encoding="utf-8")

            # Apply max_line_count if configured
            max_lines = self._config.get("max_line_count", 1000)
            lines = text.splitlines()
            if len(lines) > max_lines:
                text = "\n".join(lines[:max_lines])

            return text
        except Exception as e:
            raise PluginExtractionError(
                f"Failed to extract text from {file_path}: {e}",
                plugin_name=self.name,
                file_path=file_path,
            ) from e

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract metadata from a .mock file.

        Args:
            file_path: Path to the file to extract metadata from

        Returns:
            Dictionary of metadata

        Raises:
            FileNotFoundError: If file does not exist
            PluginExtractionError: If extraction fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # If metadata extraction disabled via config, return minimal metadata
        if not self._config.get("extract_metadata_enabled", True):
            return {"extracted_by": self.name}

        try:
            stat = file_path.stat()
            text = file_path.read_text(encoding="utf-8")
            lines = text.splitlines()

            return {
                "extracted_by": self.name,
                "file_size": stat.st_size,
                "line_count": len(lines),
                "char_count": len(text),
                "first_line": lines[0] if lines else "",
            }
        except Exception as e:
            raise PluginExtractionError(
                f"Failed to extract metadata from {file_path}: {e}",
                plugin_name=self.name,
                file_path=file_path,
            ) from e

    def get_chunking_strategy(self) -> ChunkingStrategy | None:
        """Return the chunking strategy for this file type."""
        return ChunkingStrategy.DEFAULT

    def initialize(self, config: dict[str, Any], context: Any = None) -> None:
        """Initialize the plugin with configuration.

        Args:
            config: Plugin configuration dictionary
            context: Optional plugin context for accessing krag services
        """
        self._config = config
        self._initialized = True

    def cleanup(self) -> None:
        """Clean up plugin resources."""
        self._config = {}
        self._initialized = False

    def config_schema(self) -> type[BaseModel] | None:
        """Return the configuration schema for this plugin."""
        return MockPluginConfig

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this plugin can handle the given file.

        Args:
            file_path: Path to check

        Returns:
            True if plugin can handle this file
        """
        # Use default implementation (checks extension)
        return super().can_handle_file(file_path)
