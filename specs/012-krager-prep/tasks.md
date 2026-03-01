# Tasks: krager Prep — API Normalization & Hardening

**Input**: Design documents from `/specs/012-krager-prep/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — User Story 7 (P1) mandates comprehensive test coverage for all changes. Tests are written FIRST in each phase (TDD).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing. US7 (test coverage) is satisfied by the test tasks embedded in every phase — there is no separate US7 phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/kragd/` (server), `src/krag/` (core), `src/krag_cli/` (CLI), `tests/` at repository root

---

## Phase 1: Setup

**Purpose**: Add new dependency and create shared test infrastructure for SSE testing

- [x] T001 Add sse-starlette>=2.0.0 to project dependencies in pyproject.toml
- [x] T002 [P] Create SSE test helper parse_sse_stream() utility in tests/conftest.py

---

## Phase 2: User Story 1 — Consistent API Responses (Priority: P1) 🎯 MVP

**Goal**: All response models live in the central schema module; `/index/status` always returns a list.

**Independent Test**: Call every kragd endpoint and verify each response matches its documented schema — no polymorphic surprises, all models importable from `kragd.schemas`.

**Dependency**: Phase 1 (Setup)

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T003 [P] [US1] Add tests verifying LexiconRefreshResponse, ModeListResponse, ModeDetailResponse are importable from kragd.schemas in tests/contract/api/test_system_contract.py
- [x] T004 [P] [US1] Add tests verifying /index/status always returns a list (zero, one, many jobs, in-progress job) in tests/contract/api/test_index_contract.py

### Implementation for User Story 1

- [x] T005 [US1] Relocate LexiconRefreshResponse, ModeListResponse, ModeDetailResponse to src/kragd/schemas.py
- [x] T006 [P] [US1] Update lexicon router to import LexiconRefreshResponse from schemas in src/kragd/routers/lexicon.py
- [x] T007 [P] [US1] Update modes router to import ModeListResponse and ModeDetailResponse from schemas in src/kragd/routers/modes.py
- [x] T008 [US1] Normalize /index/status response_model to list[IndexResponse] in src/kragd/routers/index.py
- [x] T009 [US1] Update get_index_status() to always return list[IndexResponse] in src/kragd/service.py
- [x] T009a [US1] Update index_status_command and index polling loop to remove isinstance(result, list) branching in src/krag_cli/commands/index.py

**Checkpoint**: Schema imports verified, /index/status always returns a list, CLI expects list-only. Run: `uv run pytest tests/contract/api/ -v -k "index or modes or lexicon or system"`

---

## Phase 3: User Story 2 — Cross-Origin Access for Remote Clients (Priority: P1)

**Goal**: Browser-based clients (including Tauri webview) can call kragd without CORS errors.

**Independent Test**: Make a cross-origin request to kragd and verify `Access-Control-Allow-Origin` headers are present.

**Dependency**: Phase 1 (Setup) — independent of US1

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T010 [US2] Create CORS contract tests (preflight OPTIONS, wildcard origin, custom KRAGD_CORS_ORIGINS, no-Origin passthrough) in tests/contract/api/test_cors_contract.py

### Implementation for User Story 2

- [x] T011 [US2] Add CORSMiddleware to create_app() with KRAGD_CORS_ORIGINS env var config in src/kragd/app.py

**Checkpoint**: CORS headers present on all responses. Run: `uv run pytest tests/contract/api/test_cors_contract.py -v`

---

## Phase 4: User Story 3 — CLI JSON Output for All Commands (Priority: P2)

**Goal**: All 5 missing CLI commands support `--json` for machine-readable output.

**Independent Test**: Run each command with `--json` and verify output is valid, parseable JSON.

**Dependency**: Phase 1 (Setup) — independent of US1/US2

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T012 [P] [US3] Add --json unit tests for health_command in tests/unit/krag_cli/test_health_json.py
- [x] T013 [P] [US3] Add --json unit tests for modes_list and modes_show (including nonexistent mode error case) in tests/unit/krag_cli/test_modes_json.py
- [x] T014 [P] [US3] Add --json unit tests for lexicon_refresh in tests/unit/krag_cli/test_lexicon_json.py
- [x] T015 [P] [US3] Add --json unit tests for stop_command (including kragd-not-running error case) in tests/unit/krag_cli/test_service_json.py

### Implementation for User Story 3

- [x] T016 [P] [US3] Add --json flag to health_command in src/krag_cli/commands/status.py
- [x] T017 [P] [US3] Add --json flag to modes_list and modes_show in src/krag_cli/commands/modes.py
- [x] T018 [P] [US3] Add --json flag to lexicon_refresh in src/krag_cli/commands/lexicon.py
- [x] T019 [P] [US3] Add --json flag to stop_command in src/krag_cli/commands/service.py

**Checkpoint**: All 5 commands produce valid JSON with --json. Run: `uv run pytest tests/unit/krag_cli/ -v -k "json"`

---

## Phase 5: User Story 4 — OpenAPI Spec Quality (Priority: P2)

**Goal**: 100% of endpoints tagged with summaries, all schema fields described, request bodies have examples.

**Independent Test**: Fetch `/openapi.json` and verify every endpoint has a tag and summary, every field has a description.

**Dependency**: Phase 2 (US1) — schemas must be consolidated in schemas.py first

### Tests for User Story 4

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T020 [US4] Create OpenAPI completeness contract test (all endpoints tagged, all fields described, request bodies have examples) in tests/contract/api/test_openapi_contract.py

### Implementation for User Story 4

- [x] T021 [P] [US4] Add/verify tags and endpoint summaries on system router in src/kragd/routers/system.py
- [x] T022 [P] [US4] Add/verify tags and endpoint summaries on debug router in src/kragd/routers/debug.py
- [x] T023 [P] [US4] Add/verify tags and endpoint summaries on index router in src/kragd/routers/index.py
- [x] T024 [P] [US4] Add/verify tags and endpoint summaries on query router in src/kragd/routers/query.py
- [x] T025 [P] [US4] Add/verify tags and endpoint summaries on modes router in src/kragd/routers/modes.py
- [x] T026 [P] [US4] Add/verify tags and endpoint summaries on lexicon router in src/kragd/routers/lexicon.py
- [x] T027 [US4] Add Field descriptions and json_schema_extra examples to all Pydantic models in src/kragd/schemas.py
- [x] T028 [US4] Add request body examples to POST endpoint decorators across all routers

**Checkpoint**: OpenAPI spec is complete. Run: `uv run pytest tests/contract/api/test_openapi_contract.py -v`

---

## Phase 6: User Story 5 — Real-Time Index Progress (Priority: P3)

**Goal**: Clients subscribe to `GET /index/stream` for real-time SSE progress events during indexing.

**Independent Test**: Start an indexing job, subscribe to the event stream, verify progress events arrive in real time.

**Dependency**: Phase 2 (US1) — requires normalized /index endpoint

### Tests for User Story 5

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T029 [US5] Write SSE index progress contract tests (idle, progress sequence, completion, error, client disconnect) in tests/contract/api/test_stream_index_contract.py

### Implementation for User Story 5

- [x] T030 [US5] Add index_event_queue and wire progress_callback in _run_indexing() in src/kragd/service.py
- [x] T031 [US5] Add GET /index/stream SSE endpoint using EventSourceResponse in src/kragd/routers/index.py

**Checkpoint**: Index progress events stream to subscribed clients. Run: `uv run pytest tests/contract/api/test_stream_index_contract.py -v`

---

## Phase 7: User Story 6 — Streaming Query Answers (Priority: P3)

**Goal**: Clients submit `POST /query/stream` and receive answer tokens as SSE events as the LLM generates them.

**Independent Test**: Submit a query to the streaming endpoint, verify partial tokens arrive before the full response completes.

**Dependency**: Phase 1 (Setup) — independent of US1-US5

### Tests for User Story 6

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T032 [US6] Write SSE streaming query contract tests (sources event, token events, done event, error event, client disconnect) in tests/contract/api/test_stream_query_contract.py

### Implementation for User Story 6

- [x] T033 [P] [US6] Add generate_stream() method yielding token deltas in src/krag/synthesis/llm_client.py
- [x] T034 [US6] Add route_and_stream() with slot busy flag pattern in src/krag/synthesis/llm_pool.py
- [x] T035 [US6] Add query_stream() method with asyncio.Queue bridging in src/kragd/service.py
- [x] T036 [US6] Add POST /query/stream SSE endpoint using EventSourceResponse in src/kragd/routers/query.py

**Checkpoint**: Streaming query answers deliver tokens in real time. Run: `uv run pytest tests/contract/api/test_stream_query_contract.py -v`

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Live tests, documentation, and final validation across all stories

- [x] T037 [P] Add SSE index progress and streaming query live tests in tests/live/test_live_kragd.py
- [x] T038 [P] Update API documentation with new endpoints and changes in docs/architecture.md
- [x] T039 Run full test suite and verify zero regressions with uv run pytest
- [x] T040 Run pre-commit workflow (uv run ruff format . && uv run ruff check --fix . && uv run pytest)

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1: Setup ─────────────────────────────────────────────────────┐
    │                                                               │
    ├──► Phase 2: US1 (P1) ──┬──► Phase 5: US4 (P2)                 │
    │                        └──► Phase 6: US5 (P3)                 │
    ├──► Phase 3: US2 (P1) ─────────────────────────────────────────┤
    ├──► Phase 4: US3 (P2) ─────────────────────────────────────────┤
    └──► Phase 7: US6 (P3) ────────────────────────────────────────►├──► Phase 8: Polish
```

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on Setup — BLOCKS US4 and US5
- **US2 (Phase 3)**: Depends on Setup — independent of all other stories
- **US3 (Phase 4)**: Depends on Setup — independent of all other stories
- **US4 (Phase 5)**: Depends on US1 (schemas must be consolidated first)
- **US5 (Phase 6)**: Depends on US1 (/index/status must be normalized first)
- **US6 (Phase 7)**: Depends on Setup only — independent of US1-US5
- **Polish (Phase 8)**: Depends on all story phases being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Setup — no dependencies on other stories
- **US2 (P1)**: Can start after Setup — independent of US1
- **US3 (P2)**: Can start after Setup — independent of US1/US2
- **US4 (P2)**: Depends on US1 (consolidated schemas in schemas.py)
- **US5 (P3)**: Depends on US1 (normalized /index/status endpoint)
- **US6 (P3)**: Can start after Setup — independent of all other stories

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Schema/model changes before service layer
- Service layer before endpoint/router changes
- Core implementation before integration
- Story complete before checkpointing

### Parallel Opportunities

**Cross-story parallelism** (after Setup):
- US1 + US2 + US3 + US6 can all begin in parallel
- US4 and US5 can begin once US1 completes

**Within-story parallelism**:
- US1: T003 ∥ T004 (tests), T006 ∥ T007 (router updates after T005)
- US3: T012 ∥ T013 ∥ T014 ∥ T015 (all tests), T016 ∥ T017 ∥ T018 ∥ T019 (all implementations)
- US4: T021 ∥ T022 ∥ T023 ∥ T024 ∥ T025 ∥ T026 (all router tag/summary tasks)
- US6: T033 can start in parallel with T032 (different files)

---

## Parallel Example: User Story 3

```bash
# Launch all tests together (all [P], different files):
T012: "--json unit tests for health_command"
T013: "--json unit tests for modes commands"
T014: "--json unit tests for lexicon_refresh"
T015: "--json unit tests for stop_command"

# After tests written, launch all implementations together (all [P], different files):
T016: "--json flag on health_command"
T017: "--json flag on modes commands"
T018: "--json flag on lexicon_refresh"
T019: "--json flag on stop_command"
```

## Parallel Example: User Story 4

```bash
# After T020 (OpenAPI test) written, launch all router tasks together (all [P]):
T021: "system router tags/summaries"
T022: "debug router tags/summaries"
T023: "index router tags/summaries"
T024: "query router tags/summaries"
T025: "modes router tags/summaries"
T026: "lexicon router tags/summaries"

# Then sequentially:
T027: "Field descriptions and examples on all models"
T028: "Request body examples on POST decorators"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: US1 — Schema consolidation + /index/status normalization
3. **STOP and VALIDATE**: Run contract tests, verify all imports, confirm list-only /index/status
4. This MVP ensures the API surface is predictable for remote client development

### Incremental Delivery

1. Setup → Foundation ready
2. US1 (P1) → Consistent API responses → **MVP checkpoint**
3. US2 (P1) → CORS enabled → Browser clients unblocked
4. US3 (P2) → CLI --json → Scripting/automation enabled
5. US4 (P2) → OpenAPI quality → Client codegen ready
6. US5 (P3) → Index streaming → Real-time progress
7. US6 (P3) → Query streaming → Responsive LLM answers
8. Polish → Live tests, docs, final validation

Each story adds value without breaking previous stories.

### Sequential Execution Order (solo developer)

1. Setup (Phase 1)
2. US1 (Phase 2) — unblocks US4 and US5
3. US2 (Phase 3) — quick win, 2 tasks
4. US3 (Phase 4) — independent, 8 tasks
5. US4 (Phase 5) — depends on US1
6. US5 (Phase 6) — depends on US1
7. US6 (Phase 7) — heaviest implementation
8. Polish (Phase 8)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- US7 (Comprehensive Test Coverage) is satisfied by the test tasks in every phase — no separate phase needed
- SSE event models are lightweight inline dicts (per data-model.md), not separate Pydantic models in schemas.py
- Pre-commit workflow (**NON-NEGOTIABLE**): `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
