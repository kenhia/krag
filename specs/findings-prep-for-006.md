# Code Quality Findings — Prep for 006

**Date**: 2026-02-17 (post-005 merge)
**Branch**: main @ fdc2041
**Test baseline**: 800 passed, 2 skipped
**Context**: Deep review of all source added/modified in the 005-code-aware-indexing branch

---

## Correctness Bugs (will cause wrong behavior now)

### F-01 — LLM routing never fires: `file_type` check uses wrong values
**Severity**: HIGH
**File**: `src/krag/synthesis/llm_pool.py` (~line 415-425)

`_analyze_chunk_composition()` checks `c.file_type in CODE_EXTENSIONS` where `CODE_EXTENSIONS` contains dotted extensions like `".py"`, `".js"`. But `file_type` holds semantic labels like `"code"`, `"markdown"`, `"text"` — never extensions. The condition is always False, so the code LLM is **never selected** via auto-routing.

```python
# What's there:
CODE_EXTENSIONS = frozenset({".py", ".js", ".java", ...})
code_count = sum(1 for c in chunks if c.file_type in CODE_EXTENSIONS)

# What file_type actually holds:
"code"  # ← set by scanner, not ".py"
```

**Fix**: Check `c.file_type == "code"` or also check `Path(c.file_path).suffix in CODE_EXTENSIONS`.

---

### F-02 — `index_incremental` doesn't delete old vectors for modified files
**Severity**: HIGH
**File**: `src/krag/orchestration/indexer.py` (~line 730-760)

When a file is modified, new chunks with fresh UUIDs are upserted. Old vectors from the previous version are never deleted (upsert is by chunk ID, and new chunks have different IDs). Over repeated incremental re-indexes, stale data accumulates.

**Fix**: Before re-indexing modified files, call `self.vector_store.delete_by_filter({"file_path": str(change.file_path)})`.

---

### F-03 — Keyword/metadata boost weights dwarf RRF scores
**Severity**: HIGH
**File**: `src/krag/retrieval/retriever.py` (~line 29-31, 97-114)

Boost weights (`_KEYWORD_BOOST_WEIGHT = 0.05`, `_METADATA_BOOST_WEIGHT = 0.08`) are calibrated for cosine similarity (0.0–1.0). RRF scores are ~0.016 per contributing list. A single keyword match (+0.05) **triples** the RRF score; a single metadata match (+0.08) **quintuples** it. This completely overrides rank-fusion ordering.

**Fix**: Scale boost weights relative to the score range — use much smaller values for RRF path.

---

### F-04 — Stale `chunker` variable leaks across loop iterations
**Severity**: MEDIUM
**File**: `src/krag/orchestration/indexer.py` (~line 570-610, ~850-870)

`chunker` is only assigned inside the `if plugin_handler is not None` block. If iteration N uses a plugin chunker and N+1 does not, `chunker` persists from the previous iteration and `"chunker" in locals()` is True. File N+1 uses the wrong chunker.

**Fix**: Initialize `chunker = None` at the start of each loop iteration.

---

### F-05 — Empty `file_path` in payload crashes entire retrieval
**Severity**: MEDIUM
**File**: `src/krag/retrieval/retriever.py` (~line 155, ~212)

`Path(payload.get("file_path", ""))` is not absolute → Pydantic `file_path_must_be_absolute` validator raises `ValidationError`, crashing the **entire** retrieval — not just skipping one bad result.

**Fix**: Catch `ValidationError` per-result and skip corrupt entries, or use a fallback path.

---

### F-06 — `QueryResult.score` validator `le=1.0` rejects valid scores
**Severity**: MEDIUM
**File**: `src/krag/models/query_result.py` (~line 12)

`score: float = Field(le=1.0)` will reject valid dot-product scores >1.0 or boosted scores. It's also semantically wrong since the field now holds RRF rank-fusion values.

**Fix**: Remove `le=1.0` upper bound.

---

## DRY Violations

### F-07 — ~80 lines of verbatim-identical setup code in query.py and eval.py
**Severity**: HIGH
**Files**: `src/krag/cli/query.py`, `src/krag/cli/eval.py`

The following blocks are character-for-character identical in both files:
- Config loading boilerplate (~12 lines)
- EmbeddingOrchestrator + plugin registration (~13 lines)
- Vector store initialization (~7 lines)
- EmbeddingGenerator construction (~4 lines)
- LLMClient construction (~11 lines, appears **3 times total**: 2x in query.py, 1x in eval.py)

**Fix**: Create `src/krag/cli/pipeline.py` with shared factory functions:
- `load_config(config_path) → Configuration`
- `create_embedding_pipeline(config) → (EmbeddingGenerator, EmbeddingOrchestrator)`
- `create_vector_store(config, generator, orchestrator) → QdrantVectorStore`
- `create_llm_client(config) → LLMClient`
- `create_query_engine(config, top_k, preset) → QueryEngine`

---

### F-08 — ~150 lines duplicated between `index_full` and `index_incremental`
**Severity**: MEDIUM
**File**: `src/krag/orchestration/indexer.py` (~line 450-670 vs ~770-970)

Per-file processing loop (plugin handler lookup, text extraction, chunking, embedding, payload building, metadata tracking) is copy-pasted between both methods. Bug fixes in one must be manually replicated in the other — and they've already diverged (see F-04, F-10).

**Fix**: Extract `_process_single_file(file_metadata, plugin_handler) → list[dict]` helper.

---

### F-09 — `_get_free_vram()` duplicated with behavioral differences
**Severity**: MEDIUM
**Files**: `src/krag/embeddings/orchestrator.py` (~line 24-37), `src/krag/synthesis/llm_pool.py` (~line 72-82)

Two nearly-identical implementations: orchestrator catches `(ImportError, RuntimeError)`, llm_pool catches bare `Exception`. `krag.gpu` already exists as the natural home.

**Fix**: Consolidate into `krag.gpu` module.

---

### F-10 — QueryResult payload→object construction duplicated in retriever
**Severity**: LOW
**File**: `src/krag/retrieval/retriever.py` (~line 141-170 vs ~204-228)

`_results_to_query_results` and `_multi_model_retrieve` inner loop have identical QueryResult construction from payload dicts.

**Fix**: Extract `_payload_to_query_result(id, score, rank, payload)` helper.

---

## Consistency Issues

### F-11 — Config path resolution diverges across CLI commands
**Severity**: HIGH
**Files**: `src/krag/cli/query.py`, `src/krag/cli/eval.py` vs `src/krag/cli/index.py`

query.py and eval.py hardcode `Path.home() / ".config" / "krag" / "config.toml"`. index.py uses XDG-aware `get_krag_config_dir()`. **Query/eval break on non-default `$XDG_CONFIG_HOME`**.

**Fix**: All commands should use `get_krag_config_dir()` (resolved by F-07 shared pipeline).

---

### F-12 — Plugin name resolution differs between full/incremental index
**Severity**: MEDIUM
**File**: `src/krag/orchestration/indexer.py`

`index_full` uses `getattr(plugin_handler, "name", plugin_handler.__class__.__name__)`.
`index_incremental` uses `plugin_handler.__class__.__name__` directly.
For `CodeFileHandler`, `.name` returns `"code"` but `.__class__.__name__` returns `"CodeFileHandler"`. Chunking config keys won't match in the incremental path.

**Fix**: Use consistent name resolution (resolved by F-08 extract helper).

---

### F-13 — Error output mechanism inconsistent across CLI commands
**Severity**: MEDIUM
**Files**: `src/krag/cli/query.py` (Rich panels), `src/krag/cli/eval.py` (plain stderr), `src/krag/cli/index.py` (Rich markup)

eval.py intentionally uses stderr for machine-parseable stdout, but inconsistency with query.py gives users visual whiplash.

**Fix**: Standardize error output approach (resolved by F-07 shared pipeline).

---

### F-14 — Exception handling patterns differ across CLI commands
**Severity**: MEDIUM
**Files**: query.py (logs + Rich + FileNotFoundError handling), eval.py (print to stderr, no logging)

**Fix**: Standardize (resolved by F-07).

---

### F-15 — Vector store pre-check missing in eval.py
**Severity**: MEDIUM
**Files**: query.py checks `Path(config.vector_store_path).exists()` with user-friendly panel. eval.py skips this — users get a raw exception.

**Fix**: Standardize (resolved by F-07).

---

### F-16 — `top_k` defaulting strategy differs
**Severity**: LOW
**Files**: query.py hardcodes CLI default 5, ignoring config. eval.py defaults to None, falls back to config.

**Fix**: Both should respect config, with CLI override taking precedence.

---

### F-17 — Keyword min-length inconsistent between boost functions
**Severity**: LOW
**File**: `src/krag/retrieval/retriever.py`

`_metadata_boost` uses min-length 2, no stop words. `_keyword_boost` uses min-length 3 with stop words. 

**Fix**: Unify keyword extraction into a shared helper.

---

## Design Issues

### F-18 — eval.py lacks LLMPool / multi-LLM routing
**Severity**: MEDIUM
**File**: `src/krag/cli/eval.py`

query.py has ~50 lines implementing LLMPool-based routing. eval.py has no awareness of LLMPool — always uses the single text LLM. Eval results don't match query behavior for code queries.

**Fix**: Resolved by F-07 shared pipeline with LLMPool support built in.

---

### F-19 — Unnecessary same-dimension enforcement for all embedding models
**Severity**: MEDIUM
**File**: `src/krag/embeddings/orchestrator.py` (~line 118-124)

Qdrant named vectors support different dimensions per space. `get_vector_config()` correctly creates per-vector VectorParams. The dimension equality check artificially prevents legitimate multi-model configurations.

**Fix**: Remove dimension equality check — dimensions only need to be consistent per vector name.

---

### F-20 — `search()` fallback hardcodes `"text"` vector name
**Severity**: LOW
**File**: `src/krag/storage/qdrant_impl.py` (~line 240-245)

If a collection has named vectors but none called `"text"`, this crashes. Currently always present, but it's a hidden coupling.

**Fix**: Add defensive check or document the invariant.

---

### F-21 — Dead code: `_display_sources_only()` never called
**Severity**: LOW
**File**: `src/krag/cli/query.py`

Defined but has zero callers. The `no_synthesis` branch inlines display logic instead.

**Fix**: Remove or wire up.

---

### F-22 — `ScoredPointLike` protocol defined but never used in type annotations
**Severity**: LOW
**File**: `src/krag/retrieval/rrf.py`

`reciprocal_rank_fusion` takes `list[list[Any]]` instead of using the protocol.

**Fix**: Either use the protocol in signatures or remove it.

---

### F-23 — `QueryEngine` and `Retriever` use `Any` for typed parameters
**Severity**: LOW
**Files**: `src/krag/orchestration/query_engine.py`, `src/krag/retrieval/retriever.py`

Three parameters typed `Any` where `VectorStore` ABC and `EmbeddingOrchestrator` class exist.

**Fix**: Use proper types or protocols.

---

### F-24 — Redundant imports inside methods
**Severity**: LOW
**File**: `src/krag/orchestration/indexer.py` (~line 329)

`from datetime import datetime` already imported at module top. `import json` done inside methods instead of at module level.

**Fix**: Move to module-level imports.

---

### F-25 — `__del__` calling `close()` on `IndexingOrchestrator` is fragile
**Severity**: LOW
**File**: `src/krag/orchestration/indexer.py` (~line 230)

`__del__` at GC/shutdown time when referenced objects may be finalized. Context manager (`__enter__`/`__exit__`) is already implemented and is correct.

**Fix**: Remove `__del__` or add defensive guards.

---

### F-26 — query.py constructs LLMClient redundantly when pool is active
**Severity**: MEDIUM
**File**: `src/krag/cli/query.py` (~line 147-185)

When `use_pool=True`, both an `LLMPool` and a full `LLMClient` are constructed. The `LLMClient` is passed to `QueryEngine`, but when the pool path is taken, `QueryEngine.query()` is never called — the code manually does retrieval + `llm_pool.route_and_generate()`. The QueryEngine and its LLMClient are constructed but unused, wasting memory.

**Fix**: Resolved by F-07 shared pipeline.

---

## Logging Improvements

### F-27 — Excessive upsert log entries during indexing
**Severity**: MEDIUM
**File**: `src/krag/storage/qdrant_impl.py`

With 6838 vectors in ~69 batches, each batch logs `"Upserted N vectors to collection"` at INFO level. This produces ~70 log entries for a single index operation. At scale (100k+ vectors), this will produce 1000+ upsert entries. Total upsert-related entries in current log: **300**.

**Fix**: Log a single "Storing N vectors" at start, then group batches into summary entries (e.g., "Upserted 7×100 vectors") with no more than ~10 log entries for the entire upsert operation.

---

### F-28 — No log rotation CLI command
**Severity**: LOW
**File**: CLI / logging infrastructure

During debugging, starting with a clean log requires manually deleting the file. A `krag log rotate` or `krag log clear` CLI command would streamline the debugging workflow.

**Fix**: Add a `krag log` subcommand group with `rotate` (archive current log) and `clear` (truncate) commands.

---

## Additional Quality Improvements Identified

### F-29 — No structured progress reporting during long indexing operations
**Severity**: MEDIUM
**File**: `src/krag/orchestration/indexer.py`

The indexer logs per-file processing but provides no periodic summary (e.g., "Processed 150/260 files, 2340 chunks so far"). For large corpora, the user has no visibility into progress from logs alone.

**Fix**: Add periodic summary logging (every N files or every M seconds).

---

### F-30 — Missing integration test for the full query pipeline with named vectors
**Severity**: MEDIUM
**Files**: `tests/`

The eval regression (3/3 → 2/3) shows that the end-to-end query pipeline with named vectors and RRF hasn't been adequately tested. There are unit tests for RRF and named-vector search individually, but no integration test that indexes with named vectors, queries with RRF, and verifies the results are relevant and correctly scored.

**Fix**: Add an integration test that: indexes sample docs with multi-model embeddings → queries via RRF → verifies results pass threshold and include expected sources.

---

### F-31 — Eval output doesn't expose retrieval metadata
**Severity**: LOW
**File**: `src/krag/cli/eval.py`

Eval results show sources but not: which embedding models were used, which vector spaces contributed, individual vector-space scores vs. RRF-fused scores, or whether RRF was active. This makes it hard to diagnose retrieval quality regressions.

**Fix**: Add optional `--verbose` flag to eval that includes retrieval metadata in the JSON report.

---

### F-32 — No type-checking in CI or pre-commit
**Severity**: LOW
**Files**: `pyproject.toml`, `mypy.ini`

`mypy.ini` exists but there's no evidence of mypy running in CI. The `Any` typing issues (F-23) and missing type annotations would be caught automatically.

**Fix**: Consider adding mypy to the test/lint workflow.
