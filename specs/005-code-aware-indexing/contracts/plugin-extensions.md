# Contract: Plugin Extensions for Code-Aware Indexing

## FileTypeHandler ABC Extension

The existing `FileTypeHandler` ABC gains one new optional method. This is a non-breaking extension — existing plugins are unaffected because the default implementation returns `None`.

### New Method: `get_embedding_model()`

```python
class FileTypeHandler(ABC):
    # ... existing interface unchanged ...

    def get_embedding_model(self) -> str | None:
        """Declare the preferred embedding model for files handled by this plugin.

        Returns:
            A HuggingFace model name or local path to a SentenceTransformer-compatible
            model, or None to use the system default (BAAI/bge-base-en-v1.5).

        Examples:
            >>> handler.get_embedding_model()
            "jinaai/jina-embeddings-v2-base-code"
            >>> handler.get_embedding_model()  # default implementation
            None
        """
        return None
```

### Contract Guarantees

1. **Backward compatibility**: Existing plugins that don't override `get_embedding_model()` automatically use the system default. No code changes required.
2. **Model availability**: The embedding orchestrator caches models by name. Multiple plugins declaring the same model share a single loaded instance.
3. **Dimension consistency**: All embedding models used in a single collection must declare the same vector dimension. The orchestrator validates this at startup and raises `ValueError` if dimensions don't match.

---

## CodeFileHandler Contract

The code plugin implements `FileTypeHandler` with the following contract:

```python
class CodeFileHandler(FileTypeHandler):
    """Code-aware file handler using tree-sitter AST parsing."""

    @property
    def name(self) -> str:
        return "code"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def required_api_version(self) -> str:
        return "1.0.0"

    def supported_extensions(self) -> list[str]:
        """Return extensions for installed tree-sitter grammars.

        Dynamically discovers installed grammars. Only claims extensions
        for which a grammar is actually available.

        Returns:
            e.g., [".py", ".rs"] if tree-sitter-python and tree-sitter-rust are installed.
        """
        ...

    def extract_text(self, file_path: Path) -> str:
        """Read source file as UTF-8 text.

        Returns raw file content. Chunking is handled by the custom chunker,
        not by text extraction.
        """
        ...

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract file-level metadata.

        Returns:
            {
                "language": "python",
                "line_count": 251,
                "has_parse_errors": false,
            }
        """
        ...

    def get_chunking_strategy(self) -> ChunkingStrategy:
        """Return CUSTOM to use the AST-based chunker."""
        return ChunkingStrategy.CUSTOM

    def get_embedding_model(self) -> str:
        """Declare code embedding model."""
        return "jinaai/jina-embeddings-v2-base-code"

    def initialize(self, config: dict, context: PluginContext | None = None) -> None:
        """Initialize tree-sitter parsers for installed languages.

        Config keys:
            code_chunk_size: int (default 2048) — max chunk size in chars
            languages: list[str] | None — restrict to specific languages (default: all installed)
        """
        ...
```

### Chunking Contract

The code plugin provides a custom chunker (via `ChunkingStrategy.CUSTOM`):

```python
class ASTChunker:
    """Tree-sitter AST-based code chunker."""

    def chunk(
        self,
        text: str,
        file_path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Chunk source code into semantic units.

        Guarantees:
        1. Each chunk is a complete semantic unit when possible.
        2. Oversized units are split at statement boundaries, never mid-expression.
        3. Method chunks include parent class name as context prefix.
        4. Chunks include code metadata in a parallel dict (not on TextChunk itself).
        5. Falls back to character-based TextChunker if tree-sitter can't parse.

        Args:
            text: Source code as string.
            file_path: Path to source file (for metadata).
            metadata: File-level metadata from extract_metadata().

        Returns:
            List of TextChunk objects. Code metadata is stored separately
            and injected into vector payload during indexing.
        """
        ...

    def get_chunk_metadata(self, chunk: TextChunk) -> dict[str, Any]:
        """Return code-specific metadata for a chunk.

        Called by the indexer after chunking to get metadata for the vector payload.

        Returns:
            {
                "language": "python",
                "function_name": "_deduplicate",
                "class_name": "Retriever",
                "start_line": 45,
                "end_line": 68,
                "node_type": "function_definition",
                "has_decorators": false,
                "imports": [],
            }
        """
        ...
```

### Metadata Flow

The code plugin's metadata flows through the system as follows:

1. **Chunking**: `ASTChunker.chunk()` produces `TextChunk` objects and stores code metadata in an internal map (`chunk_id → metadata dict`).
2. **Metadata retrieval**: `ASTChunker.get_chunk_metadata(chunk)` returns the metadata for a chunk.
3. **Indexing**: `IndexingOrchestrator` calls `get_chunk_metadata()` for each chunk and merges the result into the vector store payload dict.
4. **Retrieval**: `Retriever` reads metadata from the Qdrant payload. Missing code fields default to `None`.
5. **Display**: `QueryResult.format_source_ref()` formats the structured reference from metadata.

---

## Error Contracts

### Tree-sitter Parse Failure
- **When**: `tree.root_node.has_error` is `True` or grammar not installed.
- **Behavior**: Log warning, fall back to `TextChunker(chunk_size=2048, chunk_overlap=64)`.
- **Guarantee**: Never raises. Never crashes. Always produces chunks.

### Missing Grammar
- **When**: File extension matches but no grammar package installed.
- **Behavior**: Log info message, fall back to default chunker.
- **Guarantee**: Plugin only claims extensions for installed grammars (checked at `initialize()` time).

### Binary Files
- **When**: File detected as binary (null bytes in first 8KB).
- **Behavior**: Return empty string from `extract_text()`, producing zero chunks.
- **Guarantee**: Respects `skip_binary_files` config.
