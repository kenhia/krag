# Implementation Plan: RAG Quality Tuning & Hallucination Reduction

**Branch**: `004-rag-quality-tuning` | **Date**: 2026-02-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-rag-quality-tuning/spec.md`

## Summary

Improve krag's RAG answer quality and reduce hallucinations by: (1) refining prompt templates with named presets that enforce context-grounded answers, (2) adding a configurable similarity score threshold to filter low-quality retrieval, (3) exposing conservative LLM parameter defaults, (4) adding diagnostic logging throughout the query pipeline, and (5) building a lightweight evaluation harness to measure quality and compare configurations.

## Technical Context

**Language/Version**: Python >=3.11,<3.14 (pyproject.toml target: py311)  
**Primary Dependencies**: typer (CLI), llama-cpp-python (LLM inference), qdrant-client (vector store), sentence-transformers (embeddings), pydantic/pydantic-settings (config), rich (display), pyyaml + tomli-w (config I/O)  
**Storage**: Qdrant (vector store, local file-based), TOML config files, GGUF model files  
**Testing**: pytest + pytest-cov, ruff (format + lint), mypy (strict mode)  
**Target Platform**: Linux (primary), cross-platform CLI  
**Project Type**: Single project — `src/krag/` layout with `tests/` at root  
**Performance Goals**: Query pipeline (retrieval + generation) completes within existing latency envelope; evaluation suite of 20 queries runs in under 5 minutes  
**Constraints**: Must not require network access at query time; local LLM inference only; existing config system must remain backward-compatible  
**Scale/Scope**: Single-user CLI tool; document corpora up to ~10k files; evaluation sets of 10–20 queries  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | ✅ PASS | All changes follow existing patterns — type hints, docstrings, ruff compliance |
| II. Test-Driven Development | ✅ PASS | TDD workflow applies: unit tests for prompt presets, threshold filtering, eval harness; contract tests for new config fields; integration tests for query pipeline quality |
| III. User Experience Consistency | ✅ PASS | CLI interface extended additively (new `--prompt-preset` flag, new `evaluate` subcommand); existing behavior unchanged unless user opts in via config |
| IV. Performance & Optimization | ✅ PASS | No new heavy dependencies; similarity threshold reduces LLM input size (improvement); eval harness is offline batch tool |
| Python-Specific Requirements | ✅ PASS | uv for deps, ruff format + check, pytest; all pre-commit gates apply |
| Pre-Commit Validation | ✅ PASS | Standard workflow: `uv run ruff format . && uv run ruff check --fix . && uv run pytest` |

**Gate result: PASS** — no violations, no complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-rag-quality-tuning/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/krag/
├── cli/
│   ├── main.py              # CLI app (add evaluate subcommand)
│   ├── query.py             # Query command (add --prompt-preset flag)
│   └── evaluate.py          # NEW: Evaluation CLI command
├── config/
│   ├── defaults.py          # MODIFY: Add new defaults (threshold, top_p, repeat_penalty, prompt preset)
│   └── settings.py          # MODIFY: Parse new config sections
├── models/
│   ├── configuration.py     # MODIFY: Add new config fields
│   └── query_result.py      # Existing (no changes expected)
├── synthesis/
│   ├── prompt_builder.py    # MODIFY: Implement named prompt presets
│   └── llm_client.py        # MODIFY: Support top_p, repeat_penalty params
├── retrieval/
│   └── retriever.py         # MODIFY: Add similarity threshold filtering + debug logging
├── orchestration/
│   └── query_engine.py      # MODIFY: Enhanced diagnostic logging
└── evaluation/              # NEW: Evaluation harness module
    ├── __init__.py
    ├── runner.py             # Evaluation suite runner
    ├── checks.py             # Behavior check implementations
    └── report.py             # JSON/summary report formatter

tests/
├── unit/
│   ├── test_prompt_builder.py    # MODIFY: Tests for presets
│   ├── test_eval_checks.py       # NEW: Behavior check tests
│   ├── test_eval_runner.py       # NEW: Runner tests
│   └── test_eval_report.py       # NEW: Report formatter tests
├── contract/
│   └── test_retriever_contract.py  # MODIFY: Threshold contract
├── integration/
│   ├── test_query_pipeline.py      # MODIFY: Quality integration tests
│   └── test_evaluation_pipeline.py # NEW: End-to-end eval tests
└── fixtures/
    └── eval_queries.toml           # NEW: Sample evaluation query set
```

**Structure Decision**: Single project layout, matching existing `src/krag/` structure. One new module (`evaluation/`) for the eval harness. All other changes are additive modifications to existing modules.

## Post-Design Constitution Re-Check

*Re-evaluation after Phase 1 design artifacts are complete.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | ✅ PASS | Contracts specify type hints, docstrings, and clear module boundaries. Data model uses Pydantic dataclasses. New `evaluation/` module follows existing modularity patterns. |
| II. Test-Driven Development | ✅ PASS | Test structure defined: unit tests for checks/runner/reporter, contract tests for retriever threshold, integration tests for full pipeline + eval. Fixtures include sample TOML test set. |
| III. User Experience Consistency | ✅ PASS | CLI extended additively: `--preset` flag on `query`, new `eval` subcommand. JSON stdout + stderr summary follows Unix conventions. Existing behavior unchanged without opt-in. |
| IV. Performance & Optimization | ✅ PASS | Similarity threshold filtering reduces LLM input size. Eval runner processes queries sequentially (LLM not concurrent). No new heavy dependencies added. |
| Python-Specific Requirements | ✅ PASS | Uses existing uv, ruff, pytest toolchain. No new dev dependencies beyond existing stack. |
| Pre-Commit Validation | ✅ PASS | All new modules subject to standard `ruff format + check + pytest` gate. |

**Post-design gate result: PASS** — design artifacts comply with all constitution principles.

## Complexity Tracking

> No violations — table not needed.

## Generated Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Plan | `specs/004-rag-quality-tuning/plan.md` | This implementation plan |
| Research | `specs/004-rag-quality-tuning/research.md` | Phase 0 research findings |
| Data Model | `specs/004-rag-quality-tuning/data-model.md` | Entity definitions and relationships |
| Quickstart | `specs/004-rag-quality-tuning/quickstart.md` | Usage guide for new features |
| Contract: PromptBuilder | `specs/004-rag-quality-tuning/contracts/prompt-builder.md` | Chat message API with preset support |
| Contract: LLMClient | `specs/004-rag-quality-tuning/contracts/llm-client.md` | Chat completion API with new params |
| Contract: Retriever | `specs/004-rag-quality-tuning/contracts/retriever.md` | Post-retrieval threshold filtering |
| Contract: QueryEngine | `specs/004-rag-quality-tuning/contracts/query-engine.md` | Orchestration with preset + threshold |
| Contract: Evaluation | `specs/004-rag-quality-tuning/contracts/evaluation.md` | Full evaluation module (loader, checks, runner, reporter, CLI) |
| Agent Context | `.github/agents/copilot-instructions.md` | Updated with project technologies |
