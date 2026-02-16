# Implementation Plan: WSL to Native Linux Migration

**Branch**: `003-wsl-migration` | **Date**: 2026-02-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-wsl-migration/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Migrate krag from WSL to native Arch Linux with:
1. **Configurable storage paths** — Add config fields for vector store, model cache, and corpus paths with XDG defaults
2. **Group-based permissions** — Document setup for shared `/krag` access via UNIX group
3. **Python 3.13+ support** — Validate dependencies and update `pyproject.toml` to support Python 3.13
4. **GPU acceleration** — Add `n_gpu_layers` config field for LLM GPU offloading; existing `embedding_device` handles embeddings
5. **Enhanced config commands** — Extend `krag config show` and `validate` to report resolved storage paths and check accessibility

## Technical Context

**Language/Version**: Python 3.13+ (maintaining 3.11/3.12 compatibility if feasible)  
**Primary Dependencies**: 
  - `uv` — dependency management and virtual environments
  - `ruff` — formatting and linting
  - `pytest` — testing framework (551 existing tests)
  - `pydantic` v2 + `pydantic-settings` — configuration models with env var support
  - `sentence-transformers` — embeddings (GPU acceleration via PyTorch CUDA)
  - `llama-cpp-python` — local LLM inference (requires CUDA rebuild for GPU support)
  - `qdrant-client` — vector store (local file-based storage)
  - `typer` — CLI framework
  - `rich` — terminal UI
  
**Storage**: 
  - Vector store: Qdrant (local files at configurable path, default `~/.cache/krag/storage`)
  - Model cache: Local GGUF files (configurable path, default `~/.cache/krag/models`)
  - Logs: Rotating file logs (XDG state dir, default `~/.local/state/krag/logs`)
  - Metadata: JSON files (XDG state dir)
  - Corpus: User-provided directories (specified in `config.toml`)
  
**Testing**: pytest with contract/integration/unit test structure (551 existing tests)  
**Target Platform**: Linux (native Arch, previously WSL), NVIDIA GPU support  
**Project Type**: Single project (CLI application + library)  
**Performance Goals**: 
  - Embedding generation: 5x faster on GPU vs CPU
  - LLM inference: Noticeable speedup with GPU layer offloading
  - Indexing: Handle corpora with 1000+ files efficiently
  
**Constraints**: 
  - XDG Base Directory compliance (config/cache/state separation)
  - Config file paths must override XDG env vars
  - Backward compatibility with existing configs and vector stores
  - No breaking changes to public CLI interface
  
**Scale/Scope**: 
  - Personal/small team use (single user per instance)
  - 100k+ document corpora
  - Support for plugin architecture (chunking, extraction)
  - Local-first operation (no cloud dependencies)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design (Phase 0 Gate)

✅ **Code Quality & Standards** — Feature extends existing config system following established patterns (Pydantic models, XDG helpers, CLI commands). No new architectural patterns introduced.

✅ **Test-Driven Development** — Existing test suite (551 tests) provides baseline. New config fields, path resolution, and validation logic will follow TDD with contract/integration/unit tests.

✅ **User Experience Consistency** — Changes are backward compatible (XDG defaults preserved, new config fields optional). CLI interface (`krag config show`, `validate`) extended consistently.

✅ **Performance & Optimization** — Performance targets defined in spec (5x GPU speedup for embeddings). Storage path changes are file I/O configuration (no algorithmic impact).

✅ **Pre-Commit Validation** — Existing workflow (`uv run ruff format`, `ruff check --fix`, `pytest`) continues. All changes will be validated before commit.

**Gate Status**: ✅ PASS — No constitution violations. Feature is additive (config fields, documentation) with no breaking changes to core architecture.

### Post-Design (Phase 1 Gate)

✅ **Code Quality & Standards** — Design artifacts (data-model.md, contracts/) follow established documentation patterns. Implementation plan maintains modular structure (config, models, CLI, orchestration modules).

✅ **Test-Driven Development** — Testing contracts defined in CLI and config schema documents. Test coverage includes unit tests (field validation), integration tests (end-to-end with custom paths), and contract tests (GPU layer offloading).

✅ **User Experience Consistency** — CLI enhancements (`krag config show`, `krag gpu status`) provide additional diagnostics without changing existing behavior. Error messages give clear guidance for path and GPU configuration issues.

✅ **Performance & Optimization** — GPU configuration documented with specific recommendations (RTX 4080: n_gpu_layers=-1). Performance impact measured in quickstart (10x embedding speedup, 4x+ LLM speedup).

✅ **Pre-Commit Validation** — No changes to validation workflow. All code changes subject to existing pre-commit gates.

**Gate Status**: ✅ PASS — Design maintains constitution compliance. No new complexity introduced; all changes extend existing patterns.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project structure (Python CLI + library)
src/krag/
├── models/
│   └── configuration.py         # MODIFY: Add storage path fields (model_cache_path, corpus_cache_path)
├── config/
│   ├── xdg.py                   # EXISTING: XDG path helpers (no changes needed)
│   ├── defaults.py              # MODIFY: Update default paths to use new config fields
│   ├── settings.py              # MODIFY: ConfigManager load/validate logic for new paths
│   └── logging.py               # EXISTING: Uses XDG state dir (no changes)
├── cli/
│   ├── config.py                # MODIFY: Extend `show` and `validate` commands
│   └── __main__.py              # EXISTING: Entry point (no changes)
├── orchestration/
│   └── llm_client.py            # MODIFY: Add n_gpu_layers parameter to Llama() initialization
├── embeddings/
│   └── sentence_transformer.py  # EXISTING: Already supports embedding_device (no changes)
└── storage/
    └── qdrant_impl.py           # EXISTING: Takes storage_path param (no changes)

tests/
├── contract/
│   └── test_llm_contract.py     # ADD: Test LLM GPU layer offloading
├── integration/
│   └── test_custom_storage_paths.py  # ADD: End-to-end test with /krag paths
└── unit/
    ├── test_configuration.py    # MODIFY: Add tests for new storage path fields
    ├── test_config_manager.py   # MODIFY: Test path resolution and precedence
    └── test_xdg.py              # EXISTING: No changes needed

docs/
└── migration-guide.md           # ADD: Document /krag setup, group permissions, GPU config
```

**Structure Decision**: Single project (CLI + library). All changes are localized to existing modules (config, models, CLI, orchestration). No new architectural components. Tests follow existing contract/integration/unit structure.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**No complexity violations.** All changes extend existing patterns without introducing new architectural components or dependencies.
