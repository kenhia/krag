# Feature Specification: Infrastructure Improvements & Polish

**Feature Branch**: `010-infrastructure-polish`
**Created**: 2026-02-23
**Status**: Draft

## Overview

This sprint addresses a collection of correctness bugs, code quality debt, and user-experience improvements identified during Sprint 009 testing. Items are drawn from the project backlog and grouped around making krag more reliable, easier to configure, and more transparent to operate.

Items in scope:
1. Fix incremental indexing metadata loss across directory changes
2. Fix index-status staleness while indexing is active
3. Unify the query and debug-query code paths
4. Move code-embedding model configuration into krag core
5. Operational UX tweaks (startup log banners, log rotation, rich markdown output)
6. Concurrency safety for query engine shared state
7. Dead code and dependency cleanup
8. Exception handling and error architecture improvements
9. CLI consistency and broken feature fixes
10. Plugin registry API hardening

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Incremental indexing preserves unchanged files across directory changes (Priority: P1)

A developer has previously indexed `~/src/project-a/`. They now run a broader index of `~/src/` (which includes `project-a/` as a subdirectory). They expect the previously-indexed files to be recognised as unchanged and skipped — not deleted and re-added.

**Why this priority**: Data correctness bug. Every directory expansion causes unnecessary delete+re-add cycles in the vector store, increases indexing time, and produces misleading change counts.

**Independent Test**: Index a directory, then index a parent directory. Confirm files from the first run appear as `unchanged` in the second run, that no deletions are logged for those files, and that the vector count does not change for already-indexed files.

**Acceptance Scenarios**:

1. **Given** `~/src/proj/` has been indexed, **When** `krag index -d ~/src/` is run, **Then** all files under `~/src/proj/` are reported as `unchanged` and zero deletions are logged for those files.
2. **Given** metadata exists for 50 files, **When** the next run covers a superset directory and those files are unmodified, **Then** `files_skipped_unchanged` equals 50.
3. **Given** a file was indexed in run 1 and genuinely modified before run 2, **When** run 2 covers a parent directory, **Then** that file is reported as `modified` and re-indexed.
4. **Given** a file was indexed in run 1 but deleted before run 2, **When** run 2 covers a parent directory, **Then** that file is reported as `deleted` and removed from the index.

---

### User Story 2 — Index-status accurately reflects a running indexing job (Priority: P1)

A user triggers a large indexing run and immediately polls `krag index-status`. They expect to see that indexing is in progress, not the result of the previous run.

**Why this priority**: Correctness bug. The status command is the primary tool for monitoring indexing progress; returning stale data misleads the user into thinking the previous run is the current state.

**Independent Test**: Start a long indexing run, immediately poll `krag index-status`, and confirm it returns `status: running` rather than the prior completed result.

**Acceptance Scenarios**:

1. **Given** a previous run completed (status: completed), **When** a new indexing run is started and `index-status` is called before it finishes, **Then** the response shows `status: running`.
2. **Given** indexing is running, **When** `index-status` is polled repeatedly, **Then** all responses show `status: running` until the job completes.
3. **Given** an indexing run just completed, **When** `index-status` is called, **Then** the response shows the completed run's full statistics.

---

### User Story 3 — Debug mode is a transparent superset of standard query (Priority: P2)

A developer investigating unexpected query results runs the same query with `--debug` added. They expect identical retrieval results and LLM output — the flag must never change the answer, only add observability metadata.

**Why this priority**: The current two-path architecture creates subtle behavioural differences. Unifying the paths eliminates a class of hard-to-diagnose bugs and makes `--debug` a trustworthy diagnostic tool.

**Independent Test**: Run the same query with and without `--debug`. Confirm both return identical `answer` and `sources`. The `--debug` response additionally contains populated `debug` metadata.

**Acceptance Scenarios**:

1. **Given** any query and mode, **When** the same query is run with and without `--debug`, **Then** the `answer` and `sources` are identical.
2. **Given** a mode with `critic_enabled = true`, **When** a query is run with `--debug`, **Then** `debug.critic_scores`, `debug.chunks_pre_critic`, and `debug.chunks_post_critic` are populated and reflect the same filtering as the non-debug run.
3. **Given** a mode with `llm.slot = "code"`, **When** a query is run with `--debug`, **Then** `debug.llm_used` equals `"code"`.
4. **Given** a query with `--debug`, **When** the response is returned, **Then** all timing, routing, and retrieval metadata fields are populated.

---

### User Story 4 — Code embedding is configured in krag core without a plugin (Priority: P2)

A user who wants code-aware search enables the code embedding model by adding an `[embedding_code]` section to their krag config, without needing to install or configure a separate plugin.

**Why this priority**: The current situation couples a capability (dual-embedding for code) to the plugin distribution mechanism. Users building on krag core should not need a plugin just to get code-quality embeddings.

**Independent Test**: Remove the code plugin's embedding model declaration. Add `[embedding_code]` to the base krag config. Run indexing and confirm that code chunks are embedded using the code model and that named vector spaces (`text`, `code`) are present in the vector store.

**Acceptance Scenarios**:

1. **Given** a krag config with `[embedding_code]` section, **When** indexing runs, **Then** code files are embedded using the code embedding model and stored in the `code` named vector space.
2. **Given** a krag config without `[embedding_code]`, **When** indexing runs, **Then** all files use the default embedding model (single vector space, backwards-compatible).
3. **Given** both krag core `[embedding_code]` and a plugin that registers a code embedding model, **When** indexing runs, **Then** the plugin takes precedence.
4. **Given** `[embedding_code]` is configured, **When** `krag status` is called, **Then** both embedding models are listed under `embedding_models`.

---

### User Story 5 — Operational visibility: log bookmarks, log rotation, and rich responses (Priority: P3)

An operator monitoring kragd can clearly see in the log when the service started, became ready, and shut down. They can rotate logs before a debugging session with one flag. Query responses that contain markdown render with appropriate formatting in the terminal.

**Why this priority**: Quality-of-life improvements. Log bookmarks make it faster to find relevant log sections. Log rotation is a common operational need. Rich markdown rendering improves readability. None are correctness issues.

**Independent Test**: Start kragd and confirm `KRAGD STARTING` and `KRAGD READY` appear in the log. Stop kragd and confirm `KRAGD SHUTTING DOWN` appears. Run `kragd --rotate-logs` and confirm a fresh log file is started. Run a query whose answer contains a code block and confirm it renders with syntax highlighting.

**Acceptance Scenarios**:

1. **Given** kragd starts, **Then** the log contains a clearly visible `KRAGD STARTING` entry, followed by `KRAGD READY` once the service is accepting connections.
2. **Given** kragd receives a shutdown signal, **Then** the log contains a `KRAGD SHUTTING DOWN` entry.
3. **Given** `kragd --rotate-logs` is used at startup, **Then** any existing log file is archived and a fresh log file is started.
4. **Given** a query response contains markdown (code blocks, bullet lists, headings), **When** displayed in an interactive terminal, **Then** the output renders with rich formatting rather than raw markdown syntax.

---

### User Story 6 — Concurrent queries do not corrupt shared state (Priority: P1)

Two users (or an automated pipeline) issue queries simultaneously with different modes. Each query must receive results produced by its own mode configuration — not a blend of two modes racing on the same shared objects.

**Why this priority**: The query service mutates `query_engine.llm_client` and `query_engine.critic` on a shared instance for every request. Under concurrent load, one request's mode configuration overwrites another's mid-flight. This can produce wrong answers, wrong LLM selection, or NoneType crashes.

**Independent Test**: Issue two concurrent queries with different modes (one with critic enabled, one without). Confirm each response reflects its own mode's settings and neither errors. Repeat 50 times to expose timing-dependent races.

**Acceptance Scenarios**:

1. **Given** two simultaneous queries with different modes, **When** both complete, **Then** each response reflects its own mode's LLM and critic configuration — no cross-contamination.
2. **Given** 50 concurrent queries across 5 different modes, **When** all complete, **Then** zero errors occur and each response's `debug.llm_used` matches its requested mode.
3. **Given** a mode with `critic_enabled = true` and a mode with `critic_enabled = false` queried concurrently, **Then** critic scores appear only in the critic-enabled response.

---

### User Story 7 — Dead code and unused dependencies are removed (Priority: P2)

A developer examining the codebase or installing krag finds no dead router files, no unused heavyweight dependencies, and no duplicate configuration values that create confusion.

**Why this priority**: Dead code misleads contributors and wastes review time. The unused `llama-index` dependency adds ~100 transitive packages to every install for zero value. Duplicate constants are copy-paste error indicators.

**Independent Test**: Confirm the dead files and dependencies identified below are removed. Run the full test suite to verify nothing breaks. Confirm `pip install` no longer pulls `llama-index`.

**Acceptance Scenarios**:

1. **Given** `kragd/routers/health.py` is dead code (never mounted in `app.py`), **When** the cleanup is complete, **Then** the file is removed and all tests pass.
2. **Given** `llama-index>=0.9.0` is declared in `pyproject.toml` but never imported, **When** the cleanup is complete, **Then** it is removed from dependencies.
3. **Given** `tomli>=2.0.0 ; python_version < '3.11'` is impossible (`requires-python = ">=3.11"`), **When** the cleanup is complete, **Then** it is removed.
4. **Given** `DEFAULT_VECTOR_STORE_PATH` is defined twice in `defaults.py` (lines 114 and 121), **When** the cleanup is complete, **Then** only one definition exists.
5. **Given** `[project.optional-dependencies] dev` duplicates `[dependency-groups] dev` with conflicting version pins, **When** the cleanup is complete, **Then** only the active `[dependency-groups]` form remains.

---

### User Story 8 — Exception handling uses domain types, not string matching (Priority: P2)

When a service-layer error is mapped to an HTTP status code, the mapping is based on exception type — not fragile string matching against error messages. Silent `except Exception: pass` blocks are replaced with proper logging.

**Why this priority**: The current `app.py` exception handler matches strings like `"indexing is in progress"` and `"not started"` to decide between 409 and 503 responses. Rewording an error message silently changes HTTP behaviour. Additionally, ~10 silent `except Exception: pass` blocks hide real bugs in the indexer and service layer.

**Independent Test**: Raise each domain exception from the service layer and confirm the correct HTTP status code is returned via `isinstance` checks. Trigger each formerly-silent except block and confirm the error is now logged.

**Acceptance Scenarios**:

1. **Given** the service raises a "not started" condition, **When** the exception handler processes it, **Then** a 503 is returned based on exception type (e.g., `ServiceNotReadyError`), not string content.
2. **Given** the service raises an "indexing in progress" condition, **When** the exception handler processes it, **Then** a 409 is returned based on exception type (e.g., `IndexingInProgressError`).
3. **Given** a chunk metadata enrichment fails in the indexer, **When** the error occurs, **Then** a warning is logged with the file path and error details (not silently swallowed).
4. **Given** a vector store stats query fails in the service layer, **When** the error occurs, **Then** a warning is logged (not silently passed).
5. **Given** `LexiconValidationError` is raised, **Then** it inherits from `KragError` (not bare `Exception`).

---

### User Story 9 — CLI commands are consistent and broken features are fixed (Priority: P2)

A user switching between CLI commands finds consistent flag naming, consistent error formatting, and working features. Path aliases and local mode discovery work as intended rather than silently failing.

**Why this priority**: `ConfigManager.find_and_load()` does not exist — every call to it raises `AttributeError` which is silently caught, making path aliases and CLI mode discovery permanently broken. The `--json` flag naming and error display formatting vary across commands.

**Independent Test**: Verify `_get_path_aliases()` returns real aliases from config. Verify `--json` flags use consistent naming. Verify error messages use uniform "Error:" prefix.

**Acceptance Scenarios**:

1. **Given** `ConfigManager.find_and_load()` is called in `commands/query.py` and `cli/modes.py`, **When** the fix is applied, **Then** config is loaded successfully using the existing `find_config()` + `ConfigManager.load()` pattern.
2. **Given** path aliases are configured in `krag.toml`, **When** `krag query` displays sources, **Then** paths are shortened using the configured aliases.
3. **Given** CLI commands use `--json` (status, debug, index) or `--format` (query), **When** reviewed for consistency, **Then** a uniform approach is adopted.
4. **Given** a `ConnectionError` occurs in any CLI command, **When** the error is displayed, **Then** the prefix is uniformly `Error:` (not `Fatal:` in one command and `Error:` in others).
5. **Given** the `debug query` command, **When** reviewed, **Then** a `--mode` option is available (matching the underlying `DebugQueryRequest.mode` field).

---

### User Story 10 — Plugin registry API is robust and self-contained (Priority: P3)

A developer using the plugin registry does not need to know to call private methods in the right order. The extension map builds automatically and plugin metadata is accessible without full instantiation.

**Why this priority**: `_build_extension_map()` is a private method that external code (the indexer) must call explicitly after `discover_plugins()`. If forgotten, `get_handler_for_extension()` silently returns `None` for every extension. The `inspect.signature` check in `initialize_plugin()` is unnecessary overhead.

**Independent Test**: Call `discover_plugins()` followed by `get_handler_for_extension(".py")` without manually calling `_build_extension_map()`. Confirm it returns the correct handler.

**Acceptance Scenarios**:

1. **Given** `discover_plugins()` has been called, **When** `get_handler_for_extension(".py")` is called without any other setup, **Then** the correct handler is returned.
2. **Given** plugin initialisation, **When** `initialize_plugin()` is called, **Then** the `inspect.signature` check is removed (the base class contract guarantees the `context` parameter).
3. **Given** `IndexError` (Pydantic model in `schemas.py`) shadows Python's builtin, **When** the cleanup is complete, **Then** it is renamed to `IndexingFileError` or similar.

---

### Edge Cases

- Indexing directory changes from `/dir/a` to `/dir/b` (non-overlapping): previously indexed files in `/dir/a` must be correctly identified as deleted.
- Empty or corrupted metadata file: indexer must fall back to a fresh state without crashing.
- Index-status called concurrently as a running job finishes: the transition from `running` to `completed` must be atomic.
- `[embedding_code]` model file not present: indexer must fail with a clear actionable error, not silently fall back to single-model mode.
- Log rotation when no existing log file is present: must succeed without error.
- Query response is plain text with no markdown: rich rendering must not add spurious formatting.
- `krag` output is piped or redirected: rich markdown rendering must be suppressed (no ANSI codes in non-TTY output).
- Mode file hot-reload on every request: must not cause concurrent modification if two requests resolve modes simultaneously.
- `_index_job_cache` written from background thread and read from request threads: reads and writes must be protected or atomic.
- PID file write by two concurrent `kragd` start attempts: must not race (advisory lock or atomic write).
- `IndexingFailureCollector._failures` list appended from background thread: must be thread-safe (lock or queue).

---

## Requirements *(mandatory)*

### Functional Requirements

**Incremental indexing metadata (US1)**

- **FR-001**: When an indexing run completes, the saved metadata MUST include all files ever indexed — not just files processed in the current run — updated with the current run's results.
- **FR-002**: On a subsequent indexing run covering a different or broader directory, previously-indexed unchanged files MUST be classified as `unchanged` and not deleted and re-added to the vector store.
- **FR-003**: The metadata store MUST be the single source of truth for what is indexed; per-run state MUST be merged into the persistent store, not replace it.

**Index-status accuracy (US2)**

- **FR-004**: `GET /index/status` MUST return `status: running` whenever an indexing job is active, regardless of whether a previous completed job exists in the cache.
- **FR-005**: The active-indexing check MUST be evaluated before returning any cached results.

**Query / debug-query unification (US3)**

- **FR-006**: The `query` and `debug_query` service methods MUST share a single retrieval-and-synthesis code path; logic MUST NOT be duplicated between them.
- **FR-007**: The `--debug` flag MUST produce identical `answer` and `sources` to the non-debug run for the same query and mode.
- **FR-008**: Debug metadata (timing, routing, critic scores, vector spaces) MUST be collected and returned only when `include_debug` is requested.

**Code embedding in core (US4)**

- **FR-009**: A `[embedding_code]` configuration section MUST be supported in the krag core config file, specifying a code embedding model and its named vector space.
- **FR-010**: When `[embedding_code]` is configured, the indexer MUST embed code files using the code model and store them in the `code` named vector space.
- **FR-011**: The absence of `[embedding_code]` MUST preserve existing single-model behaviour with no breaking changes to existing configs or data.
- **FR-012**: Plugin-registered embedding models MUST continue to take precedence over the built-in `[embedding_code]` setting.

**Operational UX (US5)**

- **FR-013**: kragd MUST log a prominent startup banner when the process begins initialising.
- **FR-014**: kragd MUST log a prominent ready banner once the HTTP server is accepting requests.
- **FR-015**: kragd MUST log a prominent shutdown banner when shutdown is initiated.
- **FR-016**: kragd MUST support a `--rotate-logs` flag that archives the existing log file before starting a new one.
- **FR-017**: The CLI `query` command MUST render markdown in responses using rich formatting when stdout is an interactive terminal.

**Concurrency safety (US6)**

- **FR-018**: The query code path MUST NOT mutate shared state (`query_engine.llm_client`, `query_engine.critic`) on a singleton service instance. Per-request isolation MUST be guaranteed.
- **FR-019**: `_index_job_cache` and `_last_index_job` reads and writes MUST be protected against concurrent access from request-handler and background-indexing threads.
- **FR-020**: Mode file hot-reload (`load_user_modes()`) MUST NOT run on every request; it MUST be cached or debounced so concurrent requests do not race on the mode registry.
- **FR-021**: `IndexingFailureCollector._failures` MUST be thread-safe (e.g., guarded by a lock or using a thread-safe collection).

**Dead code and dependency cleanup (US7)**

- **FR-022**: The unused `kragd/routers/health.py` file MUST be removed.
- **FR-023**: The `llama-index` dependency MUST be removed from `pyproject.toml`.
- **FR-024**: The `tomli` dependency (with impossible Python version marker) MUST be removed from `pyproject.toml`.
- **FR-025**: The duplicate `DEFAULT_VECTOR_STORE_PATH` definition in `defaults.py` MUST be reduced to a single definition.
- **FR-026**: The stale `[project.optional-dependencies] dev` section MUST be removed (the active `[dependency-groups] dev` is the canonical source).

**Exception architecture (US8)**

- **FR-027**: Service-layer errors that map to specific HTTP status codes MUST use typed domain exceptions (e.g., `ServiceNotReadyError`, `IndexingInProgressError`) instead of `RuntimeError`.
- **FR-028**: The `app.py` exception handler MUST dispatch on exception type (`isinstance`), not string matching on `str(exc)`.
- **FR-029**: Silent `except Exception: pass` blocks in the indexer and service layer MUST be replaced with logged warnings that include context (file path, operation, error details).
- **FR-030**: `LexiconValidationError` and `EvalLoadError` MUST inherit from `KragError` to unify the exception hierarchy.

**CLI consistency (US9)**

- **FR-031**: `ConfigManager` MUST provide a `find_and_load()` class method (or callers MUST be updated to use `find_config()` + `load()`), so that path aliases and CLI mode discovery function correctly.
- **FR-032**: The `debug query` CLI command MUST accept a `--mode` option to match the underlying API.
- **FR-033**: Error message prefixes in CLI commands MUST be uniform (`Error:`) for connection failures across all commands.

**Plugin registry hardening (US10)**

- **FR-034**: `discover_plugins()` MUST automatically build the extension map as its final step; callers MUST NOT need to call `_build_extension_map()` separately.
- **FR-035**: The `inspect.signature` guard in `initialize_plugin()` MUST be removed; the base class contract guarantees the `context` parameter.
- **FR-036**: The `IndexError` Pydantic model in `schemas.py` MUST be renamed to avoid shadowing Python's builtin `IndexError`.

### Assumptions

- Metadata is stored as a single global `metadata.json` (not per-directory). The fix merges per-run results into this store rather than replacing it.
- Log rotation archives by renaming the existing log file with a timestamp suffix; it does not delete the old file.
- Rich markdown rendering uses the existing `rich` library dependency; no new dependencies are required.
- Rich markdown is suppressed when stdout is not a TTY to avoid polluting piped output with ANSI escape codes.
- The default code embedding model for `[embedding_code]` is `jinaai/jina-embeddings-v2-base-code`, matching what `krag-plugin-code` currently uses, but any model path is configurable.
- Per-request query isolation is achieved by passing LLM client and critic as parameters into the query method (or creating lightweight per-request copies), rather than adding global locks that would serialize queries.
- The concurrency fix for `_index_job_cache` uses a threading lock already present (`_indexing_lock`) rather than introducing a new synchronisation primitive.
- Mode file hot-reload is debounced with a file-modification-time check; modes are only re-parsed from disk when the modes directory mtime has changed.
- The `find_and_load()` fix reuses the existing `krag_cli.config.find_config()` + `ConfigManager.load()` rather than duplicating config discovery logic.
- Removing `llama-index` from dependencies does not affect any runtime feature — the library is confirmed to have zero imports in the codebase.
- Removing the stale `[project.optional-dependencies] dev` does not affect the development workflow — the active `[dependency-groups] dev` section is what `uv` and modern tooling use.
- `mypy.ini` overrides are documented technical debt from Sprint 006 and are not addressed in this sprint; they will be revisited when the mypy strict pass is completed.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Re-indexing a parent directory of a previously-indexed directory produces zero deletions and zero re-additions for unchanged files; `files_skipped_unchanged` equals the count of previously-indexed unmodified files.
- **SC-002**: `krag index-status` returns `status: running` within one second of a new indexing job starting, even when a previous completed result is cached.
- **SC-003**: Running the same query with and without `--debug` produces identical `answer` and `sources` fields 100% of the time (for the same mode and index state).
- **SC-004**: A fresh krag install with `[embedding_code]` in config (no extra plugins) successfully indexes a mixed codebase and produces both `text` and `code` named vector spaces in the vector store.
- **SC-005**: kragd startup, ready, and shutdown events are each identifiable in the log file by a single `grep` producing exactly one matching line per event.
- **SC-006**: A query response containing a fenced code block renders with visible syntax highlighting in an interactive terminal session.
- **SC-007**: 50 concurrent queries across different modes produce zero errors and each response's debug metadata matches its requested mode — no cross-contamination of LLM client or critic configuration.
- **SC-008**: `pip install krag` no longer pulls `llama-index` or `tomli` as transitive dependencies; the dead `health.py` router file does not exist; `grep -r 'DEFAULT_VECTOR_STORE_PATH' src/krag/config/defaults.py` returns exactly one match.
- **SC-009**: The `app.py` exception handler contains zero string-matching logic (`"in msg"` patterns); all HTTP status code dispatch is via `isinstance` checks on domain exception types.
- **SC-010**: `krag query` with configured path aliases displays shortened paths in source references (path alias feature is functional, not silently broken).
- **SC-011**: After calling `discover_plugins()`, `get_handler_for_extension(".py")` returns the code plugin handler without any additional setup calls.
