# Tasks: Retrieval Modes, Multi-Collection Qdrant, Domain Lexicon, and Context Critic

**Input**: Design documents from `/specs/009-retrieval-modes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per constitution (TDD is NON-NEGOTIABLE). Write tests first, ensure they fail, then implement.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1–US5)
- Exact file paths included in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: New packages, shared config models, and collection routing constants needed by multiple stories

- [X] T001 Create routing package with `__init__.py` in `src/krag/routing/__init__.py`
- [X] T002 [P] Create modes package with `__init__.py` in `src/krag/modes/__init__.py`
- [X] T003 [P] Create lexicon package with `__init__.py` in `src/krag/lexicon/__init__.py`
- [X] T004 [P] Create critic package with `__init__.py` in `src/krag/critic/__init__.py`
- [X] T005 Add `ModeConfiguration`, `LexiconConfiguration`, and `CriticConfiguration` pydantic models to `src/krag/models/configuration.py`
- [X] T006 Add `modes_dir`, `default_mode`, `lexicon_path`, `lexicon_max_entries`, `lexicon_max_chars`, `critic_enabled`, `critic_threshold` config fields to `src/krag/config/settings.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Collection routing rules and CollectionManager — shared infrastructure that US1 (lifecycle) does NOT need, but US2–US5 all depend on

**⚠️ CRITICAL**: US2 (multi-collection) cannot begin until T007–T008 are complete

- [X] T007 Define routing constants and `RoutingRule` value objects in `src/krag/routing/rules.py` (8-level precedence: plugin override → test dir → test filename → well-known docs → docs ext → code ext → config/data → fallback)
- [X] T008 [P] Create built-in mode TOML files: `src/krag/modes/builtin/default.toml`, `src/krag/modes/builtin/code.toml`, `src/krag/modes/builtin/docs.toml` per `contracts/mode-schema.toml`

**Checkpoint**: Package structure and shared constants ready — user story implementation can begin

---

## Phase 3: User Story 1 — Fix Lifecycle Timer Race Condition (Priority: P1) 🎯 MVP

**Goal**: Pause the idle timer during indexing so the LLM reload after indexing always succeeds (FR-001, FR-002, FR-003)

**Independent Test**: Trigger an indexing job longer than the idle timeout → verify LLM reloads cleanly with no error log

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Unit tests for `pause()` / `resume()` / `_paused` guard in `tests/unit/kragd/test_lifecycle.py`
- [X] T010 [P] [US1] Integration test: pause → wait > timeout → resume → timer fires normally in `tests/integration/test_lifecycle_pause_resume.py`

### Implementation for User Story 1

- [X] T011 [US1] Add `_paused` flag, `pause()`, and `resume()` methods to `LLMLifecycleManager` in `src/kragd/lifecycle.py` — `pause()` cancels timer via `loop.call_soon_threadsafe(task.cancel)`, `resume()` re-schedules via `loop.call_soon_threadsafe(self._schedule_idle_timeout)`
- [X] T012 [US1] Add defense-in-depth `_paused` check at top of `_unload_after_timeout()` in `src/kragd/lifecycle.py`
- [X] T013 [US1] Wire `pause()` at start of `_run_indexing()` and `resume()` in finally block after LLM reload in `src/kragd/service.py`
- [X] T014 [US1] Add `timer_paused` field to `get_status()` response in `src/kragd/service.py`
- [X] T015 [US1] Guard `on_request_end()` to skip timer scheduling when `_paused` in `src/kragd/lifecycle.py`

**Checkpoint**: Lifecycle timer race condition eliminated — SC-006 met. No "Failed to reload LLM" errors during indexing.

---

## Phase 4: User Story 2 — Multi-Collection Qdrant Setup (Priority: P1)

**Goal**: Partition indexed content into four Qdrant collections (code, tests, docs, text) with file routing and multi-collection query fusion (FR-004 – FR-010)

**Independent Test**: Index a mixed project → verify files land in correct collections → query returns results annotated with source collection

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US2] Unit tests for `CollectionRouter.route()` covering all 8 precedence levels in `tests/unit/test_collection_router.py`
- [X] T017 [P] [US2] Unit tests for `CollectionManager` lifecycle (create/get/close stores, shared client) in `tests/unit/test_collection_manager.py`
- [X] T018 [P] [US2] Integration test: index mixed project → verify per-collection file distribution in `tests/integration/test_multi_collection_indexing.py`
- [X] T018b [P] [US2] Integration test: incremental indexing with multi-collection — add/modify/delete files → verify correct collection updated in `tests/integration/test_multi_collection_incremental.py`

### Implementation for User Story 2

- [X] T019 [US2] Implement `CollectionRouter` with 8-level precedence routing in `src/krag/routing/collection_router.py`
- [X] T020 [US2] Implement `CollectionManager` — shared `QdrantClient`, four `CollectionStore` wrappers in `src/krag/storage/collection_manager.py`
- [X] T021 [US2] Refactor `QdrantVectorStore.__init__` to accept an optional pre-created `QdrantClient` in `src/krag/storage/qdrant_impl.py`
- [X] T022 [US2] Wire `CollectionRouter` into indexing pipeline — route each file to correct collection in `src/krag/orchestration/indexer.py`
- [X] T023 [US2] Extend `retriever.py` to query multiple collections and merge via weighted RRF in `src/krag/retrieval/retriever.py`
- [X] T024 [US2] Add `collection` field to query result model and tag each result with source collection in `src/krag/models/query_result.py`
- [X] T025 [US2] Initialize `CollectionManager` in service startup, replace single-collection init in `src/kragd/service.py`
- [X] T026 [US2] Add `collections` per-collection stats to `GET /status` response and `POST /index` response in `src/kragd/service.py`
- [X] T027 [US2] Handle empty collections gracefully — return empty results without error in `src/krag/retrieval/retriever.py`

**Checkpoint**: Multi-collection indexing and querying works. Files route to correct collections. SC-001 met.

---

## Phase 5: User Story 3 — Mode System (Priority: P1)

**Goal**: Replace `--llm` flag with `--mode` flag that bundles collections, LLM slot, prompt preset, and retrieval parameters (FR-011 – FR-019)

**Independent Test**: Query with `--mode code` → only code/tests collections searched, code LLM used, code preset applied

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T028 [P] [US3] Unit tests for `ModeLoader.load()` TOML parsing and validation in `tests/unit/test_mode_loader.py`
- [X] T029 [P] [US3] Unit tests for `ModeRegistry` (register, get, list, load builtins, user override, case-insensitive lookup) in `tests/unit/test_mode_registry.py`
- [X] T030 [P] [US3] Contract test: mode TOML schema validates per `contracts/mode-schema.toml` in `tests/contract/test_mode_contract.py`
- [X] T031 [P] [US3] Integration test: query with `--mode code` → correct collections/LLM/preset in `tests/integration/test_mode_query.py`

### Implementation for User Story 3

- [X] T032 [US3] Implement `ModeLoader` — load TOML, validate fields, return `ModeConfiguration` in `src/krag/modes/mode_loader.py`
- [X] T033 [US3] Implement `ModeRegistry` — load builtins then user-defined, case-insensitive lookup in `src/krag/modes/mode_registry.py`
- [X] T034 [US3] Wire mode resolution into `query_engine.py` — resolve mode name → extract collections/LLM slot/preset/params in `src/krag/orchestration/query_engine.py`
- [X] T035 [US3] Add `--mode` flag and `--llm` deprecation warning to krag-direct CLI in `src/krag/cli/query.py`
- [X] T036 [US3] Add `mode` field to POST /query and POST /retrieve request schemas in `src/kragd/schemas.py`
- [X] T037 [US3] Add `--mode` flag and `--llm` deprecation warning to krag CLI client in `src/krag_cli/commands/query.py`
- [X] T038 [US3] Pass `mode` parameter through HTTP client in `src/krag_cli/client.py`
- [X] T039 [P] [US3] Implement `krag-direct modes list` and `krag-direct modes show <name>` commands in `src/krag/cli/modes.py`
- [X] T040 [P] [US3] Implement `krag modes list` and `krag modes show <name>` commands in `src/krag_cli/commands/modes.py`
- [X] T041 [US3] Implement `GET /modes` and `GET /modes/{name}` endpoints in `src/kragd/routers/modes.py`
- [X] T042 [US3] Add `mode_registry` to `GET /status` response in `src/kragd/service.py`
- [X] T043 [US3] Add debug metadata: `mode`, `collections_searched` to debug output in `src/kragd/service.py`

**Checkpoint**: Mode system fully functional across all three execution paths (krag, krag-direct, kragd). SC-002, SC-003, SC-007, SC-008 met.

---

## Phase 6: User Story 4 — Domain Lexicon (Priority: P2)

**Goal**: Inject project-specific terminology from a JSON glossary into prompts for more accurate LLM responses (FR-020 – FR-027)

**Independent Test**: Create a lexicon with known terms → query using those terms → verify LLM response uses the glossary definitions

### Tests for User Story 4

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T044 [P] [US4] Unit tests for `LexiconStore` (load, reload, match_terms, validation errors) in `tests/unit/test_lexicon_store.py`
- [X] T045 [P] [US4] Unit tests for `LexiconInjector` (select top-N, format glossary, char limit) in `tests/unit/test_lexicon_injector.py`
- [X] T046 [P] [US4] Contract test: lexicon JSON validates per `contracts/lexicon-schema.json` in `tests/contract/test_lexicon_contract.py`
- [X] T047 [P] [US4] Integration test: query with lexicon → definitions injected into prompt in `tests/integration/test_lexicon_injection.py`

### Implementation for User Story 4

- [X] T048 [US4] Implement `LexiconStore` — load JSON, pre-compile word-boundary regex patterns, match terms in `src/krag/lexicon/lexicon_store.py`
- [X] T049 [US4] Implement `LexiconInjector` — select top-10 by specificity, cap at 1500 chars, format as prompt appendix in `src/krag/lexicon/lexicon_injector.py`
- [X] T050 [US4] Add lexicon injection point in `build_system_prompt()` — append "Project Terminology" section in `src/krag/synthesis/prompt_builder.py`
- [X] T051 [US4] Wire lexicon into query flow — match terms, inject, track count in debug in `src/krag/orchestration/query_engine.py`
- [X] T052 [US4] Implement `POST /lexicon/refresh` endpoint in `src/kragd/routers/lexicon.py`
- [X] T053 [US4] Implement `krag lexicon refresh` CLI command in `src/krag_cli/commands/lexicon.py`
- [X] T054 [US4] Add `lexicon_loaded` and `lexicon_entry_count` to `GET /status` response in `src/kragd/service.py`
- [X] T055 [US4] Add `lexicon_terms_injected` to debug output in `src/krag/orchestration/query_engine.py`

**Checkpoint**: Lexicon injection working end-to-end. SC-004 met.

---

## Phase 7: User Story 5 — Context Relevance Critic (Priority: P2)

**Goal**: Score retrieved chunks for relevance (0–5) and filter out low-scoring chunks before synthesis (FR-028 – FR-035)

**Independent Test**: Enable critic in debug mode → verify each chunk has a score → chunks below threshold excluded from prompt

### Tests for User Story 5

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T056 [P] [US5] Unit tests for `RelevanceCritic.score_chunks()` (scoring, parsing, fail-open, short-chunk bypass) in `tests/unit/test_relevance_critic.py`
- [X] T057 [P] [US5] Contract test: critic prompt format and score parsing in `tests/contract/test_critic_contract.py`
- [X] T058 [P] [US5] Integration test: query with critic enabled → chunks filtered, debug shows scores in `tests/integration/test_critic_filtering.py`

### Implementation for User Story 5

- [X] T059 [US5] Implement `RelevanceCritic` — individual scoring calls, regex parse, fail-open, <50 char bypass in `src/krag/critic/relevance_critic.py`
- [X] T060 [US5] Wire critic into query engine — after retrieval, before prompt construction, check `mode.critic_enabled` in `src/krag/orchestration/query_engine.py`
- [X] T061 [US5] Handle all-chunks-filtered case — return insufficient context response in `src/krag/orchestration/query_engine.py`
- [X] T062 [US5] Add critic debug metadata: `critic_scores`, `chunks_pre_critic`, `chunks_post_critic` to debug output in `src/krag/orchestration/query_engine.py`

**Checkpoint**: Context critic working. Disabled by default, opt-in via mode config. SC-005 met.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and full-suite validation

- [X] T063 [P] Update `docs/plugin-development.md` with collection routing override documentation
- [X] T064 [P] Update `docs/plugin-user-guide.md` with mode system and lexicon usage
- [X] T065 [P] Update `README.md` with new `--mode` flag, modes list, and lexicon features
- [X] T066 Run full pre-commit validation: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
- [X] T067 Run quickstart.md smoke test validation end-to-end
- [X] T068 Run `uv run mypy src/` type checking

> **Note**: Performance benchmarking (SC-002 mode selection latency, FR-027 no-lexicon parity) is deferred. If usage shows unacceptable performance decline, benchmarks will be added in a follow-up sprint.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — provides routing rules and built-in modes
- **US1 (Phase 3)**: Can start after Phase 1 — lifecycle fix is independent of routing/collections
- **US2 (Phase 4)**: Depends on Phase 2 (routing rules) and Phase 3 (stable lifecycle)
- **US3 (Phase 5)**: Depends on Phase 4 (needs collections to target)
- **US4 (Phase 6)**: Depends on Phase 5 (modes reference lexicon in config), independent of US5
- **US5 (Phase 7)**: Depends on Phase 5 (modes reference critic in config), independent of US4
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Phase 1 (Setup) ─────────────┐
                             ├──► Phase 3 (US1: Lifecycle Fix)
Phase 2 (Foundational) ──────┤                │
                             │                ▼
                             └──► Phase 4 (US2: Multi-Collection)
                                              │
                                              ▼
                                   Phase 5 (US3: Mode System)
                                          │         │
                                          ▼         ▼
                              Phase 6 (US4)    Phase 7 (US5)
                              Lexicon          Critic
                                          │         │
                                          ▼         ▼
                                   Phase 8 (Polish)
```

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Models/entities before services
3. Core logic before CLI/API wiring
4. Implementation before integration with other stories
5. Story complete before moving to next priority

### Parallel Opportunities

**Phase 1**: T001–T004 all create independent packages — run in parallel
**Phase 2**: T007 and T008 are independent — run in parallel
**Phase 3**: T009, T010 are test files — run in parallel; T011–T012 can run in parallel (different methods in same file)
**Phase 4**: T016–T018 are test files — run in parallel; T019, T020 are independent new files
**Phase 5**: T028–T031 are test files — run in parallel; T039, T040 are independent CLI files
**Phase 6**: T044–T047 are test files — run in parallel
**Phase 7**: T056–T058 are test files — run in parallel
**Phase 8**: T063–T065 are independent docs — run in parallel

---

## Parallel Example: User Story 2

```bash
# Launch all tests together:
Task T016: "Unit tests for CollectionRouter in tests/unit/test_collection_router.py"
Task T017: "Unit tests for CollectionManager in tests/unit/test_collection_manager.py"
Task T018: "Integration test for multi-collection indexing in tests/integration/test_multi_collection_indexing.py"

# Then launch independent implementation files:
Task T019: "Implement CollectionRouter in src/krag/routing/collection_router.py"
Task T020: "Implement CollectionManager in src/krag/storage/collection_manager.py"

# Then sequential wiring (dependencies):
Task T021 → T022 → T023 → T024 → T025 → T026 → T027
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (lifecycle fix)
4. **STOP and VALIDATE**: Timer race condition eliminated, no error logs during indexing

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. US1 (lifecycle fix) → Stable foundation → Validate SC-006
3. US2 (multi-collection) → Content partitioned → Validate SC-001
4. US3 (mode system) → User-facing feature → Validate SC-002, SC-003, SC-007, SC-008
5. US4 (lexicon) → Domain quality boost → Validate SC-004
6. US5 (critic) → Relevance filtering → Validate SC-005
7. Polish → Documentation + full validation

### Notes

- US4 and US5 are independent of each other — can be done in either order
- Each story adds value without breaking previous stories
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
