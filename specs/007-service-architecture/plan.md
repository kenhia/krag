# Implementation Plan: Service Architecture

**Branch**: `007-service-architecture` | **Date**: 2026-02-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-service-architecture/spec.md`

## Summary

Convert krag from a CLI-only tool into a service-based architecture. A new daemon (`kragd`) exposes the existing orchestration/core layers via a FastAPI REST API, keeping LLMs and embedding models loaded in memory between requests. A new thin CLI client (`krag`) communicates with `kragd` over HTTP and renders responses with Rich. The existing CLI is preserved as `krag-direct` for in-process fallback. New debug endpoints expose retrieval metadata and raw Qdrant search. LLM lifecycle is configurable: primary LLM stays loaded, secondary unloads after idle timeout.

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11,<3.14"`)
**Primary Dependencies** (new): FastAPI >=0.115.0, uvicorn[standard] >=0.34.0, httpx >=0.28.0
**Primary Dependencies** (existing, reused): Pydantic >=2.6.0, Typer >=0.9.0, Rich >=13.0.0, llama-cpp-python >=0.2.90, sentence-transformers >=2.3.0, qdrant-client >=1.8.0
**Storage**: Qdrant (embedded mode via filesystem path — no network Qdrant server)
**Testing**: pytest (800 tests passing), pytest-httpx (new, for CLI client HTTP mocking)
**Target Platform**: Linux (WSL2 / native), single-user workstation
**Project Type**: Single mono-repo with 3 co-located Python packages (`krag`, `kragd`, `krag_cli`)
**Performance Goals**: Eliminate 5-15s cold-start per query; second query within 2s of first completing; health endpoint <500ms while secondary LLM loads
**Constraints**: Single-user, single concurrent query (serialized via LLMPool threading.Lock); no auth required; LLM inference is synchronous/blocking
**Scale/Scope**: ~6,800 vectors, 1 user, 1-2 LLMs loaded, local network access

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Code Quality & Standards — PASS

- All new code in `kragd` and `krag_cli` will follow existing patterns: type hints, docstrings on all public interfaces, ruff format/check compliance.
- Pydantic models for API schemas follow existing `src/krag/models/` conventions.

### II. Test-Driven Development (TDD) — PASS

- **Red-Green-Refactor**: All new packages (`kragd`, `krag_cli`) developed with TDD.
- **Unit tests**: KragService, LLMLifecycleManager, API route handlers, CLI client, display formatting.
- **Integration tests**: FastAPI TestClient round-trips, kragd↔krag HTTP round-trip.
- **Contract tests**: API request/response schemas validated against spec contracts.
- **Pre-commit gate**: `ruff format . && ruff check --fix . && pytest` must pass before every commit.

### III. User Experience Consistency — PASS

- CLI output from `krag query` via service is visually identical to current direct-mode output (SC-002).
- Error messages for unreachable service include actionable instructions (FR-026).
- `krag-direct` preserves 100% backward compatibility (FR-031, FR-032).

### IV. Performance & Optimization — PASS

- Performance targets defined: SC-001 (2s second query), SC-005 (health <500ms during load), SC-010 (startup time reported).
- LLM inference synchronous — FastAPI `def` handlers dispatch to thread pool (no event loop blocking).
- Embedding models stay loaded for service lifetime (FR-014).

### V. Pre-Commit Validation — PASS

- Workflow: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
- All three must pass before any commit.
- New dev dependency `pytest-httpx` added to pyproject.toml.

### Gate Result: **ALL GATES PASS** — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/007-service-architecture/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── krag/                    # Core library (UNCHANGED)
│   ├── cli/                 # Retained as krag-direct entry point
│   │   ├── main.py          # Typer app (becomes krag-direct)
│   │   ├── pipeline.py      # build_query_pipeline() — reused by KragService
│   │   ├── query.py
│   │   └── ...
│   ├── config/              # ConfigManager, settings, defaults
│   ├── models/              # Pydantic models (Configuration, QueryResult, IndexingJob, etc.)
│   ├── orchestration/       # QueryEngine, IndexingOrchestrator
│   ├── retrieval/           # Retriever (dedup, boost, RRF)
│   ├── synthesis/           # LLMPool, LLMClient, PromptBuilder
│   ├── embeddings/          # EmbeddingGenerator, EmbeddingOrchestrator
│   ├── storage/             # QdrantVectorStore
│   └── ...
│
├── kragd/                   # Service daemon (NEW)
│   ├── __init__.py
│   ├── __main__.py          # Entry: python -m kragd / kragd CLI
│   ├── app.py               # FastAPI app factory with lifespan
│   ├── service.py           # KragService: lifecycle, component ownership
│   ├── lifecycle.py         # LLMLifecycleManager: primary/secondary/idle timeout
│   ├── schemas.py           # Pydantic request/response models (API-facing)
│   └── routers/
│       ├── __init__.py
│       ├── query.py         # POST /query, POST /retrieve
│       ├── index.py         # POST /index, GET /index/status
│       ├── debug.py         # POST /debug/query, POST /debug/qdrant
│       └── system.py        # GET /health, GET /status, POST /shutdown
│
└── krag_cli/                # CLI client (NEW)
    ├── __init__.py
    ├── __main__.py           # Entry: python -m krag_cli
    ├── main.py               # Typer app with subcommands
    ├── client.py             # KragClient: httpx wrapper
    ├── config.py             # CLI-local config (server URL, timeout)
    ├── display.py            # Rich output formatting (match existing look)
    └── commands/
        ├── __init__.py
        ├── query.py          # krag query ...
        ├── index.py          # krag index ...
        ├── debug.py          # krag debug query ..., krag debug qdrant ...
        ├── status.py         # krag status, krag health
        └── service.py        # krag start, krag stop

tests/
├── unit/
│   ├── kragd/               # KragService, LLMLifecycleManager, schemas
│   └── krag_cli/            # KragClient, commands, display
├── integration/
│   └── service/             # FastAPI TestClient, kragd↔krag round-trips
├── contract/
│   └── api/                 # Schema validation against OpenAPI contracts
└── ...                      # Existing test directories (unchanged)
```

**Structure Decision**: Single mono-repo with 3 co-located packages under `src/`. This matches the existing `src/krag/` layout and keeps the build system simple (one `pyproject.toml` with three `[project.scripts]` entries). The core library (`krag`) is unchanged; `kragd` and `krag_cli` are new consumers at the same architectural level as the existing CLI.

## Complexity Tracking

No constitution violations to justify. The project stays within single-repo, single-build-system boundaries. The three packages are co-located under `src/` and share the same `pyproject.toml`, so this is not a multi-project setup — it's a mono-repo with multiple entry points, which is a standard Python pattern.
