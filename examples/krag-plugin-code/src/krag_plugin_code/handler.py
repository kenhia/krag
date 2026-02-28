"""Code file handler plugin for krag.

Implements FileTypeHandler for source code files, using tree-sitter
AST parsing for semantic chunking.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from krag.plugins.interfaces import ChunkingStrategy, FileTypeHandler

from krag_plugin_code.ast_chunker import ASTChunker
from krag_plugin_code.languages import (
    get_language_for_extension,
    get_supported_extensions,
)

logger = logging.getLogger(__name__)


class CodeFileHandler(FileTypeHandler):
    """Handler for source code files.

    Uses tree-sitter for AST-based semantic chunking.
    Registered as 'code' plugin via entry point.
    """

    def __init__(self) -> None:
        """Initialize the code file handler."""
        self._config: dict[str, Any] = {}
        self._chunker_cache: dict[str, ASTChunker] = {}

    @property
    def name(self) -> str:
        """Return plugin name."""
        return "code"

    @property
    def version(self) -> str:
        """Return plugin version."""
        return "0.1.0"

    @property
    def required_api_version(self) -> str:
        """Return required plugin API version."""
        return "1.0.0"

    def supported_extensions(self) -> list[str]:
        """Return all supported code file extensions.

        Returns:
            List of extensions like ['.py', '.rs', '.js', ...].
        """
        return get_supported_extensions()

    def can_handle(self, file_path: Path) -> bool:
        """Check if this handler can process the given file.

        Args:
            file_path: Path to the file.

        Returns:
            True if the file extension is supported.
        """
        return file_path.suffix.lower() in self.supported_extensions()

    def extract_text(self, file_path: Path) -> str:
        """Extract text from a source code file.

        Args:
            file_path: Path to the source file.

        Returns:
            Source code text as a string.

        Raises:
            FileNotFoundError: If file doesn't exist.
            UnicodeDecodeError: If file isn't valid UTF-8 text.
        """
        return file_path.read_text(encoding="utf-8")

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract code-specific metadata from a source file.

        Args:
            file_path: Path to the source file.

        Returns:
            Dict with language, line_count, has_parse_errors, file_size.
        """
        extension = file_path.suffix.lower()
        language = get_language_for_extension(extension)
        try:
            text = file_path.read_text(encoding="utf-8")
            line_count = text.count("\n") + 1
            file_size = len(text.encode("utf-8"))

            # Check for parse errors if we have a grammar
            has_parse_errors = False
            if language:
                chunker = self._get_chunker(language)
                if chunker._parser is not None:
                    tree = chunker._parser.parse(text.encode("utf-8"))
                    has_parse_errors = tree.root_node.has_error
        except (FileNotFoundError, UnicodeDecodeError):
            line_count = 0
            file_size = 0
            has_parse_errors = True

        return {
            "language": language or "unknown",
            "line_count": line_count,
            "has_parse_errors": has_parse_errors,
            "file_size": file_size,
        }

    def get_chunking_strategy(self) -> ChunkingStrategy:
        """Return the chunking strategy for code files.

        Returns:
            ChunkingStrategy.CODE_AWARE
        """
        return ChunkingStrategy.CODE_AWARE

    def get_chunker(self, file_path: Path) -> ASTChunker:
        """Get an AST chunker for the given file.

        Args:
            file_path: Path to determine language.

        Returns:
            ASTChunker instance configured for the file's language.
        """
        extension = file_path.suffix.lower()
        language = get_language_for_extension(extension) or "unknown"
        return self._get_chunker(language)

    # Default code-specific embedding model (Jina v2 base code)
    _DEFAULT_CODE_EMBEDDING_MODEL = "jinaai/jina-embeddings-v2-base-code"

    def get_embedding_model(self) -> str | None:
        """Return the preferred embedding model for code.

        Defaults to jinaai/jina-embeddings-v2-base-code, a code-aware
        embedding model trained on code and documentation pairs.
        Can be overridden via plugin config ``embedding_model`` key.

        Returns:
            A code-specific embedding model name.
        """
        return self._config.get("embedding_model", self._DEFAULT_CODE_EMBEDDING_MODEL)

    def initialize(self, config: dict[str, Any], context: Any = None) -> None:
        """Initialize the handler with configuration.

        Args:
            config: Plugin configuration dict.
            context: Plugin context providing access to krag services (optional).
        """
        self._config = config
        self._context = context
        logger.info("Code file handler initialized")

    def cleanup(self) -> None:
        """Clean up resources."""
        self._chunker_cache.clear()
        logger.debug("Code file handler cleaned up")

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """Return the configuration schema for this plugin.

        Returns:
            Dict describing configuration options.
        """
        return {
            "max_chunk_size": {
                "type": "integer",
                "default": 2048,
                "description": "Maximum chunk size in characters",
            },
            "embedding_model": {
                "type": "string",
                "default": None,
                "description": "Preferred embedding model for code files",
            },
        }

    def _get_chunker(self, language: str) -> ASTChunker:
        """Get or create a cached ASTChunker for the language.

        Args:
            language: Language name.

        Returns:
            ASTChunker instance.
        """
        if language not in self._chunker_cache:
            max_chunk_size = self._config.get("max_chunk_size", 2048)
            self._chunker_cache[language] = ASTChunker(
                language=language,
                max_chunk_size=max_chunk_size,
            )
        return self._chunker_cache[language]
