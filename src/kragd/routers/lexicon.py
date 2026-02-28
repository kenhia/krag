"""Lexicon API routes — POST /lexicon/refresh.

Provides endpoint to reload the domain lexicon from disk.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/lexicon", tags=["lexicon"])


class LexiconRefreshResponse(BaseModel):
    """POST /lexicon/refresh response."""

    entries: int = Field(..., description="Number of lexicon entries after reload")
    status: str = Field(..., description="Reload status message")


@router.post("/refresh", response_model=LexiconRefreshResponse)
def refresh_lexicon(request: Request) -> LexiconRefreshResponse:
    """Reload the domain lexicon from disk."""
    service = request.app.state.service
    result = service.refresh_lexicon()
    return LexiconRefreshResponse(
        entries=result["entries"],
        status=result["status"],
    )
