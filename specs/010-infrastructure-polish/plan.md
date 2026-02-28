# Implementation Plan: Infrastructure Improvements & Polish

**Branch**: `010-infrastructure-polish` | **Date**: 2026-02-23 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/010-infrastructure-polish/spec.md`  

## Summary

This sprint addresses 10 areas of infrastructure debt: two correctness bugs (incremental indexing metadata loss, stale index-status), one architectural unification (query/debug-query paths), one feature migration (code embedding into core), operational UX improvements, concurrency safety for the query engine, dead code/dependency cleanup, exception architecture overhaul, CLI consistency fixes, and plugin registry hardening. Additionally, a live integration test suite was added to validate kragd end-to-end against a running instance, catching real-world issues (filesystem PermissionError propagation, VRAM exhaustion, cross-directory index deletion) that unit tests cannot detect. No new external dependencies are required — all work uses the existing Python 3.11+ / FastAPI / Qdrant / Rich / Typer stack.

## Technical Context

**Language/Version**: Python 3.11+ (requires-python = ">=3.11,<3.14")  
**Primary Dependencies**: FastAPI 0.115+, Qdrant-client 1.8+, sentence-transformers 2.3+, llama-cpp-python 0.2.90+, Rich 13+, Typer 0.9+, Pydantic 2.6+, uvicorn 0.34+, httpx 0.28+  
**Storage**: Qdrant (vector store), filesystem (metadata.json, TOML config, mode files, logs)  
**Testing**: pytest with pytest-cov, pytest-httpx, pytest-asyncio  
**Target Platform**: Linux (WSL2) — local developer workstation  
**Project Type**: Single Python project with 3 packages (`krag`, `kragd`, `krag_cli`)  
**Performance Goals**: Query requests must remain non-blocking under concurrent load; indexing metadata merge must not regress indexing throughput  
**Constraints**: No new runtime dependencies; thread safety without serialising queries; backward-compatible config format
**Scale/Scope**: Personal RAG system, single-user, ~100k indexed files at peak  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | PASS | All changes maintain existing ruff/mypy compliance. Removing dead code and unused deps improves maintainability. |
| II. Test-Driven Development | PASS | Each user story has independent acceptance tests defined. New domain exceptions, concurrency changes, and metadata merge logic all require tests written first. |
| III. User Experience Consistency | PASS | CLI flag unification (US9), uniform error messages, rich markdown output all improve UX consistency. No public API breaking changes. |
| IV. Performance & Optimization | PASS | Concurrency fix (US6) eliminates query serialisation. Mode file caching (FR-020) reduces per-request I/O. No new performance-critical paths introduced. |
| Pre-Commit Validation | PASS | Standard workflow: `uv run ruff format . && uv run ruff check --fix . && uv run pytest` before every commit. |
| Phase Completion Gates | PASS | Each US is independently testable and deliverable. |

**Gate result: PASS — no violations; proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/010-infrastructure-polish/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-changes.md   # HTTP API contract changes (exception types → status codes)
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── krag/                    # Core library
│   ├── cli/                 # Direct CLI (krag-direct)
│   │   └── modes.py         # US9: fix find_and_load() call
│   ├── config/
│   │   ├── defaults.py      # US7: remove duplicate DEFAULT_VECTOR_STORE_PATH
│   │   └── settings.py      # US4: add [embedding_code] parsing; US9: add find_and_load()
│   ├── models/
│   │   ├── configuration.py # US4: add EmbeddingCodeConfig fields
│   │   └── exceptions.py    # US8: add ServiceNotReadyError, IndexingInProgressError, etc.
│   ├── orchestration/
│   │   └── indexer.py       # US1: metadata merge logic; US8: replace silent excepts
│   ├── plugins/
│   │   ├── failures.py      # US6: thread-safe _failures list
│   │   ├── loader.py        # US10: remove inspect.signature guard
│   │   └── registry.py      # US10: auto-call _build_extension_map() in discover_plugins()
│   ├── lexicon/
│   │   └── lexicon_store.py # US8: LexiconValidationError → KragError
│   ├── evaluation/
│   │   └── loader.py        # US8: EvalLoadError → KragError
│   └── modes/
│       └── mode_registry.py # US6: cached/debounced mode file reload
├── kragd/                   # Service daemon
│   ├── app.py               # US8: isinstance-based exception handler
│   ├── service.py           # US1-US4, US6: core fixes (metadata, status, query, concurrency)
│   ├── schemas.py           # US10: rename IndexError → IndexingFileError
│   └── routers/
│       └── health.py        # US7: DELETE this file
└── krag_cli/                # Typer CLI client
    ├── commands/
    │   ├── debug.py         # US9: add --mode option
    │   ├── index.py         # US9: uniform error prefix
    │   ├── query.py         # US5: rich markdown; US9: fix find_and_load()
    │   └── ...              # US9: consistent --json naming
    └── main.py              # US5: rich markdown rendering

tests/
├── unit/
│   ├── test_metadata_merge.py        # US1: metadata persistence across directory changes
│   ├── test_index_status_accuracy.py # US2: running vs cached status
│   ├── test_query_debug_unified.py   # US3: identical results with/without debug
│   ├── test_embedding_code_config.py # US4: [embedding_code] config parsing
│   ├── test_domain_exceptions.py     # US8: exception hierarchy and handler dispatch
│   ├── test_concurrency_safety.py    # US6: concurrent query isolation
│   └── test_plugin_registry.py       # US10: auto extension map build
├── contract/
│   └── test_api_error_codes.py       # US8: HTTP status codes from domain exceptions
└── integration/
    └── test_metadata_roundtrip.py    # US1: end-to-end metadata merge with vector store

tests/live/                              # US11: Live integration tests (against running kragd)
├── __init__.py
├── conftest.py                          # Session fixtures: client, directories, poll helpers
└── test_live_kragd.py                   # 36 tests across 9 ordered phases
```

**Structure Decision**: Existing single-project layout (`src/krag`, `src/kragd`, `src/krag_cli`) with `tests/{unit,contract,integration}` — no structural changes needed. Live tests added under `tests/live/` with `@pytest.mark.live` marker, excluded from default pytest runs.

## Complexity Tracking

> No constitution violations — this section is intentionally empty.

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design completion.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | PASS | New exception classes follow existing patterns with docstrings. Schema rename eliminates builtin shadowing. Dead code removal improves maintainability. |
| II. Test-Driven Development | PASS | Each US has defined test files. Exception dispatch, concurrency isolation, metadata merge, and config parsing all have specific unit/contract tests planned. |
| III. User Experience Consistency | PASS | CLI error prefixes unified. `--mode` added to debug query. `--json` naming standardized. No public HTTP API schema changes (wire format identical). |
| IV. Performance & Optimization | PASS | Pass-as-parameter pattern for query isolation adds zero overhead vs current mutate-and-restore. Mode reload debounce reduces per-request I/O. Lock contention is negligible (short critical sections). |
| Pre-Commit Validation | PASS | No workflow changes. |

**Post-design gate: PASS — proceed to Phase 2 (tasks).**
