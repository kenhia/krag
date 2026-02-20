# Data Model: 006-code-quality-sprint

**Date**: 2026-02-18

## Entities

### QueryPipeline (NEW)

Immutable container holding the fully-initialized infrastructure components needed by both `krag query` and `krag eval`. Created once per CLI invocation by `build_query_pipeline()`.

| Field | Type | Description |
|-------|------|-------------|
| config | Configuration | Loaded and validated configuration |
| embedding_generator | EmbeddingGenerator | Sentence-transformer wrapper for query embedding |
| embedding_orchestrator | EmbeddingOrchestrator | Multi-model embedding coordinator with registered plugins |
| vector_store | QdrantVectorStore | Initialized vector store client |
| llm_client | LLMClient | Primary LLM for text synthesis |
| llm_pool | LLMPool \| None | Multi-LLM router (None if only one model configured) |
| query_engine | QueryEngine | Retrieval + synthesis engine |

**Relationships**: QueryPipeline is constructed by `build_query_pipeline()` in `cli/pipeline.py`. Consumed by `cli/query.py` and `cli/eval.py`. Not persisted.

**Validation Rules**:
- Config must be loaded from XDG-aware path (via `get_krag_config_dir()`)
- Vector store path must exist on disk before construction (pre-check with user-friendly error)
- `top_k` resolved: CLI arg > config value > default (5)

**State Transitions**: None — immutable after construction.

---

### FileProcessingResult (INTERNAL)

Return type of the extracted `_process_file()` method on `IndexingOrchestrator`. Captures the output of processing a single file through the text-extraction → chunking → embedding → payload-building pipeline.

| Field | Type | Description |
|-------|------|-------------|
| payloads | list[dict] | Qdrant-ready point payloads for upsert |
| chunk_count | int | Number of chunks produced |
| handler_name | str \| None | Plugin handler name used (for metadata) |
| error | str \| None | Error message if processing failed |

**Relationships**: Produced by `IndexingOrchestrator._process_file()`. Consumed by `index_full()` and `index_incremental()` for upsert and metadata tracking.

**Validation Rules**:
- `chunker` must be reset to `None` at the start of each invocation (F-04)
- Plugin name resolved via `getattr(handler, "name", handler.__class__.__name__)` consistently (F-12)

---

### LogManager (NEW — Functional)

Not a class but a set of functions in `cli/log.py` implementing the `krag log` subcommand group. Operates on the log file at `get_krag_state_dir() / "logs" / "krag.log"`.

| Operation | Behavior |
|-----------|----------|
| rotate | Archive current log → `krag.log.1`, shift existing `krag.log.{1..4}` → `{2..5}`, create fresh `krag.log` |
| clear | Truncate `krag.log` to zero bytes |
| path | Print the absolute path to the log file |

**Edge cases**:
- No log file exists → `rotate` creates parent dirs + empty file; `clear` is a no-op
- Log file is in use by another process → `clear` truncates (safe on POSIX); `rotate` uses `shutil.move`

---

## Modified Entities

### QueryResult (MODIFY)

| Change | Before | After |
|--------|--------|-------|
| `score` constraint | `Field(..., ge=0.0, le=1.0)` | `Field(..., ge=0.0)` — remove upper bound |
| `score` description | "Similarity score (0.0-1.0)" | "Relevance score (higher is better)" |

### QdrantVectorStore.upsert (MODIFY — Logging)

| Change | Before | After |
|--------|--------|-------|
| Logging | INFO per batch ("Upserted N vectors") | DEBUG per batch; single INFO at start ("Storing N vectors in M batches") + single INFO at end ("Stored N vectors") |

### EmbeddingOrchestrator (MODIFY)

| Change | Before | After |
|--------|--------|-------|
| Dimension check | Error if model dimensions differ | Removed — Qdrant supports heterogeneous dimensions per named vector space |
| `_get_free_vram()` | Inline implementation | Import from `krag.cli.gpu` |

### Retriever (MODIFY)

| Change | Before | After |
|--------|--------|-------|
| Boost weights | Fixed `0.05`/`0.08` for all score types | `0.05`/`0.08` for cosine; `0.002`/`0.003` for RRF |
| Empty file_path | Crashes entire retrieval via ValidationError | Skips individual result, logs warning |
| `_payload_to_query_result()` | Duplicated in 2 methods | Extracted to shared helper |
