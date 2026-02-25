# Tasks: Infrastructure Improvements & Polish

**Input**: Design documents from `/specs/010-infrastructure-polish/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md

**Tests**: Included — TDD is non-negotiable per project constitution.

**Organization**: Tasks are grouped by user story. Implementation order follows the quickstart.md recommendation: US7 → US8 → US1 → US2 → US10 → US9 → US3 → US6 → US4 → US5 (dependency-aware, not strict priority order).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify environment and branch readiness

- [x] T001 Verify development environment: run `uv sync --group dev && uv run pytest` to confirm green baseline

---

## Phase 2: US7 — Dead Code & Dependency Cleanup (Priority: P2)

**Goal**: Remove dead files, unused dependencies, and duplicate definitions to reduce noise before substantive changes.

**Independent Test**: `test ! -f src/kragd/routers/health.py && grep -c "llama-index" pyproject.toml` returns 0; `grep -c DEFAULT_VECTOR_STORE_PATH src/krag/config/defaults.py` returns 1; full test suite passes.

### Implementation for User Story 7

- [x] T002 [P] [US7] Delete dead router file src/kragd/routers/health.py and remove any imports referencing it
- [x] T003 [P] [US7] Remove `llama-index>=0.9.0` dependency from pyproject.toml
- [x] T004 [P] [US7] Remove `tomli>=2.0.0 ; python_version < '3.11'` dependency from pyproject.toml (impossible marker)
- [x] T005 [P] [US7] Remove stale `[project.optional-dependencies] dev` section from pyproject.toml (keep `[dependency-groups] dev`)
- [x] T006 [P] [US7] Remove duplicate `DEFAULT_VECTOR_STORE_PATH` definition (keep first at ~L114) in src/krag/config/defaults.py
- [x] T007 [US7] Run `uv sync --group dev && uv run ruff check . && uv run pytest` to verify zero regressions from cleanup

**Checkpoint**: Codebase is cleaner — dead code and unused deps removed. All tests pass.

---

## Phase 3: US8 — Exception Architecture (Priority: P2)

**Goal**: Replace string-matching exception dispatch with typed domain exceptions; replace silent except blocks with logged warnings.

**Independent Test**: Raise each domain exception from the service layer and confirm the correct HTTP status code is returned via `isinstance` checks. Trigger formerly-silent except blocks and confirm errors are logged.

### Tests for User Story 8

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [P] [US8] Write unit tests for domain exception classes and hierarchy in tests/unit/test_domain_exceptions.py
- [X] T009 [P] [US8] Write contract tests for HTTP error code dispatch (isinstance-based) in tests/contract/test_api_error_codes.py

### Implementation for User Story 8

- [X] T010 [US8] Add ServiceNotReadyError, IndexingInProgressError, ResourceNotConfiguredError to src/krag/models/exceptions.py (all inherit KragError)
- [X] T011 [P] [US8] Fix LexiconValidationError to inherit from KragError in src/krag/lexicon/lexicon_store.py
- [X] T012 [P] [US8] Fix EvalLoadError to inherit from KragError in src/krag/evaluation/loader.py
- [X] T013 [US8] Replace all 9 RuntimeError raises with domain exceptions in src/kragd/service.py
- [X] T014 [US8] Replace string-matching exception handler with isinstance-based dispatch in src/kragd/app.py (per contracts/api-changes.md)
- [X] T015 [US8] Replace silent `except Exception: pass` blocks with logged warnings in src/krag/orchestration/indexer.py and src/kragd/service.py (~10 locations)

**Checkpoint**: Exception architecture is type-safe. All HTTP status codes dispatched by `isinstance`, no string matching. All formerly-silent excepts now log warnings.

---

## Phase 4: US1 — Incremental Indexing Metadata Merge (Priority: P1) 🎯

**Goal**: Fix metadata loss when re-indexing across directory changes. Previously-indexed unchanged files must be preserved, not deleted and re-added.

**Independent Test**: Index a directory, then index a parent directory. Confirm files from the first run appear as `unchanged`, no deletions logged, vector count stable.

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US1] Write unit tests for metadata merge (directory changes, prune stale) in tests/unit/test_metadata_merge.py
- [X] T017 [P] [US1] Write integration test for metadata round-trip with vector store in tests/integration/test_metadata_roundtrip.py

### Implementation for User Story 1

- [X] T018 [US1] Remove directory-path filter from `_load_metadata()` (~L353–362) in src/krag/orchestration/indexer.py — load all entries unconditionally
- [X] T019 [US1] Preserve previously-indexed entries in `index_full()` — merge current run results into loaded metadata, retain untouched entries in src/krag/orchestration/indexer.py
- [X] T020 [US1] Add stale-entry pruning to `_save_metadata()` — remove entries where `file_path` no longer exists on disk in src/krag/orchestration/indexer.py

**Checkpoint**: Incremental indexing across directory changes preserves unchanged files. `files_skipped_unchanged` reflects correct count.

---

## Phase 5: US2 — Index-Status Accuracy (Priority: P1)

**Goal**: Fix stale index-status by checking active indexing state before returning cached results.

**Independent Test**: Start a long indexing run, immediately poll `krag index-status`, and confirm `status: running`.

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T021 [P] [US2] Write unit tests for index-status ordering (running vs cached) in tests/unit/test_index_status_accuracy.py

### Implementation for User Story 2

- [X] T022 [US2] Reorder `get_index_status()` to check `self._indexing` before `self._index_job_cache` in src/kragd/service.py (~L1038–1082)

**Checkpoint**: `index-status` returns `status: running` within 1 second of a new indexing job starting.

---

## Phase 6: US10 — Plugin Registry Hardening (Priority: P3)

**Goal**: Make `discover_plugins()` self-contained, remove unnecessary guards, fix schema naming conflict.

**Independent Test**: Call `discover_plugins()` then `get_handler_for_extension(".py")` — correct handler returned without manual `_build_extension_map()`.

### Tests for User Story 10

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T023 [P] [US10] Write unit tests for auto extension map build after discover_plugins() in tests/unit/test_plugin_registry.py

### Implementation for User Story 10

- [X] T024 [US10] Auto-call `_build_extension_map()` at end of `discover_plugins()` in src/krag/plugins/registry.py
- [X] T025 [US10] Remove explicit `_build_extension_map()` call from caller in src/krag/orchestration/indexer.py (~L151)
- [X] T026 [US10] Remove `inspect.signature` guard from `initialize_plugin()` in src/krag/plugins/loader.py (~L184–191)
- [X] T027 [US10] Rename `IndexError` Pydantic model to `IndexingFileError` in src/kragd/schemas.py and update all references in src/kragd/service.py

**Checkpoint**: Plugin registry API is self-contained. Extension map builds automatically. No builtin shadowing.

---

## Phase 7: US9 — CLI Consistency (Priority: P2)

**Goal**: Fix broken `find_and_load()`, add missing `--mode` to debug query, unify error formatting.

**Independent Test**: Verify `_get_path_aliases()` returns real aliases from config. Verify `--mode` works on debug query. Verify uniform "Error:" prefix.

### Implementation for User Story 9

- [X] T028 [US9] Add `find_and_load()` class method to ConfigManager in src/krag/config/settings.py (wraps find_config() + load())
- [X] T029 [US9] Fix path alias resolution caller in src/krag_cli/commands/query.py (~L101) to use find_and_load()
- [X] T030 [US9] Fix mode discovery caller in src/krag/cli/modes.py (~L38) to use find_and_load()
- [X] T031 [US9] Add `--mode` option to `debug_query_command` in src/krag_cli/commands/debug.py
- [X] T032 [US9] Change `[red]Fatal:[/red]` to `[red]Error:[/red]` in src/krag_cli/commands/index.py (~L103)
- [X] T033 [P] [US9] Standardize `--json` flag naming (use `output_json: bool = typer.Option(False, "--json")`) across status, debug, and index CLI commands

**Checkpoint**: Path aliases functional, `--mode` available on debug query, error messages uniform.

---

## Phase 8: US3 — Query/Debug Unification (Priority: P2)

**Goal**: Merge `query()` and `debug_query()` into a single code path controlled by `include_debug` parameter.

**Independent Test**: Run same query with and without `--debug`. Confirm identical `answer` and `sources`; debug response additionally has populated `debug` metadata.

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T034 [P] [US3] Write unit tests for unified query path (identical results, debug metadata population) in tests/unit/test_query_debug_unified.py

### Implementation for User Story 3

- [X] T035 [US3] Add `include_debug: bool = False` parameter to `query()` method in src/kragd/service.py
- [X] T036 [US3] Merge `debug_query()` retrieval/synthesis logic into `query()`, make `debug_query()` a thin wrapper calling `self.query(..., include_debug=True)` in src/kragd/service.py
- [X] T037 [US3] Update debug router to call `service.query(include_debug=True)` in src/kragd/routers/debug.py

**Checkpoint**: Single code path for query and debug-query. Identical results guaranteed. Debug metadata populated only when requested.

---

## Phase 9: US6 — Concurrency Safety (Priority: P1)

**Goal**: Eliminate shared-state mutation in query path; protect index cache and mode registry from race conditions; make failure collector thread-safe.

**Independent Test**: Issue 50 concurrent queries across 5 different modes. Zero errors, each response's `debug.llm_used` matches its requested mode.

### Tests for User Story 6

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T038 [P] [US6] Write unit tests for concurrent query isolation (multi-threaded, different modes) in tests/unit/test_concurrency_safety.py

### Implementation for User Story 6

- [X] T039 [US6] Add `llm_client` and `critic` keyword arguments to `QueryEngine.query()` (pass-as-parameter pattern) in src/krag/ synthesis module
- [X] T040 [US6] Update `query()` in service.py to construct per-request LLM client and RelevanceCritic, pass as parameters instead of mutating shared state in src/kragd/service.py
- [X] T041 [US6] Wrap `_index_job_cache` and `_last_index_job` reads/writes with `self._indexing_lock` in src/kragd/service.py
- [X] T042 [US6] Add mtime-based TTL cache (5s interval, `Lock.acquire(blocking=False)`) for mode hot-reload in `_resolve_mode()` in src/kragd/service.py
- [X] T043 [US6] Add `threading.Lock` to `IndexingFailureCollector` guarding all `_failures` access in src/krag/plugins/failures.py

**Checkpoint**: Concurrent queries are isolated. No shared-state mutation. Index cache, mode registry, and failure collector are thread-safe.

---

## Phase 10: US4 — Code Embedding Config (Priority: P2)

**Goal**: Enable code-specific embedding model via `[embedding_code]` TOML section in krag core config, without requiring a plugin.

**Independent Test**: Add `[embedding_code]` to config, index a mixed codebase, confirm both `text` and `code` named vector spaces in the vector store.

### Tests for User Story 4

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T044 [P] [US4] Write unit tests for `[embedding_code]` config parsing and field validation in tests/unit/test_embedding_code_config.py

### Implementation for User Story 4

- [X] T045 [US4] Add `embedding_code_model: str | None = None` field to Configuration model in src/krag/models/configuration.py
- [X] T046 [US4] Parse `[embedding_code]` TOML section in `_load_toml()` in src/krag/config/settings.py
- [X] T047 [US4] Wire `embedding_code_model` into `EmbeddingOrchestrator.additional_models` at construction sites in src/krag/cli/pipeline.py, src/kragd/service.py, and src/krag/orchestration/indexer.py

**Checkpoint**: Code embedding configurable in core config. Plugin precedence preserved. Single-model backward compatibility maintained.

---

## Phase 11: US5 — Operational UX (Priority: P3)

**Goal**: Add log bookmarks for lifecycle events, log rotation, and rich markdown rendering for query responses.

**Independent Test**: Start kragd — `KRAGD STARTING` and `KRAGD READY` in log. Stop — `KRAGD SHUTTING DOWN` in log. `--rotate-logs` archives old log. Query with code block renders with syntax highlighting.

### Implementation for User Story 5

- [X] T048 [P] [US5] Add startup/ready/shutdown log banners to kragd lifecycle in src/kragd/lifecycle.py
- [X] T049 [P] [US5] Implement `--rotate-logs` flag for kragd in src/kragd/__main__.py
- [X] T050 [US5] Add rich markdown rendering for query responses in src/krag_cli/commands/query.py (using existing `rich` dependency)
- [X] T051 [US5] Suppress rich formatting when stdout is not a TTY (no ANSI codes in piped output) in src/krag_cli/main.py

**Checkpoint**: Lifecycle events visible in log. Log rotation works. Markdown renders with formatting in interactive terminals.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all user stories

- [ ] T052 [P] Run quickstart.md verification commands for all user stories
- [ ] T053 [P] Run full pre-commit validation: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
- [ ] T054 Update docs/ if any public API behaviour changed (e.g., new exception types, config sections)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US7 (Phase 2)**: Depends on Setup — simplest changes, reduces noise for subsequent work
- **US8 (Phase 3)**: Depends on Setup — creates exception types used by US2, US3, US6, US9
- **US1 (Phase 4)**: Depends on US8 (uses logged warnings from silent except fix)
- **US2 (Phase 5)**: Depends on US8 (uses domain exceptions for status responses)
- **US10 (Phase 6)**: Depends on Setup only — self-contained
- **US9 (Phase 7)**: Depends on US8 (uniform error handling)
- **US3 (Phase 8)**: Depends on US8 — unified path should use domain exceptions
- **US6 (Phase 9)**: Depends on US3 — concurrency fix is simpler with unified query path (one code path to fix, not two)
- **US4 (Phase 10)**: Depends on US10 — builds on plugin registry fixes
- **US5 (Phase 11)**: No dependencies on other stories — lowest priority, can be done anytime
- **Polish (Phase 12)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Setup ──┬── US7 (dead code)
        ├── US8 (exceptions) ──┬── US1 (metadata) ── independent
        │                      ├── US2 (status) ── independent
        │                      ├── US9 (CLI) ── independent
        │                      └── US3 (query unify) ── US6 (concurrency)
        ├── US10 (plugin) ── US4 (code embedding)
        └── US5 (operational UX) ── independent
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Core logic changes before integration/wiring
- Run `uv run pytest` after each story to verify no regressions
- Commit after each completed story

### Parallel Opportunities

- **Phase 2 (US7)**: T002–T006 can all run in parallel (different files)
- **Phase 3 (US8)**: T008+T009 in parallel (test files); T011+T012 in parallel (independent hierarchy fixes)
- **Phase 4 (US1)**: T016+T017 in parallel (test files)
- **Phase 6 (US10)**: T023 standalone; T024+T026 potentially parallel (different files)
- **Phase 7 (US9)**: T033 parallel with earlier US9 tasks (different files)
- **After US8 completes**: US1, US2, US9 can proceed in parallel (independent stories)
- **After US3 completes**: US6 can start immediately
- **US5 can start anytime**: No dependencies on other stories

---

## Parallel Example: User Story 8 (Exception Architecture)

```bash
# Launch both test files in parallel:
Task: T008 "Write unit tests for domain exceptions in tests/unit/test_domain_exceptions.py"
Task: T009 "Write contract tests for HTTP error codes in tests/contract/test_api_error_codes.py"

# Then implement exception classes:
Task: T010 "Add domain exception classes to src/krag/models/exceptions.py"

# Launch hierarchy fixes in parallel:
Task: T011 "Fix LexiconValidationError in src/krag/lexicon/lexicon_store.py"
Task: T012 "Fix EvalLoadError in src/krag/evaluation/loader.py"

# Then sequential service/app changes:
Task: T013 "Replace RuntimeError raises in src/kragd/service.py"
Task: T014 "Replace string-matching handler in src/kragd/app.py"
Task: T015 "Replace silent except blocks in indexer.py and service.py"
```

## Parallel Example: User Story 1 (Metadata Merge)

```bash
# Launch both test files in parallel:
Task: T016 "Write unit tests in tests/unit/test_metadata_merge.py"
Task: T017 "Write integration test in tests/integration/test_metadata_roundtrip.py"

# Then sequential implementation (same file, depends on prior steps):
Task: T018 "Remove directory-path filter from _load_metadata()"
Task: T019 "Preserve previously-indexed entries in index_full()"
Task: T020 "Add stale-entry pruning to _save_metadata()"
```

---

## Implementation Strategy

### MVP First (P1 Correctness Bugs)

1. Complete Phase 1: Setup
2. Complete Phase 2: US7 (dead code — reduces noise)
3. Complete Phase 3: US8 (exception types — foundational)
4. Complete Phase 4: US1 (metadata merge — P1 correctness)
5. Complete Phase 5: US2 (index-status — P1 correctness)
6. **STOP and VALIDATE**: Core correctness bugs fixed, test suite green
7. Assess remaining capacity for P2/P3 stories

### Incremental Delivery

1. US7 + US8 → Foundation ready (exception types, clean codebase)
2. US1 → Metadata merge works → Indexing is reliable
3. US2 → Status is accurate → Monitoring is trustworthy
4. US10 → Plugin API robust → Extension ecosystem reliable
5. US9 → CLI consistent → User experience uniform
6. US3 → Query unified → Debug is trustworthy
7. US6 → Concurrency safe → Multi-user/pipeline ready
8. US4 → Code embedding in core → No plugin needed for code search
9. US5 → Operational polish → Production-ready logging and output
10. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Implementation order differs from priority order due to dependencies (US7/US8 first despite being P2)
- No new runtime dependencies — all work uses existing stack
- Thread safety uses `threading.Lock` (not `asyncio.Lock`) — indexing runs in `threading.Thread`
- Pre-commit validation: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
