"""Chunking strategy resolution for plugins.

This module provides the ChunkingStrategyResolver class that maps plugin chunking
preferences (ChunkingStrategy enum or custom chunkers) to actual TextChunker instances.

It also provides validation utilities for custom chunker interface compliance and
an adapter for chunkers that implement chunk_text() instead of chunk().
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from krag.extraction.chunker import TextChunker
from krag.models.text_chunk import TextChunk
from krag.plugins.interfaces import ChunkingStrategy

logger = logging.getLogger(__name__)


class CustomChunkerAdapter(TextChunker):
    """Adapter that wraps a chunk_text()-only chunker to provide the chunk() interface.

    Plugin-provided custom chunkers may implement chunk_text(text) -> list[str]
    per the plugin contract. This adapter makes them compatible with the indexing
    pipeline which calls chunk(text, file_path, file_type).

    Example:
        >>> class MyChunker:
        ...     def chunk_text(self, text: str) -> list[str]:
        ...         return text.split("\\n\\n")
        >>> adapted = CustomChunkerAdapter(MyChunker())
        >>> chunks = adapted.chunk("hello\\n\\nworld", Path("test.txt"))
    """

    def __init__(self, wrapped: Any):
        """Initialize adapter wrapping a chunk_text()-only chunker.

        Args:
            wrapped: Object with a chunk_text() method
        """
        # Initialize parent with defaults (won't be used directly)
        super().__init__(chunk_size=1000, chunk_overlap=200)
        self._wrapped = wrapped

        # Forward chunk_size/chunk_overlap if the wrapped chunker has them
        if hasattr(wrapped, "chunk_size") and wrapped.chunk_size is not None:
            self.chunk_size = wrapped.chunk_size
        if hasattr(wrapped, "chunk_overlap") and wrapped.chunk_overlap is not None:
            self.chunk_overlap = wrapped.chunk_overlap

    def chunk(
        self,
        text: str,
        file_path: Path | None = None,
        file_type: str | None = None,
    ) -> list[TextChunk]:
        """Chunk text by delegating to the wrapped chunker's chunk_text().

        Args:
            text: Text content to chunk
            file_path: Source file path (optional)
            file_type: File type (optional)

        Returns:
            List of TextChunk objects
        """
        raw_chunks = self._wrapped.chunk_text(text)

        # Convert raw output to TextChunk objects
        result = []
        char_offset = 0
        for idx, chunk_data in enumerate(raw_chunks):
            # Handle both str and dict return types
            if isinstance(chunk_data, str):
                content = chunk_data
            elif isinstance(chunk_data, dict) and "content" in chunk_data:
                content = chunk_data["content"]
            else:
                content = str(chunk_data)

            if not content or not content.strip():
                continue

            result.append(
                TextChunk(
                    chunk_id=str(uuid4()),
                    file_path=file_path or Path("unknown"),
                    chunk_index=idx,
                    content=content,
                    start_char=char_offset,
                    end_char=char_offset + len(content),
                    token_count=len(content.split()),
                )
            )
            char_offset += len(content)

        return result


class ChunkingStrategyResolver:
    """Resolves plugin chunking strategies to actual chunker instances.

    Handles mapping from ChunkingStrategy enum values or custom chunker instances
    to TextChunker instances that can be used for text chunking.

    Example:
        >>> resolver = ChunkingStrategyResolver()
        >>> chunker = resolver.resolve(ChunkingStrategy.DEFAULT)
        >>> chunks = chunker.chunk(text, file_path)
    """

    def __init__(
        self,
        default_chunk_size: int = 1000,
        default_chunk_overlap: int = 200,
        chunking_overrides: dict[str, str] | None = None,
    ):
        """Initialize chunking strategy resolver.

        Args:
            default_chunk_size: Default chunk size for built-in chunkers
            default_chunk_overlap: Default overlap for built-in chunkers
            chunking_overrides: Per-plugin chunking strategy overrides from config.
                Maps plugin name to strategy name (e.g., {"logs": "default"}).
                When set, overrides whatever the plugin returns from get_chunking_strategy().
        """
        self._default_chunk_size = default_chunk_size
        self._default_chunk_overlap = default_chunk_overlap
        self._default_chunker: TextChunker | None = None
        self._chunking_overrides = chunking_overrides or {}

        logger.debug(
            f"ChunkingStrategyResolver initialized with "
            f"chunk_size={default_chunk_size}, overlap={default_chunk_overlap}"
            + (
                f", overrides={list(self._chunking_overrides.keys())}"
                if self._chunking_overrides
                else ""
            )
        )

    def _get_default_chunker(self) -> TextChunker:
        """Get or create default TextChunker instance.

        Caches the default chunker for reuse across multiple resolutions.

        Returns:
            TextChunker: Default chunker instance
        """
        if self._default_chunker is None:
            self._default_chunker = TextChunker(
                chunk_size=self._default_chunk_size,
                chunk_overlap=self._default_chunk_overlap,
            )
            logger.debug("Created default TextChunker instance")

        return self._default_chunker

    def resolve(
        self,
        strategy: ChunkingStrategy | Any | None,
        plugin_name: str | None = None,
    ) -> TextChunker:
        """Resolve chunking strategy to actual TextChunker instance.

        Maps plugin chunking preferences to concrete chunker instances:
        - None → default chunker
        - ChunkingStrategy.DEFAULT → default chunker
        - ChunkingStrategy.SEMANTIC → default chunker (not yet implemented)
        - ChunkingStrategy.CODE_AWARE → default chunker (plugin handles chunking via chunk_file())
        - Custom TextChunker → validate and return
        - Object with chunk_text() → wrap in CustomChunkerAdapter
        - Invalid → log warning and return default

        Configuration-based overrides take precedence over plugin preferences
        when ``chunking_overrides`` are configured for a given plugin name.

        Args:
            strategy: Chunking strategy from plugin's get_chunking_strategy()
            plugin_name: Plugin name for logging and config override lookup

        Returns:
            TextChunker: Resolved chunker instance (never None, falls back to default)

        Example:
            >>> # Plugin returns None - use default
            >>> chunker = resolver.resolve(None, "pdf")
            >>>
            >>> # Plugin returns enum - use corresponding strategy
            >>> chunker = resolver.resolve(ChunkingStrategy.DEFAULT, "pdf")
            >>>
            >>> # Plugin returns custom chunker - validate and use
            >>> custom = MyCustomChunker()
            >>> chunker = resolver.resolve(custom, "pdf")
        """
        plugin_label = f"'{plugin_name}'" if plugin_name else "plugin"

        # Check for configuration-based override
        if plugin_name and plugin_name in self._chunking_overrides:
            override_value = self._chunking_overrides[plugin_name]
            override_strategy = self._parse_strategy_name(override_value)
            if override_strategy is not None:
                logger.info(
                    f"{plugin_label} chunking strategy overridden by config to '{override_value}'"
                )
                return self._resolve_enum_strategy(override_strategy, plugin_label)
            else:
                logger.warning(
                    f"Invalid chunking override '{override_value}' for {plugin_label}, "
                    f"using plugin's preferred strategy"
                )

        # Handle None - use default
        if strategy is None:
            logger.debug(f"{plugin_label} returned None, using default chunker")
            return self._get_default_chunker()

        # Handle ChunkingStrategy enum
        if isinstance(strategy, ChunkingStrategy):
            return self._resolve_enum_strategy(strategy, plugin_label)

        # Handle custom TextChunker instance (has chunk() method)
        if self._is_valid_chunker(strategy):
            logger.info(f"{plugin_label} provided custom chunker: {type(strategy).__name__}")
            return strategy

        # Handle chunk_text()-only chunkers via adapter
        if self._has_chunk_text(strategy):
            logger.info(
                f"{plugin_label} provided chunk_text()-only chunker: "
                f"{type(strategy).__name__}, wrapping with adapter"
            )
            return CustomChunkerAdapter(strategy)

        # Invalid strategy - fallback to default
        logger.warning(
            f"{plugin_label} returned invalid chunking strategy: {type(strategy).__name__}. "
            f"Using default chunker as fallback."
        )
        return self._get_default_chunker()

    @staticmethod
    def _parse_strategy_name(name: str) -> ChunkingStrategy | None:
        """Parse a strategy name string to ChunkingStrategy enum.

        Args:
            name: Strategy name (e.g., 'default', 'semantic', 'code_aware')

        Returns:
            ChunkingStrategy or None if name is invalid
        """
        name_lower = name.lower().strip()
        strategy_map = {
            "default": ChunkingStrategy.DEFAULT,
            "semantic": ChunkingStrategy.SEMANTIC,
            "code_aware": ChunkingStrategy.CODE_AWARE,
            "custom": ChunkingStrategy.CUSTOM,
        }
        return strategy_map.get(name_lower)

    def _resolve_enum_strategy(
        self,
        strategy: ChunkingStrategy,
        plugin_label: str,
    ) -> TextChunker:
        """Resolve ChunkingStrategy enum to chunker instance.

        Args:
            strategy: ChunkingStrategy enum value
            plugin_label: Plugin label for logging

        Returns:
            TextChunker: Resolved chunker instance
        """
        if strategy == ChunkingStrategy.DEFAULT:
            logger.debug(f"{plugin_label} requested DEFAULT strategy")
            return self._get_default_chunker()

        elif strategy == ChunkingStrategy.SEMANTIC:
            logger.warning(
                f"{plugin_label} requested SEMANTIC strategy, but it's not yet implemented. "
                f"Using DEFAULT strategy as fallback."
            )
            return self._get_default_chunker()

        elif strategy == ChunkingStrategy.CODE_AWARE:
            logger.debug(
                f"{plugin_label} requested CODE_AWARE strategy — "
                f"plugin handles chunking via chunk_file(); using default chunker as fallback."
            )
            return self._get_default_chunker()

        elif strategy == ChunkingStrategy.CUSTOM:
            logger.warning(
                f"{plugin_label} returned ChunkingStrategy.CUSTOM but did not provide "
                f"a custom chunker instance. Using DEFAULT strategy as fallback."
            )
            return self._get_default_chunker()

        else:
            # Unknown enum value - should not happen but handle gracefully
            logger.warning(
                f"{plugin_label} returned unknown ChunkingStrategy: {strategy}. "
                f"Using DEFAULT strategy as fallback."
            )
            return self._get_default_chunker()

    def _is_valid_chunker(self, obj: Any) -> bool:
        """Check if object is a valid TextChunker-like instance.

        A valid chunker must have a callable chunk() method that accepts
        text and returns a list of TextChunk objects.

        Args:
            obj: Object to validate

        Returns:
            bool: True if object has a callable chunk() method
        """
        # Check if it has a chunk method
        if not hasattr(obj, "chunk"):
            return False

        # Check if chunk is callable
        if not callable(obj.chunk):
            return False

        # Valid chunker (duck typing - if it has chunk(), it's a chunker)
        return True

    @staticmethod
    def _has_chunk_text(obj: Any) -> bool:
        """Check if object has a callable chunk_text() method.

        Used to detect custom chunkers that implement the plugin contract's
        chunk_text() interface but not the full TextChunker.chunk() interface.

        Args:
            obj: Object to check

        Returns:
            bool: True if object has callable chunk_text()
        """
        return hasattr(obj, "chunk_text") and callable(obj.chunk_text)

    @staticmethod
    def validate_chunker_interface(obj: Any) -> list[str]:
        """Validate a custom chunker's interface compliance.

        Checks whether the object meets the requirements for a custom chunker:
        - Must have either chunk() or chunk_text() as a callable method
        - Optionally may have chunk_size and chunk_overlap properties

        Args:
            obj: Object to validate

        Returns:
            list[str]: List of validation error messages (empty if valid)

        Example:
            >>> errors = ChunkingStrategyResolver.validate_chunker_interface(my_chunker)
            >>> if errors:
            ...     print(f"Invalid chunker: {errors}")
        """
        errors: list[str] = []

        has_chunk = hasattr(obj, "chunk") and callable(getattr(obj, "chunk", None))
        has_chunk_text = hasattr(obj, "chunk_text") and callable(getattr(obj, "chunk_text", None))

        if not has_chunk and not has_chunk_text:
            errors.append(
                "Custom chunker must implement either chunk(text, file_path) "
                "or chunk_text(text) method"
            )

        return errors
