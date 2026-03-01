"""Index API routes.

T047: POST /index (trigger indexing), GET /index/status (last job info).
T010: POST /index returns immediately; indexing runs in background thread.
US5: GET /index/stream — real-time SSE index progress.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from kragd.schemas import IndexRequest, IndexResponse

router = APIRouter(tags=["index"])


@router.post("/index", response_model=IndexResponse, summary="Trigger background indexing job")
def index(body: IndexRequest, request: Request) -> IndexResponse:
    """Trigger indexing using already-loaded embedding models.

    Returns immediately with a 'running' status. Indexing proceeds
    in background. Use GET /index/status to poll for completion.
    Returns 409 if indexing is already in progress.
    """
    service = request.app.state.service
    return service.index(body)


@router.get("/index/status", response_model=list[IndexResponse], summary="Get indexing job status")
def index_status(request: Request) -> list[IndexResponse]:
    """Return the status of indexing jobs.

    Always returns a JSON array of IndexResponse objects.
    Empty list when no jobs exist, single-element list for one job,
    multi-element list for concurrent/recent jobs.
    """
    service = request.app.state.service
    return service.get_index_status()


@router.get("/index/stream", summary="Stream real-time index progress via SSE")
async def index_stream(request: Request) -> EventSourceResponse:
    """Server-Sent Events stream for real-time indexing progress.

    Event types:
    - ``index:idle`` — no indexing job is active (stream closes)
    - ``index:progress`` — periodic progress update with current/total/stage
    - ``index:complete`` — indexing finished successfully (stream closes)
    - ``index:error`` — indexing failed (stream closes)
    """
    service = request.app.state.service

    async def _event_generator():
        async for event in service.subscribe_index_events():
            yield {
                "event": event["type"],
                "data": json.dumps(event["data"]),
            }

    return EventSourceResponse(_event_generator())
