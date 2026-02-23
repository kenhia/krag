"""FastAPI application factory for kragd.

Uses the lifespan context manager pattern (R-01) for clean startup/shutdown
of the KragService and its heavyweight components.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kragd.routers import debug, index, lexicon, modes, query, system
from kragd.service import KragService

if TYPE_CHECKING:
    from krag.models.configuration import Configuration


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage KragService lifecycle within FastAPI lifespan."""
    service: KragService = app.state.service
    await service.start()
    try:
        yield
    finally:
        await service.shutdown()


def create_app(config: Configuration) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Full krag Configuration (includes service section).

    Returns:
        Configured FastAPI application with all routers mounted.
    """
    service = KragService(config)

    app = FastAPI(
        title="kragd",
        description="krag RAG service daemon",
        version=_get_version(),
        lifespan=_lifespan,
    )

    # Attach service to app state so routers can access it
    app.state.service = service

    # Mount routers
    app.include_router(system.router)
    app.include_router(query.router)
    app.include_router(debug.router)
    app.include_router(index.router)
    app.include_router(modes.router)
    app.include_router(lexicon.router)

    # Translate service-level RuntimeErrors into appropriate HTTP responses
    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
        msg = str(exc).lower()
        if "indexing is in progress" in msg:
            return JSONResponse(status_code=409, content={"detail": str(exc)})
        if "already in progress" in msg:
            return JSONResponse(status_code=409, content={"detail": str(exc)})
        if "not started" in msg:
            return JSONResponse(status_code=503, content={"detail": str(exc)})
        # Re-raise unknown RuntimeErrors as 500
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return app


def _get_version() -> str:
    """Get krag package version."""
    try:
        from importlib.metadata import version

        return version("krag")
    except Exception:
        return "0.0.0-dev"


def create_app_from_env() -> FastAPI:
    """Factory callable for uvicorn ``factory=True``.

    Reads ``KRAGD_CONFIG_PATH`` env var to locate the config file.
    """
    import os
    from pathlib import Path

    from krag.config.logging import setup_logging
    from krag.config.settings import ConfigManager

    config_path = Path(os.environ["KRAGD_CONFIG_PATH"])
    config = ConfigManager.load(config_path)

    # Set up file + console logging so all krag/kragd loggers write to krag.log
    setup_logging(config=config)

    return create_app(config)
