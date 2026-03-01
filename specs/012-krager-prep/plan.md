# Implementation Plan: krager Prep — API Normalization & Hardening

**Branch**: `012-krager-prep` | **Date**: 2026-02-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-krager-prep/spec.md`

## Summary

Prepare the kragd API surface and krag CLI for the krager remote desktop client sprint. This includes normalizing the polymorphic `/index/status` endpoint to always return a list, consolidating three inline response schemas into `schemas.py`, adding CORS middleware, completing `--json` support across all CLI commands, enriching the OpenAPI spec with tags/descriptions/examples, and adding two new SSE streaming endpoints (index progress events and streaming query answers). All changes get comprehensive test coverage.

## Technical Context

**Language/Version**: Python >=3.11,<3.14 (ruff/mypy target: py311)  
**Primary Dependencies**: FastAPI >=0.115.0, Pydantic >=2.6.0, Uvicorn >=0.34.0, Typer >=0.9.0, Rich >=13.0.0, httpx >=0.28.0, llama-cpp-python >=0.2.90, sse-starlette >=2.0.0 (new)  
**Storage**: Qdrant vector store (via qdrant-client >=1.8.0), YAML/TOML config files  
**Testing**: pytest >=9.0.2 + pytest-cov, pytest-httpx, pytest-asyncio; test types: unit, contract (FastAPI TestClient), integration, live (@pytest.mark.live)  
**Target Platform**: Linux server (kragd) + Linux/macOS CLI (krag)  
**Project Type**: Single project — Python monorepo with `src/kragd` (server), `src/krag` (core), `src/krag_cli` (CLI)  
**Build System**: hatchling, managed via uv  
**Performance Goals**: SSE index events within 1s of file processing; streaming query tokens within 2s of submission; zero regression on existing endpoint latency  
**Constraints**: Must maintain backward compatibility — no breaking API changes except the intentional `/index/status` normalization (pre-1.0, sole consumer updated simultaneously); CORS default must be permissive for dev; all existing tests must continue to pass  
**Scale/Scope**: 12 existing endpoints + 2 new SSE endpoints, 5 CLI commands gaining `--json`, ~30 schema models total  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Code Quality & Standards

| Gate | Status | Notes |
|------|--------|-------|
| Maintainability — clear, documented, consistent patterns | PASS | Schema consolidation improves consistency; all new code follows existing patterns |
| Modularity — focused, reusable components | PASS | Schemas centralized in one module; SSE endpoints are new routers or extensions of existing ones |
| Documentation — public interfaces have docstrings | PASS | All new/moved schemas retain Field descriptions; new endpoints get docstrings; OpenAPI review is an explicit deliverable |
| Style Compliance — ruff format + check | PASS | Pre-commit workflow enforced |
| Type Safety — type hints | PASS | All Pydantic models are typed; SSE generators will have proper return type annotations |

### II. Test-Driven Development

| Gate | Status | Notes |
|------|--------|-------|
| Red-Green-Refactor | PASS | Tests written before implementation for each story |
| All new code paths have tests | PASS | User Story 7 is explicitly dedicated to test coverage |
| Unit + Contract + Integration tests | PASS | Schema consolidation → contract tests; CORS → contract tests; CLI --json → unit tests; SSE → contract + integration tests |
| Live test maintenance | PASS | New SSE endpoints and streaming query warrant live test additions |
| Pre-commit gate | PASS | `uv run ruff format . && uv run ruff check --fix . && uv run pytest` before every commit |
| Independent stories | PASS | Each user story is independently testable per spec |

### III. User Experience Consistency

| Gate | Status | Notes |
|------|--------|-------|
| Interface stability — no breaking changes | PASS | `/index/status` normalization is a breaking change, but it's pre-1.0 and the only known consumer is the CLI (which will be updated simultaneously) |
| Error messages — clear and actionable | PASS | SSE error events will include descriptive messages; CLI --json errors output JSON |
| Documentation alignment | PASS | OpenAPI review is a dedicated deliverable (FR-015 through FR-017) |
| Feedback mechanisms — progress for long ops | PASS | SSE index progress endpoint directly addresses this |

### IV. Performance & Optimization

| Gate | Status | Notes |
|------|--------|-------|
| Performance targets defined | PASS | SC-005: <1s index events; SC-006: <2s streaming query start |
| Measurement — instrumentation | PASS | Existing `DebugMetadata` captures timing; SSE events carry timestamps |
| Regression prevention | PASS | Existing test suite + new tests |
| Resource efficiency | PASS | SSE uses async generators (no polling overhead); LLM streaming releases lock after routing |

### Python-Specific Requirements

| Gate | Status | Notes |
|------|--------|-------|
| `uv` for dependency management | PASS | Project uses uv; new `sse-starlette` dep added via `uv add` |
| `ruff format` + `ruff check` | PASS | Pre-commit workflow |
| `pyproject.toml` configuration | PASS | Already configured |

**Result: All gates PASS. No violations to justify.**

## Project Structure

### Documentation (this feature)

```text
specs/012-krager-prep/
├── plan.md              # This file
├── research.md          # Phase 0: resolved unknowns
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: implementation guide
├── contracts/           # Phase 1: OpenAPI contract fragments
│   ├── index-stream.yaml    # SSE index progress endpoint
│   └── query-stream.yaml    # SSE streaming query endpoint
├── checklists/
│   └── requirements.md  # Spec quality checklist (already created)
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── kragd/                           # FastAPI server
│   ├── app.py                       # MODIFIED: add CORS middleware
│   ├── schemas.py                   # MODIFIED: add LexiconRefreshResponse, ModeListResponse, ModeDetailResponse
│   ├── service.py                   # MODIFIED: wire progress_callback, add query_stream()
│   └── routers/
│       ├── index.py                 # MODIFIED: normalize /index/status, add /index/stream SSE
│       ├── lexicon.py               # MODIFIED: remove inline schema, import from schemas
│       ├── modes.py                 # MODIFIED: remove inline schemas, import from schemas
│       ├── query.py                 # MODIFIED: add /query/stream SSE endpoint
│       ├── system.py                # MODIFIED: OpenAPI tags/descriptions
│       └── debug.py                 # MODIFIED: OpenAPI tags/descriptions
├── krag/
│   └── synthesis/
│       ├── llm_client.py            # MODIFIED: add generate_stream() method
│       └── llm_pool.py              # MODIFIED: add route_and_stream() method
└── krag_cli/
    └── commands/
        ├── status.py                # MODIFIED: add --json to health_command
        ├── modes.py                 # MODIFIED: add --json to modes_list, modes_show
        ├── lexicon.py               # MODIFIED: add --json to lexicon_refresh
        └── service.py               # MODIFIED: add --json to stop_command

tests/
├── unit/
│   └── krag_cli/                    # CLI --json unit tests
├── contract/
│   └── api/
│       ├── test_index_contract.py   # MODIFIED: /index/status always-list tests
│       ├── test_cors_contract.py            # NEW: CORS middleware tests
│       ├── test_stream_index_contract.py   # NEW: SSE index progress contract tests
│       ├── test_stream_query_contract.py   # NEW: SSE streaming query contract tests
│       └── test_system_contract.py          # MODIFIED: schema import verification
└── live/
    └── test_live_kragd.py           # MODIFIED: add SSE and streaming live tests
```

**Structure Decision**: Single project layout already exists. All changes are modifications to existing files plus two new test files. No new packages or structural changes needed.

## Constitution Re-Check (Post-Design)

*GATE: Re-evaluated after Phase 1 design completion.*

| Principle | Status | Post-Design Notes |
|-----------|--------|-------------------|
| I. Code Quality | PASS | New `sse-starlette` dep is well-maintained (BSD-3, 19.3k dependents). SSE event models are lightweight and well-documented. |
| II. TDD | PASS | Test patterns defined: `TestClient.stream()` for SSE, mock service pattern for contract tests. Live tests added for SSE endpoints. |
| III. UX Consistency | PASS | `/index/status` breaking change is justified: pre-1.0, only consumer (CLI) updated simultaneously, new behavior is more predictable. SSE event format uses consistent `resource:action` naming. |
| IV. Performance | PASS | Thread-to-async bridging uses `asyncio.Queue` (zero-latency wakeup, no polling). LLM streaming releases lock after routing, allowing concurrent non-LLM operations. |
| Python-Specific | PASS | `sse-starlette` added via `uv add`. Pre-commit workflow unchanged. |

**No new violations. All gates PASS.**
