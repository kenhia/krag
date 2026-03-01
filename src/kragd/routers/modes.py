"""Modes API routes — GET /modes and GET /modes/{name}.

Exposes the registered retrieval modes for discovery.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from kragd.schemas import ModeDetailResponse, ModeListResponse

router = APIRouter(prefix="/modes", tags=["modes"])


@router.get("", response_model=ModeListResponse, summary="List all retrieval modes")
def list_modes(request: Request) -> ModeListResponse:
    """List all registered retrieval modes."""
    service = request.app.state.service
    return ModeListResponse(modes=service._get_mode_infos())


@router.get("/{name}", response_model=ModeDetailResponse, summary="Get mode details by name")
def get_mode(request: Request, name: str) -> ModeDetailResponse:
    """Get full details for a specific mode."""
    service = request.app.state.service
    try:
        mode = service._resolve_mode(name)
    except ValueError:
        mode = None
    if mode is None:
        raise HTTPException(status_code=404, detail=f"Mode '{name}' not found")
    return ModeDetailResponse(
        name=mode.name,
        description=mode.description,
        collections=mode.collections,
        llm_slot=mode.llm_slot,
        preset=mode.preset,
        top_k=mode.top_k,
        similarity_threshold=mode.similarity_threshold,
        critic_enabled=mode.critic_enabled,
        critic_threshold=mode.critic_threshold,
    )
