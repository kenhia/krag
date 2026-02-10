"""Chunking strategy resolution for plugins.

This module provides the ChunkingStrategyResolver class that maps plugin chunking
preferences (ChunkingStrategy enum or custom chunkers) to actual TextChunker instances.
"""

from __future__ import annotations

import logging
from typing import Any

from krag.extraction.chunker import TextChunker
from krag.plugins.interfaces import ChunkingStrategy

logger = logging.getLogger(__name__)


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
    ):
        """Initialize chunking strategy resolver.

        Args:
            default_chunk_size: Default chunk size for built-in chunkers
            default_chunk_overlap: Default overlap for built-in chunkers
        """
        self._default_chunk_size = default_chunk_size
        self._default_chunk_overlap = default_chunk_overlap
        self._default_chunker: TextChunker | None = None

        logger.debug(
            f"ChunkingStrategyResolver initialized with "
            f"chunk_size={default_chunk_size}, overlap={default_chunk_overlap}"
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
        - ChunkingStrategy.CODE_AWARE → default chunker (not yet implemented)
        - Custom TextChunker → validate and return
        - Invalid → log warning and return default

        Args:
            strategy: Chunking strategy from plugin's get_chunking_strategy()
            plugin_name: Plugin name for logging (optional)

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

        # Handle None - use default
        if strategy is None:
            logger.debug(f"{plugin_label} returned None, using default chunker")
            return self._get_default_chunker()

        # Handle ChunkingStrategy enum
        if isinstance(strategy, ChunkingStrategy):
            return self._resolve_enum_strategy(strategy, plugin_label)

        # Handle custom TextChunker instance
        if self._is_valid_chunker(strategy):
            logger.info(f"{plugin_label} provided custom chunker: {type(strategy).__name__}")
            return strategy

        # Invalid strategy - fallback to default
        logger.warning(
            f"{plugin_label} returned invalid chunking strategy: {type(strategy).__name__}. "
            f"Using default chunker as fallback."
        )
        return self._get_default_chunker()

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
            logger.warning(
                f"{plugin_label} requested CODE_AWARE strategy, but it's not yet implemented. "
                f"Using DEFAULT strategy as fallback."
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
            bool: True if object is a valid chunker
        """
        # Check if it has a chunk method
        if not hasattr(obj, "chunk"):
            return False

        # Check if chunk is callable
        if not callable(obj.chunk):
            return False

        # Valid chunker (duck typing - if it has chunk(), it's a chunker)
        return True
