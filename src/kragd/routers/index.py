"""Index API routes.

T047: POST /index (trigger indexing), GET /index/status (last job info).
T010: POST /index returns immediately; indexing runs in background thread.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from kragd.schemas import IndexRequest, IndexResponse

router = APIRouter(tags=["index"])


@router.post("/index", response_model=IndexResponse)
def index(body: IndexRequest, request: Request) -> IndexResponse:
    """Trigger indexing using already-loaded embedding models.

    Returns immediately with a 'running' status. Indexing proceeds
    in background. Use GET /index/status to poll for completion.
    Returns 409 if indexing is already in progress.
    """
    service = request.app.state.service
    return service.index(body)


@router.get("/index/status", response_model=IndexResponse | list[IndexResponse])
def index_status(request: Request) -> IndexResponse | list[IndexResponse]:
    """Return the status of indexing jobs.

    Returns all undelivered results plus the most recent job.
    If only one result, returns a single IndexResponse.
    If multiple, returns a list.
    """
    service = request.app.state.service
    return service.get_index_status()
