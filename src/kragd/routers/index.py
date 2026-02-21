"""Index API routes.

T047: POST /index (trigger indexing), GET /index/status (last job info).
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from kragd.schemas import IndexRequest, IndexResponse

router = APIRouter(tags=["index"])


@router.post("/index", response_model=IndexResponse)
def index(body: IndexRequest, request: Request) -> IndexResponse:
    """Trigger indexing using already-loaded embedding models.

    Supports full or incremental mode, directory overrides,
    file type filters, exclusion patterns, and dry-run preview.
    """
    service = request.app.state.service
    return service.index(body)


@router.get("/index/status", response_model=IndexResponse)
def index_status(request: Request) -> IndexResponse:
    """Return the status of the last indexing job."""
    service = request.app.state.service
    return service.get_index_status()
