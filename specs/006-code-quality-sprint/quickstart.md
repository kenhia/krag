# Quickstart: 006-code-quality-sprint

**Branch**: `006-code-quality-sprint`
**Prerequisites**: Python 3.13, uv, existing krag dev environment

## Setup

```bash
git checkout 006-code-quality-sprint
uv sync --group dev
```

## Implementation Order

This sprint has no new user-visible features (except `krag log`), so the implementation order is driven by dependency and risk:

### Phase 1: Correctness Fixes (no refactoring, just bug fixes)

1. **FR-006**: Remove `le=1.0` from `QueryResult.score` — 1-line change, unblocks boost fixes
2. **FR-001**: Fix LLM routing in `llm_pool.py` — change file_type check to semantic label
3. **FR-005**: Fix empty-path crash in `retriever.py` — add per-result try/except
4. **FR-003**: Fix boost weights for RRF in `retriever.py` — add score-range-aware constants
5. **FR-004**: Fix stale chunker in `indexer.py` — add `chunker = None` at loop start
6. **FR-002**: Fix stale vectors in incremental indexing — add delete-before-insert

### Phase 2: DRY Refactoring (extract shared code)

7. **FR-012**: Create `cli/pipeline.py` — shared pipeline factory
8. Refactor `cli/query.py` to use pipeline.py
9. Refactor `cli/eval.py` to use pipeline.py (includes FR-007–011, FR-009)
10. **FR-013**: Extract `_process_file()` in `indexer.py`
11. **FR-014**: Consolidate `_get_free_vram()` into `cli/gpu.py`

### Phase 3: Cleanup + Logging

12. **FR-016**: Reduce upsert log noise in `qdrant_impl.py`
13. **FR-017/018**: Create `cli/log.py` with rotate/clear commands
14. **FR-019**: Remove dead code (`_display_sources_only`, fix `ScoredPointLike`)
15. **FR-020**: Remove `__del__` from `IndexingOrchestrator`
16. **FR-021**: Fix redundant imports in `indexer.py`
17. **FR-022**: Remove dimension equality check in `orchestrator.py`
18. **FR-015**: Fix `Any` types where proper types exist

### Phase 4: Verification

19. Run full test suite (800+ tests pass)
20. Add integration test for named-vector + RRF pipeline (FR-030)
21. Run eval suite — verify 3/3 pass rate restored
22. Pre-commit validation: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`

## Validation

```bash
# Full test suite
uv run pytest

# Eval suite
krag eval tests/fixtures/eval_queries.toml

# Log noise check
krag index --full && grep -c "Upserted\|upsert" ~/.local/state/krag/logs/krag.log

# New log commands
krag log path
krag log clear
krag log rotate

# LLM routing check (requires code model configured)
krag query "How does the retriever work?" --show-logs 2>&1 | grep -i "routing\|code.*llm\|pool"
```
