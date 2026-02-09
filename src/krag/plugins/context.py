"""Plugin context for accessing krag core services.

This module provides the PluginContext class that plugins receive during initialization,
giving them access to krag's embedding generation, vector storage, chunking, logging,
and failure reporting capabilities.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from krag.embeddings.generator import EmbeddingGenerator
from krag.extraction.chunker import TextChunker
from krag.storage.vector_store import VectorStore


class PluginContext:
    """Context object providing plugins access to krag's core capabilities.

    This context is passed to plugins during initialization to give them access
    to krag's services without tight coupling. Plugins can use these services
    to implement advanced functionality or report files they cannot process.

    Attributes:
        embedding_generator: Access to krag's embedding generation service
        vector_store: Access to krag's vector storage for query/upsert operations
        chunker: Access to krag's default text chunker
        logger: Plugin-scoped structured logger
        report_indexing_failure: Callback for reporting failed file processing

    Example:
        >>> def initialize(self, config: dict[str, Any], context: PluginContext) -> None:
        ...     self._context = context
        ...     self._context.logger.info(f"Initialized {self.name} plugin")
        ...
        >>> def extract_text(self, file_path: Path) -> str:
        ...     try:
        ...         return self._do_extraction(file_path)
        ...     except CorruptedFileError:
        ...         self._context.report_indexing_failure(file_path, "File is corrupted")
        ...         return ""
    """

    def __init__(
        self,
        embedding_generator: EmbeddingGenerator,
        vector_store: VectorStore,
        chunker: TextChunker,
        logger: logging.Logger,
        report_indexing_failure: Callable[[Path, str], None],
    ):
        """Initialize plugin context.

        Args:
            embedding_generator: Embedding generation service
            vector_store: Vector storage service
            chunker: Text chunking service
            logger: Logger for plugin messages
            report_indexing_failure: Callback to report files that cannot be indexed
        """
        self.embedding_generator = embedding_generator
        self.vector_store = vector_store
        self.chunker = chunker
        self.logger = logger
        self.report_indexing_failure = report_indexing_failure
