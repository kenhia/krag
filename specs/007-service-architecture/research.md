# Research: 007-service-architecture

**Date**: 2026-02-19
**Spec**: [spec.md](spec.md)
**Plan**: [plan.md](plan.md)

---

## R-01: FastAPI Lifespan & Dependency Injection

**Decision**: Use FastAPI's `lifespan` async context manager to initialize `KragService` at startup and tear it down at shutdown. Store the singleton on `app.state` and expose it to route handlers via a `Depends()` callable.

**Rationale**: The lifespan pattern replaces the deprecated `on_event("startup")`/`on_event("shutdown")` hooks. Storing on `app.state` is the FastAPI-documented approach — it avoids module-level global singletons and keeps the service testable (construct a test app with a mock service). The `Depends(get_service)` callable provides type-hinted injection into every route handler.

**Pattern**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    service = KragService(config)
    await service.start()
    app.state.service = service
    yield
    await service.shutdown()

def get_service(request: Request) -> KragService:
    return request.app.state.service
```

**Alternatives considered**:
- *Module-level global singleton*: Works but makes testing harder and couples routes to module import order.
- *`on_event` decorators*: Deprecated since FastAPI 0.93; don't support sharing state between startup and shutdown.
- *ContextVar*: Overkill for a single-user service; designed for per-request state.

---

## R-02: Sync vs Async Route Handlers

**Decision**: Use plain `def` (synchronous) route handlers for any endpoint that calls LLM inference or other blocking operations. Use `async def` only for non-blocking endpoints like `/health`.

**Rationale**: FastAPI runs `def` handlers in a thread pool (`anyio.to_thread.run_sync`), which prevents blocking the uvicorn event loop. If you declare `async def` and then call a synchronous blocking function (like `llm_pool.route_and_generate()`), you block the single event loop thread, freezing health checks, concurrent requests, and the idle-timeout timer. With `def` handlers, uvicorn's default thread pool (40 threads) dispatches each request to a worker thread. Since `LLMPool` already serializes LLM access through `threading.Lock`, concurrent requests naturally queue at the lock — exactly the desired behavior for a single-user service.

**Async-eligible endpoints**: `GET /health` (no blocking work, returns immediately).  
**Sync-required endpoints**: `POST /query`, `POST /retrieve`, `POST /index`, `POST /debug/query`, `POST /debug/qdrant`, `POST /shutdown`, `POST /eval`.  
**Either-works endpoints**: `GET /status` (calls `get_free_vram()` which may do torch CUDA call — use `def` to be safe).  

**Alternatives considered**:
- *`async def` + `asyncio.to_thread()`*: Functionally equivalent to `def` handlers but adds boilerplate for no benefit; FastAPI does this automatically for `def` handlers.
- *Increase thread pool size*: Default 40 is fine; `LLMPool._lock` serializes GPU-bound work anyway.

---

## R-03: PID File Management

**Decision**: Write the PID file to `$XDG_RUNTIME_DIR/kragd.pid`, falling back to `/tmp/kragd.pid` if `XDG_RUNTIME_DIR` is unset.

**Rationale**: `XDG_RUNTIME_DIR` (typically `/run/user/<uid>`) is the XDG-specified location for runtime files — it's per-user, has correct permissions, and is cleaned up on logout. The existing `src/krag/config/xdg.py` provides `get_xdg_config_home()`, `get_xdg_cache_home()`, and `get_xdg_state_home()`, but does **not** have a `get_xdg_runtime_dir()`. A new helper should be added following the same pattern.

**Stale PID detection**:
1. Read PID from file.
2. Call `os.kill(pid, 0)` — if `OSError` with `errno.ESRCH`, the PID is stale.
3. Optionally read `/proc/<pid>/cmdline` to verify it's a `kragd` process (avoids PID reuse false positives).
4. On startup: if PID file exists and PID is stale, overwrite. If alive, abort with error.
5. On shutdown: remove PID file in lifespan teardown.

**Alternatives considered**:
- *`XDG_STATE_HOME/krag/kragd.pid`*: State home is for persistent state across reboots. PID files are ephemeral — `XDG_RUNTIME_DIR` is semantically correct.
- *`/tmp/kragd.pid`*: World-readable, persists across login sessions. Acceptable only as fallback.
- *Lock files (fcntl.flock)*: More robust but overkill for a single-user tool.

---

## R-04: LLM Idle Timeout Implementation

**Decision**: Use `asyncio.create_task` with a cancellable timer (asyncio.sleep) for idle timeout. Track in-flight requests with a `threading.Lock`-guarded counter (accessed from thread pool workers).

**Rationale**: `asyncio.create_task` with `asyncio.sleep` is cancellable via `task.cancel()`, integrates naturally with the FastAPI/uvicorn event loop, and doesn't spawn extra OS threads. The in-flight counter uses `threading.Lock` because `def` route handlers run in the thread pool, not the event loop. The actual unload call is dispatched to a thread via `asyncio.to_thread` to avoid blocking the event loop during unload.

**Pattern**:
```python
class LLMLifecycleManager:
    def __init__(self, pool: LLMPool, idle_timeout: int, primary_llm: str | None):
        self._pool = pool
        self._idle_timeout = idle_timeout
        self._primary_llm = primary_llm
        self._timer_task: asyncio.Task | None = None
        self._inflight = 0
        self._lock = threading.Lock()

    def on_request_start(self, slot: str):
        """Called from thread pool worker at request start."""
        self._cancel_timer()
        with self._lock:
            self._inflight += 1

    def on_request_end(self, slot: str):
        """Called from thread pool worker at request end."""
        with self._lock:
            self._inflight -= 1
            if self._inflight == 0 and slot != self._primary_llm:
                self._schedule_unload(slot)

    def _schedule_unload(self, slot: str):
        loop = asyncio.get_event_loop()
        self._timer_task = loop.create_task(self._unload_after_timeout(slot))

    async def _unload_after_timeout(self, slot: str):
        await asyncio.sleep(self._idle_timeout)
        with self._lock:
            if self._inflight == 0:
                await asyncio.to_thread(self._do_unload, slot)

    def _do_unload(self, slot: str):
        # Unload via LLMPool mechanisms
        ...
```

**Key behaviors**:
- Primary LLM (if configured): never subject to idle timeout.
- Secondary LLM: loaded on demand, unloaded after `idle_timeout` seconds of inactivity.
- No primary configured: both LLMs unload after idle timeout.
- Timer is cancelled and restarted on every request.
- Unload is deferred if any request is in-flight (FR-006).

**Alternatives considered**:
- *`threading.Timer`*: Creates a new OS thread per reset, interacts poorly with asyncio.
- *APScheduler*: Heavy dependency for a simple timer.
- *Periodic polling loop*: Wastes cycles; event-driven cancel+reschedule is cleaner.

---

## R-05: Reusing `build_query_pipeline()`

**Decision**: Refactor `build_query_pipeline()` to raise `ConfigurationError` instead of `SystemExit(1)`, then have both CLI and service call it. For the service, skip LLM loading at pipeline build time and let `LLMLifecycleManager` control LLM lifecycle separately.

**Rationale**: The existing function is a clean factory with no global state mutation. It takes `config_path`, `top_k`, and `preset` and returns an immutable `QueryPipeline` dataclass containing all components KragService needs. However, two issues block direct reuse:

1. **`SystemExit(1)`**: If the vector store path doesn't exist, the function calls `print(..., file=sys.stderr)` and `raise SystemExit(1)`. In a service context, this kills the process. Fix: replace with `raise ConfigurationError(...)`.
2. **Eager LLM loading**: `LLMPool.__init__` loads the text model immediately. For the service, the `LLMLifecycleManager` should control when/how models load. Fix: either (a) add a `defer_llm_loading` parameter to `build_query_pipeline()`, or (b) have `KragService` build the pipeline components individually (config → embeddings → vector store → LLM separately).

**Recommendation**: Option (b) — KragService builds components individually, extracting the initialization logic pattern from `build_query_pipeline()` without calling it directly. This keeps `build_query_pipeline()` unchanged for `krag-direct` and gives the service full control over initialization order and error handling.

**Alternatives considered**:
- *Call `build_query_pipeline()` directly*: Requires modifying the function's error handling and LLM loading behavior, which could affect `krag-direct`.
- *Copy-paste the function*: DRY violation; diverges over time.
- *Extract shared initialization helpers*: Best long-term option. Refactor common initialization steps (config loading, embedding init, vector store init) into reusable functions called by both pipeline builder and service.

---

## R-06: LLMPool Thread Safety & Wrapping

**Decision**: `LLMLifecycleManager` wraps `LLMPool` without modifying it. For unloading the secondary slot, use `pool.swap_to(primary)` (which unloads the other) when a primary is configured, or `pool.close()` + re-init when no primary is configured.

**Rationale**: Analysis of `LLMPool` thread safety:

| Method | Thread-safe? | Notes |
|--------|-------------|-------|
| `route_and_generate()` | Yes (acquires `_lock`) | Entire route+generate cycle under lock |
| `swap_to(name)` | Yes (acquires `_lock`) | Public hot-swap API, validates target |
| `close()` | No (no lock) | Safe to call multiple times; only call when no requests in-flight |
| `get_active_llm()` | No (no lock) | Read-only, safe for status checks |
| `get_status()` | No (no lock) | Returns dict with slot status and VRAM info |

**Wrapping strategy**:
- **For queries**: Call `pool.route_and_generate()` — handles locking, routing, swap internally. The lifecycle manager tracks in-flight count around this call.
- **For idle unload (with primary)**: Call `pool.swap_to(primary_name)` to ensure primary is loaded and secondary is unloaded (hot-swap mode handles this).
- **For idle unload (no primary)**: Call `pool.close()`. On next request, re-initialize the pool.
- **For shutdown**: Call `pool.close()`.

**Key constraint**: No modifications to `LLMPool` source code. The lifecycle manager is purely additive.

**Alternatives considered**:
- *Add public `unload(name)` to LLMPool*: Would be cleaner but violates the "no core changes" constraint.
- *Call `pool._unload_slot()` directly*: Private API, not thread-safe, fragile.

---

## R-07: Signal Handling & Graceful Shutdown

**Decision**: Let uvicorn handle `SIGTERM`/`SIGINT` natively. Put all cleanup logic in the FastAPI lifespan teardown (code after `yield`).

**Rationale**: Uvicorn installs its own signal handlers. When SIGTERM/SIGINT is received, uvicorn:
1. Stops accepting new connections.
2. Waits for in-flight requests to complete (configurable timeout).
3. Triggers ASGI lifespan shutdown (code after `yield`).

Custom `signal.signal()` handlers would conflict with uvicorn's and with asyncio's event loop.

**Shutdown flow**:
```
SIGTERM → uvicorn stops accepting → in-flight requests complete → lifespan teardown:
  1. Cancel idle timer
  2. pool.close() (unload LLMs, free VRAM)
  3. vector_store.close() (if applicable)
  4. Remove PID file
  5. Log "kragd shut down cleanly"
```

**`POST /shutdown` endpoint**: Calls `os.kill(os.getpid(), signal.SIGTERM)` to trigger the same graceful flow through uvicorn's handler.

**`krag stop` CLI command**: Reads PID from PID file, sends `os.kill(pid, signal.SIGTERM)`.

**Edge cases**:
- *Hard kill (SIGKILL)*: Lifespan teardown won't run. PID file is stale. Handled by stale-PID detection on next startup. VRAM freed by OS on process exit.
- *Double SIGTERM*: Uvicorn handles gracefully (second signal forces immediate exit).

**Alternatives considered**:
- *Custom `signal.signal()`*: Conflicts with uvicorn and asyncio.
- *`atexit` handlers*: Not reliable for SIGTERM; only fires on normal interpreter exit.
- *`loop.add_signal_handler()`*: Duplicates what uvicorn already does.

---

## R-08: Configuration Extension for `[service]` Section

**Decision**: Add a `ServiceConfiguration` Pydantic model and a `[service]` section to the TOML config. Extend `ConfigManager` to parse this new section. All fields have defaults so the service works without explicit configuration.

**Rationale**: The existing `ConfigManager.load()` parses TOML section-by-section and maps to `Configuration` fields. Adding a `[service]` section follows the established pattern. The `ServiceConfiguration` is a nested `BaseModel` on `Configuration` (like `PluginConfiguration`).

**Config fields**:
```toml
[service]
host = "0.0.0.0"           # Default: bind to all interfaces (LAN access per user Q1)
port = 8742                 # Default: "KRAG" on phone keypad
primary_llm = "text"        # "text", "code", or omit for no primary
idle_timeout = 300           # Seconds before non-primary LLM unloads
log_requests = true          # Log API requests to krag.log
```

**Impact on existing code**: Additive only. `Configuration` gets a new optional `service: ServiceConfiguration` field with a default factory. Existing code that doesn't use `[service]` is unaffected.

---

## R-09: QdrantVectorStore Direct Search for Debug Endpoint

**Decision**: The `POST /debug/qdrant` endpoint bypasses `Retriever` and calls `QdrantVectorStore.search()` (or `search_named()`) directly, then returns raw results without dedup, boost, or RRF.

**Rationale**: The spec (FR-020) requires raw vector store search. The existing `QdrantVectorStore` already exposes `search()` and `search_named()` methods that return `QueryResult` objects with scores. The `Retriever` adds dedup, keyword/metadata boosting, threshold filtering, and RRF — all of which the debug endpoint deliberately skips. By calling the vector store directly, we get raw similarity scores that can be independently verified against the Qdrant client.

**Filtering**: Qdrant supports payload filtering via `qdrant_client.models.Filter`. The debug endpoint can construct filter conditions from the request's `file_type` and `file_path_contains` fields and pass them to the search call. This may require a small extension to the vector store's search method (adding a `filter` parameter), or constructing the filter and calling the qdrant_client directly.

**Alternatives considered**:
- *Add a `raw_search()` method to Retriever*: Muddies the Retriever's responsibility. The debug endpoint should go directly to the vector store.
- *New `DebugRetriever` class*: Over-engineering for what's a simple pass-through to Qdrant.
