"""API request/response schemas for kragd.

Pydantic models for all HTTP API payloads. These are distinct from the internal
domain models in krag.models and serve as the API contract boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ──────────────────────────────────────────────
# Enums / Literals (used by multiple schemas)
# ──────────────────────────────────────────────

_LLM_SLOTS = {"text", "code"}
_INDEX_MODES = {"full", "incremental"}
_HEALTH_STATUSES = {"healthy", "degraded"}
_INDEX_STATUSES = {"completed", "failed", "none", "running"}


# ──────────────────────────────────────────────
# Request Models
# ──────────────────────────────────────────────


class QueryRequest(BaseModel):
    """POST /query request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "What is the krag architecture?",
                    "top_k": 5,
                    "mode": "default",
                    "include_debug": False,
                }
            ]
        }
    )

    query: str = Field(..., min_length=1, max_length=10000, description="Query text")
    top_k: int | None = Field(None, ge=1, le=100, description="Number of results")
    preset: str | None = Field(None, description="Prompt preset name")
    llm: str | None = Field(None, description="Force specific LLM slot (deprecated — use mode)")
    mode: str | None = Field(None, description="Named retrieval mode (e.g. default, code, docs)")
    include_debug: bool = Field(False, description="Include debug metadata in response")

    @field_validator("llm")
    @classmethod
    def validate_llm(cls, v: str | None) -> str | None:
        """Ensure llm is a valid slot name."""
        if v is not None and v not in _LLM_SLOTS:
            raise ValueError(f"llm must be 'text' or 'code', got: {v!r}")
        return v


class RetrieveRequest(BaseModel):
    """POST /retrieve request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "How does the indexing pipeline work?",
                    "top_k": 10,
                    "mode": "code",
                }
            ]
        }
    )

    query: str = Field(..., min_length=1, max_length=10000, description="Query text")
    top_k: int | None = Field(None, ge=1, le=100, description="Number of results")
    mode: str | None = Field(None, description="Named retrieval mode")


class DebugQueryRequest(BaseModel):
    """POST /debug/query request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "Explain the retriever module",
                    "top_k": 5,
                    "preset": "rag",
                    "mode": "code",
                }
            ]
        }
    )

    query: str = Field(..., min_length=1, max_length=10000, description="Query text")
    top_k: int | None = Field(None, ge=1, le=100, description="Number of results")
    preset: str | None = Field(None, description="Prompt preset name")
    llm: str | None = Field(None, description="Force specific LLM slot (deprecated — use mode)")
    mode: str | None = Field(None, description="Named retrieval mode")

    @field_validator("llm")
    @classmethod
    def validate_llm(cls, v: str | None) -> str | None:
        """Ensure llm is a valid slot name."""
        if v is not None and v not in _LLM_SLOTS:
            raise ValueError(f"llm must be 'text' or 'code', got: {v!r}")
        return v


class QdrantFilters(BaseModel):
    """Payload filters for QdrantSearchRequest."""

    file_type: str | None = Field(None, description="Filter by file_type payload field")
    file_path_contains: str | None = Field(
        None, description="Substring match on file_path (include)"
    )
    file_path_excludes: list[str] | None = Field(
        None, description="Substring patterns to exclude from file_path"
    )


class QdrantSearchRequest(BaseModel):
    """POST /debug/qdrant request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "vector store implementation",
                    "vector_space": "code",
                    "top_k": 10,
                    "score_threshold": 0.5,
                    "with_payload": True,
                }
            ]
        }
    )

    query: str = Field(..., min_length=1, description="Query text")
    vector_space: str | None = Field(None, description="Restrict to one vector space")
    top_k: int = Field(10, ge=1, le=1000, description="Number of results")
    score_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum similarity score"
    )
    with_payload: bool = Field(True, description="Include chunk payloads")
    filters: QdrantFilters | None = Field(None, description="Payload filtering")


class IndexRequest(BaseModel):
    """POST /index request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mode": "incremental",
                    "dry_run": False,
                }
            ]
        }
    )

    mode: str = Field("incremental", description="Indexing mode")
    directories: list[str] | None = Field(None, description="Override directories")
    file_types: list[str] | None = Field(None, description="Filter file extensions")
    exclude_patterns: list[str] | None = Field(None, description="Additional exclusions")
    vector_store_path: str | None = Field(None, description="Override vector store path")
    dry_run: bool = Field(False, description="Preview without indexing")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Ensure mode is valid."""
        if v not in _INDEX_MODES:
            raise ValueError(f"mode must be 'full' or 'incremental', got: {v!r}")
        return v


# ──────────────────────────────────────────────
# Response Models
# ──────────────────────────────────────────────


class SourceChunk(BaseModel):
    """A source chunk returned in query/retrieve responses."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    file_path: str = Field(..., description="Source file path")
    score: float = Field(..., description="Relevance score")
    rank: int = Field(..., description="Position in results")
    chunk_content: str = Field(..., description="Chunk text content")
    file_type: str = Field(..., description="File extension/type")
    language: str | None = Field(None, description="Programming language")
    function_name: str | None = Field(None, description="Containing function")
    class_name: str | None = Field(None, description="Containing class")
    start_line: int | None = Field(None, description="Start line in source file")
    end_line: int | None = Field(None, description="End line in source file")
    collection: str | None = Field(None, description="Source collection (code, tests, docs, text)")


class DebugMetadata(BaseModel):
    """Debug information returned alongside query responses."""

    llm_used: str = Field(..., description="Which LLM generated the answer")
    llm_model: str = Field(..., description="Full model filename")
    route: str = Field(..., description="Route decision (text or code)")
    auto_routed: bool = Field(..., description="Whether routing was automatic")
    route_reason: str | None = Field(None, description="Why auto-routing chose this LLM")
    preset: str = Field(..., description="Active prompt preset name")
    mode: str | None = Field(None, description="Active retrieval mode name (if used)")
    collections_searched: list[str] | None = Field(
        None, description="Collections targeted by the active mode"
    )
    retrieval_time_ms: float = Field(..., ge=0.0, description="Milliseconds for retrieval")
    generation_time_ms: float = Field(..., ge=0.0, description="Milliseconds for LLM synthesis")
    embedding_models_used: list[str] = Field(..., description="Embedding model names")
    vector_spaces_searched: list[str] = Field(..., description="Qdrant named spaces queried")
    total_candidates_before_dedup: int = Field(..., ge=0, description="Results before dedup")
    total_candidates_after_dedup: int = Field(..., ge=0, description="Results after dedup")
    similarity_threshold: float = Field(..., description="Active similarity threshold")
    per_space_result_counts: dict[str, int] = Field(..., description="Results per vector space")
    lexicon_terms_injected: int = Field(
        0, ge=0, description="Number of lexicon terms injected into prompt"
    )
    critic_scores: list[int] = Field(
        default_factory=list, description="Per-chunk critic scores (0–5)"
    )
    chunks_pre_critic: int = Field(0, ge=0, description="Number of chunks before critic filtering")
    chunks_post_critic: int = Field(0, ge=0, description="Number of chunks after critic filtering")


class QueryResponse(BaseModel):
    """POST /query response."""

    answer: str = Field(..., description="Synthesized answer text")
    sources: list[SourceChunk] = Field(..., description="Ranked source chunks")
    debug: DebugMetadata | None = Field(None, description="Debug info (if requested)")


class DebugQueryResponse(BaseModel):
    """POST /debug/query response (debug always present)."""

    answer: str = Field(..., description="Synthesized answer")
    sources: list[SourceChunk] = Field(..., description="Ranked sources")
    debug: DebugMetadata = Field(..., description="Always present debug info")


class RetrieveResponse(BaseModel):
    """POST /retrieve response."""

    sources: list[SourceChunk] = Field(..., description="Retrieved chunks")


class QdrantSearchResult(BaseModel):
    """Single result from raw Qdrant search."""

    chunk_id: str = Field(..., description="Qdrant point ID")
    score: float = Field(..., description="Raw similarity score")
    file_path: str = Field(..., description="Source file path")
    file_type: str = Field(..., description="File type")
    chunk_content: str = Field(..., description="Chunk text")
    chunk_index: int = Field(..., description="Position in source file")
    start_line: int | None = Field(None, description="Start line")
    end_line: int | None = Field(None, description="End line")


class QdrantSearchResponse(BaseModel):
    """POST /debug/qdrant response."""

    results: list[QdrantSearchResult] = Field(..., description="Raw vector search results")
    total_results: int = Field(..., description="Count of results")
    vector_space: str | None = Field(None, description="Space searched")


class IndexingFileError(BaseModel):
    """Individual file indexing error."""

    file_path: str = Field(..., description="Path of failed file")
    error_type: str = Field(..., description="Exception type")
    error_message: str = Field(..., description="Error description")


class IndexResponse(BaseModel):
    """POST /index response."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="completed, failed, or running")
    mode: str = Field(..., description="full or incremental")
    files_scanned: int = Field(..., ge=0, description="Total files discovered")
    files_processed: int = Field(..., ge=0, description="Files successfully indexed")
    files_skipped: int = Field(..., ge=0, description="Total files skipped (unchanged + other)")
    files_skipped_unchanged: int = Field(
        0, ge=0, description="Files skipped because content was unchanged"
    )
    files_skipped_other: int = Field(
        0, ge=0, description="Files skipped for other reasons (empty, no chunks)"
    )
    files_errored: int = Field(..., ge=0, description="Files with errors")
    chunks_created: int = Field(..., ge=0, description="New chunks generated")
    vectors_stored: int = Field(..., ge=0, description="Vectors written to Qdrant")
    duration_seconds: float = Field(..., ge=0.0, description="Elapsed time")
    dry_run: bool = Field(..., description="Whether this was a preview")
    errors: list[IndexingFileError] = Field(default_factory=list, description="Error details")
    collections: dict[str, int] = Field(
        default_factory=dict,
        description="Per-collection vector counts (code, tests, docs, text)",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Ensure status is valid."""
        if v not in _INDEX_STATUSES:
            raise ValueError(f"status must be one of {_INDEX_STATUSES}, got: {v!r}")
        return v


class LLMSlotStatus(BaseModel):
    """Status of a single LLM slot."""

    loaded: bool = Field(..., description="Whether model is loaded")
    model: str | None = Field(None, description="Model filename")
    primary: bool = Field(..., description="Whether this is the primary slot")
    idle_timeout_s: int | None = Field(None, description="Timeout for non-primary")


class VectorStoreStatus(BaseModel):
    """Vector store collection status."""

    collection: str = Field(..., description="Collection name")
    total_vectors: int = Field(..., ge=0, description="Total vectors stored")
    named_spaces: list[str] = Field(..., description="Available vector spaces")


class CollectionStatus(BaseModel):
    """Per-collection stats for the multi-collection vector store."""

    collection_name: str = Field(..., description="Qdrant collection name")
    vectors_count: int = Field(0, ge=0, description="Vectors stored in this collection")
    status: str = Field("ok", description="Collection health (ok or error)")


class VRAMStatus(BaseModel):
    """GPU memory status."""

    total_mb: int = Field(..., description="Total GPU memory (MB)")
    used_mb: int = Field(..., description="Used GPU memory (MB)")
    free_mb: int = Field(..., description="Free GPU memory (MB)")


class ModeInfo(BaseModel):
    """Summary of a registered retrieval mode."""

    name: str = Field(..., description="Mode name")
    description: str = Field("", description="Brief description")
    collections: list[str] = Field(..., description="Target collections")
    llm_slot: str = Field(..., description="LLM slot (text/code)")
    preset: str = Field(..., description="Prompt preset")


class ServiceStatus(BaseModel):
    """GET /status response."""

    version: str = Field(..., description="krag version")
    uptime_seconds: float = Field(..., ge=0.0, description="Seconds since service start")
    llm: dict[str, LLMSlotStatus] = Field(..., description="Per-slot LLM status")
    embedding_models: list[str] = Field(..., description="Loaded embedding model names")
    vector_store: VectorStoreStatus = Field(..., description="Collection stats")
    collections: dict[str, CollectionStatus] = Field(
        default_factory=dict,
        description="Per-collection stats (code, tests, docs, text)",
    )
    modes: list[ModeInfo] = Field(default_factory=list, description="Registered retrieval modes")
    lexicon_loaded: bool = Field(False, description="Whether a domain lexicon is loaded")
    lexicon_entry_count: int = Field(0, ge=0, description="Number of lexicon entries")
    vram: VRAMStatus | None = Field(None, description="GPU memory (null if no CUDA)")


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str = Field(..., description="healthy or degraded")
    version: str = Field(..., description="krag version")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Ensure status is valid."""
        if v not in _HEALTH_STATUSES:
            raise ValueError(f"status must be 'healthy' or 'degraded', got: {v!r}")
        return v


class ShutdownResponse(BaseModel):
    """POST /shutdown response."""

    message: str = Field(..., description="Shutdown confirmation message")


# ── Relocated from routers (T005) ───────────────


class LexiconRefreshResponse(BaseModel):
    """POST /lexicon/refresh response."""

    entries: int = Field(..., description="Number of lexicon entries after reload")
    status: str = Field(..., description="Reload status message")


class ModeDetailResponse(BaseModel):
    """Full detail for a single mode."""

    name: str = Field(..., description="Mode name")
    description: str = Field("", description="Brief description")
    collections: dict[str, float] = Field(..., description="Collection weights")
    llm_slot: str = Field(..., description="LLM slot")
    preset: str = Field(..., description="Prompt preset")
    top_k: int = Field(..., description="Default top_k")
    similarity_threshold: float = Field(..., description="Default threshold")
    critic_enabled: bool = Field(..., description="Context critic active")
    critic_threshold: int = Field(..., description="Minimum critic score")


class ModeListResponse(BaseModel):
    """GET /modes response."""

    modes: list[ModeInfo] = Field(..., description="All registered modes")
