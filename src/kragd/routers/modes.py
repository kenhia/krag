"""Modes API routes — GET /modes and GET /modes/{name}.

Exposes the registered retrieval modes for discovery.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from kragd.schemas import ModeInfo

router = APIRouter(prefix="/modes", tags=["modes"])


class ModeDetailResponse(BaseModel):
    """Full detail for a single mode."""

    name: str = Field(..., description="Mode name")
    description: str = Field("", description="Brief description")
    collections: dict[str, float] = Field(..., description="Collection weights")
    llm_slot: str = Field(..., description="LLM slot")
    preset: str = Field(..., description="Prompt preset")
    top_k: int = Field(..., description="Default top_k")
    similarity_threshold: float = Field(..., description="Default threshold")
    critic_enabled: bool = Field(..., description="Context critic active")
    critic_threshold: int = Field(..., description="Minimum critic score")


class ModeListResponse(BaseModel):
    """GET /modes response."""

    modes: list[ModeInfo] = Field(..., description="All registered modes")


@router.get("", response_model=ModeListResponse)
def list_modes(request: Request) -> ModeListResponse:
    """List all registered retrieval modes."""
    service = request.app.state.service
    return ModeListResponse(modes=service._get_mode_infos())


@router.get("/{name}", response_model=ModeDetailResponse)
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
