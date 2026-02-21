# Tasks: Service Architecture

**Input**: Design documents from `/specs/007-service-architecture/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: Included (TDD is non-negotiable per constitution)

**Organization**: Tasks grouped by user story. Each story is independently testable.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-progress tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Exact file paths included in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, package scaffolding

- [X] T001 Update pyproject.toml with new dependencies (fastapi>=0.115.0, uvicorn[standard]>=0.34.0, httpx>=0.28.0) and dev dependency (pytest-httpx), add entry points (krag=krag_cli.main:app, kragd=kragd.__main__:main, krag-direct=krag.cli.main:app) in pyproject.toml
- [X] T002 [P] Create src/kragd/ package with __init__.py and routers/__init__.py
- [X] T003 [P] Create src/krag_cli/ package with __init__.py and commands/__init__.py
- [X] T004 [P] Create test directories: tests/unit/kragd/, tests/unit/krag_cli/, tests/integration/service/, tests/contract/api/ (each with __init__.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can begin

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first, verify they fail)

- [X] T005 [P] Unit tests for ServiceConfiguration defaults, validation, and [service] TOML parsing in tests/unit/test_service_config.py
- [X] T006 [P] Unit tests for API request/response schema validation (QueryRequest, RetrieveRequest, IndexRequest, SourceChunk, DebugMetadata) in tests/unit/kragd/test_schemas.py
- [X] T007 [P] Unit tests for KragService lifecycle (init, start, shutdown, started-guard) in tests/unit/kragd/test_service.py
- [X] T008 [P] Unit tests for KragClient (connection errors, timeout, error translation) in tests/unit/krag_cli/test_client.py

### Implementation

- [X] T009 [P] Add ServiceConfiguration model (host, port, primary_llm, idle_timeout, log_requests) to src/krag/models/configuration.py and add service field to Configuration
- [X] T010 [P] Add get_xdg_runtime_dir() helper following existing pattern in src/krag/config/xdg.py
- [X] T011 Extend ConfigManager.load() to parse [service] TOML section in src/krag/config/settings.py
- [X] T012 Implement Pydantic request/response schemas (QueryRequest, QueryResponse, RetrieveRequest, RetrieveResponse, DebugQueryRequest, DebugQueryResponse, DebugMetadata, QdrantSearchRequest, QdrantSearchResponse, IndexRequest, IndexResponse, ServiceStatus, HealthResponse, SourceChunk, all supporting models) in src/kragd/schemas.py
- [X] T013 Implement KragService core — __init__, start() (load config, embeddings, vector store, LLMPool), shutdown() (unload LLMs, close connections), started-guard decorator — in src/kragd/service.py
- [X] T014 Implement FastAPI app factory create_app() with lifespan context manager and get_service() dependency in src/kragd/app.py
- [X] T015 Implement kragd CLI entry point with foreground, --daemon, and --reload modes using uvicorn in src/kragd/__main__.py
- [X] T016 Implement KragClient HTTP wrapper (query, retrieve, index, status, health, shutdown methods) with connection error translation and configurable timeout in src/krag_cli/client.py
- [X] T017 Implement CLI-local server config reader (host, port from Configuration [service] section) in src/krag_cli/config.py
- [X] T018 Implement krag_cli Typer app shell with subcommand registration — include delegated sub-apps for config, plugin, gpu, log (reuse existing krag.cli.{config,plugin,gpu,log} modules directly) in src/krag_cli/main.py
- [X] T019 Implement krag_cli entry point in src/krag_cli/__main__.py

**Checkpoint**: Foundation ready — all packages exist, schemas defined, KragService boots, KragClient connects, entry points work. User story implementation can begin.

---

## Phase 3: User Story 1 — Start Service and Query via CLI (Priority: P1) 🎯 MVP

**Goal**: Start kragd, run `krag query "..."`, get answer + sources formatted identically to current CLI. Second query completes without cold-start.

**Independent Test**: Start kragd, run a query via CLI, verify answer/sources display. Time a second query to confirm <2s (excluding inference).

### Tests (write first, verify they fail)

- [X] T020 [P] [US1] Contract tests validating POST /query and POST /retrieve request/response schemas against OpenAPI spec in tests/contract/api/test_query_contract.py
- [X] T021 [P] [US1] Integration test for query round-trip via FastAPI TestClient (mock LLM, verify response structure) in tests/integration/service/test_query_roundtrip.py

### Implementation

- [X] T022 [US1] Implement KragService.query() (delegates to QueryEngine, converts QueryResponse to API schema) and KragService.retrieve() (retrieval-only, no LLM) in src/kragd/service.py
- [X] T023 [US1] Implement query router with POST /query and POST /retrieve endpoints (sync def handlers) and register in app in src/kragd/routers/query.py and src/kragd/app.py
- [X] T024 [P] [US1] Implement Rich display formatting for query answers and source chunks matching existing CLI output in src/krag_cli/display.py
- [X] T025 [US1] Implement CLI query command (--top-k, --preset, --llm, --no-synthesis, --format, --debug flags) and register in app in src/krag_cli/commands/query.py and src/krag_cli/main.py

**Checkpoint**: `kragd` starts, `krag query "..."` returns answer + sources. Second query is fast (no cold-start). US1 fully functional.

---

## Phase 4: User Story 2 — Service Lifecycle Management (Priority: P1)

**Goal**: Start/stop kragd reliably, check status (loaded models, VRAM, uptime), PID file management.

**Independent Test**: Start kragd → verify PID file → `krag status` → shows models/uptime → `krag stop` → clean shutdown.

### Tests (write first, verify they fail)

- [X] T026 [P] [US2] Unit tests for PID file utilities (write, read, stale detection via os.kill, removal) in tests/unit/kragd/test_pid.py
- [X] T027 [P] [US2] Contract tests for GET /health, GET /status, POST /shutdown against OpenAPI spec in tests/contract/api/test_system_contract.py

### Implementation

- [X] T028 [US2] Implement PID file utilities (write_pid, read_pid, is_pid_alive, remove_pid, get_pid_path using get_xdg_runtime_dir) in src/kragd/pid.py
- [X] T029 [US2] Integrate PID file write/remove into KragService.start()/shutdown() and implement get_status() (uptime, LLM slots, VRAM, embeddings, vector store stats) and get_health() in src/kragd/service.py
- [X] T030 [US2] Implement system router (async GET /health, sync GET /status, sync POST /shutdown via os.kill SIGTERM) and register in app in src/kragd/routers/system.py and src/kragd/app.py
- [X] T031 [US2] Implement CLI status command (Rich table for models/VRAM/uptime) and health command in src/krag_cli/commands/status.py
- [X] T032 [US2] Implement CLI start (delegates to kragd) and stop (reads PID, sends SIGTERM) commands and register all in app in src/krag_cli/commands/service.py and src/krag_cli/main.py

**Checkpoint**: Full lifecycle: start → status → health → stop. PID file management works. US1 + US2 both functional.

---

## Phase 5: User Story 3 — Configurable LLM Lifecycle (Priority: P2)

**Goal**: Primary LLM stays loaded permanently, secondary loads on demand and unloads after idle timeout. VRAM reclaimed after unload.

**Independent Test**: Configure text as primary with short timeout, trigger code query → code LLM loads → wait → verify unload via `krag status`.

### Tests (write first, verify they fail)

- [X] T033 [P] [US3] Unit tests for LLMLifecycleManager (primary never unloads, secondary idle timeout, in-flight defer, no-primary both-unload, timer cancel/restart) in tests/unit/kragd/test_lifecycle.py

### Implementation

- [X] T034 [US3] Implement LLMLifecycleManager (asyncio timer, threading.Lock in-flight counter, on_request_start/end, ensure_loaded, primary/secondary logic per R-04/R-06) in src/kragd/lifecycle.py
- [X] T035 [US3] Integrate LLMLifecycleManager into KragService — hook on_request_start/end around query and debug methods, pass event loop from lifespan in src/kragd/service.py
- [X] T036 [US3] Add LLM lifecycle fields (primary designation, idle_timeout_s, timer active) to ServiceStatus and GET /status response in src/kragd/routers/system.py and src/kragd/schemas.py

**Checkpoint**: LLM lifecycle works — primary persists, secondary unloads after idle. VRAM reclaimed (SC-006).

---

## Phase 6: User Story 4 — Debug Query Mode (Priority: P2)

**Goal**: `krag debug query "..."` returns answer + sources + 14 debug metadata fields (LLM used, routing, timings, candidates, spaces).

**Independent Test**: Run debug query, verify all metadata fields present with plausible values (SC-003: ≥10 fields).

### Tests (write first, verify they fail)

- [X] T037 [P] [US4] Contract tests for POST /debug/query validating DebugMetadata has ≥10 fields in tests/contract/api/test_debug_contract.py

### Implementation

- [X] T038 [US4] Implement KragService.debug_query() — wraps query with timing instrumentation (retrieval_time_ms, generation_time_ms), collects routing decision, embedding models, vector spaces, candidate counts in src/kragd/service.py
- [X] T039 [US4] Implement debug router with POST /debug/query endpoint (sync def handler) and register in app in src/kragd/routers/debug.py and src/kragd/app.py
- [X] T040 [US4] Implement CLI debug query command with Rich metadata panel (timings, routing, candidates) and register debug subcommand in app in src/krag_cli/commands/debug.py and src/krag_cli/main.py

**Checkpoint**: `krag debug query "..."` shows answer + 14 debug fields. Aliases: `krag query "..." --debug`.

---

## Phase 7: User Story 5 — Raw Qdrant Search (Priority: P2)

**Goal**: `krag debug qdrant "..."` returns raw vector store results bypassing Retriever (no dedup, boost, RRF). Filterable by space, file type, path.

**Independent Test**: Run raw search, compare to normal query to verify pipeline stages bypassed (SC-004).

### Tests (write first, verify they fail)

- [X] T041 [P] [US5] Contract tests for POST /debug/qdrant validating QdrantSearchResponse schema in tests/contract/api/test_debug_contract.py

### Implementation

- [X] T042 [US5] Implement KragService.debug_qdrant() — calls QdrantVectorStore.search() directly, constructs Qdrant filters from file_type and file_path_contains, bypasses Retriever per R-09 in src/kragd/service.py
- [X] T043 [US5] Add POST /debug/qdrant endpoint to debug router in src/kragd/routers/debug.py
- [X] T044 [US5] Implement CLI debug qdrant command (--space, --top-k, --threshold, --filter-type, --filter-path flags, Rich table output) in src/krag_cli/commands/debug.py

**Checkpoint**: `krag debug qdrant "..." --space text --top-k 20` returns raw scores. US4 + US5 both functional.

---

## Phase 8: User Story 6 — Indexing via Service (Priority: P3)

**Goal**: `krag index` and `krag index --full` perform indexing via kragd using already-loaded embedding models. Display stats on completion.

**Independent Test**: Run `krag index`, verify stats match direct-mode output.

### Tests (write first, verify they fail)

- [X] T045 [P] [US6] Contract tests for POST /index and GET /index/status validating IndexResponse schema in tests/contract/api/test_index_contract.py

### Implementation

- [X] T046 [US6] Implement KragService.index() (delegates to IndexingOrchestrator, stores last job, converts IndexingJob to API schema) in src/kragd/service.py
- [X] T047 [US6] Implement index router (sync POST /index, GET /index/status) and register in app in src/kragd/routers/index.py and src/kragd/app.py
- [X] T048 [US6] Implement CLI index command (--full, --dir, --type, --exclude, --dry-run flags, Rich stats display) and register in app in src/krag_cli/commands/index.py and src/krag_cli/main.py

**Checkpoint**: `krag index` completes via service, shows matching stats. All P1-P3 stories up through US6 functional.

---

## Phase 9: User Story 7 — Network Access from Other Machines (Priority: P3)

**Goal**: kragd binds to `0.0.0.0` by default, queryable from other machines on the LAN.

**Independent Test**: Start kragd with `host = "0.0.0.0"`, query from another machine.

- [X] T049 [US7] Add --host and --port CLI argument overrides to kragd entry point in src/kragd/__main__.py
- [X] T050 [US7] Integration test verifying kragd binds to configured host and CLI connects to non-localhost address in tests/integration/service/test_network_access.py

**Checkpoint**: kragd accessible from other machines on the LAN (SC-009).

---

## Phase 10: User Story 8 — Direct Mode Fallback (Priority: P3)

**Goal**: `krag-direct query "..."` works identically to pre-service CLI, in-process, no kragd needed.

**Independent Test**: Run `krag-direct query "..."` without kragd, verify identical output.

- [X] T051 [US8] Verify krag-direct entry point in pyproject.toml maps to krag.cli.main:app and all existing flags work unchanged
- [X] T052 [US8] Integration test verifying krag-direct executes in-process independently of kragd in tests/integration/service/test_direct_mode.py

**Checkpoint**: `krag-direct` works exactly as the current CLI. All user stories complete.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, final quality checks

- [X] T053 [P] Update docs/architecture.md with service architecture diagrams (kragd, krag_cli, krag-direct layers)
- [X] T054 [P] Add service usage documentation (start/stop/status, debug commands, config) to README.md
- [X] T055 Verify all 800+ existing tests pass unchanged after service architecture changes (SC-007)
- [X] T056 Run pre-commit validation: uv run ruff format . && uv run ruff check --fix . && uv run pytest
- [X] T057 Run quickstart.md end-to-end validation (start kragd, query, debug, index, status, stop, verify /docs accessible)
- [X] T058 [P] Integration test verifying second query completes within 2s excluding inference (SC-001) and health endpoint responds <500ms during LLM loading (SC-005) in tests/integration/service/test_performance.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational — **MVP target**
- **US2 (Phase 4)**: Depends on Foundational — can parallel with US1
- **US3 (Phase 5)**: Depends on US1 or US2 (needs KragService with query flow)
- **US4 (Phase 6)**: Depends on US1 (needs working query pipeline)
- **US5 (Phase 7)**: Depends on US4 (shares debug router)
- **US6 (Phase 8)**: Depends on Foundational (independent of query stories)
- **US7 (Phase 9)**: Depends on US1 (needs working query to test remote access)
- **US8 (Phase 10)**: Depends on Setup only (verifies existing CLI unchanged)
- **Polish (Phase 11)**: Depends on all desired user stories

### User Story Dependencies

```
Phase 1: Setup
    │
Phase 2: Foundational ──── BLOCKS ALL ────┐
    │                                      │
    ├── Phase 3: US1 (Query) ←── MVP       ├── Phase 8: US6 (Index)
    │       │                              │
    │       ├── Phase 5: US3 (Lifecycle)   ├── Phase 10: US8 (Direct)
    │       │
    │       ├── Phase 6: US4 (Debug Query)
    │       │       │
    │       │       └── Phase 7: US5 (Raw Qdrant)
    │       │
    │       └── Phase 9: US7 (Network)
    │
    └── Phase 4: US2 (Lifecycle Mgmt) ←── can parallel with US1
                │
                └── Phase 5: US3 (LLM Lifecycle) ←── also needs US2 for status
```

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (TDD)
2. Service methods before routers
3. Routers before CLI commands
4. Core implementation before integration points

### Parallel Opportunities

**Phase 1**: T002, T003, T004 all parallel (different directories)
**Phase 2**: T005–T008 (tests) all parallel; T009, T010 parallel; T012 parallel with T016
**Phase 3**: T020, T021 parallel (tests); T024 parallel with T022 (different packages)
**Phase 4**: T026, T027 parallel (tests)
**Phase 5**: T033 parallel (test only)
**Phase 6–8**: Test tasks parallelizable within their phases
**Phase 11**: T053, T054 parallel (different docs)
**Cross-phase**: US1 and US2 can proceed in parallel after Foundational; US6 and US8 are independent of query stories

---

## Parallel Example: Foundational Phase

```
# Batch 1: Write all foundational tests in parallel
T005: Unit tests for ServiceConfiguration
T006: Unit tests for API schemas
T007: Unit tests for KragService lifecycle
T008: Unit tests for KragClient

# Batch 2: Implement independent foundational components in parallel
T009: ServiceConfiguration model        (makes T005 pass)
T010: XDG runtime dir helper
T012: API schemas                        (makes T006 pass)
T016: KragClient HTTP wrapper            (makes T008 pass)

# Batch 3: Sequential foundational components
T011: ConfigManager [service] parsing    (depends on T009)
T013: KragService core                   (makes T007 pass, depends on T009, T012)
T014: FastAPI app factory                (depends on T013)
T015: kragd entry point                  (depends on T014)
T017: CLI config reader
T018: CLI Typer app shell                (depends on T016, T017)
T019: CLI entry point                    (depends on T018)
```

## Parallel Example: US1 + US2 After Foundational

```
# Worker A: US1 (Query)           # Worker B: US2 (Lifecycle)
T020: Query contract tests         T026: PID file unit tests
T021: Query integration test       T027: System contract tests
T022: KragService.query()          T028: PID file utilities
T023: Query router                 T029: KragService.get_status()
T024: Rich display formatting      T030: System router
T025: CLI query command            T031: CLI status command
                                   T032: CLI start/stop commands
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL** — blocks everything)
3. Complete Phase 3: US1 — Query via service
4. Complete Phase 4: US2 — Lifecycle management
5. **STOP and VALIDATE**: kragd starts, queries work, status/health/stop work
6. This is a deployable, usable service

### Incremental Delivery

1. Setup + Foundational → packages exist, entry points work
2. US1 → `krag query` works via service → **MVP!**
3. US2 → start/stop/status → **Production-ready lifecycle**
4. US3 → LLM lifecycle → VRAM optimization
5. US4 + US5 → Debug tools → Developer productivity
6. US6 → Indexing via service → Embedding model reuse
7. US7 + US8 → Network + fallback → Full feature set
8. Polish → Docs, validation → Sprint complete

### Task Count by Phase

| Phase | User Story | Tasks | Test Tasks | Impl Tasks |
|-------|-----------|-------|------------|------------|
| 1 | Setup | 4 | 0 | 4 |
| 2 | Foundational | 15 | 4 | 11 |
| 3 | US1 - Query (P1) | 6 | 2 | 4 |
| 4 | US2 - Lifecycle (P1) | 7 | 2 | 5 |
| 5 | US3 - LLM Lifecycle (P2) | 4 | 1 | 3 |
| 6 | US4 - Debug Query (P2) | 4 | 1 | 3 |
| 7 | US5 - Raw Qdrant (P2) | 4 | 1 | 3 |
| 8 | US6 - Indexing (P3) | 4 | 1 | 3 |
| 9 | US7 - Network (P3) | 2 | 1 | 1 |
| 10 | US8 - Direct Mode (P3) | 2 | 1 | 1 |
| 11 | Polish | 6 | 1 | 5 |
| **Total** | | **58** | **15** | **43** |

---

## Notes

- All `def` route handlers for blocking LLM/embedding ops; `async def` only for GET /health (R-02)
- KragService builds components individually — does NOT call build_query_pipeline() directly (R-05)
- LLMLifecycleManager wraps LLMPool without modifying it (R-06)
- Uvicorn handles SIGTERM natively; cleanup in lifespan teardown (R-07)
- POST /shutdown sends SIGTERM to self; krag stop reads PID file (R-07)
- POST /debug/qdrant bypasses Retriever, calls QdrantVectorStore directly (R-09)
- All tests follow Red-Green-Refactor: write test → fail → implement → pass → refactor
- Pre-commit gate: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
