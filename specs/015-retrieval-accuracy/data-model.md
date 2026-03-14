# Data Model — 015-retrieval-accuracy

**Date**: 2025-07-17 | **Branch**: `015-retrieval-accuracy`

## Entities

### Existing (Modified)

#### `Retriever` (src/krag/retrieval/retriever.py)

Instance attributes added/changed:

| Attribute | Type | Current | Change |
|-----------|------|---------|--------|
| `_last_per_space_counts` | `dict[str, int]` | Set only in `_multi_model_retrieve()` | Also set in `_multi_collection_retrieve()` with collection-level keys |
| `_last_collections_searched` | `list[str]` | Does not exist | New — tracks which collections were actually searched (including 0-result ones) |

**Key behaviour**: In multi-collection mode, `_last_per_space_counts` keys are collection names (e.g. `"code"`, `"tests"`). In single-collection multi-model mode, keys remain vector-space names (e.g. `"text"`, `"code-embeddings"`). The combined multi-model + multi-collection path uses composite keys: `"code:text"`, `"code:code-embeddings"`, `"tests:text"`.

#### `_multi_collection_retrieve()` (src/krag/retrieval/retriever.py)

| Aspect | Current | After |
|--------|---------|-------|
| Embedding | `generate_single(query)` | `embed_query(query)` when `is_multi_model`, else `generate_single(query)` |
| Per-collection search | `vs.search()` (unnamed vector) | `vs.search_named()` per vector space (if named vectors exist), fallback to `vs.search()` |
| Inner merge | None (single result list per collection) | `reciprocal_rank_fusion()` per collection when multi-model |
| `_last_per_space_counts` | Not set (bug) | Set with collection name keys (single-model) or composite `collection:space` keys (multi-model) |
| `_last_collections_searched` | Not set | Set with all collection names attempted (including 0-result ones) |

#### `DebugMetadata` (src/kragd/schemas.py)

No schema changes. The existing `per_space_result_counts: dict[str, int]` field already accepts arbitrary string keys. The semantic meaning of keys changes:
- Single-collection multi-model: keys = vector-space names (unchanged)
- Multi-collection single-model: keys = collection names (new, was incorrectly `{"default": N}`)
- Multi-collection multi-model: keys = `"collection:space"` composites (new)

### Existing (Unchanged)

#### `QueryResult` (src/krag/models/query_result.py)

No changes. The `collection: str | None` field already populated by `_multi_collection_retrieve()`.

#### `RRFScoredPoint` (src/krag/retrieval/rrf.py)

No changes. Dataclass with `id`, `score`, `payload` — already compatible with two-level RRF.

#### `CollectionStore` (src/krag/storage/collection_manager.py)

No changes. Provides `vector_store: QdrantVectorStore` per collection.

### New

#### `HealthLogFilter` (src/kragd/app.py)

Middleware state for health-check log suppression.

| Field | Type | Description |
|-------|------|-------------|
| `_last_was_health` | `bool` | Whether the most-recently-logged request was `GET /health` |

Initial value: `False` (reset on server startup, satisfying FR-010).

**State transitions**:
```
                  non-health request
    ┌──────────────────────────────────────────┐
    │                                          ▼
 ┌──┴────────────┐  GET /health (log it)   ┌────────────────┐
 │ _last_was_    │ ──────────────────────► │ _last_was_     │
 │ health=False  │                         │ health=True    │
 └───────────────┘ ◄────────────────────── └──────┬─────────┘
                    non-health request            │
                                                  │ GET /health
                                                  │ (suppress)
                                                  └──────┘
```

## Validation Rules

| Rule | Entity | Constraint |
|------|--------|------------|
| Per-space counts sum | `_last_per_space_counts` | Sum of values ≤ `fetch_limit × num_sources` (each source returns at most `fetch_limit`) |
| Collections searched | `_last_collections_searched` | Subset of keys from `target_collections` parameter |
| Composite key format | `_last_per_space_counts` | When composite: exactly one `:` separator, non-empty parts on both sides |
| Health filter reset | `HealthLogFilter` | `_last_was_health` is `False` at construction time |

## Relationships

```
Retriever
 ├─ owns → _last_per_space_counts: dict[str, int]
 ├─ owns → _last_collections_searched: list[str]
 ├─ uses → CollectionManager.get_store() → CollectionStore
 ├─ uses → EmbeddingOrchestrator.embed_query() (multi-model)
 ├─ uses → EmbeddingGenerator.generate_single() (single-model fallback)
 ├─ uses → QdrantVectorStore.search_named() / .search()
 └─ uses → reciprocal_rank_fusion() (inner) + _weighted_rrf() (outer)

KragService
 ├─ creates → Retriever (per query)
 ├─ reads  → retriever._last_per_space_counts (via getattr)
 ├─ reads  → retriever._last_collections_searched (via getattr, new)
 └─ builds → DebugMetadata

FastAPI app
 └─ middleware → HealthLogFilter (request logging + suppression)
```
