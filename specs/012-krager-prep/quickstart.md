# Quickstart: krager Prep — API Normalization & Hardening

**Branch**: `012-krager-prep` | **Date**: 2026-02-28

## Overview

This guide covers the implementation order, key patterns, and verification steps for the krager prep sprint. Work is organized into 6 implementation phases, ordered by dependency and priority.

---

## Phase 1: Schema Consolidation & API Normalization (P1)

**Goal**: All response models live in `schemas.py`; `/index/status` always returns a list.

### Steps

1. **Move `LexiconRefreshResponse`** from `src/kragd/routers/lexicon.py` to `src/kragd/schemas.py`
   - Copy the class definition (with `Field` descriptors) to `schemas.py`
   - In `lexicon.py`, replace the class with `from kragd.schemas import LexiconRefreshResponse`
   - Verify the `@router.post` decorator still references the correct model

2. **Move `ModeDetailResponse` and `ModeListResponse`** from `src/kragd/routers/modes.py` to `src/kragd/schemas.py`
   - Copy both class definitions to `schemas.py`
   - `ModeListResponse` depends on `ModeInfo` which is already in `schemas.py` — no import changes
   - In `modes.py`, replace both classes with imports from `schemas`

3. **Normalize `/index/status`** in `src/kragd/routers/index.py`
   - Change `response_model=IndexResponse | list[IndexResponse]` to `response_model=list[IndexResponse]`
   - Change return type annotation to `list[IndexResponse]`
   - Update `KragService.get_index_status()` in `service.py` to always return `list[IndexResponse]`
   - Update CLI `krag index-status` if it handles the polymorphic type

### Verification

```bash
uv run pytest tests/contract/api/ -v -k "index or modes or lexicon"
# Verify all existing tests still pass (update assertions for list return)
python -c "from kragd.schemas import LexiconRefreshResponse, ModeListResponse, ModeDetailResponse; print('OK')"
```

---

## Phase 2: CORS Middleware (P1)

**Goal**: Browser-based clients can call kragd without CORS errors.

### Steps

1. **Add CORS middleware** to `src/kragd/app.py`:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   import os

   cors_origins = os.environ.get("KRAGD_CORS_ORIGINS", "*").split(",")
   app.add_middleware(
       CORSMiddleware,
       allow_origins=cors_origins,
       allow_credentials=False,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. **Add CORS middleware inside `create_app()`** — after `FastAPI()` construction, before router mounting.

### Verification

```bash
uv run pytest tests/contract/api/test_cors_contract.py -v
# Manual: curl -H "Origin: http://tauri.localhost" http://localhost:11435/health -v
# Verify Access-Control-Allow-Origin header present
```

---

## Phase 3: CLI --json Output (P2)

**Goal**: All 5 missing commands support `--json`.

### Pattern (from existing `status_command`)

```python
output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
```

Then early in the function:
```python
if output_json:
    console.print(json.dumps(data, indent=2))
    return
```

### Steps

1. **`krag health --json`** in `src/krag_cli/commands/status.py`
   - Add `output_json` parameter to `health_command`
   - Use `client.health()` to get response dict
   - JSON path: `json.dumps(data, indent=2)`

2. **`krag modes list --json`** in `src/krag_cli/commands/modes.py`
   - Add `output_json` parameter to `modes_list`
   - JSON path: dump the list response

3. **`krag modes show <name> --json`** in `src/krag_cli/commands/modes.py`
   - Add `output_json` parameter to `modes_show`
   - JSON path: dump the mode detail response

4. **`krag lexicon refresh --json`** in `src/krag_cli/commands/lexicon.py`
   - Add `output_json` parameter to `lexicon_refresh`
   - JSON path: dump the refresh response

5. **`krag stop --json`** in `src/krag_cli/commands/service.py`
   - Add `output_json` parameter to `stop_command`
   - JSON path: dump shutdown confirmation
   - Handle "not running" case as JSON error too

### Verification

```bash
uv run pytest tests/unit/krag_cli/ -v -k "json"
```

---

## Phase 4: OpenAPI Spec Enhancement (P2)

**Goal**: 100% of endpoints tagged, all fields described, request bodies have examples.

### Steps

1. **Router tags** — verify each `APIRouter(tags=[...])` in all 6 routers:
   - `system.py`: `tags=["System"]`
   - `query.py`: `tags=["Query"]`
   - `debug.py`: `tags=["Debug"]`
   - `index.py`: `tags=["Index"]`
   - `modes.py`: `tags=["Modes"]`
   - `lexicon.py`: `tags=["Lexicon"]`

2. **Endpoint summaries** — add `summary="..."` to every `@router.get/post(...)` that lacks one.

3. **Field descriptions** — audit every `Field()` in `schemas.py` for `description=`. Add missing descriptions.

4. **Request body examples** — add `model_config = ConfigDict(json_schema_extra={"examples": [...]})` to request models or use `Body(examples=[...])` on endpoint parameters.

### Verification

```bash
# Start kragd, then:
curl http://localhost:11435/openapi.json | python -m json.tool | grep -c '"description"'
# Programmatic: write a test that fetches /openapi.json and asserts completeness
```

---

## Phase 5: SSE Index Progress (P3)

**Goal**: Clients can subscribe to real-time index progress events.

### Steps

1. **Add `sse-starlette` dependency**:
   ```bash
   uv add sse-starlette
   ```

2. **Wire progress callback in `service.py`**:
   - Add an `asyncio.Queue` attribute to `KragService` for SSE events
   - In `_run_indexing()`, pass a `progress_callback` to the orchestrator that pushes events to the queue via `run_coroutine_threadsafe`
   - On completion/error, push terminal event to the queue

3. **Create SSE endpoint** in `src/kragd/routers/index.py`:
   ```python
   @router.get("/index/stream")
   async def stream_index_progress(request: Request) -> EventSourceResponse:
       # Read events from service.index_event_queue
       # Yield SSE events until terminal event
   ```

4. **Handle client disconnect**:
   - The async generator catches `CancelledError` from sse-starlette
   - Sets a threading.Event flag to signal the indexing thread (optional optimization)

### Verification

```bash
uv run pytest tests/contract/api/test_stream_contract.py -v -k "index"
# Manual: start indexing, then curl http://localhost:11435/index/stream
```

---

## Phase 6: Streaming Query Answers (P3)

**Goal**: Clients receive LLM answer tokens as they're generated.

### Steps

1. **Add `generate_stream()` to `LLMClient`** in `src/krag/synthesis/llm_client.py`:
   - Call `self.model.create_chat_completion(messages=..., stream=True)`
   - Yield token deltas from the response generator

2. **Add `route_and_stream()` to `LLMPool`** in `src/krag/synthesis/llm_pool.py`:
   - Acquire lock → route → load model → mark slot busy → release lock
   - Yield tokens from `slot.instance.generate_stream(messages)`
   - On completion, acquire lock → clear slot busy → release lock

3. **Add `query_stream()` to `KragService`** in `src/kragd/service.py`:
   - Perform retrieval (synchronous) → push `query:sources` event
   - Stream LLM generation → push `query:token` events
   - On completion → push `query:done` event
   - On error → push `query:error` event

4. **Create SSE endpoint** in `src/kragd/routers/query.py`:
   ```python
   @router.post("/query/stream")
   async def stream_query(body: QueryRequest, request: Request) -> EventSourceResponse:
       # Run service.query_stream() in thread executor
       # Yield SSE events from asyncio.Queue
   ```

5. **Handle client disconnect**:
   - Set `threading.Event` flag → LLM client checks between tokens → stops generation

### Verification

```bash
uv run pytest tests/contract/api/test_stream_contract.py -v -k "query"
# Manual: curl -X POST http://localhost:11435/query/stream -H "Content-Type: application/json" -d '{"query": "hello"}'
```

---

## Pre-Commit Workflow (every commit)

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pytest
```

All three must pass before committing. This is mandated by the project constitution.

---

## Implementation Order Summary

| Phase | Priority | Dependencies | Files Modified |
|-------|----------|-------------|----------------|
| 1. Schema Consolidation | P1 | None | schemas.py, lexicon.py, modes.py, index.py, service.py |
| 2. CORS Middleware | P1 | None | app.py |
| 3. CLI --json | P2 | None | status.py, modes.py, lexicon.py, service.py |
| 4. OpenAPI Enhancement | P2 | Phase 1 (schemas moved) | All routers, schemas.py |
| 5. SSE Index Progress | P3 | Phase 1 (index normalized) | index.py, service.py, pyproject.toml |
| 6. Streaming Queries | P3 | None | query.py, service.py, llm_client.py, llm_pool.py |

Phases 1-2 are independent and can be done in parallel. Phase 3 is independent. Phase 4 depends on Phase 1. Phases 5-6 are independent of each other but best done after Phases 1-4 are stable.

**Tests accompany every phase** — write tests first (TDD), then implement.
