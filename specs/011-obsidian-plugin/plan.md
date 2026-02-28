# Implementation Plan: Obsidian Vault Plugin

**Branch**: `011-obsidian-plugin` | **Date**: 2026-02-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-obsidian-plugin/spec.md`

## Summary

A krag file-type plugin for Obsidian vault content that claims `.md` files by vault path (not just extension), splits mixed content into prose (→ `docs`) and fenced code blocks (→ `code`), stores chunks under virtual `obsidian://` path prefixes, and provides a custom retrieval mode plus domain lexicon. Requires extending the core plugin architecture with `claims_file()` for path-based resolution and per-chunk collection routing via payload metadata.

## Technical Context

**Language/Version**: Python 3.11–3.13
**Primary Dependencies**: krag (core), pyyaml (frontmatter parsing), pydantic (config schema)
**Storage**: Qdrant (existing `krag_docs` and `krag_code` collections via CollectionManager)
**Testing**: pytest (unit + integration + contract + live tests per constitution)
**Target Platform**: Linux (primary), macOS compatible
**Project Type**: Single project (plugin package under `examples/`)
**Performance Goals**: <10ms overhead per file for path-based resolution (SC-005); 10k notes without errors (SC-007)
**Constraints**: No file I/O in `claims_file()` — path prefix checks only; backward compatible with all existing plugins
**Scale/Scope**: Vaults up to 10,000 notes; 1–5 configured vaults per user

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | PASS | Plugin follows existing patterns; docstrings on all public interfaces; type hints throughout |
| II. TDD (Non-Negotiable) | PASS | Tests first for: `claims_file`, content splitting, virtual paths, routing, config validation. Live tests for end-to-end vault indexing + query. |
| III. User Experience Consistency | PASS | Plugin uses existing CLI/API — no new interfaces. Virtual paths in results are clear and consistent. Error messages guide resolution. |
| IV. Performance & Optimization | PASS | SC-005 defines per-file overhead target. `claims_file()` is pure string ops (<1μs). |
| Pre-Commit Validation | PASS | `ruff format` → `ruff check --fix` → `pytest` before every commit |
| Phase Completion Gates | PASS | Each story is independently testable per spec |
| Version Control Discipline | PASS | Conventional commits; commit before each phase |
| Live Test Maintenance | PASS | Live tests required for: vault indexing, mixed-content routing, virtual path display, mode query |

**Post-Phase 1 Re-check**: PASS — no design decisions violate constitution. The per-chunk routing extends the indexer minimally (~10 lines in two places); `claims_file()` default `False` preserves backward compatibility. TDD applies to all new code.

## Project Structure

### Documentation (this feature)

```text
specs/011-obsidian-plugin/
├── plan.md              # This file
├── research.md          # Phase 0: Technical research findings
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: User-facing setup guide
├── contracts/           # Phase 1: Interface & API contracts
│   ├── plugin-interface.md   # FileTypeHandler extension, registry changes, chunk routing
│   ├── configuration.md      # Plugin config schema & validation
│   ├── retrieval-mode.md     # obsidian.toml mode definition
│   └── lexicon.md            # LexiconStore extension & Obsidian terms
└── tasks.md             # Phase 2: Task breakdown (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Core changes (existing files)
src/krag/
├── plugins/
│   ├── interfaces.py        # Add claims_file() method to FileTypeHandler
│   └── registry.py          # Add _resolve_by_path_claim(), modify get_handler_for_file()
├── orchestration/
│   └── indexer.py            # Add per-chunk target_collection routing in index_full/incremental
├── lexicon/
│   └── lexicon_store.py      # Add merge_entries() method
└── modes/builtin/
    └── obsidian.toml         # New retrieval mode file

# New plugin package
examples/krag-plugin-obsidian/
├── pyproject.toml
├── README.md
├── src/
│   └── krag_plugin_obsidian/
│       ├── __init__.py
│       ├── handler.py        # ObsidianFileTypeHandler
│       ├── chunker.py        # ObsidianChunker (content splitting + routing metadata)
│       ├── config.py         # ObsidianConfig (Pydantic schema)
│       └── lexicon.json      # Bundled Obsidian terms
└── tests/
    ├── test_handler.py       # Handler tests (claims_file, extract_text, virtual paths)
    ├── test_chunker.py       # Content splitting tests (prose vs code blocks)
    └── test_config.py        # Config validation tests

# Core tests
tests/
├── unit/
│   ├── test_claims_file.py           # FileTypeHandler.claims_file() default behavior
│   ├── test_registry_path_claim.py   # Path-based resolution priority
│   └── test_chunk_routing.py         # Per-chunk target_collection routing
├── integration/
│   └── test_obsidian_indexing.py     # End-to-end indexing with mixed content
└── live/
    └── test_live_obsidian.py         # Live tests against kragd with vault content
```

**Structure Decision**: Single project — the Obsidian plugin is a separate package under `examples/` (consistent with `krag-plugin-code`, `krag-plugin-logs`, `krag-plugin-markdown`). Core changes are minimal modifications to existing files.

## Complexity Tracking

No constitution violations to justify. All changes are within normal complexity bounds:
- One new method on existing ABC (backward compatible default)
- ~10 lines of routing logic in indexer (two places)
- One new method on `LexiconStore`
- One new TOML file (zero code for mode)
- One new plugin package (follows established pattern)
