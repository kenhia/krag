# Implementation Plan: Code Quality Sprint

**Branch**: `006-code-quality-sprint` | **Date**: 2026-02-18 | **Spec**: [`spec.md`](spec.md)
**Input**: Feature specification from `/specs/006-code-quality-sprint/spec.md`

## Summary

Fix 32 findings from the post-005 deep code review: 6 correctness bugs (LLM routing, stale vectors, boost weight distortion, chunker state leakage, crash on empty payload, score validation), 4 DRY violations (~80 lines duplicated CLI pipeline, ~200 lines duplicated indexer loop, 3× VRAM function, result construction duplication), 7 consistency issues (XDG config path, error output, exception handling, vector store pre-check, top_k defaults, keyword extraction), 8 design issues (eval lacks LLMPool, dimension enforcement, hardcoded fallback, dead code, unused protocol, Any typing, redundant imports, fragile __del__), 2 logging improvements (reduce upsert noise to ≤10 lines, add `krag log rotate`/`clear` CLI), and 5 additional quality items (progress reporting, integration test, eval metadata, type checking).

Technical approach: Extract shared CLI pipeline factory, extract shared file processor for indexer, consolidate VRAM utility, fix correctness bugs inline, add `krag log` CLI subcommand group.

## Technical Context

**Language/Version**: Python >=3.11, <3.14 (tested on 3.13)
**Primary Dependencies**: typer, sentence-transformers, qdrant-client, llama-cpp-python, pydantic, rich
**Storage**: Qdrant vector store (local file-based), JSON metadata files
**Testing**: pytest (800 tests: unit, integration, contract), pytest-cov
**Target Platform**: Linux (Arch Linux primary), any POSIX with optional CUDA
**Project Type**: Single CLI application with plugin architecture
**Performance Goals**: Indexing ≤10 upsert log entries regardless of corpus size; eval pass rate 3/3
**Constraints**: No new dependencies; backward-compatible with existing config files and vector stores
**Scale/Scope**: ~60 source files, ~1010-line indexer, ~460-line query CLI, ~200-line eval CLI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | ✅ PASS | This sprint directly improves maintainability, modularity, and type safety |
| II. Test-Driven Development | ✅ PASS | 800 existing tests as regression baseline; new integration test for named-vector pipeline (F-30); all refactoring validated by existing test suite |
| III. User Experience Consistency | ✅ PASS | FR-007–011 directly address CLI consistency; new `krag log` commands follow existing CLI patterns |
| IV. Performance & Optimization | ✅ PASS | FR-016 defines measurable logging performance target (≤10 entries); no performance regressions expected |
| Python-Specific Requirements | ✅ PASS | uv for deps, ruff format + ruff check before commit, pytest for validation |
| Pre-Commit Validation | ✅ PASS | All changes validated via `uv run ruff format . && uv run ruff check --fix . && uv run pytest` |
| Phase Completion Gates | ✅ PASS | Plan → tasks → implement workflow with gates |

**Gate result**: PASS — no violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/006-code-quality-sprint/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (entities: Pipeline, FileProcessor, LogManager)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal API contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/krag/
├── cli/
│   ├── main.py          # Typer app entry point (add `log` subcommand group)
│   ├── pipeline.py      # NEW: Shared CLI pipeline factory (FR-012)
│   ├── log.py           # NEW: `krag log rotate`/`clear` commands (FR-017, FR-018)
│   ├── query.py         # MODIFY: Use pipeline.py, remove duplication
│   ├── eval.py          # MODIFY: Use pipeline.py, remove duplication
│   ├── index.py         # MODIFY: Minor consistency fixes
│   ├── config.py        # Existing
│   ├── gpu.py           # MODIFY: Consolidate VRAM checking here
│   ├── plugin.py        # Existing
│   └── utils.py         # Existing
├── config/
│   ├── logging.py       # MODIFY: Add log path resolution helper for CLI
│   └── xdg.py           # Existing (already correct)
├── embeddings/
│   ├── orchestrator.py  # MODIFY: Remove _get_free_vram(), fix dimension check
│   └── generator.py     # Existing
├── models/
│   └── query_result.py  # MODIFY: Remove le=1.0 constraint
├── orchestration/
│   └── indexer.py       # MODIFY: Extract _process_file(), fix stale chunker,
│                        #   fix plugin name, remove __del__, fix imports
├── retrieval/
│   ├── retriever.py     # MODIFY: Fix boost weights, fix empty path crash,
│   │                    #   extract _payload_to_query_result()
│   └── rrf.py           # MODIFY: Use ScoredPointLike or remove it
├── storage/
│   └── qdrant_impl.py   # MODIFY: Reduce upsert log noise, document "text" invariant
└── synthesis/
    ├── llm_pool.py      # MODIFY: Fix CODE_EXTENSIONS check, remove _get_free_vram()
    └── llm_client.py    # Existing

tests/
├── unit/
│   ├── cli/
│   │   ├── test_pipeline.py  # NEW: Tests for shared pipeline factory
│   │   └── test_log.py       # NEW: Tests for log rotate/clear
│   └── test_retriever.py     # MODIFY: Add RRF boost scaling tests
├── integration/
│   └── test_named_vector_query_pipeline.py  # NEW: End-to-end named vector + RRF test
└── contract/
    └── (existing contracts adequate)
```

**Structure Decision**: Single project. All changes are modifications to existing modules or new files within the established `src/krag/` and `tests/` structure. Two new source files (`cli/pipeline.py`, `cli/log.py`) and three new test files.
