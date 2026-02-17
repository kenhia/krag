# Implementation Plan: Code-Aware Indexing

**Branch**: `005-code-aware-indexing` | **Date**: 2026-02-16 | **Spec**: [spec.md](specs/005-code-aware-indexing/spec.md)
**Input**: Feature specification from `/specs/005-code-aware-indexing/spec.md`

## Summary

Add code-specialized indexing and retrieval to krag via five integrated capabilities:

1. **Code-aware chunking plugin** (`krag-plugin-code`) using tree-sitter to parse source files into AST-based semantic units (functions, methods, classes) instead of character-based splitting
2. **Multi-model embedding orchestration** — plugins declare preferred embedding models, the system routes files to the correct embedder, searches multiple vector spaces per query, and merges results via min-max score normalization
3. **Multi-LLM routing with hot-swap fallback** — route synthesis to a code-specialized LLM (Qwen2.5-Coder-7B) or general-purpose LLM (Phi-3-medium) based on retrieved chunk composition, with `load_multi_llm` config control and `--llm` CLI switch for VRAM-constrained fallback
4. **Code prompt preset** — a `"code"` preset in PromptBuilder tuned for code Q&A, auto-coupled to LLM selection
5. **Enriched retrieval metadata** — identifier-aware score boosting and structured source references (symbol names, line numbers)

**Technical approach**: Extend the existing plugin system (`FileTypeHandler` ABC) for chunking and embedding model declaration. Add an `EmbeddingOrchestrator` to manage multiple embedding models and vector namespaces. Add an `LLMPool` to manage LLM lifecycle, routing, and hot-swap. Use pynvml for VRAM detection and graceful fallback selection. All new dependencies (tree-sitter, pynvml) are MIT/Apache-2.0 licensed.

## Technical Context

**Language/Version**: Python 3.11+ (pyproject.toml: `>=3.11,<3.14`)
**Build System**: hatchling, managed with `uv`
**Primary Dependencies** (existing):
  - `sentence-transformers>=2.3.0` — embedding model loading
  - `llama-cpp-python>=0.2.90` — GGUF LLM inference
  - `qdrant-client>=1.8.0` — vector storage (embedded mode)
  - `typer>=0.9.0` + `rich>=13.0.0` — CLI
  - `pydantic>=2.6.0` + `pydantic-settings>=2.2.0` — models/config

**New Dependencies** (this feature):
  - `tree-sitter>=0.23.0` — core AST parsing library (MIT)
  - `tree-sitter-python>=0.23.0` — Python grammar (MIT)
  - `tree-sitter-rust>=0.23.0` — Rust grammar (MIT)
  - `pynvml` — GPU VRAM detection at runtime (transitive dep of llama-cpp-python; MIT)
  - `jinaai/jina-embeddings-v2-base-code` — code embedding model (Apache-2.0, 161M params, 768-dim)
  - `Qwen2.5-Coder-7B-Instruct Q5_K_M` — code LLM (Apache-2.0, ~5.4 GB GGUF)

**Storage**: Qdrant (embedded, disk-backed via `QdrantVectorStore`). Cosine distance. Currently single collection `"krag_embeddings"`. This feature adds per-model vector namespaces.
**Testing**: `pytest` with `pytest-cov`, `mypy` strict mode. Tests organized as `tests/{unit,contract,integration}/`.
**Target Platform**: Linux x86_64 (primary). GPU: NVIDIA RTX 4080 SUPER, 16 GB VRAM.
**Project Type**: Single Python package (`src/krag/`) + standalone plugin packages (`krag-plugin-code`)
**Performance Goals**:
  - Indexing 10k-line Python project with code plugin ≤2x default chunking time (SC-004)
  - LLM hot-swap ≤60 seconds (SC-008)
  - Combined embedding models ≤1.5 GB VRAM (SC-003)
  - Total VRAM (embedders + 1 LLM) ≤14 GB, leaving 2 GB headroom (SC-003)
**Constraints**:
  - 16 GB VRAM budget — simultaneous dual LLMs (~14 GB combined) generally infeasible with embedders
  - `load_multi_llm` defaults `false`; hot-swap is the default LLM strategy
  - Plugin must not require krag core code changes to `FileTypeHandler` ABC (use CUSTOM chunking strategy + embedding model declaration)
  - Both LLMs must work via existing `LLMClient` chat-completion interface
**Scale/Scope**: Single-user local-first tool. Typical corpus: 1–50k files, 1M LOC. One GPU.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Code Quality & Standards

| Principle | Status | Evidence |
|-----------|--------|----------|
| Maintainability | ✅ PASS | New code follows existing module patterns (plugin ABC, Pydantic models, separated orchestration). Code-aware chunker is a separate plugin package. |
| Modularity | ✅ PASS | Five independent capabilities map to distinct modules: plugin package, embedding orchestrator, LLM pool, prompt preset, retriever enhancement. Each can be developed and tested independently. |
| Documentation | ✅ PASS | All new public interfaces will have docstrings. Plugin follows existing krag-plugin-logs pattern which includes README and usage docs. |
| Style Compliance | ✅ PASS | `ruff format` + `ruff check` enforced. `pyproject.toml` already configured with rule selection. |
| Type Safety | ✅ PASS | `mypy --strict` already enforced. All new code will use type annotations. |

### II. Test-Driven Development

| Principle | Status | Evidence |
|-----------|--------|----------|
| Red-Green-Refactor | ✅ PASS | Each user story is independently testable (spec acceptance scenarios define test cases). Will write tests before implementation for each phase. |
| Test Coverage | ✅ PASS | Unit tests for AST chunker, embedding orchestrator, LLM pool, prompt preset, retriever boost. Contract tests for plugin interface extensions. Integration tests for end-to-end indexing and query with code plugin. |
| Pre-Commit Gate | ✅ PASS | `uv run ruff format . && uv run ruff check --fix . && uv run pytest` before every commit. |
| Independent Stories | ✅ PASS | P1 (chunking) deliverable without P2-P5. P2 (embedding) works with any chunker. P3 (LLM) works with any retriever. P4/P5 are additive. |

### III. User Experience Consistency

| Principle | Status | Evidence |
|-----------|--------|----------|
| Interface Stability | ✅ PASS | No breaking changes to existing CLI commands. New `--llm` switch is additive. Plugin system already supports CUSTOM chunking strategy. |
| Error Messages | ✅ PASS | Graceful fallback with clear log messages for: tree-sitter parse failures, VRAM insufficient, hot-swap progress feedback. |
| Documentation Alignment | ✅ PASS | Plugin user guide and plugin dev guide exist. Will update with code plugin specifics. |
| Feedback Mechanisms | ✅ PASS | Hot-swap progress feedback (FR-021), VRAM fallback messages (FR-016), tree-sitter fallback warnings (FR-009). |

### IV. Performance & Optimization

| Principle | Status | Evidence |
|-----------|--------|----------|
| Requirements Defined | ✅ PASS | SC-003 (VRAM budget), SC-004 (indexing time ≤2x), SC-008 (hot-swap ≤60s). |
| Measurement | ✅ PASS | VRAM queried via pynvml. Indexing time logged. Hot-swap duration logged (FR-021). |
| Resource Efficiency | ✅ PASS | Sequential embedding fallback for VRAM-constrained systems. LLM hot-swap avoids OOM. pynvml pre-check prevents CUDA OOM crashes. |

### V. Pre-Commit Validation

| Principle | Status | Evidence |
|-----------|--------|----------|
| Format + Lint + Test | ✅ PASS | Standard workflow applies. Plugin package will have its own test suite runnable via `uv run pytest` from plugin root. |

**Gate Result**: ✅ ALL GATES PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/005-code-aware-indexing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── embedding-orchestrator.md
│   ├── llm-pool.md
│   └── plugin-extensions.md
├── checklists/
│   └── requirements.md  # Existing quality checklist
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# krag core (existing, extended)
src/krag/
├── cli/
│   └── main.py              # Add --llm switch to query command
├── config/
│   ├── defaults.py          # Add code-related defaults
│   └── settings.py          # Add multi-LLM config section parsing
├── embeddings/
│   ├── generator.py         # Existing (unchanged)
│   └── orchestrator.py      # NEW: multi-model embedding orchestrator
├── models/
│   ├── configuration.py     # Extend Configuration for multi-LLM settings
│   ├── text_chunk.py        # Existing (metadata already flexible via dict)
│   ├── embedding.py         # Existing (already has model_name field)
│   └── query_result.py      # Extend for structured source references
├── orchestration/
│   └── indexer.py           # Wire EmbeddingOrchestrator, per-plugin model routing
├── plugins/
│   ├── interfaces.py        # Extend FileTypeHandler with embedding_model property
│   └── chunking.py          # Update CODE_AWARE resolution (may use CUSTOM instead)
├── retrieval/
│   └── retriever.py         # Add metadata-based score boosting
├── storage/
│   ├── vector_store.py      # Existing ABC (unchanged)
│   └── qdrant_impl.py       # Add namespace/collection management helpers
└── synthesis/
    ├── llm_client.py        # Existing (unchanged — models just load via path)
    ├── llm_pool.py          # NEW: multi-LLM lifecycle and routing manager
    └── prompt_builder.py    # Add "code" preset, auto-coupling logic

# Code plugin (new separate package)
examples/krag-plugin-code/
├── pyproject.toml           # Entry point: krag.plugins → code
├── README.md
├── src/krag_plugin_code/
│   ├── __init__.py
│   ├── handler.py           # CodeFileHandler(FileTypeHandler)
│   ├── ast_chunker.py       # tree-sitter AST-based chunking
│   └── languages.py         # Grammar discovery and language mapping
└── tests/
    ├── unit/
    │   ├── test_ast_chunker.py
    │   └── test_languages.py
    ├── contract/
    │   └── test_handler_contract.py
    └── fixtures/
        ├── sample_python.py
        └── sample_rust.rs

# krag core tests (extended)
tests/
├── unit/
│   ├── test_embedding_orchestrator.py   # NEW
│   ├── test_llm_pool.py                # NEW
│   ├── test_prompt_builder.py          # Extend for "code" preset
│   ├── test_retriever_dedup.py         # Extend for metadata boosting
│   └── plugins/                        # Existing
├── contract/
│   ├── test_embedding_contract.py      # Extend for multi-model
│   └── test_llm_contract.py            # Extend for multi-LLM
└── integration/
    ├── test_code_indexing_pipeline.py   # NEW: end-to-end with code plugin
    └── test_multi_model_query.py        # NEW: multi-model query + merge
```

**Structure Decision**: Single project with an additional plugin package following the existing `krag-plugin-logs` pattern. The core `src/krag/` package gets two new modules (`embeddings/orchestrator.py`, `synthesis/llm_pool.py`) and extensions to existing modules. The code plugin lives in `examples/krag-plugin-code/` as a separately installable package with its own test suite.

## Complexity Tracking

> No Constitution Check violations — this section is intentionally empty.

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design completion.*

### I. Code Quality & Standards — ✅ PASS

No changes from pre-research check. The design follows existing krag patterns:
- `EmbeddingOrchestrator` wraps existing `EmbeddingGenerator` (same pattern as `IndexingOrchestrator` wrapping components)
- `LLMPool` wraps existing `LLMClient` / `Llama` (adds lifecycle management, doesn't change the client API)
- `CodeFileHandler` implements existing `FileTypeHandler` ABC
- One new optional method on `FileTypeHandler` (`get_embedding_model()`) — non-breaking, returns `None` by default

### II. Test-Driven Development — ✅ PASS

Test plan covers all new components:
- **Unit tests**: `ASTChunker`, `EmbeddingOrchestrator`, `LLMPool`, code prompt preset, metadata boosting, RRF merge
- **Contract tests**: `CodeFileHandler` implements `FileTypeHandler`, `EmbeddingOrchestrator` embedding/query contract, `LLMPool` routing contract
- **Integration tests**: End-to-end code indexing pipeline, multi-model query pipeline
- Each user story has acceptance scenarios that map directly to test cases

### III. User Experience Consistency — ✅ PASS

- Existing CLI commands unchanged. New `--llm` switch is additive.
- No changes to query output format for non-code queries.
- Code-enriched output (line numbers, symbol refs) only appears when metadata is present — graceful absence for non-code chunks.
- Hot-swap feedback provides Rich spinner + timing log — consistent with existing krag progress indicators.

### IV. Performance & Optimization — ✅ PASS

- Tree-sitter parsing is negligible (~5-15ms per 10k lines) vs. embedding generation
- VRAM budgets researched and validated against actual GPU (RTX 4080 SUPER, 16 GB)
- Sequential fallbacks for VRAM-constrained scenarios prevent OOM without user intervention
- RRF merge is O(n log n) — negligible vs. network/embedding costs

### V. Pre-Commit Validation — ✅ PASS

Standard workflow applies. Plugin package has its own test suite. Both krag core tests and plugin tests must pass before commit.

**Post-Design Gate Result**: ✅ ALL GATES PASS

## Spec Deviations from Research

The following changes to the spec are recommended based on Phase 0 research findings. These should be applied before tasks are generated.

### Deviation 1: RRF Instead of Min-Max Normalization

**Spec reference**: FR-014, Clarification Q2, Edge case "Multi-model score merging"

**Current spec**: "normalize scores using min-max normalization per model per query (scaling each model's result set to [0, 1])"

**Recommended change**: Replace with "merge results using Reciprocal Rank Fusion (RRF) with k=60"

**Rationale**: Scores from different embedding models are in different semantic spaces. Min-max normalization inflates weak results from a consistently-high-scoring model. RRF uses rank positions (which are comparable across models) and is used by Qdrant internally for their own multi-vector fusion. See [research.md](research.md#r5-score-merging-strategy--spec-deviation).

### Deviation 2: torch.cuda.mem_get_info() Instead of pynvml

**Spec reference**: FR-016, Clarification Q3, Dependencies section

**Current spec**: "query available GPU VRAM at runtime (via `pynvml`)"

**Recommended change**: Replace `pynvml` with `torch.cuda.mem_get_info()`

**Rationale**: pynvml is NOT a transitive dependency of llama-cpp-python (spec assumed it was). torch IS already available (via sentence-transformers) and provides more accurate post-context-init VRAM values. See [research.md](research.md#r3-vram-detection).

### Deviation 3: Named Vectors Instead of Separate Collections

**Spec reference**: FR-015

**Current spec**: "separate vector namespaces (collections or payload-filtered partitions)"

**Recommended precision**: Use Qdrant named vectors in a single collection (`vectors_config={"text": ..., "code": ...}`). Points that only have one model's embedding omit the other vector name. Search uses `using="text"` or `using="code"`. Batch search via `query_batch_points`. See [research.md](research.md#r2-qdrant-multi-vector-architecture).
