"""Query, retrieve, index, and debug API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from kragd.schemas import (
    QueryRequest,
    QueryResponse,
    RetrieveRequest,
    RetrieveResponse,
)

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse, summary="Full RAG query with synthesis")
def query(request: Request, body: QueryRequest) -> QueryResponse:
    """Full RAG query with LLM synthesis."""
    service = request.app.state.service
    return service.query(body)


@router.post(
    "/retrieve", response_model=RetrieveResponse, summary="Retrieve chunks without synthesis"
)
def retrieve(request: Request, body: RetrieveRequest) -> RetrieveResponse:
    """Retrieve relevant chunks without LLM synthesis."""
    service = request.app.state.service
    sources = service.retrieve(body)
    return RetrieveResponse(sources=sources)


@router.post("/query/stream", summary="Stream query answer via SSE")
async def query_stream(request: Request, body: QueryRequest) -> EventSourceResponse:
    """Submit a query and receive streaming answer via Server-Sent Events.

    Event types:

    - ``query:sources`` — retrieved source chunks (sent once, before tokens)
    - ``query:token``   — partial answer text (one or more tokens per event)
    - ``query:done``    — complete response (answer + sources + debug)
    - ``query:error``   — error during retrieval or generation
    """
    service = request.app.state.service

    async def _event_generator():
        async for event in service.query_stream(body):
            yield {
                "event": event["type"],
                "data": json.dumps(event["data"]),
            }

    return EventSourceResponse(_event_generator())
