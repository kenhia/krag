"""Query, retrieve, index, and debug API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from kragd.schemas import (
    QueryRequest,
    QueryResponse,
    RetrieveRequest,
    RetrieveResponse,
)

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(request: Request, body: QueryRequest) -> QueryResponse:
    """Full RAG query with LLM synthesis."""
    service = request.app.state.service
    return service.query(body)


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve(request: Request, body: RetrieveRequest) -> RetrieveResponse:
    """Retrieve relevant chunks without LLM synthesis."""
    service = request.app.state.service
    sources = service.retrieve(body)
    return RetrieveResponse(sources=sources)
