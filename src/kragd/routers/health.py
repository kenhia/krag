"""Health and status API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from kragd.schemas import HealthResponse, ServiceStatus, ShutdownResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Simple health check endpoint."""
    service = request.app.state.service
    return service.get_health()


@router.get("/status", response_model=ServiceStatus)
def status(request: Request) -> ServiceStatus:
    """Full service status including model info and uptime."""
    service = request.app.state.service
    return service.get_status()


@router.post("/shutdown", response_model=ShutdownResponse)
async def shutdown(request: Request) -> ShutdownResponse:
    """Graceful shutdown of the service."""
    service = request.app.state.service
    await service.shutdown()
    return ShutdownResponse(message="Shutdown initiated")
