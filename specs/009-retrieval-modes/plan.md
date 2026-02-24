# Implementation Plan: Retrieval Modes, Multi-Collection Qdrant, Domain Lexicon, and Context Critic

**Branch**: `009-retrieval-modes` | **Date**: 2026-02-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-retrieval-modes/spec.md`

## Summary

Sprint 009 adds four capabilities to krag's retrieval pipeline: (1) multi-collection Qdrant storage that partitions indexed content into four collections (code, tests, docs, text) by content type, (2) a mode system that replaces the `--llm` flag with a richer `--mode` flag bundling collection targeting, LLM selection, prompt preset, and retrieval parameters into TOML-defined configurations, (3) a domain lexicon system that injects project-specific terminology into prompts from a JSON glossary, and (4) a context relevance critic that scores retrieved chunks on a 0–5 scale and filters low-relevance content before synthesis. A prerequisite lifecycle timer race fix ensures the service reliably reloads LLMs after indexing.

## Technical Context

**Language/Version**: Python 3.11–3.13 (requires-python = ">=3.11,<3.14")
**Primary Dependencies**: FastAPI >=0.115.0, Typer >=0.9.0, qdrant-client >=1.8.0, sentence-transformers >=2.3.0, llama-cpp-python >=0.2.90, pydantic >=2.6.0, pydantic-settings >=2.2.0, httpx >=0.28.0, rich >=13.0.0, tomli-w >=1.0.0
**Storage**: Qdrant (embedded file-based via qdrant-client, stored at `~/.cache/krag/storage`)
**Testing**: pytest >=9.0.2, pytest-cov, pytest-httpx, pytest-asyncio; 1056 tests passing, 2 skipped
**Target Platform**: Linux (local-first, GPU-accelerated via CUDA)
**Project Type**: Three-package monorepo (`krag` core, `krag_cli` client, `kragd` service)
**Performance Goals**: Mode selection <1s latency overhead; critic scoring should not exceed 2× query latency when enabled
**Constraints**: Single-GPU VRAM management (hot-swap or simultaneous LLMs); offline-only (no cloud); backward-compatible `--llm` flag
**Scale/Scope**: Personal use, indexing up to ~100K files across multiple project directories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | PASS | All new modules will have docstrings, type hints, consistent patterns. Ruff format/check enforced. |
| II. Test-Driven Development | PASS | Each story is independently testable. Unit, integration, and contract tests required for every new module. Red-green-refactor workflow. |
| III. User Experience Consistency | PASS | `--mode` replaces `--llm` with deprecation warning. CLI interface patterns preserved. Error messages guide users. |
| IV. Performance & Optimization | PASS | Critic disabled by default (no perf impact). Mode selection is config lookup only. Multi-collection query adds RRF merge (already exists). |
| Python-Specific Requirements | PASS | uv, ruff format, ruff check, pytest pre-commit workflow. pyproject.toml maintained. |
| Pre-Commit Validation | PASS | All commits run format → lint → test before merge. |

No violations. Gate passed.

## Project Structure

### Documentation (this feature)

```text
specs/009-retrieval-modes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── mode-schema.toml
│   ├── lexicon-schema.json
│   └── api-extensions.md
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── krag/
│   ├── models/
│   │   └── configuration.py     # + ModeConfiguration, LexiconConfiguration, CriticConfiguration
│   ├── config/
│   │   └── settings.py          # + mode loading, lexicon path resolution
│   ├── routing/                  # NEW — collection routing
│   │   ├── __init__.py
│   │   ├── collection_router.py # Routes files to collections by type/path
│   │   └── rules.py             # Routing rule definitions
│   ├── modes/                    # NEW — mode system
│   │   ├── __init__.py
│   │   ├── mode_loader.py       # Loads/validates mode TOML files
│   │   ├── mode_registry.py     # Registry of built-in + custom modes
│   │   └── builtin/             # Built-in mode TOML files
│   │       ├── default.toml
│   │       ├── code.toml
│   │       └── docs.toml
│   ├── lexicon/                  # NEW — domain lexicon
│   │   ├── __init__.py
│   │   ├── lexicon_store.py     # Loads/validates/queries lexicon JSON
│   │   └── lexicon_injector.py  # Selects relevant terms, formats for prompt
│   ├── critic/                   # NEW — context relevance critic
│   │   ├── __init__.py
│   │   └── relevance_critic.py  # Scores chunks, filters by threshold
│   ├── retrieval/
│   │   └── retriever.py         # + multi-collection retrieve, weighted fusion
│   ├── storage/
│   │   ├── qdrant_impl.py       # + multi-collection management
│   │   └── collection_manager.py # NEW — creates/manages 4 collections
│   ├── synthesis/
│   │   └── prompt_builder.py    # + lexicon injection point
│   ├── orchestration/
│   │   ├── indexer.py           # + collection routing during indexing
│   │   └── query_engine.py      # + mode-aware query orchestration
│   └── cli/
│       ├── query.py             # + --mode flag (krag-direct)
│       └── modes.py             # NEW — krag-direct modes list/show
├── krag_cli/
│   ├── commands/
│   │   ├── query.py             # + --mode flag, --llm deprecation
│   │   ├── modes.py             # NEW — krag modes list/show
│   │   └── lexicon.py           # NEW — krag lexicon refresh
│   └── client.py                # + mode parameter, lexicon endpoints
└── kragd/
    ├── lifecycle.py             # + pause/resume timer for indexing
    ├── service.py               # + mode-aware query, multi-collection init, lexicon, critic
    └── routers/
        ├── query.py             # + mode parameter in request schema
        ├── modes.py             # NEW — GET /modes, GET /modes/{name}
        └── lexicon.py           # NEW — POST /lexicon/refresh

tests/
├── unit/
│   ├── test_collection_router.py    # NEW
│   ├── test_mode_loader.py          # NEW
│   ├── test_mode_registry.py        # NEW
│   ├── test_lexicon_store.py        # NEW
│   ├── test_lexicon_injector.py     # NEW
│   ├── test_relevance_critic.py     # NEW
│   ├── test_collection_manager.py   # NEW
│   └── kragd/
│       └── test_lifecycle.py        # + timer pause/resume tests
├── integration/
│   ├── test_multi_collection_indexing.py  # NEW
│   ├── test_mode_query.py                # NEW
│   ├── test_lexicon_injection.py         # NEW
│   └── test_critic_filtering.py          # NEW
└── contract/
    ├── test_mode_contract.py        # NEW
    ├── test_lexicon_contract.py     # NEW
    └── test_critic_contract.py      # NEW
```

**Structure Decision**: Extends the existing three-package monorepo. Four new subpackages (`routing`, `modes`, `lexicon`, `critic`) in `krag` core follow the established pattern of one-responsibility modules. No new top-level packages needed.

## Constitution Re-Check (Post-Design)

*Re-evaluated after Phase 1 design artifacts (data-model, contracts, quickstart) are complete.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | PASS | All 8 new entities have clear interfaces with docstrings and type hints. Contracts define schemas for validation. Consistent patterns (BaseModel for config, re-export via __init__.py). |
| II. Test-Driven Development | PASS | Quickstart specifies test files for every step. Unit (7 new files), integration (4), and contract (3) tests planned per story. Each story is independently testable and deliverable. |
| III. User Experience Consistency | PASS | `--mode` flag follows existing `--llm` pattern. Deprecation warning guides migration. `krag modes list/show` follows `krag config list/show` pattern. Error messages specified in contracts. |
| IV. Performance & Optimization | PASS | Critic disabled by default (FR-032). Mode selection is config dict lookup (<1ms). Collection routing is O(1) rule matching. RRF merge already exists. Performance targets defined: <1s mode overhead, critic ≤2× query latency. |
| Python-Specific Requirements | PASS | No new dependencies — all stdlib (tomllib, json, re, asyncio). pyproject.toml unchanged. uv/ruff/pytest workflow preserved. |
| Pre-Commit Validation | PASS | Quickstart ends with full format → lint → test workflow. Each step includes verification commands. |

No violations. All design decisions comply with the constitution. Gate passed.
