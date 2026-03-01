"""Contract tests for CORS middleware (US2).

T010: Verify that:
- Preflight OPTIONS requests return correct CORS headers
- Wildcard origin is the default when KRAGD_CORS_ORIGINS is unset
- Custom KRAGD_CORS_ORIGINS restricts allowed origins
- Requests without Origin header pass through unmodified
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_test_client(env_origins: str | None = None) -> TestClient:
    """Create a TestClient with mocked service, optionally setting KRAGD_CORS_ORIGINS."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app

    config = Configuration(directory_paths=[Path("/test").absolute()])

    env_patch = {}
    if env_origins is not None:
        env_patch["KRAGD_CORS_ORIGINS"] = env_origins

    with (
        patch("kragd.app.KragService") as MockService,
        patch.dict("os.environ", env_patch, clear=False),
    ):
        mock_service = MagicMock()
        mock_service.start = AsyncMock()
        mock_service.shutdown = AsyncMock()

        # Provide minimal mock responses so endpoints don't error
        from kragd.schemas import HealthResponse

        mock_service.get_health.return_value = HealthResponse(status="healthy", version="0.0.0")

        MockService.return_value = mock_service

        app = create_app(config)
        app.state.service = mock_service

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


@pytest.fixture
def test_client():
    """Default TestClient (wildcard CORS)."""
    yield from _make_test_client()


@pytest.fixture
def test_client_custom_origins():
    """TestClient with specific allowed origins."""
    yield from _make_test_client("http://localhost:3000,http://example.com")


@pytest.fixture
def test_client_no_env():
    """TestClient without KRAGD_CORS_ORIGINS env var (default wildcard)."""
    yield from _make_test_client()


# ── Preflight (OPTIONS) ─────────────────────────


class TestCORSPreflight:
    """Preflight OPTIONS requests must return CORS allow headers."""

    def test_preflight_returns_200(self, test_client: TestClient) -> None:
        resp = test_client.options(
            "/health",
            headers={
                "Origin": "http://tauri.localhost",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200

    def test_preflight_has_allow_origin(self, test_client: TestClient) -> None:
        resp = test_client.options(
            "/health",
            headers={
                "Origin": "http://tauri.localhost",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in resp.headers

    def test_preflight_has_allow_methods(self, test_client: TestClient) -> None:
        resp = test_client.options(
            "/health",
            headers={
                "Origin": "http://tauri.localhost",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-methods" in resp.headers

    def test_preflight_has_allow_headers(self, test_client: TestClient) -> None:
        resp = test_client.options(
            "/health",
            headers={
                "Origin": "http://tauri.localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert "access-control-allow-headers" in resp.headers


# ── Wildcard origin (default) ───────────────────


class TestCORSWildcardDefault:
    """Default config allows any origin (wildcard)."""

    def test_wildcard_origin_on_get(self, test_client: TestClient) -> None:
        resp = test_client.get(
            "/health",
            headers={"Origin": "http://tauri.localhost"},
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin == "*"

    def test_wildcard_origin_on_post(self, test_client: TestClient) -> None:
        resp = test_client.options(
            "/index",
            headers={
                "Origin": "http://some-other-app.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin == "*"

    def test_credentials_not_allowed(self, test_client: TestClient) -> None:
        """allow_credentials should be False (wildcard + credentials is invalid)."""
        resp = test_client.get(
            "/health",
            headers={"Origin": "http://tauri.localhost"},
        )
        # With allow_credentials=False, the header should not be present
        assert resp.headers.get("access-control-allow-credentials") != "true"


# ── Custom origins via env var ──────────────────


class TestCORSCustomOrigins:
    """KRAGD_CORS_ORIGINS restricts allowed origins."""

    def test_allowed_origin_reflected(self, test_client_custom_origins: TestClient) -> None:
        resp = test_client_custom_origins.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        allow_origin = resp.headers.get("access-control-allow-origin", "")
        assert allow_origin == "http://localhost:3000"

    def test_disallowed_origin_no_header(self, test_client_custom_origins: TestClient) -> None:
        resp = test_client_custom_origins.get(
            "/health",
            headers={"Origin": "http://evil.example.com"},
        )
        # When origin is not in allowed list, no ACAO header should be present
        allow_origin = resp.headers.get("access-control-allow-origin")
        assert allow_origin is None


# ── No-Origin passthrough ───────────────────────


class TestCORSNoOriginPassthrough:
    """Requests without an Origin header pass through unmodified."""

    def test_no_origin_header_returns_200(self, test_client: TestClient) -> None:
        """Regular request (no Origin) should work normally."""
        resp = test_client.get("/health")
        assert resp.status_code == 200

    def test_no_origin_header_no_cors_headers(self, test_client: TestClient) -> None:
        """Without Origin, CORS headers should not be in response."""
        resp = test_client.get("/health")
        # CORSMiddleware only adds CORS headers when Origin is present
        assert "access-control-allow-origin" not in resp.headers
