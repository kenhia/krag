# Data Model: 007-service-architecture

**Date**: 2026-02-19
**Spec**: [spec.md](spec.md)
**Research**: [research.md](research.md)

---

## Entity Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Configuration                           │
│  (existing — extended with ServiceConfiguration)            │
└────────────────────────┬────────────────────────────────────┘
                         │ owns
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                      KragService                             │
│  Owns lifecycle of all heavyweight components                │
│  Provides unified interface for API route handlers           │
├──────────────────────────────┬───────────────────────────────┤
│         LLMLifecycleManager  │  QueryPipeline (existing)     │
│  idle timeout, in-flight     │  embeddings, vector store,    │
│  tracking, primary/secondary │  query engine                 │
└──────────────────────────────┴───────────────────────────────┘
          ▲                                    ▲
          │ wraps                               │ reuses
          ▼                                    ▼
┌──────────────────┐              ┌──────────────────────────┐
│    LLMPool       │              │  QdrantVectorStore       │
│  (existing)      │              │  EmbeddingGenerator      │
│                  │              │  QueryEngine             │
└──────────────────┘              │  (all existing)          │
                                  └──────────────────────────┘

┌──────────────────────┐        ┌──────────────────────────┐
│   KragClient         │  HTTP  │  FastAPI App              │
│  (krag_cli)          │ ─────> │  (kragd)                  │
│  httpx wrapper       │        │  routers → KragService    │
└──────────────────────┘        └──────────────────────────┘
```

---

## New Entities

### ServiceConfiguration

**Package**: `krag.models.configuration` (extends existing)
**Purpose**: Configuration for the `[service]` TOML section.

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `host` | `str` | `"0.0.0.0"` | Valid IP or hostname | Bind address for kragd |
| `port` | `int` | `8742` | 1–65535 | Bind port for kragd |
| `primary_llm` | `str \| None` | `"text"` | `"text"`, `"code"`, or `None` | LLM that stays loaded permanently |
| `idle_timeout` | `int` | `300` | >= 0 (0 = never unload) | Seconds before non-primary LLM unloads |
| `log_requests` | `bool` | `True` | — | Log API requests to krag.log |

**Relationships**: Nested in `Configuration` as `service: ServiceConfiguration` (like existing `plugins: PluginConfiguration`).

**State transitions**: None — immutable configuration.

---

### KragService

**Package**: `kragd.service`
**Purpose**: Central service object managing lifecycle of all heavyweight components. Provides a unified interface for API route handlers.

| Field | Type | Description |
|-------|------|-------------|
| `config` | `Configuration` | Full application configuration |
| `service_config` | `ServiceConfiguration` | Shortcut to `config.service` |
| `lifecycle` | `LLMLifecycleManager` | Manages LLM loading/unloading |
| `embedding_generator` | `EmbeddingGenerator` | Loaded once, stays loaded |
| `embedding_orchestrator` | `EmbeddingOrchestrator` | Multi-model orchestration |
| `vector_store` | `QdrantVectorStore` | Qdrant embedded client |
| `llm_pool` | `LLMPool \| None` | LLM pool (may be None if no models configured) |
| `query_engine` | `QueryEngine` | Orchestrates query pipeline |
| `_started` | `bool` | Whether service has been initialized |
| `_start_time` | `datetime` | Timestamp of service start |
| `_last_indexing_job` | `IndexingJob \| None` | Most recent indexing result |

**Methods**:

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `start` | `async def start() -> None` | — | Initialize all components, write PID file |
| `shutdown` | `async def shutdown() -> None` | — | Unload LLMs, close connections, remove PID |
| `query` | `def query(request: QueryRequest) -> QueryResponse` | `QueryResponse` | Full query with synthesis |
| `retrieve` | `def retrieve(request: RetrieveRequest) -> list[QueryResult]` | `list[QueryResult]` | Retrieval only, no LLM |
| `debug_query` | `def debug_query(request: DebugQueryRequest) -> DebugQueryResponse` | `DebugQueryResponse` | Query with full debug metadata |
| `debug_qdrant` | `def debug_qdrant(request: QdrantSearchRequest) -> QdrantSearchResponse` | `QdrantSearchResponse` | Raw vector store search |
| `index` | `def index(request: IndexRequest) -> IndexingJob` | `IndexingJob` | Run indexing (full/incremental) |
| `get_status` | `def get_status() -> ServiceStatus` | `ServiceStatus` | Service health, models, VRAM |
| `get_health` | `def get_health() -> HealthResponse` | `HealthResponse` | Simple up/down |

**State transitions**:
```
UNINITIALIZED ──start()──> RUNNING ──shutdown()──> STOPPED
```

**Validation rules**:
- `start()` must be called before any other method (raises `RuntimeError` if `_started` is False).
- `shutdown()` is idempotent — safe to call multiple times.

---

### LLMLifecycleManager

**Package**: `kragd.lifecycle`
**Purpose**: Manages loading, unloading, and idle timeout tracking for primary and secondary LLMs.

| Field | Type | Description |
|-------|------|-------------|
| `_pool` | `LLMPool` | Reference to the LLM pool (not owned) |
| `_primary_llm` | `str \| None` | Name of the primary LLM slot (`"text"`, `"code"`, or None) |
| `_idle_timeout` | `int` | Seconds of inactivity before non-primary unloads |
| `_timer_task` | `asyncio.Task \| None` | Active idle timer (cancellable) |
| `_inflight_count` | `int` | Number of in-flight requests |
| `_lock` | `threading.Lock` | Guards `_inflight_count` (accessed from thread pool) |
| `_last_used_slot` | `str \| None` | Which LLM slot was last used |
| `_event_loop` | `asyncio.AbstractEventLoop` | Reference to the main event loop |

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `start` | `def start(loop: asyncio.AbstractEventLoop) -> None` | Store event loop reference, load primary LLM if configured |
| `stop` | `async def stop() -> None` | Cancel timer, wait for in-flight, unload all |
| `on_request_start` | `def on_request_start(slot: str) -> None` | Increment in-flight, cancel idle timer |
| `on_request_end` | `def on_request_end(slot: str) -> None` | Decrement in-flight, maybe schedule unload |
| `ensure_loaded` | `def ensure_loaded(slot: str) -> None` | Load LLM if not already loaded (on-demand) |
| `get_status` | `def get_status() -> dict` | Return slot statuses, timer info |

**State transitions (per LLM slot)**:
```
UNLOADED ──ensure_loaded()──> LOADED ──idle timeout──> UNLOADING ──> UNLOADED
                                 ▲                          │
                                 │    request arrives       │
                                 └──────(defer)─────────────┘

Primary LLM (if configured):
UNLOADED ──start()──> LOADED (stays loaded, never times out)
```

**Validation rules**:
- `on_request_end` defers unload if `_inflight_count > 0` (FR-006).
- Primary LLM is never subject to idle timeout.
- If no primary LLM configured, both slots unload after idle timeout.

---

### KragClient

**Package**: `krag_cli.client`
**Purpose**: HTTP client wrapper for communication with kragd.

| Field | Type | Description |
|-------|------|-------------|
| `_client` | `httpx.Client` | Underlying HTTP client |
| `_base_url` | `str` | kragd base URL (e.g., `http://0.0.0.0:8742`) |
| `_timeout` | `float` | Request timeout in seconds |

**Methods**:

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `query` | `def query(query: str, **kwargs) -> dict` | API response dict | POST /query |
| `retrieve` | `def retrieve(query: str, **kwargs) -> list[dict]` | Chunk list | POST /retrieve |
| `debug_query` | `def debug_query(query: str, **kwargs) -> dict` | Response + debug | POST /debug/query |
| `debug_qdrant` | `def debug_qdrant(query: str, **kwargs) -> dict` | Raw results | POST /debug/qdrant |
| `index` | `def index(**kwargs) -> dict` | Indexing result | POST /index |
| `index_status` | `def index_status() -> dict` | Last job info | GET /index/status |
| `status` | `def status() -> dict` | Full status | GET /status |
| `health` | `def health() -> bool` | True if up | GET /health |
| `shutdown` | `def shutdown() -> None` | — | POST /shutdown |
| `close` | `def close() -> None` | — | Close HTTP client |

**Validation rules**:
- All methods raise `ConnectionError` with actionable message if kragd is unreachable (FR-026).
- Timeout is configurable per-request for long-running operations (FR-030).

---

### DebugMetadata

**Package**: `kragd.schemas`
**Purpose**: Debug information returned alongside query responses.

| Field | Type | Description |
|-------|------|-------------|
| `llm_used` | `str` | Which LLM generated the answer (`"text"` or `"code"`) |
| `llm_model` | `str` | Full model filename |
| `route` | `str` | Route decision (`"text"` or `"code"`) |
| `auto_routed` | `bool` | Whether routing was automatic |
| `route_reason` | `str \| None` | Why auto-routing chose this LLM |
| `preset` | `str` | Active prompt preset name |
| `retrieval_time_ms` | `float` | Milliseconds for retrieval phase |
| `generation_time_ms` | `float` | Milliseconds for LLM synthesis |
| `embedding_models_used` | `list[str]` | Embedding model names |
| `vector_spaces_searched` | `list[str]` | Qdrant named spaces queried |
| `total_candidates_before_dedup` | `int` | Total results before dedup |
| `total_candidates_after_dedup` | `int` | Results after dedup |
| `similarity_threshold` | `float` | Active similarity threshold |
| `per_space_result_counts` | `dict[str, int]` | Results per vector space |

**Validation rules**:
- At least 10 distinct fields present (SC-003).
- All timing fields are non-negative.

---

## API Request/Response Schemas

### Request Models (kragd.schemas)

#### QueryRequest

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `query` | `str` | **required** | Non-empty, max 10000 chars | Query text |
| `top_k` | `int \| None` | `None` (uses config) | 1–100 if set | Number of results |
| `preset` | `str \| None` | `None` (uses config) | Valid preset name | Prompt preset |
| `llm` | `str \| None` | `None` (auto-route) | `"text"` or `"code"` | Force specific LLM |
| `include_debug` | `bool` | `False` | — | Include debug metadata |

#### RetrieveRequest

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `query` | `str` | **required** | Non-empty | Query text |
| `top_k` | `int \| None` | `None` | 1–100 if set | Number of results |

#### DebugQueryRequest

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `query` | `str` | **required** | Non-empty | Query text |
| `top_k` | `int \| None` | `None` | 1–100 if set | Number of results |
| `preset` | `str \| None` | `None` | — | Prompt preset |
| `llm` | `str \| None` | `None` | — | Force specific LLM |

#### QdrantSearchRequest

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `query` | `str` | **required** | Non-empty | Query text |
| `vector_space` | `str \| None` | `None` (all spaces) | Valid space name | Restrict to one space |
| `top_k` | `int` | `10` | 1–1000 | Number of results |
| `score_threshold` | `float \| None` | `None` | 0.0–1.0 if set | Minimum similarity |
| `with_payload` | `bool` | `True` | — | Include chunk payloads |
| `filters` | `QdrantFilters \| None` | `None` | — | Payload filtering |

#### QdrantFilters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file_type` | `str \| None` | `None` | Filter by file_type payload field |
| `file_path_contains` | `str \| None` | `None` | Filter by substring in file_path |

#### IndexRequest

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `mode` | `str` | `"incremental"` | `"full"` or `"incremental"` | Indexing mode |
| `directories` | `list[str] \| None` | `None` | Valid paths if set | Override directories |
| `file_types` | `list[str] \| None` | `None` | — | Filter file extensions |
| `exclude_patterns` | `list[str] \| None` | `None` | — | Additional exclusions |
| `vector_store_path` | `str \| None` | `None` | Valid path if set | Override vector store |
| `dry_run` | `bool` | `False` | — | Preview without indexing |

### Response Models (kragd.schemas)

#### QueryResponse (API)

| Field | Type | Description |
|-------|------|-------------|
| `answer` | `str` | Synthesized answer text |
| `sources` | `list[SourceChunk]` | Ranked source chunks |
| `debug` | `DebugMetadata \| None` | Debug info (if requested) |

#### SourceChunk

| Field | Type | Description |
|-------|------|-------------|
| `chunk_id` | `str` | Unique chunk identifier |
| `file_path` | `str` | Source file path |
| `score` | `float` | Relevance score |
| `rank` | `int` | Position in results |
| `chunk_content` | `str` | Chunk text content |
| `file_type` | `str` | File extension/type |
| `language` | `str \| None` | Programming language (code) |
| `function_name` | `str \| None` | Containing function (code) |
| `class_name` | `str \| None` | Containing class (code) |
| `start_line` | `int \| None` | Start line in source file |
| `end_line` | `int \| None` | End line in source file |

**Note**: Maps 1:1 from existing `QueryResult` model. `file_path` serialized as string (not `Path`) for JSON transport.

#### DebugQueryResponse

| Field | Type | Description |
|-------|------|-------------|
| `answer` | `str` | Synthesized answer |
| `sources` | `list[SourceChunk]` | Ranked sources |
| `debug` | `DebugMetadata` | Always present (not optional) |

#### QdrantSearchResponse

| Field | Type | Description |
|-------|------|-------------|
| `results` | `list[QdrantSearchResult]` | Raw vector search results |
| `total_results` | `int` | Count of results returned |
| `vector_space` | `str \| None` | Space searched (or null = all) |

#### QdrantSearchResult

| Field | Type | Description |
|-------|------|-------------|
| `chunk_id` | `str` | Qdrant point ID |
| `score` | `float` | Raw similarity score |
| `file_path` | `str` | Source file path |
| `file_type` | `str` | File type |
| `chunk_content` | `str` | Chunk text (if with_payload) |
| `chunk_index` | `int` | Position in source file |
| `start_line` | `int \| None` | Start line |
| `end_line` | `int \| None` | End line |

#### IndexResponse

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `str` | Unique job identifier |
| `status` | `str` | `"completed"`, `"failed"`, `"running"` |
| `mode` | `str` | `"full"` or `"incremental"` |
| `files_scanned` | `int` | Total files discovered |
| `files_processed` | `int` | Files successfully indexed |
| `files_skipped` | `int` | Files unchanged/excluded |
| `files_errored` | `int` | Files with errors |
| `chunks_created` | `int` | New chunks generated |
| `vectors_stored` | `int` | Vectors written to Qdrant |
| `duration_seconds` | `float` | Elapsed time |
| `dry_run` | `bool` | Whether this was a preview |
| `errors` | `list[IndexError]` | Error details |

**Note**: Maps from existing `IndexingJob` model.

#### IndexError

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Path of failed file |
| `error_type` | `str` | Exception type |
| `error_message` | `str` | Error description |

#### ServiceStatus

| Field | Type | Description |
|-------|------|-------------|
| `version` | `str` | krag version |
| `uptime_seconds` | `float` | Seconds since service start |
| `llm` | `dict[str, LLMSlotStatus]` | Per-slot LLM status |
| `embedding_models` | `list[str]` | Loaded embedding model names |
| `vector_store` | `VectorStoreStatus` | Collection stats |
| `vram` | `VRAMStatus \| None` | GPU memory (null if no CUDA) |

#### LLMSlotStatus

| Field | Type | Description |
|-------|------|-------------|
| `loaded` | `bool` | Whether model is currently loaded |
| `model` | `str \| None` | Model filename (if loaded) |
| `primary` | `bool` | Whether this is the primary slot |
| `idle_timeout_s` | `int \| None` | Timeout for non-primary (null for primary) |

#### VectorStoreStatus

| Field | Type | Description |
|-------|------|-------------|
| `collection` | `str` | Collection name |
| `total_vectors` | `int` | Total vectors stored |
| `named_spaces` | `list[str]` | Available vector spaces |

#### VRAMStatus

| Field | Type | Description |
|-------|------|-------------|
| `total_mb` | `int` | Total GPU memory (MB) |
| `used_mb` | `int` | Used GPU memory (MB) |
| `free_mb` | `int` | Free GPU memory (MB) |

#### HealthResponse

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"healthy"` or `"degraded"` |
| `version` | `str` | krag version |

---

## Existing Entities (Unchanged)

These entities are consumed by the new service layer but not modified:

| Entity | Package | Used By |
|--------|---------|---------|
| `Configuration` | `krag.models.configuration` | KragService (extended with `service` field) |
| `QueryResult` | `krag.models.query_result` | API response serialization → SourceChunk |
| `IndexingJob` | `krag.models.indexing_job` | API response serialization → IndexResponse |
| `QueryPipeline` | `krag.cli.pipeline` | KragService initialization |
| `QueryResponse` | `krag.orchestration.query_engine` | KragService.query() return |
| `LLMPool` | `krag.synthesis.llm_pool` | Wrapped by LLMLifecycleManager |
| `LLMSlot` | `krag.synthesis.llm_pool` | Status reporting |
| `QdrantVectorStore` | `krag.storage` | Direct search for debug endpoint |
| `EmbeddingGenerator` | `krag.embeddings` | Stays loaded for service lifetime |
