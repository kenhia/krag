# Middleware Contracts — 015-retrieval-accuracy

## Health-Check Log Suppression Middleware

**File**: `src/kragd/app.py`

### Registration

Added in `create_app()` as an ASGI middleware, after CORS middleware:

```python
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next: ...) -> Response:
```

### State

| Field | Type | Initial | Description |
|-------|------|---------|-------------|
| `_last_was_health` | `bool` | `False` | Tracks whether the most-recently-logged request was `GET /health` |

State is scoped to the FastAPI `app` instance (via closure or `app.state`). Resets on server restart (FR-010).

### Behaviour

```
on_request(request):
  response = await call_next(request)
  is_health = (request.method == "GET" and request.url.path == "/health")

  if is_health and _last_was_health:
      # Suppress from INFO — log at DEBUG
      log DEBUG: "{method} {path} → {status} (suppressed)"
  elif is_health:
      # First health in a sequence — log and set flag
      log INFO: "{method} {path} → {status}"
      _last_was_health = True
  else:
      # Non-health request — always log, reset flag
      log INFO: "{method} {path} → {status}"
      _last_was_health = False

  return response
```

### Invariants

- Every non-health request is logged (INFO level)
- The first `GET /health` after a non-health request is logged (INFO level)
- Consecutive `GET /health` requests after the first are logged at DEBUG level (suppressed from INFO)
- `_last_was_health` is `False` at startup (no stale state)
- Middleware does not modify the response body or headers
- Middleware does not affect response timing (logging is post-`call_next`)

### Edge Cases

| Scenario | Behaviour |
|----------|-----------|
| First request ever is `GET /health` | Logged (initial state is `False`) |
| `GET /health` with query params | Still treated as health check (path match only) |
| `POST /health` (hypothetical) | NOT treated as health check (method must be GET) |
| Concurrent requests | State is per-process; race conditions between concurrent requests are acceptable since exact suppression count is not critical |
| Server restart | `_last_was_health` resets to `False` |

### Test Contract

Tests must verify (see spec acceptance scenarios for US3):
1. 5 consecutive `GET /health` → only 1 INFO log entry (remaining 4 at DEBUG)
2. `GET /health` → `GET /query` → `GET /health` → 3 log entries (all logged)
3. Single `GET /health` in isolation → logged
