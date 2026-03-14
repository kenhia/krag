# Quickstart — 015-retrieval-accuracy

**Branch**: `015-retrieval-accuracy` | **Sprint**: Debug Metadata Accuracy & Retrieval Completeness

## Prerequisites

- Python >=3.11 with `uv` package manager
- CUDA 12.4 toolkit (for GPU-accelerated inference, not required for this sprint's changes)
- krag repo cloned and on `015-retrieval-accuracy` branch

## Setup

```bash
cd /home/ken/src/krag
git checkout 015-retrieval-accuracy
uv sync
```

## Key Files to Modify

| Priority | File | What to change |
|----------|------|----------------|
| P1 | `src/krag/retrieval/retriever.py` | Set `_last_per_space_counts` in `_multi_collection_retrieve()` |
| P2 | `src/krag/retrieval/retriever.py` | Add multi-model search within `_multi_collection_retrieve()` (two-level RRF) |
| P3 | `src/kragd/app.py` | Add health-check log suppression middleware |

### Supporting files (may need minor updates)

| File | Why |
|------|-----|
| `src/kragd/service.py` | Debug metadata builder — may benefit from using `_last_collections_searched` |
| `src/kragd/schemas.py` | No schema changes expected, but verify `DebugMetadata` field descriptions |

## Test Files

| File | Scope | Notes |
|------|-------|-------|
| `tests/unit/test_retriever.py` | P1+P2 unit tests | Extend existing test module |
| `tests/unit/test_rrf_merge.py` | RRF edge cases | Extend if needed for two-level merge |
| `tests/unit/test_health_log.py` | P3 middleware unit tests | **New file** |
| `tests/integration/test_multi_collection.py` | P2 integration | New or extend existing |
| `tests/live/test_live_kragd.py` | All stories live | Extend existing |

## Development Loop (TDD — NON-NEGOTIABLE)

```bash
# 1. Write failing test
uv run pytest tests/unit/test_retriever.py -x -v

# 2. Implement minimal fix
# 3. Run tests again — should pass
uv run pytest tests/unit/test_retriever.py -x -v

# 4. Pre-commit validation (NON-NEGOTIABLE)
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/
uv run pytest

# 5. Commit
git add -A && git commit -m "descriptive message"
```

## Architecture Context

### Retrieval Paths (current)

```
retrieve(query)
  ├─ single-model, single-collection → vector_store.search()
  ├─ multi-model, single-collection  → _multi_model_retrieve()
  │   └─ search_named() per space → reciprocal_rank_fusion()
  └─ multi-collection                → _multi_collection_retrieve()
      └─ vs.search() per collection → _weighted_rrf()
          ⚠ BUG: uses single model only, doesn't set _last_per_space_counts
```

### Retrieval Paths (after this sprint)

```
retrieve(query)
  ├─ single-model, single-collection → vector_store.search()
  ├─ multi-model, single-collection  → _multi_model_retrieve()
  │   └─ search_named() per space → reciprocal_rank_fusion()
  └─ multi-collection                → _multi_collection_retrieve()
      ├─ if multi-model:
      │   └─ per collection: search_named() per space → inner RRF
      │       └─ _weighted_rrf() across collections (two-level RRF)
      ├─ if single-model:
      │   └─ per collection: vs.search() → _weighted_rrf()
      └─ ALWAYS: set _last_per_space_counts + _last_collections_searched
```

### Key Type References

- `QueryResult`: `src/krag/models/query_result.py` — Pydantic BaseModel with `collection: str | None`
- `RRFScoredPoint`: `src/krag/retrieval/rrf.py` — dataclass with `id`, `score`, `payload`
- `DebugMetadata`: `src/kragd/schemas.py` — Pydantic BaseModel with `per_space_result_counts: dict[str, int]`
- `CollectionStore`: `src/krag/storage/collection_manager.py` — dataclass with `vector_store: QdrantVectorStore`
- `_weighted_rrf()`: module-level function in `retriever.py`, line ~88
- `reciprocal_rank_fusion()`: `src/krag/retrieval/rrf.py`

## Running Tests

```bash
# All tests
uv run pytest

# Unit only
uv run pytest tests/unit/ -v

# Specific test file
uv run pytest tests/unit/test_retriever.py -v -k "multi_collection"

# With coverage
uv run pytest --cov=src/krag --cov=src/kragd --cov-report=term-missing

# Live tests (requires kragd running)
uv run pytest tests/live/ -v
```

## Verification Checklist

- [ ] `per_space_result_counts` shows collection names in multi-collection debug output
- [ ] Multi-model + multi-collection queries use all embedding models
- [ ] `vector_spaces_searched` lists all spaces across all collections
- [ ] Health-check log suppression: burst of 100 → 1 log entry
- [ ] No regression on single-collection multi-model queries
- [ ] No regression on single-collection single-model queries
- [ ] Pre-commit validation passes: `ruff format` + `ruff check` + `pytest`
