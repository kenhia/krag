# Data Model: Text-Based RAG Indexing & Retrieval System

**Feature**: 001-text-rag-indexing  
**Date**: 2026-02-03  
**Purpose**: Core entity definitions and relationships

## Overview

The system operates on six core entities that flow through the indexing and query pipelines. Entities are designed to be immutable where possible and support serialization for persistence.

---

## Core Entities

### 1. FileMetadata

Represents a discovered file with tracking information for indexing status.

**Attributes**:
- `file_path: Path` - Absolute path to the file
- `file_size: int` - File size in bytes
- `modification_time: datetime` - Last modification timestamp from filesystem
- `file_type: str` - Detected file type (e.g., "python", "markdown", "text")
- `content_hash: str` - SHA-256 hash of file content (for change detection)
- `indexing_status: IndexingStatus` - Current status (pending, completed, failed, skipped)
- `last_indexed_at: datetime | None` - Timestamp of last successful indexing
- `error_message: str | None` - Error details if indexing failed
- `chunk_count: int` - Number of chunks generated from this file

**Validation Rules**:
- `file_path` must exist or have existed (for deletion tracking)
- `file_size` must be non-negative
- `modification_time` must be <= current time
- `file_type` must be in supported types list
- `chunk_count` must be non-negative

**State Transitions**:
```
pending → completed  (successful indexing)
pending → failed     (error during indexing)
pending → skipped    (exclusion pattern or size limit)
completed → pending  (file modified, needs re-indexing)
completed → deleted  (file removed from filesystem)
```

**Relationships**:
- One FileMetadata has many TextChunks (1:N)

---

### 2. TextChunk

Represents a segment of extracted and chunked text from a source file.

**Attributes**:
- `chunk_id: str` - Unique identifier (UUID)
- `file_path: Path` - Reference to source file
- `chunk_index: int` - Sequential index within file (0-based)
- `content: str` - The actual text content of the chunk
- `start_char: int` - Character offset where chunk starts in original file
- `end_char: int` - Character offset where chunk ends in original file
- `token_count: int` - Number of tokens in chunk (for embedding model)
- `created_at: datetime` - Timestamp when chunk was created

**Validation Rules**:
- `chunk_id` must be unique across all chunks
- `chunk_index` must be non-negative
- `content` must be non-empty and <= max_chunk_size
- `start_char` < `end_char`
- `token_count` must match actual token count of content
- `token_count` must be <= embedding model max tokens

**Relationships**:
- Many TextChunks belong to one FileMetadata (N:1)
- One TextChunk has one EmbeddingRecord (1:1)

---

### 3. EmbeddingRecord

Represents a vector embedding of a text chunk, stored in the vector database.

**Attributes**:
- `embedding_id: str` - Unique identifier (matches chunk_id)
- `chunk_id: str` - Reference to source TextChunk
- `vector: List[float]` - The embedding vector (dimensionality depends on model)
- `vector_dim: int` - Dimension of the vector (e.g., 384, 768)
- `model_name: str` - Name of embedding model used
- `created_at: datetime` - Timestamp when embedding was generated

**Payload** (stored in vector DB alongside vector):
- `file_path: str` - Source file path
- `chunk_index: int` - Chunk position in file
- `file_type: str` - File type for filtering
- `modification_time: str` - ISO format timestamp for filtering

**Validation Rules**:
- `embedding_id` must be unique
- `vector` length must equal `vector_dim`
- `vector_dim` must match embedding model output dimension
- All vector values must be finite floats (no NaN/Inf)
- `model_name` must match configured embedding model

**Relationships**:
- One EmbeddingRecord corresponds to one TextChunk (1:1)

---

### 4. QueryResult

Represents a retrieved chunk with relevance score from similarity search.

**Attributes**:
- `chunk_id: str` - Reference to retrieved TextChunk
- `score: float` - Similarity score (0.0 to 1.0, higher is more similar)
- `rank: int` - Rank in results (1-based, 1 = most relevant)
- `chunk_content: str` - The text content of the chunk
- `file_path: Path` - Source file of the chunk
- `chunk_index: int` - Position within source file
- `file_type: str` - Type of source file

**Validation Rules**:
- `score` must be in range [0.0, 1.0]
- `rank` must be positive integer
- `chunk_content` must be non-empty

**Relationships**:
- Many QueryResults returned per Query (N:1 conceptually)

---

### 5. IndexingJob

Represents a single indexing operation (full or incremental).

**Attributes**:
- `job_id: str` - Unique identifier (UUID)
- `job_type: JobType` - Type (full, incremental)
- `status: JobStatus` - Current status (running, completed, failed)
- `start_time: datetime` - When job started
- `end_time: datetime | None` - When job completed (None if still running)
- `files_discovered: int` - Total files found
- `files_processed: int` - Files successfully indexed
- `files_skipped: int` - Files skipped (exclusions, already indexed)
- `files_errored: int` - Files with errors
- `chunks_generated: int` - Total chunks created
- `embeddings_created: int` - Total embeddings generated
- `error_summary: List[FileError]` - List of errors encountered

**FileError** sub-structure:
- `file_path: Path`
- `error_type: str`
- `error_message: str`

**Validation Rules**:
- `files_processed + files_skipped + files_errored` should equal `files_discovered`
- `end_time` must be >= `start_time` when set
- Status cannot transition from completed/failed back to running

**State Transitions**:
```
running → completed  (job finished successfully)
running → failed     (critical error halted job)
```

---

### 6. Configuration

Represents system configuration settings.

**Attributes**:

**Directories**:
- `directory_paths: List[Path]` - Directories to index
- `exclusion_patterns: List[str]` - Glob patterns to exclude

**File Processing**:
- `supported_file_types: List[str]` - File extensions to process
- `max_file_size_mb: int` - Maximum file size to process
- `skip_binary_files: bool` - Whether to skip binary files

**Embedding**:
- `embedding_model: str` - Model name (e.g., "all-MiniLM-L6-v2")
- `embedding_batch_size: int` - Batch size for embedding generation
- `embedding_device: str` - Device to use ("cpu", "cuda", "mps")

**Chunking**:
- `chunk_size: int` - Target chunk size in tokens
- `chunk_overlap: int` - Overlap between chunks in tokens

**Vector Store**:
- `vector_store_path: Path` - Path to Qdrant storage
- `collection_name: str` - Collection name in vector store
- `distance_metric: str` - Distance metric ("cosine", "dot", "euclidean")

**Retrieval**:
- `top_k: int` - Number of results to retrieve

**LLM**:
- `llm_model_path: Path` - Path to GGUF model file
- `llm_context_size: int` - Context window size (n_ctx)
- `llm_num_threads: int` - Number of threads for inference
- `llm_temperature: float` - Temperature for generation

**Validation Rules**:
- All paths must be absolute
- `directory_paths` must not be empty
- `chunk_size` > `chunk_overlap`
- `chunk_overlap` >= 0
- `embedding_batch_size` > 0
- `max_file_size_mb` > 0 (files exceeding this are skipped, never truncated)
- `top_k` > 0
- `llm_temperature` in range [0.0, 2.0]

---

## Enumerations

### IndexingStatus
```python
class IndexingStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DELETED = "deleted"
```

### JobType
```python
class JobType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
```

### JobStatus
```python
class JobStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

---

## Data Flow

### Indexing Pipeline
```
FileMetadata → TextChunk → EmbeddingRecord → Vector Store
```

1. Discovery creates `FileMetadata` records
2. Extraction creates `TextChunk` records from each file
3. Embedding creates `EmbeddingRecord` for each chunk
4. Storage persists `EmbeddingRecord` to vector store

### Query Pipeline
```
Query String → Query Embedding → Similarity Search → QueryResult List → LLM → Answer
```

1. Query string is embedded (same model as documents)
2. Vector store returns top-k similar embeddings
3. Results hydrated into `QueryResult` objects
4. Content from `QueryResult` passed to LLM with query
5. LLM generates synthesized answer

---

## Storage Strategy

### Vector Store (Qdrant)
- Collection contains `EmbeddingRecord` vectors
- Payload stores: file_path, chunk_index, file_type, modification_time
- Indexed by `embedding_id` (chunk_id)

### FileMetadata Persistence (JSON)
- Location: `{vector_store_path}/metadata.json`
- Format: JSON array of FileMetadata objects
- Purpose: Enable incremental indexing across CLI invocations
- Saved after each indexing operation (full or incremental)
- Loaded on IndexingOrchestrator initialization
- Contains: file_path, file_size, modification_time, content_hash, last_indexed_at, chunk_count

### Metadata Store (SQLite) [Future Enhancement]
- Table: `file_metadata` - All FileMetadata records
- Table: `indexing_jobs` - Job history and statistics
- Indexed by file_path for quick lookups
- Used for incremental update logic
- Note: Currently using JSON file; SQLite planned for Phase 6+

### Configuration
- TOML file: `~/.krag/config.toml` (or YAML for legacy support)
- Loaded on startup, validated with Pydantic

---

## Entity Serialization

All entities implement:
- `to_dict() -> Dict[str, Any]` - For JSON serialization
- `from_dict(data: Dict[str, Any]) -> Self` - For deserialization
- Pydantic models used for validation and serialization
