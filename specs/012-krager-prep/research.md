# Research: krager Prep — API Normalization & Hardening

**Branch**: `012-krager-prep` | **Date**: 2026-02-28

All NEEDS CLARIFICATION items from Technical Context have been resolved.

---

## 1. SSE Transport: sse-starlette vs StreamingResponse

**Decision**: Use `sse-starlette` (v3.3.2, current stable)

**Rationale**: Provides SSE field formatting, keep-alive pings (default 15s), automatic client disconnect detection via `CancelledError`, cooperative graceful shutdown, and `send_timeout` for dead connections. All things that would need manual reimplementation with raw `StreamingResponse`.

**Alternatives considered**:
- `StreamingResponse` with `media_type="text/event-stream"` — requires manual SSE formatting, keep-alive, and disconnect detection. Rejected: unnecessary boilerplate.
- WebSocket — bidirectional, more complex. Rejected: SSE is unidirectional which matches both use cases (server pushes events to client).

---

## 2. Thread-to-Async Bridging Pattern

**Decision**: `asyncio.Queue` + `asyncio.get_event_loop().run_coroutine_threadsafe(queue.put(event), loop)`

**Rationale**: Zero-latency wakeup (no polling interval), stdlib only, no new dependencies. The indexing thread calls `run_coroutine_threadsafe(queue.put(event), loop)` to push progress events. The async SSE generator does `await queue.get()` to consume them.

**Client disconnect handling**: Set a `threading.Event` flag that the background thread checks between work units. When the SSE generator's `CancelledError` fires (client disconnects), set the flag to stop the producer.

**Alternatives considered**:
- `queue.Queue` polled from async generator — requires polling interval, adds latency. Rejected.
- `janus` library (dual sync/async queue) — clean API but adds a dependency for a simple use case. Rejected.

---

## 3. CORS Configuration for Tauri Webview

**Decision**: Add `CORSMiddleware` to kragd with `allow_origins=["*"]` as the default, configurable via `KRAGD_CORS_ORIGINS` environment variable.

**Rationale**: Tauri v2's webview (webkit2gtk on Linux) sends an `Origin` header (`tauri://localhost` on Linux, `http://tauri.localhost` on Windows) and enforces standard CORS. Without CORS middleware, `fetch()` calls from the Tauri webview to kragd are blocked. Since kragd binds to localhost by default and doesn't use credentials/cookies, a wildcard origin is safe and avoids platform-specific origin configuration.

**Configuration details**:
- `allow_origins`: `["*"]` default, overridable via `KRAGD_CORS_ORIGINS` env var (comma-separated)
- `allow_credentials`: `False` (no auth cookies; keeps wildcard spec-compliant)
- `allow_methods`: `["*"]` (future-proof as endpoints evolve)
- `allow_headers`: `["*"]` (same reasoning)
- Non-browser clients (no `Origin` header): pass through unmodified — middleware only activates when `Origin` is present

**Alternatives considered**:
- Specific origin list per platform (`tauri://localhost`, `http://tauri.localhost`) — fragile, platform-dependent. Rejected for default config.
- No CORS at all — doesn't work; webview enforces CORS. Rejected.

---

## 4. LLM Streaming Lock Strategy

**Decision**: Hold LLM pool lock only during routing and model loading; release before streaming. Use a "slot in use" flag to prevent concurrent access during streaming.

**Rationale**: The current `LLMPool.route_and_generate()` holds `self._lock` for the entire generation. For streaming, this would block all other requests for the full duration of generation (which can be seconds). Instead:
1. Acquire lock → route to slot → ensure model loaded → set `slot.streaming = True` → release lock
2. Stream tokens from the model (lock-free, but slot is marked busy)
3. On completion/error, acquire lock → set `slot.streaming = False` → release lock

The LLM is single-slot anyway, so concurrent generation isn't possible — but releasing the lock allows health checks, status queries, and mode switches to proceed without blocking.

**Sync-to-async bridge for LLM tokens**: Run `create_chat_completion(stream=True)` iteration in a `ThreadPoolExecutor(max_workers=1)`. Push token deltas into an `asyncio.Queue`. The SSE generator reads from the queue. Client disconnect sets a `threading.Event` checked between token iterations.

**Alternatives considered**:
- Hold lock for entire stream duration — simpler but blocks all other LLM operations. Rejected.
- Use asyncio-native LLM library — none available for llama-cpp-python. Rejected.

---

## 5. SSE Event Format

**Decision**: JSON-encoded `data:` field, named `event:` types using `resource:action` convention, sequential `id:` fields.

**Event types for index progress**:
- `event: index:progress` — `data: {"current": N, "total": M, "stage": "Processing files", "file": "path/to/file"}`
- `event: index:complete` — `data: {"job_id": "...", "status": "completed", ...full IndexResponse fields}`
- `event: index:error` — `data: {"job_id": "...", "error": "message"}`
- `event: index:idle` — `data: {"message": "No active indexing job"}` (sent on connect when nothing is running)

**Event types for streaming queries**:
- `event: query:sources` — `data: {"sources": [...SourceChunk...]}` (sent first, after retrieval completes)
- `event: query:token` — `data: {"token": "partial text"}` (sent per token/chunk from LLM)
- `event: query:done` — `data: {"answer": "full answer", "sources": [...], "debug": {...}}` (final complete response)
- `event: query:error` — `data: {"error": "message"}` (mid-stream error)

**Alternatives considered**:
- Untyped SSE (all data, no event field) — clients can't distinguish event types. Rejected.
- Colon-free event names (e.g., `indexProgress`) — less readable, no convention. Rejected in favor of `resource:action`.

---

## 6. Testing SSE Endpoints

**Decision**: Use `TestClient.stream()` + `response.iter_lines()` to parse SSE events in contract tests.

**Rationale**: FastAPI's TestClient (built on httpx) supports streaming responses. Iterate lines, parse `event:` and `data:` fields. A small `parse_sse_stream()` test helper avoids repetitive parsing across tests.

**Test patterns**:
- Contract tests: mock service, verify event sequence (progress → complete) and (sources → tokens → done)
- Live tests: against running kragd, verify real SSE events during actual indexing and query operations
- Timeout handling: tests set a reasonable timeout and assert events arrive within it

**Alternatives considered**:
- `pytest-httpx` for SSE testing — designed for mocking outbound requests, not SSE consumption. Rejected.
- Playwright/browser-based SSE testing — overkill for API contract tests. Rejected.

---

## 7. `/index/status` Normalization Impact

**Decision**: Change return type from `IndexResponse | list[IndexResponse]` to `list[IndexResponse]` unconditionally.

**Rationale**: The polymorphic return type forces every client to check `isinstance` or inspect the response shape. Returning a list always — empty when no jobs exist, one-element for a single job — is idiomatic and predictable.

**Impact assessment**:
- **kragd router**: Change `response_model` and return type annotation on `index_status()`
- **Service layer**: `get_index_status()` already returns a list internally; just ensure it always returns `list` even when one result (currently unwraps single-element lists)
- **CLI `krag index-status`**: Already has `--json` and handles both shapes. Update to expect list only.
- **Existing contract tests**: Must be updated to expect list response
- No external consumers beyond CLI (kragd is a personal tool, pre-1.0)

**Alternatives considered**:
- Keep polymorphic and require clients to handle both — defeats the purpose. Rejected.
- Return a wrapper object `{"jobs": [...]}` — unnecessary envelope, breaks convention with other endpoints. Rejected.

---

## 8. Existing Index Progress Callback Infrastructure

**Decision**: Leverage the existing `progress_callback: Callable[[int, int, str], None]` parameter on `IndexingOrchestrator.index_full()` and `index_incremental()`.

**Rationale**: The orchestrator already accepts a `progress_callback(current, total, stage_name)` but `_run_indexing()` in `service.py` does not pass one. Wiring a callback that pushes events to an `asyncio.Queue` is the cleanest integration point — no changes needed to the orchestrator itself.

**Callback granularity**:
- File discovery: `(0, 0, "Discovering files")`
- Per-file processing: `(i+1, total_files, "Processing files")`
- Vector storage batches: `(stored, total, "Storing vectors (collection_name)")`

This gives sufficient granularity for real-time progress display in a client UI.

---

## 9. New Dependency: sse-starlette

**Decision**: Add `sse-starlette>=2.0.0` to project dependencies in `pyproject.toml`.

**Rationale**: Well-maintained (19.3k dependents), BSD-3 licensed, no transitive dependencies beyond Starlette (already a FastAPI dependency). Provides `EventSourceResponse` with keep-alive, disconnect detection, and proper SSE formatting.

**Alternative considered**:
- Manual implementation via `StreamingResponse` — more code, less reliable disconnect handling. Rejected.

---

## 10. OpenAPI Enhancement Strategy

**Decision**: Enhance existing FastAPI endpoint decorators and Pydantic model definitions in-place.

**Changes needed**:
- **Router tags**: Each `APIRouter` already has or should have a `tags=["..."]` parameter. Verify all 6 routers.
- **Endpoint summaries**: Add `summary="..."` to every `@router.get/post(...)` decorator.
- **Field descriptions**: Audit every Pydantic model field for `description=` in `Field()`. Models in `schemas.py` are mostly complete; verify the three relocated schemas.
- **Request body examples**: Add `model_config = ConfigDict(json_schema_extra={"examples": [...]})` or use `Body(examples=[...])` on endpoint parameters.

**No external tooling needed** — FastAPI auto-generates the OpenAPI spec from these decorators.
