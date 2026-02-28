"""Core interfaces for the plugin system.

This module defines the abstract base class that all file type plugins must implement,
along with the chunking strategy enum for specifying chunking preferences.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from krag.plugins.context import PluginContext


class ChunkingStrategy(Enum):
    """Available built-in chunking strategies for plugins.

    Plugins can return a ChunkingStrategy value to select from krag's available
    chunkers, or provide a custom TextChunker instance directly from
    ``get_chunking_strategy()``.

    Strategy Selection Guide:
        - Most plugins should use ``DEFAULT`` or return ``None`` (equivalent).
        - Use ``CUSTOM`` only when the file format requires content-aware
          boundaries (e.g., log timestamps, code function boundaries).
        - ``SEMANTIC`` and ``CODE_AWARE`` are reserved for future built-in
          strategies. Requesting them today falls back to ``DEFAULT`` with a
          logged warning, so plugins can declare intent for future support.

    Configuration Override:
        Users can override any plugin's chunking strategy via config.toml::

            [plugins.logs]
            chunking_strategy = "default"  # Force default instead of custom

        Valid override values: ``default``, ``semantic``, ``code_aware``.
    """

    DEFAULT = "default"
    """Use krag's default TextChunker with character-based splitting and overlap.

    This is the recommended strategy for most file types. It splits text into
    fixed-size chunks with configurable overlap, using sentence boundary
    awareness when possible.

    Chunk size and overlap are inherited from the global configuration
    (``chunking.size`` and ``chunking.overlap`` in config.toml).
    """

    SEMANTIC = "semantic"
    """Reserved for future semantic boundary detection.

    When implemented, this strategy will:
    - Detect paragraph and section boundaries
    - Preserve complete sentences at chunk edges
    - Optimize for narrative and article content

    **Status**: Not yet implemented. Falls back to DEFAULT with a warning.
    Plugins may request this to signal intent for when it becomes available.
    """

    CODE_AWARE = "code_aware"
    """Reserved for future code-structure-aware chunking.

    When implemented, this strategy will:
    - Detect function and class boundaries
    - Keep syntactic units intact (no mid-function splits)
    - Preserve import blocks and docstrings

    **Status**: Not yet implemented. Falls back to DEFAULT with a warning.
    Plugins may request this to signal intent for when it becomes available.
    """

    CUSTOM = "custom"
    """Plugin provides a custom TextChunker instance.

    Return this enum value from ``get_chunking_strategy()`` alongside a
    custom chunker from ``get_custom_chunker()``, or return the custom
    chunker instance directly from ``get_chunking_strategy()``.

    Custom chunkers must implement either:
    - ``chunk(text, file_path=None, file_type=None) -> list[TextChunk]``
    - ``chunk_text(text) -> list[str | dict]`` (will be adapted automatically)

    Example::

        def get_chunking_strategy(self):
            return LogFileChunker(window_minutes=5)
    """


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

        Must include leading dot (e.g., '.pdf' not 'pdf'). Extensions should be
        lowercase as matching is case-insensitive. Must not be empty.

        Returns:
            list[str]: File extensions (e.g., ['.pdf', '.docx'])

        Example:
            >>> handler.supported_extensions()
            ['.pdf']
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

    def get_chunking_strategy(self) -> ChunkingStrategy | Any | None:  # noqa: B027
        """Return preferred chunking strategy for this file type.

        Optional method to specify chunking strategy. Default implementation returns None.

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
        return None

    def initialize(self, config: dict[str, Any], context: PluginContext | None = None) -> None:  # noqa: B027
        """Called once after plugin is loaded, before first use.

        Optional lifecycle hook for plugin initialization. Default implementation
        does nothing.

        Args:
            config: Plugin-specific configuration from config.toml
            context: Plugin context providing access to krag services (optional)

        Raises:
            PluginConfigurationError: If configuration is invalid

        Note:
            - Should validate configuration
            - Should initialize any stateful resources
            - Should not perform expensive operations (defer to first extract call)
            - Context parameter provides access to embedding_generator, vector_store,
              chunker, logger, and report_indexing_failure callback
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

    def claims_file(self, file_path: Path) -> bool:
        """Claim ownership of a file by path, regardless of extension.

        Path-claiming plugins take priority over extension-based resolution
        in PluginRegistry.get_handler_for_file(). Default returns False
        (no path-based claiming).

        Args:
            file_path: Absolute path to the file.

        Returns:
            bool: True if this plugin claims exclusive ownership.

        Note:
            - Should be fast — use path prefix checks, not file I/O.
            - Should not raise exceptions (return False on error).
            - When True, this plugin handles the file instead of extension-based lookup.
            - If file_path is not absolute, resolve it before comparison.
              Return False for paths that cannot be resolved.
        """
        return False

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

    def get_embedding_model(self) -> str | None:  # noqa: B027
        """Declare the preferred embedding model for files handled by this plugin.

        Plugins can override this to specify a specialized embedding model.
        The EmbeddingOrchestrator will load and route embeddings accordingly.
        Plugins that don't override this method use the system default model.

        Returns:
            A HuggingFace model name or local path to a SentenceTransformer-compatible
            model, or None to use the system default (BAAI/bge-base-en-v1.5).

        Example:
            >>> handler.get_embedding_model()
            "jinaai/jina-embeddings-v2-base-code"
            >>> handler.get_embedding_model()  # default implementation
            None
        """
        return None

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
