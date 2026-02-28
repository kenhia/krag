"""Debug API routes (query with metadata, raw Qdrant search).

T039/T043: POST /debug/query and POST /debug/qdrant endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from kragd.schemas import (
    DebugQueryRequest,
    DebugQueryResponse,
    QdrantSearchRequest,
    QdrantSearchResponse,
    QueryRequest,
)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/query", response_model=DebugQueryResponse)
def debug_query(body: DebugQueryRequest, request: Request) -> DebugQueryResponse:
    """Execute a query with full debug metadata.

    Returns answer + sources + 14 debug fields (timings, routing,
    candidates, embedding models, vector spaces).
    """
    service = request.app.state.service
    query_request = QueryRequest(
        query=body.query,
        top_k=body.top_k,
        preset=body.preset,
        llm=body.llm,
        mode=body.mode,
        include_debug=True,
    )
    result = service.query(query_request)
    return DebugQueryResponse(
        answer=result.answer,
        sources=result.sources,
        debug=result.debug,
    )


@router.post("/qdrant", response_model=QdrantSearchResponse)
def debug_qdrant(body: QdrantSearchRequest, request: Request) -> QdrantSearchResponse:
    """Raw vector store search bypassing Retriever.

    Returns raw similarity scores without dedup, boost, or RRF.
    Supports filtering by file_type, file_path_contains, and vector space.
    """
    service = request.app.state.service
    return service.debug_qdrant(body)
