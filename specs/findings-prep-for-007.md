# Service Architecture Findings — Prep for 007

**Date**: 2026-02-19 (post-006 merge)
**Branch**: main (synced)
**Test baseline**: 800 passed, 2 skipped
**Context**: Planning the conversion of krag from a CLI-only tool into a service-based application with a separate CLI client

---

## Sprint Goal

Convert krag into a service-based architecture where:
- **`kragd`** — the service daemon that holds LLM(s) in memory, manages the vector store, and exposes a REST API
- **`krag`** — a lightweight CLI client that communicates with `kragd` via HTTP
- Both modes benefit from persistent LLM loading (no cold-start per query)
- New debugging/introspection capabilities are exposed through both CLI and API

---

## Decision Record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| REST framework | **FastAPI** | Pydantic-native (already used everywhere), auto OpenAPI docs, lightweight, well-documented |
| Service name | **`kragd`** | Unix daemon convention (`httpd`, `sshd`); short, unambiguous |
| CLI name | **`krag`** (unchanged) | Users keep their muscle memory; CLI becomes a thin HTTP client |
| LLM lifecycle | **Configurable** | Primary LLM stays loaded; secondary unloads after idle timeout; no-primary = unload both after timeout |
| Sprint scope | **Full** | Service layer + CLI split + debug features in one sprint |
| Mono-repo | **Yes** | `src/kragd/` and `src/krag-cli/` live alongside `src/krag/` |

---

## 1. Architecture Overview

### Current State

```
┌─────────────────────────────┐
│  CLI (typer + rich)         │
│  krag query / index / eval  │
├─────────────────────────────┤
│  Orchestration              │
│  QueryEngine, Indexer       │
├─────────────────────────────┤
│  Core                       │
│  Retriever, Embeddings,     │
│  LLMPool, PromptBuilder     │
├─────────────────────────────┤
│  Infrastructure             │
│  Qdrant, Config, Models     │
└─────────────────────────────┘
```

Everything runs in-process. LLMs load on every `krag query` invocation (~5-15s cold start) and unload when the process exits.

### Target State

```
                                    ┌──────────────────────┐
                                    │  krag (CLI client)    │
                                    │  Thin HTTP wrapper    │
                                    │  typer + httpx/rich   │
                                    └──────────┬───────────┘
                                               │ HTTP/REST
                                               ▼
┌──────────────────────────────────────────────────────────────┐
│  kragd (service)                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  API Layer (FastAPI)                                    │ │
│  │  /query  /index  /eval  /debug  /status  /health        │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  Service Layer (NEW)                                    │ │
│  │  KragService: lifecycle, LLM management, request router │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  Orchestration (EXISTING — no changes)                  │ │
│  │  QueryEngine, IndexingOrchestrator                      │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  Core (EXISTING — no changes)                           │ │
│  │  Retriever, Embeddings, LLMPool, PromptBuilder          │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  Infrastructure (EXISTING — no changes)                 │ │
│  │  Qdrant, Config, Models                                 │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

The key insight: **the existing orchestration and core layers need zero changes**. The separation is already clean — CLI imports orchestration, orchestration imports core, core imports infrastructure. The new service layer slots in at the same level as the CLI.

---

## 2. Package Layout

```
src/
├── krag/                    # Core library (UNCHANGED)
│   ├── cli/                 # Retained for direct-mode / debugging
│   ├── config/
│   ├── discovery/
│   ├── embeddings/
│   ├── extraction/
│   ├── models/
│   ├── orchestration/
│   ├── plugins/
│   ├── retrieval/
│   ├── storage/
│   └── synthesis/
│
├── kragd/                   # Service daemon (NEW)
│   ├── __init__.py
│   ├── __main__.py          # Entry: python -m kragd
│   ├── app.py               # FastAPI app factory
│   ├── routers/             # FastAPI routers (one per domain)
│   │   ├── __init__.py
│   │   ├── query.py         # POST /query, POST /retrieve
│   │   ├── index.py         # POST /index, GET /index/status
│   │   ├── debug.py         # POST /debug/query, POST /debug/qdrant
│   │   ├── eval.py          # POST /eval
│   │   └── system.py        # GET /health, GET /status, POST /shutdown
│   ├── service.py           # KragService: lifecycle, LLM pool management
│   ├── schemas.py           # Pydantic request/response models (API-facing)
│   └── lifecycle.py         # LLM lifecycle manager (load/unload/idle timeout)
│
└── krag_cli/                # CLI client (NEW)
    ├── __init__.py
    ├── __main__.py           # Entry: python -m krag_cli
    ├── main.py               # Typer app, subcommands
    ├── client.py             # HTTP client (httpx) wrapper
    ├── config.py             # CLI-local config (server URL, timeout)
    ├── display.py            # Rich output formatting
    └── commands/
        ├── __init__.py
        ├── query.py          # krag query ...
        ├── index.py          # krag index ...
        ├── debug.py          # krag debug query ..., krag debug qdrant ...
        ├── status.py         # krag status, krag health
        └── service.py        # krag start, krag stop
```

### pyproject.toml Scripts

```toml
[project.scripts]
krag = "krag_cli.main:app"           # CLI client
kragd = "kragd.__main__:main"        # Service daemon

# Keep direct-mode for debugging (bypass service):
krag-direct = "krag.cli.main:app"    # Original CLI, talks to components directly
```

### Why `krag_cli` not `krag-cli`?

Python package names can't contain hyphens. The directory is `krag_cli/`, the import is `krag_cli`, and the installed command is still `krag`. The README and docs can call it "krag CLI" conversationally.

---

## 3. REST API Design

### Framework: FastAPI

**Why FastAPI over alternatives:**
- Pydantic-native request/response validation — krag already uses Pydantic models for `Configuration`, `QueryResult`, `IndexingJob`, etc. FastAPI uses Pydantic natively; schemas become trivial wrappers.
- Auto-generated OpenAPI docs at `/docs` — immediate interactive API exploration.
- Dependency injection — clean way to inject `KragService` into route handlers.
- ASGI + uvicorn — lightweight server with reload support for development.
- `krag-web` (future) benefits from the same API — the web UI is just another HTTP client.

**What to watch for:**
- LLM inference is synchronous and blocking. FastAPI routes calling LLM inference should use `def` (not `async def`) so FastAPI runs them in a thread pool, or explicitly use `run_in_executor`. This avoids blocking the event loop.
- Single-user local service means we don't need connection pooling, rate limiting, or auth (yet). Keep it simple.

**Dependencies to add:**
```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
httpx>=0.28.0          # For CLI client
```

### Proposed Endpoints

#### Query

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/query` | Full query with synthesis (replaces `krag query`) |
| `POST` | `/retrieve` | Retrieval only, no synthesis (replaces `krag query --no-synthesis`) |

**`POST /query`** request:
```json
{
  "query": "How does the plugin system work?",
  "top_k": 5,
  "preset": "balanced",
  "llm": null,
  "include_debug": false
}
```

**`POST /query`** response:
```json
{
  "answer": "The plugin system works by...",
  "sources": [
    {
      "chunk_id": "abc-123",
      "file_path": "/home/ken/docs/plugins.md",
      "score": 0.42,
      "rank": 1,
      "chunk_content": "...",
      "file_type": "markdown",
      "language": null,
      "function_name": null,
      "class_name": null,
      "start_line": 10,
      "end_line": 45
    }
  ],
  "debug": {
    "llm_used": "text",
    "llm_model": "qwen2.5-7b-instruct-q4_k_m.gguf",
    "route": "text",
    "auto_routed": true,
    "preset": "balanced",
    "retrieval_time_ms": 142,
    "generation_time_ms": 3200,
    "embedding_models_used": ["all-MiniLM-L6-v2"],
    "vector_spaces_searched": ["text"],
    "total_candidates_before_dedup": 15,
    "similarity_threshold": 0.2
  }
}
```

When `include_debug` is `false`, the `debug` field is omitted.

#### Retrieval / Debug

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/debug/retrieve` | Raw retrieval with full metadata (per-space scores, pre/post-dedup counts) |
| `POST` | `/debug/qdrant` | Direct Qdrant query — raw vector search with user-specified parameters |

**`POST /debug/qdrant`** request:
```json
{
  "query": "plugin architecture",
  "vector_space": "text",
  "top_k": 20,
  "score_threshold": null,
  "with_payload": true,
  "filters": {
    "file_type": "code",
    "file_path_contains": "plugins"
  }
}
```

This gives direct access to Qdrant's search without krag's deduplication, boosting, or RRF — useful for debugging retrieval quality.

#### Indexing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/index` | Start indexing job (full or incremental) |
| `GET`  | `/index/status` | Get current/last job status |
| `GET`  | `/index/stats` | Collection statistics |

**`POST /index`** request:
```json
{
  "mode": "incremental",
  "directories": null,
  "file_types": null,
  "exclude_patterns": null,
  "vector_store_path": null,
  "dry_run": false
}
```

All fields are optional — omitted or `null` fields fall back to config values:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `"full" \| "incremental"` | `"incremental"` | Full reindex or incremental update |
| `directories` | `list[str] \| null` | config `directory_paths` | Override directories to index |
| `file_types` | `list[str] \| null` | config `supported_file_types` | Filter to specific extensions (e.g., `[".py", ".md"]`) |
| `exclude_patterns` | `list[str] \| null` | config `exclusion_patterns` | Additional glob patterns to exclude |
| `vector_store_path` | `string \| null` | config `vector_store_path` | Override vector store location |
| `dry_run` | `bool` | `false` | Show what would be indexed without actually indexing |

**`POST /index`** response:
```json
{
  "job_id": "idx-20260219-143022",
  "status": "completed",
  "mode": "incremental",
  "files_scanned": 260,
  "files_processed": 12,
  "files_skipped": 248,
  "files_errored": 0,
  "chunks_created": 184,
  "vectors_stored": 184,
  "duration_seconds": 45.2,
  "dry_run": false,
  "errors": []
}
```

Indexing is long-running. Options:
- **Option A**: Synchronous — block until done (simpler, fine for CLI usage).
- **Option B**: Background job — return job ID, poll `/index/status` (better for web UI).

**Recommendation**: Start with synchronous (Option A) for the sprint, design the response schema to be forward-compatible with async jobs. Add a `/index/status` endpoint that returns the last completed job info from memory.

#### Eval

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/eval` | Run eval suite (send TOML content or path) |

#### System

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Simple health check (is the service up?) |
| `GET`  | `/status` | Detailed status: loaded models, VRAM, vector store stats, uptime |
| `POST` | `/shutdown` | Graceful shutdown |
| `GET`  | `/config` | Current (redacted) configuration |

**`GET /status`** response:
```json
{
  "version": "0.1.0",
  "uptime_seconds": 3600,
  "llm": {
    "text": {"loaded": true, "model": "qwen2.5-7b-...", "primary": true},
    "code": {"loaded": false, "model": "qwen2.5-coder-7b-...", "primary": false, "idle_timeout_s": 300}
  },
  "embedding_models": ["all-MiniLM-L6-v2"],
  "vector_store": {
    "collection": "krag",
    "total_vectors": 6838,
    "named_spaces": ["text"]
  },
  "vram": {
    "total_mb": 8192,
    "used_mb": 5400,
    "free_mb": 2792
  }
}
```

---

## 4. Service Layer Design (`KragService`)

The `KragService` class is the heart of `kragd`. It owns the lifecycle of all heavyweight components and provides a clean interface for API routes.

```python
class KragService:
    """Central service managing all krag components."""

    def __init__(self, config: Configuration):
        self.config = config
        self.lifecycle = LLMLifecycleManager(config)
        self.query_pipeline: QueryPipeline | None = None
        self._started = False

    async def start(self) -> None:
        """Initialize components: embeddings, vector store, LLMs."""
        self.query_pipeline = build_query_pipeline(...)
        self.lifecycle.start(self.query_pipeline.llm_pool)
        self._started = True

    async def shutdown(self) -> None:
        """Graceful shutdown: unload LLMs, close connections."""
        self.lifecycle.stop()
        if self.query_pipeline:
            self.query_pipeline.llm_client.close()
            if self.query_pipeline.llm_pool:
                self.query_pipeline.llm_pool.close()
        self._started = False

    def query(self, request: QueryRequest) -> QueryResponse: ...
    def retrieve(self, request: RetrieveRequest) -> list[QueryResult]: ...
    def debug_qdrant(self, request: QdrantDebugRequest) -> QdrantDebugResponse: ...
    def index(self, mode: str, progress_cb=None) -> IndexingJob: ...
    def get_status(self) -> ServiceStatus: ...
```

### LLM Lifecycle Manager

```python
class LLMLifecycleManager:
    """Manages LLM loading/unloading with configurable idle timeouts."""

    # Configurable behavior:
    # - primary_llm: "text" | "code" | None
    #   If set, primary stays loaded forever; secondary unloads after idle_timeout.
    #   If None, both unload after idle_timeout.
    # - idle_timeout_s: seconds of inactivity before unloading (default: 300)
    # - load_on_demand: if True, LLMs load on first query (not at startup)
```

### Config Additions

New fields in `Configuration` / config.toml:

```toml
[service]
host = "127.0.0.1"          # Bind address (localhost only by default)
port = 8742                  # Default port (arbitrary, "KRAG" on phone keypad)
primary_llm = "text"         # "text", "code", or unset for no primary
idle_timeout = 300           # Seconds before non-primary LLM unloads
log_requests = true          # Log API requests
```

---

## 5. CLI Client Design

The new `krag` CLI is a thin Typer app that sends HTTP requests to `kragd` and formats responses with Rich.

### Core Principle

The CLI should **feel identical** to the current direct-mode CLI. Same commands, same flags, same output formatting. The only visible difference: it's faster (no cold-start) and it needs a running `kragd`.

### Connection Management

```python
# krag_cli/client.py
class KragClient:
    """HTTP client for communicating with kragd."""

    def __init__(self, base_url: str = "http://127.0.0.1:8742"):
        self.client = httpx.Client(base_url=base_url, timeout=120.0)

    def query(self, query: str, top_k: int = 5, ...) -> dict: ...
    def retrieve(self, query: str, top_k: int = 5, ...) -> list[dict]: ...
    def index(self, mode: str = "incremental") -> dict: ...
    def status(self) -> dict: ...
    def health(self) -> bool: ...
```

### Server Auto-Detection

When `krag` runs a command, it should first check if `kragd` is reachable. If not:
- Print a friendly message: `"kragd is not running. Start it with: kragd start"`
- **Or** fall back to direct mode (run everything in-process, like today). This is the `krag-direct` behavior.

We should decide: fall back transparently, or require explicit `kragd`? **Recommendation**: Require `kragd` by default. Users wanting direct mode use `krag-direct` or `krag --direct`. This avoids confusion about whether an LLM is being loaded in-process or not.

### New CLI Commands

```
krag query "..."           # Same as today, hits POST /query
krag query "..." --debug   # Includes debug metadata in output
krag index [--full]        # Hits POST /index
krag status                # Hits GET /status, shows loaded models, VRAM, etc.
krag health                # Quick up/down check

krag debug query "..."     # Full debug output (retrieval metadata, routing, timings)
krag debug qdrant "..."    # Raw Qdrant search with knobs:
                           #   --space text|code
                           #   --top-k 20
                           #   --threshold 0.3
                           #   --filter-type code
                           #   --filter-path "plugins"
                           #   --raw-scores (show per-space scores, not RRF)
```

---

## 6. Debug & Introspection Features

### 6a. Debug Query Mode (`krag debug query`)

Returns everything `krag query` returns, plus:

| Field | Description |
|-------|-------------|
| `llm_used` | Which LLM generated the answer (`"text"` or `"code"`) |
| `llm_model` | Full model filename |
| `auto_routed` | Whether the LLM was chosen automatically or by `--llm` flag |
| `route_reason` | Why auto-routing chose this LLM (e.g., "67% code chunks") |
| `preset` | Which prompt preset was active |
| `retrieval_time_ms` | Time for retrieval phase |
| `generation_time_ms` | Time for LLM synthesis |
| `embedding_models_used` | Which embedding models contributed to retrieval |
| `vector_spaces_searched` | Which Qdrant named spaces were queried |
| `candidates_before_dedup` | Total results before deduplication |
| `candidates_after_dedup` | Results after dedup, before boosting |
| `rrf_active` | Whether RRF was used (multi-model) |
| `per_space_result_counts` | `{"text": 12, "code": 8}` — how many results per space |

### 6b. Raw Qdrant Search (`krag debug qdrant`)

Direct vector search bypassing krag's retrieval pipeline (no dedup, no boost, no RRF). This is for debugging what the vector store actually returns for a query.

**Knobs to expose:**

| Flag | Description | Default |
|------|-------------|---------|
| `--space` | Named vector space to search | all spaces |
| `--top-k` | Number of results | 10 |
| `--threshold` | Minimum score threshold | none |
| `--filter-type` | Filter by `file_type` payload field | none |
| `--filter-path` | Filter by substring in `file_path` | none |
| `--raw-scores` | Show raw similarity scores (not RRF-fused) | true |
| `--with-vectors` | Include the actual embedding vectors in output | false |

**Implementation**: This requires a new method on `QdrantVectorStore` (or using the existing `search` / `search_named` methods directly through the API). The key difference from `--no-synthesis` is that this bypasses the `Retriever` entirely — no boosting, no dedup, no threshold filtering — giving raw Qdrant results.

### 6c. Enhanced `--no-synthesis` (existing feature, augmented)

The existing `krag query --no-synthesis` already skips LLM generation. We should augment it with the debug metadata (retrieval timings, which spaces were searched, etc.) so users get more visibility without needing the full debug mode.

---

## 7. Implementation Plan

### Phase 1: Service Foundation (kragd)

| Task | Description | Estimate |
|------|-------------|----------|
| **S-01** | Create `src/kragd/` package structure | 0.5h |
| **S-02** | Implement `KragService` core — lifecycle, query pipeline wrapper | 2h |
| **S-03** | Implement `LLMLifecycleManager` — primary/secondary, idle timeout, load-on-demand | 3h |
| **S-04** | Add `[service]` section to `Configuration` model | 1h |
| **S-05** | FastAPI app factory (`app.py`) with lifespan events | 1h |
| **S-06** | Query router — `POST /query`, `POST /retrieve` | 2h |
| **S-07** | Index router — `POST /index`, `GET /index/status`, `GET /index/stats` | 2h |
| **S-08** | System router — `GET /health`, `GET /status`, `POST /shutdown` | 1h |
| **S-09** | Debug router — `POST /debug/query`, `POST /debug/qdrant` | 3h |
| **S-10** | Pydantic request/response schemas (`schemas.py`) | 2h |
| **S-11** | `kragd` CLI entry point (start/stop/foreground) | 1h |
| **S-12** | uvicorn integration and signal handling | 1h |

### Phase 2: CLI Client (krag)

| Task | Description | Estimate |
|------|-------------|----------|
| **C-01** | Create `src/krag_cli/` package structure | 0.5h |
| **C-02** | HTTP client wrapper (`client.py`) with error handling | 2h |
| **C-03** | Port `query` command to use HTTP client | 2h |
| **C-04** | Port `index` command to use HTTP client | 1h |
| **C-05** | `status` and `health` commands | 1h |
| **C-06** | `debug query` command with rich debug output | 2h |
| **C-07** | `debug qdrant` command with raw search output | 2h |
| **C-08** | Server auto-detection and fallback messaging | 1h |
| **C-09** | CLI-local config (server URL, timeout) | 1h |
| **C-10** | Rich output formatting (match existing look) | 2h |

### Phase 3: Testing & Integration

| Task | Description | Estimate |
|------|-------------|----------|
| **T-01** | Unit tests for `KragService` and `LLMLifecycleManager` | 3h |
| **T-02** | Unit tests for API routes (FastAPI TestClient) | 3h |
| **T-03** | Unit tests for CLI client (mock HTTP) | 2h |
| **T-04** | Integration test: kragd ↔ krag round-trip | 2h |
| **T-05** | Update `pyproject.toml` with new packages and entry points | 1h |
| **T-06** | Update architecture docs | 2h |

---

## 8. What Stays the Same

This is as important as what changes. The following are **untouched**:

- `src/krag/` (the core library) — zero changes needed
- `src/krag/cli/` — retained as `krag-direct` for debugging and development
- All existing tests — should continue to pass unmodified
- Configuration file format — new `[service]` section is additive
- Plugin system — plugins are loaded by the service just as they are by the CLI
- Qdrant storage — same embedded Qdrant, same collection format
- `build_query_pipeline()` — reused by `KragService` internally

---

## 9. Open Questions & Risks

### Q1: Authentication?
For local-only use, `127.0.0.1` binding is sufficient. No auth needed for sprint 007. If we later bind to `0.0.0.0` for network access, we'll need API keys or mTLS. **Action**: defer, but design header injection in the client for future token support.

A: No auth yet, but do want to expose it across my local net so I can use krag from my other computers.

### Q2: Concurrent queries?
`LLMPool` already has `threading.Lock` for thread safety. FastAPI's thread pool will serialize LLM calls naturally. For a single-user system this is fine. Multiple simultaneous queries will queue, not crash. **Action**: no special handling needed.

A: Single query at time with queue is perfect for now.

### Q3: Embedding model persistence?
Embedding models (sentence-transformers) load in ~2s. In the service, they stay loaded alongside the LLMs. The `LLMLifecycleManager` should NOT unload embedding models — they're small and always needed. **Action**: only manage LLM lifecycle, not embeddings.

A: Agree.

### Q4: PID file / process management?
Should `kragd` write a PID file for `krag stop` to find it? Or use systemd/launchd for production? **Recommendation**: write a PID file to `$XDG_RUNTIME_DIR/kragd.pid` (or `/tmp/kragd.pid` fallback). `krag stop` reads it and sends SIGTERM. This is simple and works without a service manager.

A: Agree

### Q5: Log separation?
Should `kragd` log to the same krag log file, or a separate `kragd.log`? **Recommendation**: same log file (`krag.log` in XDG data dir) with a `[kragd]` logger prefix so all events are in one place. The existing `krag log` commands work for both.

A: Agree

### Q6: Config file sharing?
Both `kragd` and `krag` read the same `config.toml`. The CLI client only needs `[service]` section (for host/port). The service needs everything. **Action**: no separate config files; client reads host/port from the existing config.

A: Agree

### Q7: Streaming responses?
LLM generation could stream tokens via SSE (`text/event-stream`). This is a big UX win for long answers but adds complexity. **Recommendation**: defer to a follow-up. The initial API returns complete responses. Design response schemas to be compatible with future streaming (include a `stream: bool` request field that's initially ignored).

A: Agree

---

## 10. Dependencies

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `>=0.115.0` | REST framework for kragd |
| `uvicorn[standard]` | `>=0.34.0` | ASGI server |
| `httpx` | `>=0.28.0` | HTTP client for krag CLI |

### Existing Dependencies Leveraged

| Package | Usage |
|---------|-------|
| `pydantic` | API schemas (already `>=2.6.0`) |
| `typer` | CLI client (same as current CLI) |
| `rich` | CLI output formatting |

### Dev Dependencies

| Package | Usage |
|---------|-------|
| `pytest-httpx` | Mock HTTP for CLI client tests |
| `httpx` | FastAPI TestClient uses it internally |

---

## 11. Migration Path

### For Users

1. Install updated krag (new packages auto-installed)
2. Run `kragd start` (or `kragd` for foreground)
3. Use `krag query` as before — it now talks to the service
4. For debugging / old behavior: `krag-direct query` works exactly as before

### For Development

1. During development, `krag-direct` is the fast iteration path (no server needed)
2. `kragd --reload` uses uvicorn's auto-reload for API development
3. Tests can use FastAPI's `TestClient` without starting a real server

---

## 12. Sprint Definition (007-service-architecture)

### Sprint Deliverables

1. **`kragd`** service runs, accepts queries, keeps LLMs loaded
2. **`krag`** CLI client sends queries to `kragd`, displays results identically to today
3. **`krag debug query`** shows full retrieval + generation metadata
4. **`krag debug qdrant`** provides raw vector store access with filtering knobs
5. **`kragd` status/health** endpoints for monitoring
6. **Configurable LLM lifecycle** — primary model persists, secondary unloads after idle timeout
7. **Tests** for all new code (target: same coverage standard as existing)
8. **Updated docs** — architecture.md, new service user guide

### Out of Scope (Future Sprints)

- `krag-web` (web UI) — benefits from the same API but is a separate sprint
- Streaming SSE responses
- Authentication / network binding
- systemd/launchd service files
- WebSocket support
- Multi-user / multi-tenant
