# Research: Text-Based RAG Indexing & Retrieval System

**Feature**: 001-text-rag-indexing  
**Date**: 2026-02-03  
**Purpose**: Technology evaluation and best practices research for implementation planning

## Technology Decisions

### 1. Embedding Model Framework: sentence-transformers

**Decision**: Use `sentence-transformers` library with HuggingFace models

**Rationale**:
- Most mature and widely-adopted embedding library in Python ecosystem
- Excellent model selection: all-MiniLM-L6-v2 (384-dim, fast), all-mpnet-base-v2 (768-dim, accurate)
- Simple API for both single and batch embeddings
- Strong community support and documentation
- PyTorch dependency acceptable for local desktop deployment
- Built-in support for model caching and automatic downloads

**Alternatives Considered**:
- **llama-cpp-python with embeddings**: Lighter weight but limited model selection, primarily optimized for LLM inference
- **OpenAI-compatible API**: Adds service management complexity, overkill for single-user local deployment

**Best Practices**:
- Use `all-MiniLM-L6-v2` as default (fast, 384-dim, 80MB model)
- Batch embeddings in groups of 32-64 for optimal throughput
- Enable multi-process data loading for large corpora
- Cache model in `~/.cache/huggingface/` (automatic)
- Use `encode()` method with `show_progress_bar=True` for user feedback

---

### 2. Vector Store: Qdrant (Embedded Mode)

**Decision**: Use `qdrant-client` in embedded mode for local vector database

**Rationale**:
- High-performance Rust core with Python bindings
- Embedded mode requires zero external service management
- Rich filtering capabilities (by file type, date, path patterns)
- Excellent documentation and API design
- Scales to millions of vectors on modern hardware
- Supports payload storage (metadata alongside vectors)
- HNSW algorithm for fast approximate nearest neighbor search
- Snapshot support for backup/restore

**Alternatives Considered**:
- **Chroma**: Easier initial setup but performance concerns at scale, less mature filtering
- **SQLite + FAISS**: Maximum control but requires manual index management, no built-in filtering
- **LanceDB**: Excellent for multimodal future but newer ecosystem, less Python tooling maturity

**Best Practices**:
- Use embedded mode: `QdrantClient(path="./qdrant_storage")`
- Create collection with cosine distance metric (standard for sentence embeddings)
- Store file metadata in payload: `{file_path, chunk_index, modification_time, file_type}`
- Use HNSW parameters: `m=16, ef_construct=100` (balance speed/accuracy)
- Implement upsert for incremental updates (idempotent)
- Regular collection optimization: `client.optimize_collection()`
- Snapshot before major re-indexing operations

---

### 3. LLM Framework: llama-cpp-python

**Decision**: Use `llama-cpp-python` for local LLM inference

**Rationale**:
- Excellent performance on both CPU and GPU via llama.cpp C++ backend
- Support for quantized models (Q4, Q5, Q8) reduces memory footprint
- Wide model compatibility (LLaMA, Mistral, Phi, Qwen families)
- Streaming response support for better UX
- No separate service required (embedded in Python process)
- Lower memory usage than transformers library
- Active development and model format support

**Alternatives Considered**:
- **Ollama API**: Great UX but adds service management complexity, unnecessary for embedded use case
- **transformers**: Maximum compatibility but high memory usage, slower CPU inference
- **vLLM**: Optimized for server/batch inference, overkill for single-user queries

**Best Practices**:
- Use GGUF format models (llama.cpp standard)
- Start with Q4_K_M quantization (good quality/speed balance)
- Set `n_ctx=2048` for context window (enough for ~5-10 retrieved chunks)
- Enable streaming: `stream=True` for real-time response display
- Configure `n_threads` based on CPU cores (e.g., `n_threads=4` for typical desktop)
- Implement timeout for long-running synthesis
- Default to 7B parameter models (Mistral-7B, LLaMA-2-7B) for desktop performance

---

### 4. Text Chunking: llama-index

**Decision**: Use `llama-index` text splitters for semantic-aware chunking

**Rationale**:
- Purpose-built for RAG workflows
- Intelligent chunking strategies that preserve semantic boundaries
- Code-aware splitting (respects function/class boundaries)
- Token-accurate chunking using tiktoken
- Lighter dependency footprint than full LangChain
- Good defaults for chunk size and overlap
- Markdown and document-aware splitting

**Alternatives Considered**:
- **LangChain TextSplitter**: Full featured but brings entire LangChain framework (heavy dependency)
- **Custom with tiktoken**: Maximum control but requires implementing semantic boundary logic
- **semantic-text-splitter**: Excellent performance but newer library, less battle-tested

**Best Practices**:
- Use `SentenceSplitter` for general text (respects sentence boundaries)
- Use `CodeSplitter` for source code (tree-sitter backed, language-aware)
- Default chunk size: 512 tokens (fits embedding model context, reasonable semantic unit)
- Overlap: 50 tokens (preserves context across chunks)
- Use tiktoken tokenizer matching embedding model (`cl100k_base` for general use)
- Preserve metadata: store chunk index and character offsets for source traceability

---

## Architecture Patterns

### Pipeline Architecture

**Pattern**: Modular pipeline with clear stage boundaries

**Stages**:
1. **Discovery**: File scanning → FileMetadata list
2. **Extraction**: FileMetadata → TextChunk list (with content)
3. **Embedding**: TextChunk list → EmbeddingRecord list
4. **Storage**: EmbeddingRecord list → Vector store persistence
5. **Retrieval**: Query string → TextChunk list (via similarity search)
6. **Synthesis**: Query + TextChunk list → Answer string (via LLM)

**Benefits**:
- Each stage independently testable
- Clear contracts between stages
- Easy to parallelize stages (e.g., batch embedding)
- Future multimodal support adds parallel pipelines

---

### Configuration Management

**Pattern**: Pydantic settings with TOML configuration file

**Structure**:
```python
# config/settings.py using Pydantic BaseSettings
class KragConfig(BaseSettings):
    directories: List[Path]
    exclusion_patterns: List[str]
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 512
    chunk_overlap: int = 50
    vector_store_path: Path = Path("./qdrant_storage")
    llm_model_path: Path
    top_k: int = 5
```

**Configuration File** (`~/.krag/config.toml`):
```toml
[directories]
paths = ["/home/user/documents", "/mnt/nas/projects"]

[exclusion]
patterns = ["node_modules", ".git", "__pycache__", "build", "dist"]

[embedding]
model = "all-MiniLM-L6-v2"
batch_size = 32

[chunking]
size = 512
overlap = 50

[retrieval]
top_k = 5

[llm]
model_path = "/home/user/.models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
n_ctx = 2048
```

---

### Incremental Indexing Strategy

**Approach**: Modification time tracking with file hash verification

**Algorithm**:
1. Query vector store for all indexed file paths
2. Scan filesystem for current files
3. Categorize files:
   - **New**: In filesystem, not in store → full index
   - **Modified**: In both, but mtime newer → re-index
   - **Deleted**: In store, not in filesystem → remove from store
   - **Unchanged**: In both, mtime matches → skip
4. Process only New + Modified files through pipeline
5. Delete vectors for Deleted files from store

**Optimization**: Store file content hash (SHA-256) to detect true modifications (handles mtime-only changes from file moves)

---

### Error Handling Strategy

**Principle**: Fail gracefully per-file, log errors, continue processing

**Implementation**:
- Wrap each file processing in try-except
- Log errors with file path and exception details
- Collect error summary for end-of-indexing report
- Provide `--strict` flag for fail-fast behavior in development
- Store processing status in metadata store for retry logic

---

## Performance Optimization

### Embedding Generation
- **Batch processing**: Group chunks into batches of 32-64
- **Multi-GPU support**: sentence-transformers auto-detects CUDA
- **Progress tracking**: Use tqdm for user feedback on long operations

### Vector Storage
- **Bulk upsert**: Collect embedding records and upsert in batches of 100-500
- **Async operations**: Use Qdrant async client for concurrent writes
- **Index optimization**: Run optimize after major batch operations

### File Discovery
- **Parallel scanning**: Use concurrent.futures for multi-directory scanning
- **Early filtering**: Apply exclusion patterns during scan, not after

### Memory Management
- **Streaming processing**: Process files in chunks, don't load entire corpus into memory
- **Model caching**: Load embedding/LLM models once, reuse across operations
- **Cleanup**: Explicitly del large tensors/model outputs after use

---

## Testing Strategy

### Unit Tests
- **Discovery**: Mock filesystem, test filtering logic
- **Extraction**: Test chunking with known text samples
- **Embeddings**: Mock sentence-transformers, verify batching
- **Storage**: Use in-memory Qdrant for fast tests
- **Retrieval**: Test similarity ranking with known vectors
- **Synthesis**: Mock LLM, test prompt construction

### Integration Tests
- **End-to-end indexing**: Small test corpus → verify all files embedded
- **Query pipeline**: Query test corpus → verify relevant retrieval
- **Incremental update**: Index, modify files, re-index → verify correct updates

### Contract Tests
- **Vector store contract**: Verify upsert, search, delete operations
- **Embedding model contract**: Verify output dimensions and format
- **LLM contract**: Verify response format and streaming

### Performance Tests
- **Indexing throughput**: Measure files/second on test corpus
- **Query latency**: Measure p50, p95, p99 for retrieval + synthesis
- **Memory usage**: Profile memory consumption during large batch operations

---

## Security & Privacy Considerations

- **Local-only**: All processing on-device, no external API calls
- **File access**: Respect filesystem permissions, log access denials
- **Sensitive data**: No automatic redaction (user responsible for exclusion patterns)
- **Model provenance**: Document model sources (HuggingFace, GGUF repos)
- **Data persistence**: Document where embeddings and metadata are stored

---

## Observability & Logging

### Logging Levels
- **INFO**: Indexing progress, files processed, query execution
- **WARNING**: Skipped files, parsing errors, performance degradation
- **ERROR**: Fatal errors per file, configuration issues
- **DEBUG**: Detailed pipeline stage timings, vector store operations

### Metrics to Track
- Files discovered, processed, skipped, errored
- Chunks generated, embeddings created
- Vector store size, query latency
- LLM token usage, generation speed

### Progress Indicators
- Use `rich` library for CLI progress bars
- Show: current file, files processed/total, elapsed time, ETA
- Summary report at end: success/error counts, total time

---

## Future Extensibility (Phase 2+)

### Multimodal Support
- Add `ImageExtractor` alongside `TextExtractor`
- Use CLIP embeddings for images (different embedding model)
- Store modality type in vector store payload
- Query router selects appropriate modality pipeline

### 3D Model Support
- Extract mesh metadata, thumbnails
- Use specialized 3D embedding models or multi-view CLIP
- Similar pipeline structure, different extraction/embedding modules

### Advanced Features
- Query filtering (by date, file type, directory)
- Hybrid search (keyword + semantic)
- Re-ranking with cross-encoder models
- Citation tracking (source file + chunk position)
