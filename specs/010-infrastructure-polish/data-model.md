# Data Model: Infrastructure Improvements & Polish

**Sprint**: 010-infrastructure-polish
**Date**: 2026-02-23

---

## Entity Changes

This sprint modifies existing entities rather than introducing new domain concepts. Changes are grouped by subsystem.

---

### 1. Exception Hierarchy (US8)

**File**: `src/krag/models/exceptions.py`

#### New Exception Classes

| Exception | Parent | Fields | HTTP Mapping |
|-----------|--------|--------|-------------|
| `ServiceNotReadyError` | `KragError` | `message: str` | 503 |
| `IndexingInProgressError` | `KragError` | `message: str` | 409 |
| `ResourceNotConfiguredError` | `KragError` | `resource: str, message: str` | 500 |

#### Modified Exception Classes

| Exception | Change | File |
|-----------|--------|------|
| `LexiconValidationError` | Parent: `Exception` → `KragError` | `src/krag/lexicon/lexicon_store.py` |
| `EvalLoadError` | Parent: `Exception` → `KragError` | `src/krag/evaluation/loader.py` |

#### Relationships
- `app.py` exception handler dispatches on `isinstance(exc, ServiceNotReadyError)` → 503, `isinstance(exc, IndexingInProgressError)` → 409, etc.
- All domain exceptions inherit from `KragError`, enabling a catch-all handler for krag-specific errors.

---

### 2. Configuration Model (US4)

**File**: `src/krag/models/configuration.py`

#### New Fields on `Configuration`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `embedding_code_model` | `str \| None` | `None` | Code-specific embedding model name. When set, enables dual-model indexing with a `"code"` named vector space. |

#### Validation Rules
- When `embedding_code_model` is set, it must be a non-empty string.
- When `None`, the system uses single-model behaviour (backward-compatible).
- No interaction with `embedding_model` — they are independent.

#### State Transitions
- `None` → `"jinaai/jina-embeddings-v2-base-code"`: Enables code embedding. Next indexing run creates the `"code"` named vector space and dual-embeds code files.
- `"model-name"` → `None`: Disables core code embedding. If a plugin registers a code model, that takes over. Otherwise, reverts to single-model.

---

### 3. Schema Rename (US10)

**File**: `src/kragd/schemas.py`

#### Rename: `IndexError` → `IndexingFileError`

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Path of the failed file |
| `error_type` | `str` | Exception type name |
| `error_message` | `str` | Error description |

All references updated:
- `IndexResponse.errors: list[IndexingFileError]`
- `service.py` import alias removed (currently `from kragd.schemas import IndexError as IndexErr`)

---

### 4. Metadata Store (US1)

**File**: `metadata.json` (filesystem, not a model class)

#### No structural change — behavioural change only

Current format (array of objects):
```json
[
  {
    "file_path": "/absolute/path/to/file.py",
    "file_size": 1234,
    "modification_time": "2026-02-20T10:30:00",
    "file_type": ".py",
    "content_hash": "sha256hex...",
    "last_indexed_at": "2026-02-20T10:31:00",
    "chunk_count": 5
  }
]
```

#### Behavioural Changes
- **Load**: No longer filtered by current `directory_paths`. All entries loaded unconditionally.
- **Save**: Includes all entries from the merged state (current run + previously loaded). Prunes entries where `file_path` no longer exists on disk.
- **Merge rule**: Current run's entries overwrite same-path entries from the load. Entries not touched by the current run are preserved as-is.

---

### 5. Mode Registry Cache (US6)

**File**: `src/kragd/service.py` (internal state on `KragService`)

#### New Internal Fields

| Field | Type | Purpose |
|-------|------|---------|
| `_modes_last_reload` | `float` | `time.monotonic()` timestamp of last mode reload |
| `_modes_dir_mtime` | `int` | `st_mtime_ns` of the modes directory at last reload |
| `_modes_reload_lock` | `threading.Lock` | Prevents concurrent mode file reloads |

#### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `_MODES_RELOAD_INTERVAL` | `5.0` | Minimum seconds between mode reload checks |

---

### 6. Failure Collector Thread Safety (US6)

**File**: `src/krag/plugins/failures.py`

#### New Internal Field on `IndexingFailureCollector`

| Field | Type | Purpose |
|-------|------|---------|
| `_lock` | `threading.Lock` | Guards all accesses to `_failures` list |

---

### 7. QueryEngine Parameter Extension (US6)

**File**: `src/krag/synthesis/` or wherever `QueryEngine` is defined

#### Modified Method Signature

```
query(
    query_text: str,
    ...,
    llm_client: LLMClient | None = None,   # NEW — per-request override
    critic: RelevanceCritic | None = None,  # NEW — per-request override
) -> QueryResult
```

When `llm_client` / `critic` are provided, they are used for that invocation instead of `self.llm_client` / `self.critic`. The shared instance attributes are no longer mutated by callers.
