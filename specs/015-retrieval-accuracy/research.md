# Research — 015-retrieval-accuracy

**Date**: 2025-07-17 | **Branch**: `015-retrieval-accuracy`

## R1: Two-Level RRF Feasibility (Type Flow)

**Decision**: Two-level RRF is feasible and will be implemented within `_multi_collection_retrieve()`.

**Rationale**:
- `_multi_model_retrieve()` returns `list[QueryResult]` after converting `RRFScoredPoint` objects via `_payload_to_query_result()`
- `_weighted_rrf()` accepts `list[list[Any]]` where each element has `.id`, `.score`, `.payload` attributes (lines 80-125 of retriever.py)
- `RRFScoredPoint` objects from an inner per-collection RRF satisfy the same duck-typed protocol
- The inner (per-collection) RRF merges vector-space results; the outer RRF merges per-collection results with collection weights

**Type flow for the combined path**:
```
Query
 ├─ embed_query() → dict[str, list[float]]           # all models
 ├─ Per collection:
 │   ├─ search_named() per vector space → list[ScoredPoint]
 │   ├─ reciprocal_rank_fusion() → list[RRFScoredPoint]  # inner merge
 │   └─ Wrap as list for outer merge
 └─ _weighted_rrf(per_collection_lists, weights) → list[RRFScoredPoint]
    └─ _payload_to_query_result() → list[QueryResult]    # final output
```

**Alternatives considered**:
- Flatten all vector-space results across all collections into a single RRF — rejected because it loses collection-weight semantics
- Return `list[QueryResult]` from inner merge instead of `RRFScoredPoint` — rejected because `_weighted_rrf()` needs `.id`/`.score`/`.payload` protocol, not `QueryResult` attributes

## R2: Named Vector Space Availability Per Collection

**Decision**: Collections may or may not have named vector spaces; the combined path must handle both formats gracefully.

**Rationale**:
- `CollectionManager.__init__()` creates all 4 collections as **single-vector** (no `vectors_config` parameter) — see collection_manager.py lines 81-97
- Named vectors are added only during **indexing** when `embedding_orchestrator.is_multi_model` is True — see indexer.py lines 240-258
- `qdrant_impl._ensure_collection()` handles format upgrades: if a collection exists as single-vector but named vectors are requested, it recreates the collection (lines 142-181)
- Whether a collection has named vectors depends on whether it has been indexed with a multi-model orchestrator

**Design implication**: The combined retrieval path must:
1. Check each collection's vector configuration before searching
2. Use `search_named()` for collections with named vectors
3. Fall back to `search()` (unnamed) for single-vector collections
4. Still track per-space counts accurately in both cases

**Alternatives considered**:
- Always recreate collections with named vectors at service start — rejected because it would destroy existing index data
- Require all collections to be re-indexed before using multi-model retrieval — rejected as poor UX; graceful degradation is preferred

## R3: `search_named()` Error Handling

**Decision**: Rely on existing exception-based error handling with per-space fallback tracking.

**Rationale**:
- `search_named()` (qdrant_impl.py lines 310-354) makes a direct Qdrant `query_points()` call with `using=vector_name` — no pre-validation of vector name existence
- Qdrant raises `ValueError` or HTTP 400 (BadRequest) if `vector_name` doesn't exist in the collection
- The caller in `_multi_model_retrieve()` (retriever.py lines 387-392) already catches `Exception`, logs a warning, and continues with `results = []`
- Per-space count is still recorded as 0 for failed spaces (line 394)

**Design implication**: The same try/except pattern should be replicated in the combined path when searching named vector spaces across multiple collections. No pre-validation query is needed.

**Alternatives considered**:
- Pre-fetch collection info to validate vector space existence before searching — rejected as an extra Qdrant round-trip per collection; the exception path is rare and already handled cleanly

## R4: Request Logging & Health-Check Suppression

**Decision**: Add a lightweight ASGI middleware in `create_app()` that logs all HTTP requests, suppressing `/health` to DEBUG level.

**Rationale**:
- **No HTTP request logging middleware** exists today (app.py) — only CORS middleware and exception handlers
- Uvicorn's default access log covers basic request logging, but filtering requires application-layer middleware
- Exception handlers (app.py lines 93-166) only log errors, not successful requests
- FastAPI's `@app.middleware("http")` is the standard pattern for per-request logging

**Implementation approach**:
```python
@app.middleware("http")
async def request_logging(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/health":
        logger.debug("%s %s → %d", request.method, request.url.path, response.status_code)
    else:
        logger.info("%s %s → %d", request.method, request.url.path, response.status_code)
    return response
```

**Alternatives considered**:
- Configure uvicorn's log filter to exclude `/health` — rejected because it requires patching uvicorn's logger, which is fragile across versions
- Use a third-party logging middleware (e.g., `loguru`) — rejected to avoid a new dependency for a simple feature
- Disable uvicorn access log entirely and replace with custom middleware — considered viable but more intrusive; the middleware approach supplements uvicorn's log

## R5: Debug Metadata Flow (Retriever → Service)

**Decision**: Extend the existing `_last_per_space_counts` pattern to the multi-collection path and add a `_last_collections_searched` attribute.

**Rationale**:
- `_multi_model_retrieve()` sets `self._last_per_space_counts: dict[str, int]` at line 376 of retriever.py
- `_multi_collection_retrieve()` does **NOT** set this attribute — this is the root cause of the debug metadata bug (FR-1 from spec)
- Service accesses the attribute via `getattr(retriever, "_last_per_space_counts", None)` at service.py line ~525
- When the attribute is missing, service falls back to Qdrant collection introspection, which incorrectly reports all results as "default" space
- The fallback path introspects vector spaces from one collection only, not per-collection breakdown

**Fix approach**:
1. In `_multi_collection_retrieve()`: set `self._last_per_space_counts` with collection-qualified keys (e.g., `"code:bge-base"`, `"code:jina-code"`) or a structured dict
2. Also set `self._last_collections_searched: list[str]` for the `collections_searched` debug field
3. Service's existing `getattr()` pattern picks up the data automatically — no service-side change needed for the core fix

**Alternatives considered**:
- Return debug metadata as part of `retrieve()` return value — rejected because it would change the public API signature; the attribute pattern is already established
- Use a separate debug context object passed through — rejected as over-engineering for the current need; instance attributes are sufficient
