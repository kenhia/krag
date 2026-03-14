# Retriever Contracts — 015-retrieval-accuracy

## `_multi_collection_retrieve` (Modified)

**File**: `src/krag/retrieval/retriever.py`

### Signature (unchanged)

```python
def _multi_collection_retrieve(
    self,
    query: str,
    fetch_limit: int,
    target_collections: dict[str, float],
) -> list[QueryResult]:
```

### Preconditions

- `self.collection_manager is not None`
- `self.embedding_generator is not None`
- `target_collections` is non-empty, keys are collection names, values are positive floats
- If multi-model path: `self.embedding_orchestrator is not None` and `self.embedding_orchestrator.is_multi_model is True`

### Postconditions

- Returns `list[QueryResult]` — each result has `collection` field set to its source collection name
- `self._last_per_space_counts` is set to `dict[str, int]`:
  - **Single-model path**: keys are collection names (e.g. `{"code": 60, "tests": 45}`)
  - **Multi-model path**: keys are `"collection:space"` composites (e.g. `{"code:text": 60, "code:code-embeddings": 58, "tests:text": 45, "tests:code-embeddings": 42}`)
  - Collections that returned 0 results still appear with value `0`
  - Collections skipped due to KeyError do NOT appear
- `self._last_collections_searched` is set to `list[str]` — all collection names attempted (including 0-result, excluding unknown collections)

### Behavioural Contract

1. **Embedding generation**:
   - If `self.embedding_orchestrator is not None` and `self.embedding_orchestrator.is_multi_model`:
     - Call `self.embedding_orchestrator.embed_query(query)` → `dict[str, list[float]]`
   - Else:
     - Call `self.embedding_generator.generate_single(query)` → single embedding

2. **Per-collection search**:
   - For each `(collection_name, weight)` in `target_collections`:
     - Resolve `CollectionStore` via `self.collection_manager.get_store(collection_name)`
     - **Multi-model**: For each `(vector_name, embedding)` in query embeddings:
       - Try `vs.search_named(embedding, vector_name, limit=fetch_limit)`
       - On exception: log warning, use empty results, record count as 0
       - Record `_last_per_space_counts[f"{collection_name}:{vector_name}"] = len(results)`
     - **Multi-model inner merge**: `reciprocal_rank_fusion(per_space_lists, k=60, limit=fetch_limit)` → inner `list[RRFScoredPoint]`
     - **Single-model**: `vs.search(embedding, limit=fetch_limit)` → convert to `list[RRFScoredPoint]`
       - Record `_last_per_space_counts[collection_name] = len(results)`
     - Tag each point's payload with `_collection: collection_name`

3. **Cross-collection merge**:
   - `_weighted_rrf(all_result_lists, collection_weights, k=60, limit=fetch_limit)` → `list[RRFScoredPoint]`

4. **Conversion**:
   - Convert each `RRFScoredPoint` → `QueryResult` via `_payload_to_query_result()`
   - Set `qr.collection = point.payload.pop("_collection")`

### Error Handling

| Error | Handling |
|-------|----------|
| Unknown collection name (KeyError) | Log warning, skip collection, continue |
| `search()` / `search_named()` failure | Log warning with `exc_info`, use empty results, continue |
| All collections return empty | Return `[]`, `_last_per_space_counts` shows all zeros |

---

## `_last_per_space_counts` (Modified Attribute)

**File**: `src/krag/retrieval/retriever.py`

### Contract

| Path | Set by | Key format | Example |
|------|--------|------------|---------|
| Single-collection, single-model | `retrieve()` (not set — fallback in service) | N/A | N/A |
| Single-collection, multi-model | `_multi_model_retrieve()` | vector-space name | `{"text": 60, "code-embeddings": 58}` |
| Multi-collection, single-model | `_multi_collection_retrieve()` | collection name | `{"code": 60, "tests": 45}` |
| Multi-collection, multi-model | `_multi_collection_retrieve()` | `collection:space` | `{"code:text": 60, "code:code-embeddings": 58, ...}` |

### Consumer

`KragService.query()` reads via `getattr(retriever, "_last_per_space_counts", None)`. No service-side changes needed for core fix — the existing `getattr` + fallback logic already handles all cases.

---

## `_last_collections_searched` (New Attribute)

**File**: `src/krag/retrieval/retriever.py`

### Contract

- Type: `list[str]`
- Set by: `_multi_collection_retrieve()` only
- Contains: All collection names that were attempted (resolved from `target_collections` keys), including those that returned 0 results
- Does NOT contain: Collection names that raised `KeyError` (unknown collections)
- Consumer: `KragService.query()` — can use via `getattr(retriever, "_last_collections_searched", None)` to populate `DebugMetadata.collections_searched`

---

## Debug Metadata Builder (Modified Logic)

**File**: `src/kragd/service.py`, lines ~630-696

### Contract Change

Current: When `_last_per_space_counts` is `None`, falls back to introspecting Qdrant collection metadata from a single vector store, producing `{"default": N}`.

After: When `_last_per_space_counts` is populated (which it now always is for multi-collection), use it directly. The fallback path remains for the single-collection single-model case (no change needed there).

Additional: if `_last_collections_searched` is available, use it for `DebugMetadata.collections_searched` field instead of deriving from mode config.

### `vector_spaces_searched` Extraction

When `_last_per_space_counts` contains composite `collection:space` keys (multi-model + multi-collection path), the debug metadata builder MUST extract clean vector-space names for `DebugMetadata.vector_spaces_searched` by splitting each key on `:` and collecting the unique space-name parts (right-hand side). For non-composite keys (single-model multi-collection), `vector_spaces_searched` should report the collection names as-is (matching current passthrough behaviour).
