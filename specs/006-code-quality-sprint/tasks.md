# Tasks: Code Quality Sprint

**Input**: Design documents from `/specs/006-code-quality-sprint/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths included in each task description

---

## Phase 1: Setup

**Purpose**: No project initialization needed — existing codebase. This phase handles the single foundational fix that unblocks all other work.

- [x] T001 Remove `le=1.0` upper-bound constraint from `score` field and update description to "Relevance score (higher is better)" in `src/krag/models/query_result.py` (FR-006)

**Checkpoint**: Score validation no longer rejects RRF or dot-product scores. All existing tests still pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Consolidate shared utilities that multiple user stories depend on. MUST complete before user-story phases.

**⚠️ CRITICAL**: US1 needs `get_free_vram` consolidated before LLM pool fix; US4 needs it for DRY.

- [x] T002 Add `get_free_vram(device: int = 0) -> int | None` function to `src/krag/cli/gpu.py` using `torch.cuda.mem_get_info()`, catching `(ImportError, RuntimeError, ValueError)` (FR-014, contract: gpu-vram.md)
- [x] T003 [P] Add `get_log_file_path() -> Path` helper to `src/krag/config/logging.py` that returns `get_krag_state_dir() / "logs" / "krag.log"`

**Checkpoint**: Shared utilities ready. No behavior changes yet — old callsites still use inline implementations.

---

## Phase 3: User Story 1 — Correct Retrieval Results (Priority: P1) 🎯 MVP

**Goal**: Fix all 6 correctness bugs so multi-model retrieval returns accurate, correctly-ranked results.

**Independent Test**: Run `krag eval tests/fixtures/eval_queries.toml` → 3/3 pass rate. Verify code LLM routing fires for code queries.

### Implementation for User Story 1

- [x] T004 [P] [US1] Fix LLM routing in `src/krag/synthesis/llm_pool.py`: change `_analyze_chunk_composition()` to check `c.file_type == "code"` OR `Path(c.file_path).suffix in CODE_EXTENSIONS` instead of only `c.file_type in CODE_EXTENSIONS` (FR-001, research: R-04)
- [x] T005 [P] [US1] Fix empty `file_path` crash in `src/krag/retrieval/retriever.py`: wrap per-result `QueryResult` construction in try/except, skip and log warning for invalid payloads instead of crashing entire retrieval (FR-005, contract: retriever-boosts.md `_payload_to_query_result`)
- [x] T006 [P] [US1] Extract `_payload_to_query_result(point_id, score, rank, payload) -> QueryResult | None` helper in `src/krag/retrieval/retriever.py` to deduplicate result construction from `_results_to_query_results` and `_multi_model_retrieve` (FR-005, contract: retriever-boosts.md)
- [x] T007 [US1] Add score-range-aware boost weights in `src/krag/retrieval/retriever.py`: add `_KEYWORD_BOOST_WEIGHT_RRF = 0.002` and `_METADATA_BOOST_WEIGHT_RRF = 0.003` constants; modify `_keyword_boost` and `_metadata_boost` to accept `is_rrf` flag and use appropriate weights (FR-003, research: R-03, contract: retriever-boosts.md)
- [x] T008 [US1] Thread `is_rrf` flag through `src/krag/retrieval/retriever.py`: in `_multi_model_retrieve` pass `is_rrf=True` to boost functions; in single-model `search` pass `is_rrf=False` (FR-003)
- [x] T009 [P] [US1] Fix stale chunker variable in `src/krag/orchestration/indexer.py`: add `chunker = None` at the start of each per-file loop iteration in both `index_full` (~L500) and `index_incremental` (~L830) (FR-004)
- [x] T010 [US1] Fix stale vectors in incremental indexing in `src/krag/orchestration/indexer.py`: before re-indexing modified files, call `self.vector_store.delete_by_filter({"file_path": str(change.file_path)})` to remove old vectors (FR-002)

**Checkpoint**: All 6 correctness bugs fixed. Eval should restore to 3/3. Existing tests pass. LLM routing fires for code-heavy results.

---

## Phase 4: User Story 4 + User Story 2 — DRY Codebase & Consistent CLI (Priority: P2)

**Goal**: Extract shared CLI pipeline factory, eliminating ~65 lines of duplication and unifying XDG config resolution, vector-store pre-check, LLM routing, and top_k defaults across `query` and `eval` commands.

**Independent Test**: `grep -c 'EmbeddingOrchestrator(' src/krag/cli/*.py` returns 1. `grep -c 'LLMClient(' src/krag/cli/*.py` returns 1. Set `$XDG_CONFIG_HOME` to non-default → all commands find config.

**Note**: US4 (DRY) and US2 (CLI Consistency) are combined because the pipeline extraction (US4/FR-012) is the mechanism that delivers CLI consistency (US2/FR-007–011).

### Implementation for User Story 4 + User Story 2

- [x] T011 [US4] Create `src/krag/cli/pipeline.py` with `QueryPipeline` frozen dataclass and `resolve_config_path()` function using `get_krag_config_dir()` for XDG-aware config discovery with TOML/YAML fallback (FR-012, FR-007, contract: pipeline.md)
- [x] T012 [US4] Implement `build_query_pipeline(config_path, top_k, preset) -> QueryPipeline` in `src/krag/cli/pipeline.py`: config loading, vector-store pre-check with user-friendly error, EmbeddingGenerator, EmbeddingOrchestrator with plugin registration, QdrantVectorStore, LLMClient, LLMPool (if multi-model), effective top_k resolution (CLI > config > default 5), QueryEngine construction (FR-012, FR-007, FR-008, FR-009, FR-010, contract: pipeline.md)
- [x] T013 [US2] Refactor `src/krag/cli/query.py` to use `build_query_pipeline()`: remove duplicated config loading (L82–96), EmbeddingGenerator init (L118–121), EmbeddingOrchestrator setup (L124–136), vector store init (L139–145), LLMClient construction (L165–175), QueryEngine construction (L187–196); replace with single `pipeline = build_query_pipeline(...)` call (FR-012, FR-007–011)
- [x] T014 [US2] Refactor `src/krag/cli/eval.py` to use `build_query_pipeline()`: remove duplicated config loading (L73–79), EmbeddingGenerator init (L88–91), EmbeddingOrchestrator setup (L94–106), vector store init (L109–115), LLMClient construction (L117–127), QueryEngine construction (L132–142); replace with single `pipeline = build_query_pipeline(...)` call; now gets LLMPool routing for free (FR-012, FR-007–011, FR-009)
- [x] T015 [P] [US4] Replace inline `_get_free_vram()` in `src/krag/embeddings/orchestrator.py` (~L23–35) with import from `krag.cli.gpu.get_free_vram` (FR-014)
- [x] T016 [P] [US4] Replace inline `_get_free_vram()` in `src/krag/synthesis/llm_pool.py` (~L75–83) with import from `krag.cli.gpu.get_free_vram` (FR-014)
- [x] T017 [P] [US4] Fix `Any` type annotations: change `vector_store: Any` to `VectorStore` in `src/krag/orchestration/query_engine.py`; change `vector_store: Any` and `embedding_orchestrator: Any` to proper types in `src/krag/retrieval/retriever.py` (FR-015)

**Checkpoint**: CLI pipeline deduplicated. `query` and `eval` share config resolution, vector-store check, LLM routing, and top_k defaults. VRAM function consolidated. Type safety improved. All existing tests pass.

---

## Phase 5: User Story 5 — Robust Indexer (Priority: P2)

**Goal**: Extract shared `_process_file()` method, fixing chunker leakage and plugin name divergence across full/incremental indexing paths.

**Independent Test**: Index a file, modify it, re-index incrementally, query for new content — old content should not appear. Plugin chunker does not leak across file boundaries.

**Note**: Depends on Phase 3 (T009, T010 fix the bugs in‐place) — this phase extracts the shared method and ensures both paths use it.

### Implementation for User Story 5

- [x] T018 [US5] Create `FileProcessingResult` dataclass in `src/krag/orchestration/indexer.py` with fields: `payloads: list[dict]`, `chunk_count: int`, `handler_name: str | None`, `error: str | None` and `success` property (contract: file-processor.md)
- [x] T019 [US5] Extract `_process_file(self, file_meta, plugin_handler) -> FileProcessingResult` method in `src/krag/orchestration/indexer.py`: consolidate per-file logic from `index_full` (~L450–620) — text extraction, chunking (with `chunker = None` reset), embedding, payload building, consistent plugin name resolution via `getattr(handler, "name", handler.__class__.__name__)` (FR-013, FR-004, FR-012, contract: file-processor.md)
- [x] T020 [US5] Refactor `index_full()` in `src/krag/orchestration/indexer.py` to call `_process_file()` instead of inlining per-file logic; keep orchestration (file discovery, progress, metadata save, upsert) in `index_full` (FR-013)
- [x] T021 [US5] Refactor `index_incremental()` in `src/krag/orchestration/indexer.py` to call `_process_file()` instead of inlining per-file logic; keep incremental-specific logic (change detection, delete-before-insert from T010, metadata diff) in `index_incremental` (FR-013, FR-002)

**Checkpoint**: `index_full` and `index_incremental` share a single `_process_file()`. No duplicated per-file logic. Chunker state reset and plugin name resolution are consistent. All existing tests pass.

---

## Phase 6: User Story 3 — Clean, Actionable Logs (Priority: P3)

**Goal**: Reduce upsert log noise to ≤10 entries per operation. Add `krag log rotate`/`clear`/`path` CLI commands.

**Independent Test**: `krag index --full && grep -c 'Upsert' ~/.local/state/krag/logs/krag.log` returns ≤10. `krag log rotate` archives log. `krag log clear` truncates log.

### Implementation for User Story 3

- [x] T022 [US3] Reduce upsert log noise in `src/krag/storage/qdrant_impl.py`: change per-batch `logger.info("Upserted N vectors")` to `logger.debug()`; add single `logger.info("Storing N vectors in M batches")` before loop and `logger.info("Stored N vectors successfully")` after loop completes (FR-016)
- [x] T023 [US3] Create `src/krag/cli/log.py` with Typer subcommand group: implement `rotate()` (shift backups krag.log→krag.log.1, max 5), `clear()` (truncate to zero), and `path()` (print log path with exists/not-found suffix) commands using `get_log_file_path()` from T003 (FR-017, FR-018, contract: log-cli.md)
- [x] T024 [US3] Register `log` subcommand group in `src/krag/cli/main.py`: add `app.add_typer(log_app, name="log")` import from `cli/log.py` (FR-017, FR-018)

**Checkpoint**: Upsert logging reduced from ~70 to ≤3 INFO entries. `krag log rotate`, `krag log clear`, `krag log path` all functional. All existing tests pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Dead code removal, import cleanup, design improvements, and final verification.

- [x] T025 [P] Remove dead function `_display_sources_only()` (~55 lines, L406–461) from `src/krag/cli/query.py` (FR-019)
- [x] T026 [P] Use `ScoredPointLike` protocol in `reciprocal_rank_fusion()` signature in `src/krag/retrieval/rrf.py`: change `result_lists: list[list[Any]]` to `result_lists: list[list[ScoredPointLike]]` (FR-019, research: R-09)
- [x] T027 [P] Remove `__del__` method from `IndexingOrchestrator` in `src/krag/orchestration/indexer.py` (~L234–236); context manager `__enter__`/`__exit__` already handles cleanup (FR-020)
- [x] T028 [P] Fix redundant imports in `src/krag/orchestration/indexer.py`: move `import json` to module-level; remove duplicate `from datetime import datetime` inside `_load_metadata` (~L314) (FR-021)
- [x] T029 [P] Remove dimension equality check in `src/krag/embeddings/orchestrator.py` (~L118–124) — Qdrant supports different dimensions per named vector space natively (FR-022)
- [x] T030 [P] Document `"text"` vector space invariant: add docstring comment in `src/krag/storage/qdrant_impl.py` at the `search()` fallback (~L268–271) explaining that `"text"` is the default vector space convention (research: R-05)
- [x] T031 [P] Unify keyword extraction in `src/krag/retrieval/retriever.py`: align `_metadata_boost` min-length (currently 2) with `_keyword_boost` min-length (currently 3); use consistent stop-word filtering in both
- [x] T032 Add integration test for named-vector + RRF pipeline in `tests/integration/test_named_vector_query_pipeline.py`: index sample docs with multi-model mock embeddings, query via RRF, verify expected sources in top-k results (research: R-10)
- [x] T033 Run full pre-commit validation: `uv run ruff format . && uv run ruff check --fix . && uv run pytest` — all 800+ tests must pass with zero regressions (SC-002)
- [ ] T034 Run eval suite: `krag eval tests/fixtures/eval_queries.toml` — verify 3/3 pass rate restored (SC-001) *(requires indexed corpus and LLM models)*
- [ ] T035 Run quickstart.md validation: execute all validation commands from `specs/006-code-quality-sprint/quickstart.md` to verify measurable outcomes SC-001 through SC-008 *(requires live environment)*

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Can start in parallel with Phase 1 (different files)
- **Phase 3 (US1 — Correctness)**: Depends on Phase 1 (T001 score validation) for boost weight changes
- **Phase 4 (US4+US2 — DRY+CLI)**: Depends on Phase 2 (T002 VRAM util) and Phase 3 completion (correctness must be fixed before refactoring around it)
- **Phase 5 (US5 — Indexer)**: Depends on Phase 3 (T009, T010 fix bugs that `_process_file` must incorporate) and Phase 4 (T015/T016 VRAM consolidation)
- **Phase 6 (US3 — Logging)**: Depends on Phase 2 (T003 log path helper). Can run in parallel with Phase 4/5.
- **Phase 7 (Polish)**: Depends on all user-story phases completion

### User Story Dependencies

- **US1 (P1)**: Phase 1 only — no dependencies on other stories
- **US4+US2 (P2)**: Phase 2 + US1 correctness fixes must be stable before refactoring
- **US5 (P2)**: Phase 3 (US1 bug fixes in indexer) + Phase 4 (`_get_free_vram` consolidation)
- **US3 (P3)**: Phase 2 only — independent of other stories

### Within Each User Story

- Correctness fixes (Phase 3): T004–T006 are parallel (different functions/files); T007→T008 are sequential (constants then threading); T009–T010 are parallel with each other
- Pipeline extraction (Phase 4): T011→T012 sequential (types then factory); T013, T014 sequential (query then eval, to validate incrementally); T015–T017 parallel (different files)
- Indexer extraction (Phase 5): T018→T019→T020→T021 sequential (dataclass → extract → refactor full → refactor incremental)
- Logging (Phase 6): T022 parallel with T023–T024 (different files)
- Polish (Phase 7): T025–T031 all parallel (different files); T032–T035 sequential (test → validate → verify)

### Parallel Opportunities

```
Phase 1: T001
Phase 2: T002 ∥ T003    (parallel — different files)
Phase 3: T004 ∥ T005 ∥ T006 ∥ T009   (parallel — different files/functions)
         T007 → T008                   (sequential — same file, dependent)
         T010                          (parallel with T007 — different location in indexer)
Phase 4: T011 → T012 → T013 → T014    (sequential — build pipeline incrementally)
         T015 ∥ T016 ∥ T017           (parallel after T012 — different files)
Phase 5: T018 → T019 → T020 → T021    (sequential — build on each step)
Phase 6: T022 ∥ T023                   (parallel — different files)
         T023 → T024                   (sequential — create module then register)
Phase 7: T025 ∥ T026 ∥ T027 ∥ T028 ∥ T029 ∥ T030 ∥ T031  (all parallel)
         T032 → T033 → T034 → T035    (sequential — test → validate → verify)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Score validation fix (T001)
2. Complete Phase 2: Shared utilities (T002, T003)
3. Complete Phase 3: All 6 correctness bugs (T004–T010)
4. **STOP and VALIDATE**: Run eval suite → expect 3/3 restored
5. Commit and verify — correctness is the highest-value deliverable

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1) → Correctness restored → **Primary value delivered**
3. Phase 4 (US4+US2) → DRY + CLI consistency → Code maintainability improved
4. Phase 5 (US5) → Indexer robustness → Incremental indexing reliable
5. Phase 6 (US3) → Logging improvements → Debug experience improved
6. Phase 7 → Polish → Production-ready quality

Each phase can be committed, tested, and validated independently.

---

## Notes

- All tasks reference specific file paths and line numbers from the codebase analysis
- [P] tasks operate on different files and have no mutual dependencies
- The spec does not request TDD — tests are included only for new functionality and final validation
- Total: 35 tasks across 7 phases covering all 22 functional requirements
- Pre-commit validation (ruff format + ruff check + pytest) required before final commit per constitution
