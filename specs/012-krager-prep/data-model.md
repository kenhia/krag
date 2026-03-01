# Data Model: krager Prep — API Normalization & Hardening

**Branch**: `012-krager-prep` | **Date**: 2026-02-28

## Entities

### Relocated Schemas (existing → centralized)

These models already exist inline in router files and are moved to `schemas.py` without field changes.

#### LexiconRefreshResponse

| Field | Type | Description |
|-------|------|-------------|
| `entries` | `int` | Number of lexicon entries after reload |
| `status` | `str` | Reload status message |

**Source**: `src/kragd/routers/lexicon.py` → `src/kragd/schemas.py`
**Validation**: No changes to field names, types, or descriptions.

#### ModeDetailResponse

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Mode name |
| `description` | `str` | Brief description (default: `""`) |
| `collections` | `dict[str, float]` | Collection weights |
| `llm_slot` | `str` | LLM slot identifier |
| `preset` | `str` | Prompt preset |
| `top_k` | `int` | Default top_k |
| `similarity_threshold` | `float` | Default similarity threshold |
| `critic_enabled` | `bool` | Whether context critic is active |
| `critic_threshold` | `int` | Minimum critic score |

**Source**: `src/kragd/routers/modes.py` → `src/kragd/schemas.py`
**Validation**: No changes to field names, types, or descriptions.

#### ModeListResponse

| Field | Type | Description |
|-------|------|-------------|
| `modes` | `list[ModeInfo]` | All registered modes |

**Source**: `src/kragd/routers/modes.py` → `src/kragd/schemas.py`
**Dependency**: `ModeInfo` already lives in `schemas.py`.

---

### Modified Entities

#### `/index/status` Return Type

**Before**: `IndexResponse | list[IndexResponse]` (polymorphic)
**After**: `list[IndexResponse]` (always a list)

| Scenario | Before | After |
|----------|--------|-------|
| No jobs | Single `IndexResponse` with status="idle" or empty | `[]` (empty list) |
| One job | Single `IndexResponse` | `[IndexResponse]` (list with one element) |
| Multiple jobs | `list[IndexResponse]` | `list[IndexResponse]` (unchanged) |
| Job in progress | Single `IndexResponse` with status="running" | `[IndexResponse]` with status="running" |

**Affected service method**: `KragService.get_index_status()` — must always return `list[IndexResponse]`.

---

### New Entities

#### SSE Event Models

These are not Pydantic models persisted to storage — they are the JSON payloads within SSE `data:` fields.

##### IndexProgressEvent

| Field | Type | Description |
|-------|------|-------------|
| `current` | `int` | Current item number being processed |
| `total` | `int` | Total items to process (0 if unknown) |
| `stage` | `str` | Pipeline stage name (e.g., "Processing files", "Storing vectors") |
| `file` | `str \| null` | File path currently being processed (if applicable) |
| `job_id` | `str` | Job identifier |
| `timestamp` | `str` | ISO 8601 timestamp |

**SSE event type**: `index:progress`

##### IndexCompleteEvent

| Field | Type | Description |
|-------|------|-------------|
| (all IndexResponse fields) | — | Full index job result |
| `timestamp` | `str` | ISO 8601 timestamp |

**SSE event type**: `index:complete`

##### IndexErrorEvent

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | `str` | Job identifier |
| `error` | `str` | Error message |
| `timestamp` | `str` | ISO 8601 timestamp |

**SSE event type**: `index:error`

##### QueryTokenEvent

| Field | Type | Description |
|-------|------|-------------|
| `token` | `str` | Partial answer text (one or more tokens) |

**SSE event type**: `query:token`

##### QuerySourcesEvent

| Field | Type | Description |
|-------|------|-------------|
| `sources` | `list[SourceChunk]` | Retrieved source chunks (sent before tokens) |

**SSE event type**: `query:sources`

##### QueryDoneEvent

| Field | Type | Description |
|-------|------|-------------|
| `answer` | `str` | Complete answer text |
| `sources` | `list[SourceChunk]` | All source chunks |
| `debug` | `DebugMetadata \| null` | Debug metadata (if requested) |

**SSE event type**: `query:done`

##### QueryErrorEvent

| Field | Type | Description |
|-------|------|-------------|
| `error` | `str` | Error description |

**SSE event type**: `query:error`

---

### CORS Configuration (not a Pydantic model)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `allow_origins` | `list[str]` | `["*"]` | Allowed origins; overridable via `KRAGD_CORS_ORIGINS` env var |
| `allow_credentials` | `bool` | `False` | Whether to allow credentials |
| `allow_methods` | `list[str]` | `["*"]` | Allowed HTTP methods |
| `allow_headers` | `list[str]` | `["*"]` | Allowed HTTP headers |

**Configuration source**: `KRAGD_CORS_ORIGINS` environment variable (comma-separated string) or default wildcard.

---

## Entity Relationships

```text
schemas.py
├── QueryRequest ──────────────────► POST /query, POST /query/stream
├── QueryResponse ◄─────────────── POST /query
├── SourceChunk ◄────── QueryResponse, DebugQueryResponse, QuerySourcesEvent, QueryDoneEvent
├── DebugMetadata ◄──── DebugQueryResponse, QueryDoneEvent
├── IndexRequest ──────────────────► POST /index
├── IndexResponse ◄──── GET /index/status (always list), IndexCompleteEvent
├── LexiconRefreshResponse ◄────── POST /lexicon/refresh  (RELOCATED)
├── ModeListResponse ◄─────────── GET /modes              (RELOCATED)
├── ModeDetailResponse ◄────────── GET /modes/{name}       (RELOCATED)
└── ModeInfo ◄──────── ModeListResponse

SSE Events (not in schemas.py — these are inline dicts or lightweight dataclasses)
├── IndexProgressEvent ──► GET /index/stream
├── IndexCompleteEvent ──► GET /index/stream
├── IndexErrorEvent ────► GET /index/stream
├── QueryTokenEvent ────► POST /query/stream
├── QuerySourcesEvent ──► POST /query/stream
├── QueryDoneEvent ─────► POST /query/stream
└── QueryErrorEvent ────► POST /query/stream
```

## State Transitions

### Index Job Lifecycle (SSE perspective)

```text
Client subscribes to GET /index/stream
    │
    ├── No active job → index:idle event → stream ends (or waits)
    │
    └── Active job exists
         │
         ├──► index:progress (current=0, stage="Discovering files")
         ├──► index:progress (current=1, total=N, stage="Processing files", file="...")
         ├──► index:progress (current=2, total=N, stage="Processing files", file="...")
         │    ... (repeats for each file)
         ├──► index:progress (current=M, total=T, stage="Storing vectors (collection)")
         │    ... (repeats for each batch)
         ├──► index:complete (full IndexResponse)
         │    └── Stream ends
         │
         └── On error at any point:
              └── index:error (error message) → stream ends
```

### Streaming Query Lifecycle

```text
Client sends POST /query/stream {query, top_k?, mode?, ...}
    │
    ├──► Retrieval phase (synchronous, no events)
    ├──► query:sources (retrieved chunks)
    ├──► query:token ("The")
    ├──► query:token (" answer")
    ├──► query:token (" is")
    │    ... (repeats for each token batch)
    ├──► query:done (complete answer + sources + debug)
    │    └── Stream ends
    │
    └── On error at any point:
         └── query:error (error message) → stream ends
```
