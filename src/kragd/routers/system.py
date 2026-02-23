"""System lifecycle API routes (health, status, shutdown).

T030: Implements GET /health (async), GET /status, POST /shutdown
with SIGTERM-based graceful shutdown.
"""

from __future__ import annotations

import os
import signal
import threading

from fastapi import APIRouter, Request

from kragd.schemas import HealthResponse, ServiceStatus, ShutdownResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Simple health check endpoint (async for non-blocking)."""
    service = request.app.state.service
    return service.get_health()


@router.get("/status", response_model=ServiceStatus)
def status(request: Request) -> ServiceStatus:
    """Full service status including models, VRAM, uptime, and vector store."""
    service = request.app.state.service
    return service.get_status()


@router.post("/shutdown", response_model=ShutdownResponse)
def shutdown(request: Request) -> ShutdownResponse:
    """Graceful shutdown via SIGTERM to self.

    Sends SIGTERM to the current process, which triggers uvicorn's
    graceful shutdown flow and the lifespan teardown (R-07).
    """

    # Schedule SIGTERM after response is sent
    def _send_sigterm() -> None:
        import time

        time.sleep(0.5)  # Allow response to be sent first
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_send_sigterm, daemon=True).start()
    return ShutdownResponse(message="Shutdown initiated")
