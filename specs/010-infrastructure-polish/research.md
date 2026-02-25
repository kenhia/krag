# Research: Infrastructure Improvements & Polish

**Sprint**: 010-infrastructure-polish
**Date**: 2026-02-23

---

## R1: Incremental Indexing Metadata Merge

### Decision
Remove the directory-path filter from `_load_metadata()` and preserve all metadata entries across runs. The save operation retains the full merged state.

### Rationale
The root cause is twofold: (1) `_load_metadata()` filters entries to only those under the current `directory_paths`, dropping metadata for files outside the scan scope; (2) `index_full()` rebuilds `self.indexed_files` from only the current run's processed files, discarding previously-indexed entries.

The fix is behavioral — no data structure changes are needed. The existing flat-array JSON format and `dict[str, FileMetadata]` in-memory structure are sufficient.

### Approach
1. **Remove filter on load**: `_load_metadata()` at [indexer.py L353–362](../../../src/krag/orchestration/indexer.py#L353-L362) should load all entries from `metadata.json` unconditionally. Directory filtering is already handled by the scanner — `categorize_changes()` only operates on files in the scan scope.
2. **Preserve entries in `index_full()`**: After the processing loop, retain metadata entries from the load that weren't re-processed (files outside the current scan scope). These are still valid and should survive.
3. **Prune stale entries on save**: In `_save_metadata()`, remove any entry whose `file_path` no longer exists on disk. This prevents unbounded growth from abandoned directories.
4. **No changes to `categorize_changes()`**: It already correctly classifies previously-indexed files as UNCHANGED when they appear in both the metadata and the current scan.

### Alternatives Considered
- **Per-directory metadata files**: Rejected — adds complexity for a single-user tool, makes cross-directory deduplication harder, and the current single-file approach works fine.
- **Only load metadata for superset directories**: Rejected — fragile and doesn't handle subset → superset → different directory sequences.

### Edge Cases
- Files from a removed directory: pruned on save via `Path.exists()` check.
- Concurrent orchestrator instances: pre-existing last-writer-wins race — out of scope but noted.
- Corrupted `metadata.json`: existing try/except in `_load_metadata()` handles this (falls back to empty).

---

## R2: Index-Status Accuracy

### Decision
Check `self._indexing` **before** checking `self._index_job_cache` in `get_index_status()`.

### Rationale
The current code at [service.py L1038–1082](../../../src/kragd/service.py#L1038-L1082) checks the cache first. If a previous run's result is cached, it returns that without checking whether a new run is active.

### Approach
Reorder the logic: if `self._indexing` is `True`, return a `status: running` response immediately (using `self._last_index_job` if available). Only fall through to the cache if not indexing. This is a ~5-line reorder, not a rewrite.

### Alternatives Considered
- Clear cache on new run start: rejected — loses the previous run's result, which is useful for `--history`.

---

## R3: Query/Debug-Query Unification

### Decision
Merge `query()` and `debug_query()` into a single code path where debug metadata collection is controlled by an `include_debug: bool` parameter.

### Rationale
The current two methods in [service.py](../../../src/kragd/service.py) duplicate retrieval, synthesis, and routing logic. Any fix to one must be manually applied to the other, and subtle behavioural differences have already caused bugs (e.g., critic handling differs).

### Approach
1. Add an `include_debug: bool = False` parameter to the unified `query()` method.
2. Always run the same retrieval, critic evaluation, and synthesis pipeline.
3. When `include_debug=True`, populate timing, routing, and chunk debug metadata in the response.
4. The `debug_query()` service method becomes a thin wrapper: `return self.query(..., include_debug=True)`.
5. The `/debug/query` router calls the same service method with `include_debug=True`.

### Alternatives Considered
- Decorator-based: wrap `query()` with a debug decorator that captures metadata. Rejected — adds indirection without simplification.
- Keep two methods but extract shared logic: rejected — still leaves two call sites to maintain.

---

## R4: Code Embedding in Core Config

### Decision
Add an `embedding_code_model: str | None` field to `Configuration` and parse it from a `[embedding_code]` TOML section. Register via the existing `EmbeddingOrchestrator.additional_models` mechanism.

### Rationale
The `EmbeddingOrchestrator` already fully supports multiple named embedding models via `additional_models` dict and `register_model()`. The infrastructure exists — only the config wiring is missing.

### Approach
1. **Configuration model**: Add `embedding_code_model: str | None = Field(default=None)` to `Configuration` at [configuration.py ~L360](../../../src/krag/models/configuration.py#L360).
2. **TOML parsing**: Parse `[embedding_code]` section in `_load_toml()` at [settings.py ~L96](../../../src/krag/config/settings.py#L96).
3. **Registration**: In the three call-sites that construct `EmbeddingOrchestrator` ([pipeline.py L126](../../../src/krag/cli/pipeline.py#L126), [service.py L142](../../../src/kragd/service.py#L142), [indexer.py constructor](../../../src/krag/orchestration/indexer.py#L281)), pass `additional_models={"code": config.embedding_code_model}` when the field is set.
4. **Plugin precedence**: The existing `register_model()` duplicate guard (returns early if vector name exists) means whoever registers first wins. Core registers via constructor → plugin's `register_model()` silently no-ops. If no core config, plugin registers as today. **Fully backward-compatible.**

### Alternatives Considered
- Plugin-only approach: status quo, rejected because it couples a core capability to the plugin distribution mechanism.
- Auto-detect code files and use code model: rejected — implicit magic, harder to debug.

---

## R5: Concurrency Safety

### Decision
Four targeted fixes, no new dependencies, no query serialisation.

### Approach

#### R5a: Query Isolation — Pass-as-Parameter
- Add `llm_client` and `critic` keyword arguments to `QueryEngine.query()`.
- Callers construct per-request `llm_client` and `RelevanceCritic` instances and pass them.
- Remove the shared-state mutation pattern (`self.query_engine.llm_client = ...` / `prev_critic = ...` / `finally restore`).
- No lock needed — each request gets its own instances. Zero contention.

#### R5b: Index Job Cache — Extend `_indexing_lock`
- Wrap all reads/writes to `_index_job_cache` and `_last_index_job` in `with self._indexing_lock:`.
- Critical sections are short (single assignment/append) — negligible contention.
- The lock is already `threading.Lock`, which is correct for the background `Thread`.

#### R5c: Mode Hot-Reload — mtime + TTL + Non-Blocking Lock
- Store `_modes_last_reload` timestamp and `_modes_dir_mtime`.
- On `_resolve_mode()`, skip reload if within 5s TTL.
- When TTL expires, `stat()` the modes directory; only call `load_user_modes()` if mtime changed.
- Use `Lock.acquire(blocking=False)` so contending requests skip reload instead of blocking.

#### R5d: Failure Collector — `threading.Lock`
- Add `self._lock = threading.Lock()` to `IndexingFailureCollector.__init__()`.
- Wrap `_failures.append()`, `get_failures()`, `total_failures()`, `failures_by_plugin()`, and `clear()` with `with self._lock:`.
- A `queue.Queue` is overkill — this is a batch accumulator, not a producer/consumer pipeline.

### Alternatives Considered
- `asyncio.Lock`: wrong tool — indexing runs in a `threading.Thread`, not an asyncio task.
- Global query lock: rejected — would serialize all queries, destroying latency.
- Per-request `QueryEngine` copy: rejected — shares mutable vector store state, expensive.

---

## R6: Exception Architecture

### Decision
Introduce typed domain exceptions; replace string-matching dispatch in `app.py` with `isinstance` checks; replace silent `except Exception: pass` blocks with logged warnings.

### Approach
1. **New exception classes** in [models/exceptions.py](../../../src/krag/models/exceptions.py):
   - `ServiceNotReadyError(KragError)` — replaces `RuntimeError("Service not started")`
   - `IndexingInProgressError(KragError)` — replaces `RuntimeError("Indexing is in progress")`
   - `ResourceNotConfiguredError(KragError)` — replaces `RuntimeError("No LLM model configured")`
2. **Update service.py**: Replace all 9 `RuntimeError` raises with appropriate domain exceptions.
3. **Update app.py**: Replace string matching with `isinstance` dispatch.
4. **Fix hierarchy**: `LexiconValidationError` → inherit from `KragError`; `EvalLoadError` → inherit from `KragError`.
5. **Silent except blocks**: Replace ~10 `except Exception: pass` blocks with `except Exception as e: logger.warning(...)`.

### Alternatives Considered
- HTTP exception integration (FastAPI's `HTTPException`): rejected — leaks HTTP concerns into the service layer. Domain exceptions are HTTP-agnostic.
- Exception middleware: rejected — more complexity than the simple `isinstance` handler.

---

## R7: Dead Code and Dependency Cleanup

### Decision
Remove identified dead code and unused dependencies.

### Items
1. **Delete** `src/kragd/routers/health.py` — dead file, never mounted in `app.py`. `system.py` provides identical endpoints.
2. **Remove** `llama-index>=0.9.0` from `pyproject.toml` — zero imports in codebase, ~100 transitive packages for nothing.
3. **Remove** `tomli>=2.0.0 ; python_version < '3.11'` — impossible marker given `requires-python = ">=3.11"`.
4. **Remove** duplicate `DEFAULT_VECTOR_STORE_PATH` in [defaults.py L121](../../../src/krag/config/defaults.py#L121) — keep the first definition at L114.
5. **Remove** `[project.optional-dependencies] dev` — stale duplicate of `[dependency-groups] dev` with conflicting version pins.

### Alternatives Considered
- Keep `health.py` as a fallback: rejected — it has divergent shutdown behaviour compared to `system.py` and is never imported.
- Keep `llama-index` for future use: rejected — can be re-added when actually needed. Unnecessary install burden today.

---

## R8: CLI Consistency

### Decision
Fix `ConfigManager.find_and_load()`, unify error formatting, add missing `--mode` to debug query.

### Approach
1. **`find_and_load()` fix**: Add a `find_and_load()` static method to `ConfigManager` that reuses `krag_cli.config.find_config()` + `ConfigManager.load()`. Alternatively, update the two callers ([cli/modes.py L38](../../../src/krag/cli/modes.py#L38), [commands/query.py L101](../../../src/krag_cli/commands/query.py#L101)) to use `find_config()` + `load()` directly. Preferred: add the method to `ConfigManager` since it's the natural API surface.
2. **Error prefix**: Change `[red]Fatal:[/red]` in [index.py L103](../../../src/krag_cli/commands/index.py#L103) to `[red]Error:[/red]` for consistency with all other commands.
3. **`--mode` option**: Add `mode: str | None = typer.Option(None, "--mode", "-m")` to the `debug_query_command` in [debug.py](../../../src/krag_cli/commands/debug.py).
4. **`--json` naming**: Standardize on `output_json: bool = typer.Option(False, "--json")` across status, debug, and index commands. The query command's `--format` enum approach is a superset and should be preserved there.

### Alternatives Considered
- Deprecation path for `--json` vs `--format`: not worth the effort for a personal tool. Just fix it.

---

## R9: Plugin Registry Hardening

### Decision
Make `discover_plugins()` self-contained; remove unnecessary `inspect.signature` guard; rename shadowing `IndexError`.

### Approach
1. **Auto-build extension map**: Add `self._build_extension_map()` as the final step of `discover_plugins()` in [registry.py](../../../src/krag/plugins/registry.py). Remove the explicit call from [indexer.py L151](../../../src/krag/orchestration/indexer.py#L151).
2. **Remove inspect.signature**: In `initialize_plugin()` at [loader.py L184–191](../../../src/krag/plugins/loader.py#L184-L191), always call `handler.initialize(config, context=context)` without the signature inspection. The base class contract guarantees the parameter.
3. **Rename `IndexError`**: Rename to `IndexingFileError` in [schemas.py L211](../../../src/kragd/schemas.py#L211). Update all references (primarily in `IndexResponse.errors` field and `service.py` import alias).

### Alternatives Considered
- Lazy extension map build in `get_handler_for_extension()`: rejected — adds per-call overhead and confusing semantics.
