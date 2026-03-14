# Implementation Plan: Debug Metadata Accuracy & Retrieval Completeness

**Branch**: `015-retrieval-accuracy` | **Date**: 2026-03-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/015-retrieval-accuracy/spec.md`

## Summary

Fix debug metadata accuracy for multi-collection retrieval (per_space_result_counts shows `{'default': 120}` instead of per-collection breakdown), unify multi-model and multi-collection retrieval paths so secondary embedding models are used during cross-collection search, and add health-endpoint log suppression to reduce log noise from monitoring probes.

## Technical Context

**Language/Version**: Python >=3.11, <3.14  
**Primary Dependencies**: FastAPI >=0.115.0, uvicorn[standard] >=0.34.0, qdrant-client >=1.8.0, sentence-transformers >=2.3.0  
**Storage**: Qdrant (file-based, shared single client) with 4 collections: code, tests, docs, text  
**Testing**: pytest >=9.0.2, pytest-cov, pytest-httpx, pytest-asyncio  
**Target Platform**: Linux server (Ubuntu 22.04, CUDA 12.4)  
**Project Type**: Single Python project with FastAPI service layer  
**Performance Goals**: No regression in query latency; multi-collection + multi-model path should be ≤1.5× the latency of multi-collection single-model  
**Constraints**: GPU VRAM budget enforced by orchestrator (1.2 GB per model); RRF merge is CPU-bound and lightweight  
**Scale/Scope**: 4 collections, 2 embedding models, typical queries return 60-120 candidates per collection

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | ✅ PASS | Changes confined to existing modules with clear interfaces |
| II. TDD (NON-NEGOTIABLE) | ✅ PASS | Tests first for all three stories; live tests required per constitution |
| III. User Experience Consistency | ✅ PASS | Debug output format preserved; log suppression is transparent to users |
| IV. Performance & Optimization | ✅ PASS | Performance constraint defined (≤1.5× latency); no new allocations in hot path beyond additional vector-space searches |
| Pre-Commit Validation (NON-NEGOTIABLE) | ✅ PASS | `ruff format` + `ruff check --fix` + `pytest` before every commit |
| Terminal Reuse | ✅ PASS | Single terminal for all commands |

**Gate result: PASS** — no violations, no justifications needed.

## Project Structure

### Documentation (this feature)

```text
specs/015-retrieval-accuracy/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (affected files)

```text
src/
├── krag/
│   ├── retrieval/
│   │   ├── retriever.py          # P1: _last_per_space_counts in _multi_collection_retrieve
│   │   │                         # P2: multi-model within _multi_collection_retrieve
│   │   └── rrf.py                # Unweighted RRF utility (no changes expected)
│   ├── embeddings/
│   │   └── orchestrator.py       # embed_query() — already supports multi-model
│   └── storage/
│       ├── qdrant_impl.py        # search_named() — already supports named vectors
│       └── collection_manager.py # collection access
├── kragd/
│   ├── service.py                # P1: debug metadata builder (~line 630-696)
│   ├── app.py                    # P3: health-log suppression middleware
│   └── routers/
│       └── system.py             # GET /health endpoint
└── ...

tests/
├── unit/
│   ├── test_retriever_debug_metadata.py  # P1: debug metadata unit tests (new)
│   ├── test_retriever_multi_collection.py # P2: multi-collection retrieval tests (new)
│   ├── test_service_debug_metadata.py    # P1: service debug metadata tests (new)
│   ├── test_rrf_merge.py                 # RRF tests (existing)
│   └── test_health_log_filter.py         # P3: middleware unit tests (new)
├── integration/
│   └── test_multi_collection.py          # P2: integration test for combined path (new)
└── live/
    └── test_live_kragd.py                # Retest all three stories live
```

**Structure Decision**: Single Python project. All changes are within existing `src/krag/` and `src/kragd/` packages. New test files for retriever debug metadata, multi-collection retrieval, service debug metadata, and health-log middleware.

## Constitution Check — Post-Design Re-evaluation

*GATE: Re-checked after Phase 1 design completion.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | ✅ PASS | Contracts use existing types (`RRFScoredPoint`, `QueryResult`); no new public APIs; changes are internal to existing modules |
| II. TDD (NON-NEGOTIABLE) | ✅ PASS | Test files identified: extend `test_retriever.py`, new `test_health_log.py`, extend `test_live_kragd.py`. Red-green-refactor mandated in quickstart. |
| III. User Experience Consistency | ✅ PASS | `DebugMetadata` schema unchanged; key semantics shift from "default" to collection names — this is a bug fix, not a breaking change. Health-log suppression is transparent to API consumers. |
| IV. Performance & Optimization | ✅ PASS | Two-level RRF adds one `reciprocal_rank_fusion()` call per collection (CPU-bound, sub-ms). Multi-model adds `search_named()` calls per space per collection — bounded by VRAM budget (max 2 models). Performance target: ≤1.5× current latency. |
| Pre-Commit Validation (NON-NEGOTIABLE) | ✅ PASS | `ruff format` + `ruff check --fix` + `pytest` before every commit — enforced in quickstart dev loop. |
| Terminal Reuse | ✅ PASS | Single terminal for all commands. |

**Gate result: PASS** — no violations found post-design. No complexity tracking entries needed.

## Complexity Tracking

> No constitution violations — section not applicable.
