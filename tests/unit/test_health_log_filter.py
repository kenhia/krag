"""Unit tests for health-check log suppression middleware (US3).

Verifies the request_logging_middleware in create_app() suppresses
consecutive GET /health log entries at INFO level while keeping them
at DEBUG level.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app_with_middleware() -> FastAPI:
    """Create a minimal FastAPI app with request_logging_middleware applied."""
    from kragd.app import create_app

    config = MagicMock()
    config.service = MagicMock()
    config.service.host = "127.0.0.1"
    config.service.port = 8000

    app = create_app(config)

    # Override lifespan to avoid real service startup
    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/query")
    async def query_endpoint() -> dict:
        return {"results": []}

    return app


class TestHealthLogFilter:
    """Test suite for health-check log suppression middleware."""

    def setup_method(self) -> None:
        self.app = _make_app_with_middleware()
        # Disable lifespan for testing (avoid service startup)
        self.app.router.lifespan_context = None  # type: ignore[assignment]
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_first_health_check_is_logged_at_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """First GET /health should be logged at INFO level."""
        with caplog.at_level(logging.DEBUG, logger="kragd.app"):
            self.client.get("/health")

        info_msgs = [
            r for r in caplog.records if r.levelno == logging.INFO and "/health" in r.message
        ]
        assert len(info_msgs) >= 1, "First health check should produce at least one INFO log"

    def test_consecutive_health_checks_suppressed(self, caplog: pytest.LogCaptureFixture) -> None:
        """5 consecutive GET /health → only 1 INFO log entry; remaining 4 at DEBUG."""
        with caplog.at_level(logging.DEBUG, logger="kragd.app"):
            for _ in range(5):
                self.client.get("/health")

        info_msgs = [
            r for r in caplog.records if r.levelno == logging.INFO and "/health" in r.message
        ]
        debug_msgs = [
            r for r in caplog.records if r.levelno == logging.DEBUG and "/health" in r.message
        ]
        assert len(info_msgs) == 1, f"Expected 1 INFO health log, got {len(info_msgs)}"
        assert len(debug_msgs) == 4, f"Expected 4 DEBUG health logs, got {len(debug_msgs)}"

    def test_non_health_request_resets_suppression(self, caplog: pytest.LogCaptureFixture) -> None:
        """GET /health → GET /query → GET /health → all 3 logged at INFO."""
        with caplog.at_level(logging.DEBUG, logger="kragd.app"):
            self.client.get("/health")
            self.client.get("/query")
            self.client.get("/health")

        info_msgs = [r for r in caplog.records if r.levelno == logging.INFO]
        # Should have 3 INFO entries: health, query, health
        health_info = [r.message for r in info_msgs if "/health" in r.message]
        assert len(health_info) == 2, f"Expected 2 INFO health logs, got {len(health_info)}"

    def test_health_after_non_health_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """`GET /query` then `GET /health` → health check is logged (not suppressed)."""
        with caplog.at_level(logging.DEBUG, logger="kragd.app"):
            self.client.get("/query")
            self.client.get("/health")

        info_msgs = [
            r for r in caplog.records if r.levelno == logging.INFO and "/health" in r.message
        ]
        assert len(info_msgs) == 1, "Health check after non-health should be logged at INFO"

    def test_last_was_health_false_at_startup(self) -> None:
        """At startup, _last_was_health should be False — first health check always logged."""
        # This is implicitly tested by test_first_health_check_is_logged_at_info,
        # but we verify explicitly by checking that a fresh app logs the first health.
        app = _make_app_with_middleware()
        app.router.lifespan_context = None  # type: ignore[assignment]
        client = TestClient(app, raise_server_exceptions=False)

        import io

        handler = logging.StreamHandler(io.StringIO())
        handler.setLevel(logging.DEBUG)
        kragd_logger = logging.getLogger("kragd.app")
        kragd_logger.addHandler(handler)
        kragd_logger.setLevel(logging.DEBUG)
        try:
            client.get("/health")
            output = handler.stream.getvalue()  # type: ignore[attr-defined]
            assert "/health" in output, "First health check should be logged on fresh app"
        finally:
            kragd_logger.removeHandler(handler)

    def test_post_health_not_treated_as_health_check(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """POST /health is NOT treated as a health check — does not trigger suppression."""
        with caplog.at_level(logging.DEBUG, logger="kragd.app"):
            # Send POST to /health (would get method not allowed or 405, but middleware runs)
            self.client.post("/health")
            self.client.get("/health")

        # Both should be at INFO — POST /health is not a health check,
        # so GET /health after it is "first health after non-health"
        info_msgs = [
            r for r in caplog.records if r.levelno == logging.INFO and "/health" in r.message
        ]
        assert len(info_msgs) == 2, f"Expected 2 INFO logs (POST + GET), got {len(info_msgs)}"
