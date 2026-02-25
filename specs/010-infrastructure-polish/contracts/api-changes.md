# API Contract Changes: Infrastructure Polish

**Sprint**: 010-infrastructure-polish
**Date**: 2026-02-23

---

## 1. Exception-to-HTTP-Status Mapping (US8)

### Current (fragile string matching)

```python
# app.py — BEFORE
@app.exception_handler(RuntimeError)
async def runtime_error_handler(request, exc):
    msg = str(exc).lower()
    if "indexing is in progress" in msg:
        return JSONResponse(status_code=409, ...)
    if "already in progress" in msg:
        return JSONResponse(status_code=409, ...)
    if "not started" in msg:
        return JSONResponse(status_code=503, ...)
    return JSONResponse(status_code=500, ...)
```

### Target (type-based dispatch)

```python
# app.py — AFTER
@app.exception_handler(ServiceNotReadyError)
async def service_not_ready_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})

@app.exception_handler(IndexingInProgressError)
async def indexing_in_progress_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(ResourceNotConfiguredError)
async def resource_not_configured_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})

@app.exception_handler(KragError)
async def krag_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
```

### HTTP Response Contract (unchanged)

No changes to response body formats. All error responses continue to use:

```json
{
  "detail": "Human-readable error message"
}
```

Status code semantics remain identical:
| Code | Meaning | Exception Type |
|------|---------|---------------|
| 409 | Indexing in progress / already running | `IndexingInProgressError` |
| 503 | Service not started | `ServiceNotReadyError` |
| 500 | Unhandled / resource not configured | `ResourceNotConfiguredError`, `KragError` |

---

## 2. Query/Debug-Query Unification (US3)

### Current Endpoints

| Method | Path | Service Method |
|--------|------|---------------|
| POST | `/query` | `service.query()` |
| POST | `/debug/query` | `service.debug_query()` |

### Target Endpoints (unchanged URLs, unified backend)

| Method | Path | Service Method | Notes |
|--------|------|---------------|-------|
| POST | `/query` | `service.query(include_debug=False)` | Same response schema |
| POST | `/debug/query` | `service.query(include_debug=True)` | Debug metadata populated |

### Response Schema Contract

**`POST /query`** — No change to `QueryResponse`:
```json
{
  "answer": "...",
  "sources": [...],
  "mode": "default"
}
```

**`POST /debug/query`** — No change to `DebugQueryResponse`:
```json
{
  "answer": "...",
  "sources": [...],
  "mode": "default",
  "debug": {
    "llm_used": "default",
    "query_time_ms": 123.4,
    "retrieval_time_ms": 45.6,
    "synthesis_time_ms": 77.8,
    "chunks_retrieved": 10,
    "chunks_post_critic": 7,
    "critic_scores": [...],
    "vector_spaces_searched": ["text", "code"]
  }
}
```

**Guarantee**: For the same query, mode, and index state, `answer` and `sources` are identical between `/query` and `/debug/query`.

---

## 3. Index Status Accuracy (US2)

### Endpoint

`GET /index/status`

### Behavioural Contract Change

| Condition | Current Response | Target Response |
|-----------|-----------------|-----------------|
| Indexing active, previous result cached | Returns cached previous result | Returns `{"status": "running", ...}` |
| Indexing active, no previous result | Returns `{"status": "running", ...}` | No change |
| Indexing complete | Returns completed result | No change |

The response schema for `IndexResponse` is unchanged. The fix is ordering — the active-indexing check runs before the cache check.

---

## 4. Schema Rename (US10)

### `IndexError` → `IndexingFileError`

This is an internal Pydantic model name change. The JSON wire format is unchanged:

```json
{
  "errors": [
    {
      "file_path": "/path/to/file.py",
      "error_type": "UnicodeDecodeError",
      "error_message": "..."
    }
  ]
}
```

The OpenAPI schema name changes from `IndexError` to `IndexingFileError`. Clients using generated SDKs would see a renamed type, but the JSON structure is identical.

---

## 5. Index Status Union Return Type (noted, not changed this sprint)

`GET /index/status` currently has `response_model=IndexResponse | list[IndexResponse]`. This produces confusing OpenAPI schemas. Noted for future cleanup but out of scope for this sprint to avoid client-breaking changes.

---

## 6. No New Endpoints

This sprint adds no new HTTP endpoints. All changes are to internal implementation, exception handling, and behavioural correctness of existing endpoints.
