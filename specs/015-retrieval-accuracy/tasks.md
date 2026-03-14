# Tasks: Debug Metadata Accuracy & Retrieval Completeness

**Input**: Design documents from `/specs/015-retrieval-accuracy/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required — TDD is NON-NEGOTIABLE per project constitution. Tests are written first and must FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify project state and confirm baseline

- [x] T001 Verify branch `015-retrieval-accuracy`, run `uv sync`, confirm existing tests pass with `uv run pytest`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No new foundational infrastructure required

This is an existing mature project with all infrastructure in place (FastAPI service layer, Qdrant storage, embedding orchestrator, pytest/ruff/mypy tooling, CI pipeline). The Phase 1 setup confirmation serves as the foundation gate.

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Accurate per-collection result counts in debug output (Priority: P1) 🎯 MVP

**Goal**: Fix `_multi_collection_retrieve()` so `per_space_result_counts` in debug output shows per-collection keys (e.g. `{"code": 60, "tests": 45}`) instead of `{"default": 120}`

**Independent Test**: Run a multi-collection query with debug enabled and verify `per_space_result_counts` keys match collection names with values summing to total candidates

### Tests for User Story 1 (TDD — write first, verify they FAIL)

- [x] T002 [US1] Write unit tests for `_multi_collection_retrieve()` populating `_last_per_space_counts` with collection-name keys in tests/unit/test_retriever_debug_metadata.py — covers: two-collection query produces `{"code": N, "tests": M}`, zero-result collection appears with value 0, unknown collection is skipped (KeyError handling)
- [x] T003 [US1] Write unit tests for `_multi_collection_retrieve()` setting `_last_collections_searched` with all attempted collection names in tests/unit/test_retriever_debug_metadata.py — covers: all resolved collections present, unknown collections excluded, order matches attempt order
- [x] T004 [P] [US1] Write unit test for debug metadata builder consuming `_last_collections_searched` to populate `DebugMetadata.collections_searched` in tests/unit/test_service_debug_metadata.py

### Implementation for User Story 1

- [x] T005 [US1] Populate `_last_per_space_counts` with collection-name keys and `_last_collections_searched` list in `_multi_collection_retrieve()` in src/krag/retrieval/retriever.py — per contract: collection names as keys, zero-result collections included, skipped collections excluded
- [x] T006 [US1] Update debug metadata builder in src/kragd/service.py: use `_last_collections_searched` (via `getattr`) for `DebugMetadata.collections_searched` field; extract clean vector-space names from composite `collection:space` keys in `_last_per_space_counts` for `vector_spaces_searched` (split on `:` and deduplicate)
- [x] T007 [US1] Verify all US1 tests pass including single-collection regression (FR-003), run pre-commit validation (`uv run ruff format src/ tests/`, `uv run ruff check --fix src/ tests/`, `uv run pytest`)

**Checkpoint**: Multi-collection debug output shows per-collection keys. Single-collection path unchanged (no regression).

---

## Phase 4: User Story 2 — Multi-model embeddings in multi-collection retrieval (Priority: P2)

**Goal**: When multi-model is configured, `_multi_collection_retrieve()` uses all embedding models per collection with inner RRF merge before cross-collection weighted RRF — enabling two-level fusion

**Independent Test**: Configure two collections and two embedding models, query with debug, verify `vector_spaces_searched` lists all spaces and `per_space_result_counts` has composite `collection:space` keys

### Tests for User Story 2 (TDD — write first, verify they FAIL)

- [x] T008 [US2] Write unit tests for multi-model multi-collection retrieval path in tests/unit/test_retriever_multi_collection.py — covers: `embed_query()` called instead of `generate_single()` when `is_multi_model`, `search_named()` invoked per vector space per collection, inner `reciprocal_rank_fusion()` per collection before outer `_weighted_rrf()`, composite `collection:space` keys in `_last_per_space_counts`
- [x] T009 [US2] Write unit tests for graceful degradation in tests/unit/test_retriever_multi_collection.py — covers: collection without named vectors falls back to `search()` (unnamed), `search_named()` exception logged as warning with empty results and count recorded as 0, single-model collections mixed with multi-model collections
- [x] T010 [P] [US2] Write integration test for end-to-end multi-model multi-collection retrieval with mocked Qdrant in tests/integration/test_multi_collection.py — covers: two collections × two vector spaces produces correct result merge and debug metadata

### Implementation for User Story 2

- [x] T011 [US2] Implement multi-model embedding branch in `_multi_collection_retrieve()`: call `embed_query(query)` when `is_multi_model`, iterate vector spaces per collection using `search_named()`, merge per-collection results via `reciprocal_rank_fusion()` before outer `_weighted_rrf()` in src/krag/retrieval/retriever.py
- [x] T012 [US2] Add composite `collection:space` key tracking in `_last_per_space_counts` for multi-model path, and graceful try/except fallback with warning logging for `search_named()` failures in src/krag/retrieval/retriever.py
- [x] T013 [US2] Verify all US2 tests pass (unit + integration), run pre-commit validation (`uv run ruff format src/ tests/`, `uv run ruff check --fix src/ tests/`, `uv run pytest`)

**Checkpoint**: Multi-collection queries use all configured embedding models. Single-model multi-collection path unchanged. Two-level RRF merge produces correct results.

---

## Phase 5: User Story 3 — Suppress repetitive health-check log entries (Priority: P3)

**Goal**: Add ASGI middleware that logs the first `GET /health` in a consecutive run, suppresses subsequent ones, and resumes logging when a different endpoint is hit

**Independent Test**: Send 5 consecutive `GET /health` requests — only 1 logged. Send a non-health request then another `GET /health` — both logged.

### Tests for User Story 3 (TDD — write first, verify they FAIL)

- [x] T014 [US3] Write unit tests for health-check log suppression middleware in tests/unit/test_health_log_filter.py — covers: first health check logged, 5 consecutive health checks produce 1 log entry, non-health request resets suppression, `GET /health` after non-health is logged, `_last_was_health` is `False` at startup, `POST /health` is NOT treated as health check

### Implementation for User Story 3

- [x] T015 [US3] Implement `request_logging_middleware` with `_last_was_health` boolean state machine in `create_app()` in src/kragd/app.py — per contract: closure-scoped state, INFO-level logging for non-suppressed requests, suppressed health checks silent or DEBUG-level
- [x] T016 [US3] Verify all US3 tests pass, run pre-commit validation (`uv run ruff format src/ tests/`, `uv run ruff check --fix src/ tests/`, `uv run pytest`)

**Checkpoint**: Health-check log noise eliminated. All non-health requests logged normally. No effect on response behaviour.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all stories and live testing

- [x] T017 [P] Run full test suite across all stories (`uv run pytest -x -v`), fix any cross-story regressions
- [x] T018 Extend live tests for all three stories in tests/live/test_live_kragd.py — US1: multi-collection debug metadata keys, US2: multi-model vector spaces searched (include basic top-10 result overlap sanity check and latency measurement — log but don't fail on perf), US3: health-log suppression via kragd server log inspection
- [x] T019 Final pre-commit validation (`uv run ruff format src/ tests/`, `uv run ruff check --fix src/ tests/`, `uv run pytest`) and quickstart.md dev loop verification

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: No new work — existing project infrastructure is sufficient
- **User Story 1 (Phase 3)**: Depends on Phase 1 only
- **User Story 2 (Phase 4)**: Depends on Phase 3 (US1) — US2 extends the same `_multi_collection_retrieve()` method that US1 fixes
- **User Story 3 (Phase 5)**: Depends on Phase 1 only — completely independent of US1 and US2 (different files, different concerns)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    │
    ├──► Phase 3: US1 (P1) ──► Phase 4: US2 (P2) ──┐
    │                                                 ├──► Phase 6: Polish
    └──► Phase 5: US3 (P3) ──────────────────────────┘
```

- **US1 → US2**: US2 builds on US1's changes to `_multi_collection_retrieve()`. US1 adds `_last_per_space_counts` with collection-name keys; US2 extends this to composite `collection:space` keys for the multi-model path.
- **US3**: Fully independent — modifies only `src/kragd/app.py` and creates new test file. Can run in parallel with US1 or US2.

### Within Each User Story

1. Tests MUST be written first and MUST FAIL before implementation
2. Implementation tasks make tests pass
3. Pre-commit validation after each story
4. Story complete before moving to next priority (unless parallel opportunity)

### Parallel Opportunities

- **US1 tests**: T002/T003 (same file, sequential) and T004 (different file, parallel with T002/T003)
- **US2 tests**: T008/T009 (same file, sequential) and T010 (different file, parallel with T008/T009)
- **US3 vs US1**: Entire Phase 5 can run in parallel with Phase 3 (different files, no dependencies)
- **US3 vs US2**: Entire Phase 5 can run in parallel with Phase 4 (different files, no dependencies)
- **Polish**: T017 is parallel-safe (read-only test run)

---

## Parallel Example: User Story 1

```bash
# Launch tests in parallel (different files):
Task T002: "Unit tests for _last_per_space_counts in tests/unit/test_retriever_debug_metadata.py"
Task T004: "Unit test for debug metadata builder in tests/unit/test_service_debug_metadata.py"

# Then sequential (same file as T002):
Task T003: "Unit tests for _last_collections_searched in tests/unit/test_retriever_debug_metadata.py"
```

## Parallel Example: US1 + US3 (Cross-Story)

```bash
# These can run simultaneously — no shared files:
Phase 3 (US1): T002-T007 in src/krag/retrieval/retriever.py + src/kragd/service.py
Phase 5 (US3): T014-T016 in src/kragd/app.py + tests/unit/test_health_log_filter.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup verification
2. Complete Phase 3: User Story 1 — debug metadata fix
3. **STOP and VALIDATE**: Run multi-collection query with `--debug`, verify per-collection keys
4. Commit and push — this alone fixes the most impactful bug

### Incremental Delivery

1. Setup → US1 → Test independently → Commit (MVP — fixes data-correctness bug)
2. Add US2 → Test independently → Commit (enables multi-model + multi-collection)
3. Add US3 → Test independently → Commit (reduces log noise)
4. Polish + live tests → Final commit
5. Each story adds value without breaking previous stories

### Key Files Modified Per Story

| Story | Primary File | Test File(s) | Other Files |
|-------|-------------|--------------|-------------|
| US1 | `src/krag/retrieval/retriever.py` | `tests/unit/test_retriever_debug_metadata.py` (new), `tests/unit/test_service_debug_metadata.py` (new) | `src/kragd/service.py` |
| US2 | `src/krag/retrieval/retriever.py` | `tests/unit/test_retriever_multi_collection.py` (new), `tests/integration/test_multi_collection.py` (new) | — |
| US3 | `src/kragd/app.py` | `tests/unit/test_health_log_filter.py` (new) | — |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable (except US2 depends on US1)
- TDD is NON-NEGOTIABLE: write tests, verify they fail, then implement
- Pre-commit validation is NON-NEGOTIABLE: `ruff format` + `ruff check --fix` + `pytest` before every commit
- Commit after each completed user story (not after each task)
