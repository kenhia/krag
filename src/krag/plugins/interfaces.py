"""Core interfaces for the plugin system.

This module defines the abstract base class that all file type plugins must implement,
along with the chunking strategy enum for specifying chunking preferences.
"""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ChunkingStrategy(Enum):
    """Available built-in chunking strategies for plugins.

    Plugins can return a ChunkingStrategy value to select from krag's available
    chunkers, or provide a custom TextChunker instance directly.
    """

    DEFAULT = "default"
    """Use krag's default TextChunker (current behavior)"""

    SEMANTIC = "semantic"
    """Reserved for future semantic boundary detection"""

    CODE_AWARE = "code_aware"
    """Reserved for future code-structure-aware chunking"""

    CUSTOM = "custom"
    """Plugin provides custom chunker instance"""


class FileTypeHandler(ABC):
    """Abstract base class for file type handler plugins.

    All plugins must inherit from this class and implement the required abstract
    methods and properties. Plugins are discovered via Python entry points and
    loaded lazily when files matching their extensions are encountered.

    Example:
        >>> class PDFHandler(FileTypeHandler):
        ...     @property
        ...     def name(self) -> str:
        ...         return "pdf"
        ...
        ...     def extract_text(self, file_path: Path) -> str:
        ...         return extract_pdf_text(file_path)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin identifier (e.g., 'pdf', 'docx').

        Must be unique across all plugins and be a valid Python identifier
        (alphanumeric + underscore). Should be lowercase for consistency.

        Returns:
            str: Plugin name
        """

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version string.

        Must be a valid semantic version (e.g., '1.0.0', '2.1.3-beta').

        Returns:
            str: Plugin version
        """

    @property
    @abstractmethod
    def required_api_version(self) -> str:
        """Minimum plugin API version required by this plugin.

        Must be a valid semantic version and compatible with current krag
        plugin API version using semver major-version compatibility rules.

        Returns:
            str: Required API version (e.g., '1.0.0')
        """

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this plugin handles.

        Must include leading dot (e.g., '.pdf' not 'pdf'). Should include
        case variations if filesystem is case-sensitive. Must not be empty.

        Returns:
            list[str]: File extensions (e.g., ['.pdf', '.PDF'])

        Example:
            >>> handler.supported_extensions()
            ['.pdf', '.PDF']
        """

    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """Extract plain text content from the file.

        Args:
            file_path: Absolute path to file to process

        Returns:
            str: Extracted text content (may be empty string if file has no text)

        Raises:
            PluginExtractionError: If file cannot be processed
            FileNotFoundError: If file does not exist
            PermissionError: If file cannot be read

        Note:
            - Must return valid UTF-8 string
            - Should strip control characters except newlines/tabs
            - Should handle empty or corrupted files gracefully
            - Should not raise on empty content (return '' instead)
        """

    @abstractmethod
    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract file-specific metadata.

        Args:
            file_path: Absolute path to file to process

        Returns:
            dict[str, Any]: Metadata dictionary (may be empty)

        Raises:
            PluginExtractionError: If metadata extraction fails critically

        Note:
            - Must return dictionary (may be empty {})
            - Keys should be descriptive strings (e.g., 'author', 'page_count')
            - Values must be JSON-serializable (str, int, float, bool, list, dict)
            - Should not raise on missing metadata (return {} instead)
            - Recommended keys: title, author, creation_date, page_count, language
        """

    @abstractmethod
    def get_chunking_strategy(self) -> "ChunkingStrategy | Any | None":
        """Return preferred chunking strategy for this file type.

        Returns:
            ChunkingStrategy | TextChunker | None:
                - ChunkingStrategy enum for built-in strategies
                - TextChunker instance for custom chunking
                - None to use krag's default chunker

        Note:
            - If returning custom TextChunker, must have chunk_text(text: str) method
            - ChunkingStrategy.CUSTOM requires returning custom TextChunker
            - None is equivalent to ChunkingStrategy.DEFAULT

        Example:
            >>> handler.get_chunking_strategy()
            ChunkingStrategy.DEFAULT
        """

    def initialize(self, config: dict[str, Any]) -> None:  # noqa: B027
        """Called once after plugin is loaded, before first use.

        Optional lifecycle hook for plugin initialization. Default implementation
        does nothing.

        Args:
            config: Plugin-specific configuration from config.toml

        Raises:
            PluginConfigurationError: If configuration is invalid

        Note:
            - Should validate configuration
            - Should initialize any stateful resources
            - Should not perform expensive operations (defer to first extract call)
        """
        pass

    def cleanup(self) -> None:  # noqa: B027
        """Called at krag shutdown for resource cleanup.

        Optional lifecycle hook for cleanup. Default implementation does nothing.

        Note:
            - Should release file handles, network connections, etc.
            - Should not raise exceptions
        """
        pass

    def can_handle_file(self, file_path: Path) -> bool:
        """Additional validation beyond file extension matching.

        Optional validation hook. Default implementation checks extension only.

        Args:
            file_path: File to check

        Returns:
            bool: True if plugin can handle this file

        Note:
            - Should be lightweight (check magic bytes, not full parse)
            - Should not raise exceptions (return False instead)
        """
        return file_path.suffix.lower() in [ext.lower() for ext in self.supported_extensions()]

    def config_schema(self) -> type[BaseModel] | None:
        """Return Pydantic model class for validating plugin-specific settings.

        Optional configuration schema. Default implementation returns None (no settings).

        Returns:
            type[BaseModel] | None: Pydantic model class for validation, or None

        Note:
            - If provided, PluginConfiguration validates plugin settings against this model
            - Validation errors disable the plugin with a logged warning
            - Return None if plugin has no configurable settings

        Example:
            >>> class PDFSettings(BaseModel):
            ...     max_pages: int = 1000
            ...     ocr_enabled: bool = False
            >>> def config_schema(self) -> type[BaseModel] | None:
            ...     return PDFSettings
        """
        return None
