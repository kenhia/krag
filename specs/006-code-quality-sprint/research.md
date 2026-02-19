# Research: 006-code-quality-sprint

**Date**: 2026-02-18
**Status**: Complete — all unknowns resolved

## R-01: CLI Pipeline Duplication Scope and Divergence Points

**Decision**: Extract `src/krag/cli/pipeline.py` with shared factory functions.

**Rationale**: ~65 lines of near-identical initialization exist across `query.py` and `eval.py`. They've already diverged in 3 ways: (1) `query.py` has LLMPool routing while `eval.py` does not, (2) `query.py` hardcodes `top_k=5` while `eval.py` falls back to config, (3) error handling uses Rich panels in query vs stderr in eval.

**Alternatives considered**:
- **Class-based pipeline** (e.g., `QueryPipeline` class): Rejected — adds unnecessary OOP overhead. The initialization is procedural (build objects, return them). A dataclass or namedtuple holding the built components + factory functions is simpler.
- **Move to QueryEngine**: Rejected — QueryEngine is domain logic, not CLI infrastructure. Config resolution, plugin loading, and LLM pool creation are CLI concerns.

**Exact duplication inventory** (from codebase analysis):

| Block | query.py | eval.py | Identical? |
|-------|----------|---------|-----------|
| Config loading | L82–96 | L73–79 | ~90% (query has YAML fallback attempt) |
| EmbeddingGenerator init | L118–121 | L88–91 | 100% |
| EmbeddingOrchestrator + plugin registration | L124–136 | L94–106 | 100% |
| Vector store kwargs + QdrantVectorStore | L139–145 | L109–115 | 100% |
| LLMClient construction | L165–175 | L117–127 | 100% |
| QueryEngine construction | L187–196 | L132–142 | ~95% (top_k handling differs) |

**Design**:
```python
@dataclass(frozen=True)
class QueryPipeline:
    config: Configuration
    embedding_generator: EmbeddingGenerator
    embedding_orchestrator: EmbeddingOrchestrator
    vector_store: QdrantVectorStore
    llm_client: LLMClient
    llm_pool: LLMPool | None
    query_engine: QueryEngine

def build_query_pipeline(
    config_path: Path | None,
    top_k: int | None,
    preset: str | None,
) -> QueryPipeline: ...
```

## R-02: Indexer Per-File Processing Duplication

**Decision**: Extract `_process_file(self, file_meta, plugin_handler) -> list[dict]` method shared by `index_full` and `index_incremental`.

**Rationale**: ~200 lines duplicated across L398–625 (full) and L627–1010 (incremental). Bug fixes (F-04 chunker, F-12 plugin name) applied in one path don't propagate to the other.

**Alternatives considered**:
- **Separate class** (`FileProcessor`): Rejected — the processing depends on `self.chunker`, `self.chunking_resolver`, `self.embedding_generator`, etc. Extracting a class would require passing ~8 dependencies. A private method on `IndexingOrchestrator` is more natural.
- **Generator/iterator pattern**: Rejected — no streaming benefit since all chunks for a file must be collected before upsert anyway.

**Key bugs to fix during extraction**:
- Initialize `chunker = None` at loop start (F-04)
- Use consistent `getattr(plugin_handler, "name", plugin_handler.__class__.__name__)` (F-12)
- Delete existing vectors before re-insert in incremental path (F-02)

## R-03: RRF Score Interaction with Boost Weights

**Decision**: Scale boost weights relative to score range. For RRF path, use `_KEYWORD_BOOST_WEIGHT_RRF = 0.002` and `_METADATA_BOOST_WEIGHT_RRF = 0.003` (proportional to RRF score range of ~0.01–0.03).

**Rationale**: Current weights (0.05 / 0.08) are 3–5× the typical RRF score. A keyword match triples an RRF score, completely overriding rank-fusion ordering. The fix scales boosts to ~10–15% of a typical RRF score, preserving the same proportional boost as the cosine-calibrated weights (0.05/0.08 ≈ 5–8% of a typical cosine score of ~0.7–0.9).

**Alternatives considered**:
- **Disable boosts for RRF entirely**: Rejected — keyword/metadata boosts add genuine signal. They should nudge, not dominate.
- **Normalize boosts as percentage of max score**: More principled but requires knowing the max score at boost time. The RRF path always produces scores in the same narrow range, so fixed constants are adequate.
- **Apply boosts as rank adjustments instead of score adjustments**: Cleaner semantically but would require refactoring the boost functions to operate on position, not score. Too invasive for this sprint.

## R-04: LLM Pool File Type Detection

**Decision**: Change `_analyze_chunk_composition()` to check `c.file_type == "code"` (semantic label) OR `Path(c.file_path).suffix in CODE_EXTENSIONS` (extension fallback).

**Rationale**: Investigation revealed `file_type` in `QueryResult` may contain either semantic labels (`"code"`, `"text"`, `"markdown"`) OR dotted extensions (`".py"`, `".rs"`) depending on how the payload was built. The dual check handles both without breaking either path.

**Alternatives considered**:
- **Only check `c.file_type == "code"`**: Simpler but fragile — if any code path sets `file_type` to the extension, routing breaks.
- **Normalize `file_type` during indexing**: Better long-term but larger scope. Would need to audit all payload construction sites. Defer to a future spec.

## R-05: VRAM Utility Consolidation

**Decision**: Consolidate into `src/krag/cli/gpu.py` module since it already has `check_cuda_available()`. Expose a simple `get_free_vram(device: int = 0) -> int | None` function.

**Rationale**: Three implementations exist with different error handling and calculation methods:
- `orchestrator.py`: `torch.cuda.mem_get_info(device)` — catches `(ImportError, RuntimeError)`
- `llm_pool.py`: `torch.cuda.mem_get_info()` — catches bare `Exception`
- `gpu.py`: `total_memory - memory_allocated()` — different calculation entirely

The `mem_get_info()` approach is correct (accounts for fragmentation). The `device` parameter from `orchestrator.py` should be preserved. Error handling should catch `(ImportError, RuntimeError, ValueError)` — ValueError for invalid device index.

**Alternatives considered**:
- **New `src/krag/utils/gpu.py`**: Creates new package. Rejected — `cli/gpu.py` already exists and is the natural home.
- **Keep duplication**: Rejected — already caused inconsistent behavior.

## R-06: Log Rotation CLI Design

**Decision**: Add `krag log` subcommand group with `rotate` and `clear` commands.

**Rationale**: Log file path is deterministic via `get_krag_state_dir() / "logs" / "krag.log"`. Python's `logging` module already has `RotatingFileHandler` with 10MB/5-backup rotation, but there's no CLI trigger. Users must manually `rm` or `truncate` log files.

**Design**:
```
krag log show        # cat the log file (optional, low priority)
krag log rotate      # archive current → krag.log.1, shift existing backups
krag log clear       # truncate to zero bytes
krag log path        # print log file path
```

**Implementation**: Use `RotatingFileHandler.doRollover()` for rotate (leverages existing handler config). For clear, simple `open(path, 'w').close()`. For edge case (no log file yet), create parent dirs + empty file.

**Alternatives considered**:
- **`krag --clear-log` flag**: Rejected — mixing behavior flags with commands is anti-pattern in Typer CLIs.
- **Automatic rotation only (no CLI)**: Already exists (10MB/5-backup RotatingFileHandler). But users want manual rotation before debugging sessions.

## R-07: Score Validation Constraint

**Decision**: Remove `le=1.0` from `QueryResult.score`. Keep `ge=0.0` (scores should never be negative). Update description to "Relevance score (higher is better)".

**Rationale**: RRF scores are ~0.01–0.03 (valid under current constraint by accident), but boosted RRF scores could exceed 1.0 if boosts are ever miscalibrated. Dot-product distances can exceed 1.0 natively. The `le=1.0` constraint provides no safety benefit and creates a latent failure mode.

**Alternatives considered**:
- **Remove all constraints**: Rejected — `ge=0.0` is a useful invariant (negative scores would indicate a bug).
- **Use separate score types**: Rejected — over-engineering for the current use case.

## R-08: Embedding Dimension Enforcement

**Decision**: Remove the dimension equality check in `EmbeddingOrchestrator.get_vector_config()`. Each named vector space has its own dimension from its model; Qdrant supports heterogeneous dimensions natively.

**Rationale**: The check at `orchestrator.py` L118–124 enforces that all registered embedding models produce the same vector dimension. This is incorrect — the text model (e.g., `all-MiniLM-L6-v2`, 384-dim) and code model (e.g., `code-search-net`, 768-dim) legitimately have different dimensions. Qdrant's named vectors feature explicitly supports this.

**Alternatives considered**:
- **Warn instead of error**: Rejected — different dimensions are expected, not suspicious. A warning would be noise.

## R-09: Dead Code and Unused Protocol

**Decision**: Remove `_display_sources_only()` (55 lines, query.py L406–461). Either use `ScoredPointLike` in `reciprocal_rank_fusion()` signature or remove it.

**Rationale**: `_display_sources_only()` is dead code — the `no_synthesis` branch at L217–228 inlines its own display logic. `ScoredPointLike` is a well-designed protocol that should be used in the `reciprocal_rank_fusion()` signature to replace `list[list[Any]]`.

**Decision detail**: Keep `ScoredPointLike` and use it — it improves type safety. Change `reciprocal_rank_fusion(result_lists: list[list[Any]])` to `reciprocal_rank_fusion(result_lists: list[list[ScoredPointLike]])`.

## R-10: Integration Test for Named Vector + RRF Pipeline

**Decision**: Add `tests/integration/test_named_vector_query_pipeline.py` that indexes sample documents with multi-model embeddings, queries via RRF, and verifies results include expected sources.

**Rationale**: The eval regression (3/3 → 2/3) proves the end-to-end pipeline lacks test coverage for the named-vector + RRF path. Unit tests exist for RRF and named-vector search individually, but no integration test validates the full pipeline.

**Test design**: Use mock embeddings (deterministic). Index 5–10 sample documents covering code, markdown, and text. Run 3 queries exercising different retrieval paths. Assert expected source files appear in top-k results.
