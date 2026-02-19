# Contract: Indexer File Processor

**Module**: `src/krag/orchestration/indexer.py`  
**Method**: `IndexingOrchestrator._process_file()`  

## Signature

```python
def _process_file(
    self,
    file_meta: FileMetadata,
    plugin_handler: FileHandler | None,
) -> FileProcessingResult:
    """Process a single file through the extraction → chunking → embedding → payload pipeline.

    This is the shared per-file processing method used by both index_full()
    and index_incremental(). It ensures consistent behavior across indexing modes.

    Args:
        file_meta: Metadata for the file to process.
        plugin_handler: Plugin handler for this file type, or None for default processing.

    Returns:
        FileProcessingResult with payloads ready for upsert, or error info on failure.

    Invariants:
        - Chunker is ALWAYS reset at the start (no state leakage from previous files)
        - Plugin name resolution uses getattr(handler, "name", handler.__class__.__name__)
        - Empty file_path in metadata is rejected with an error result
    """
```

## FileProcessingResult

```python
@dataclass
class FileProcessingResult:
    payloads: list[dict]
    chunk_count: int
    handler_name: str | None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None
```

## Processing Steps

1. Reset `chunker = None` (prevents F-04 state leakage)
2. If `plugin_handler` provided:
   a. Resolve handler name via `getattr(plugin_handler, "name", plugin_handler.__class__.__name__)` (F-12 consistency)
   b. Extract text via plugin handler
   c. Resolve chunker via `chunking_resolver` using consistent handler name
3. If no plugin handler or extraction failed:
   a. Extract text via default `TextExtractor`
   b. Use `self.chunker` as the active chunker
4. Chunk text with active chunker
5. Generate embeddings via `self.embedding_generator`
6. Build Qdrant point payloads with metadata
7. Return `FileProcessingResult`
