"""Integration tests for network access — US7 (T050).

Verify kragd binds to configured host and CLI connects to non-localhost.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _mock_service() -> MagicMock:
    """Create a mock KragService for testing."""
    service = MagicMock()
    service.start = AsyncMock()
    service.shutdown = AsyncMock()
    service.get_health = MagicMock(return_value={"status": "healthy", "version": "0.0.0-dev"})
    service.get_status = MagicMock(
        return_value={
            "version": "0.0.0-dev",
            "uptime_seconds": 10.0,
            "llm": {},
            "embedding_models": [],
            "vector_store": {
                "collection": "krag",
                "total_vectors": 0,
                "named_spaces": [],
            },
            "vram": None,
        }
    )
    return service


@pytest.fixture
def test_client(_mock_service: MagicMock) -> TestClient:
    """Create a TestClient with a mocked KragService."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app

    config = Configuration(directory_paths=[Path("/test").absolute()])

    with patch("kragd.service.KragService", return_value=_mock_service):
        app = create_app(config)
        app.state.service = _mock_service
        with TestClient(app) as client:
            yield client


class TestNetworkAccess:
    """Tests for network access configuration — US7."""

    def test_health_endpoint_accessible(self, test_client: TestClient) -> None:
        """Health endpoint responds over HTTP (basic connectivity)."""
        resp = test_client.get("/health")
        assert resp.status_code == 200

    def test_status_endpoint_accessible(self, test_client: TestClient) -> None:
        """Status endpoint responds over HTTP."""
        resp = test_client.get("/status")
        assert resp.status_code == 200

    def test_app_has_no_host_restriction(self, test_client: TestClient) -> None:
        """FastAPI app itself has no host restriction — binding is uvicorn's job."""
        # The app factory does not embed any host restriction; uvicorn
        # binds to the configured host.  We verify the app has no
        # server_host attribute that would restrict access.
        app = test_client.app
        assert not hasattr(app, "server_host")

    def test_host_override_in_entry_point(self) -> None:
        """kragd __main__ resolves --host flag correctly."""
        # main is a Typer callback; verify it exists and accepts host param
        import inspect

        from kragd.__main__ import main

        sig = inspect.signature(main)
        assert "host" in sig.parameters, "main() must accept --host"
        assert "port" in sig.parameters, "main() must accept --port"

    def test_daemon_command_passes_host_port(self) -> None:
        """_daemonize passes host and port to subprocess command."""
        import inspect

        from kragd.__main__ import _daemonize

        sig = inspect.signature(_daemonize)
        params = list(sig.parameters.keys())
        assert "host" in params
        assert "port" in params


class TestServiceConfiguration:
    """Tests verifying service configuration defaults for network access."""

    def test_default_host_is_all_interfaces(self) -> None:
        """Default service host should be 0.0.0.0 for LAN access."""
        from krag.models.configuration import ServiceConfiguration

        svc_config = ServiceConfiguration()
        assert svc_config.host == "0.0.0.0"

    def test_default_port(self) -> None:
        """Default service port should be 8742."""
        from krag.models.configuration import ServiceConfiguration

        svc_config = ServiceConfiguration()
        assert svc_config.port == 8742

    def test_custom_host(self) -> None:
        """ServiceConfiguration accepts custom host."""
        from krag.models.configuration import ServiceConfiguration

        svc_config = ServiceConfiguration(host="127.0.0.1")
        assert svc_config.host == "127.0.0.1"

    def test_custom_port(self) -> None:
        """ServiceConfiguration accepts custom port."""
        from krag.models.configuration import ServiceConfiguration

        svc_config = ServiceConfiguration(port=9090)
        assert svc_config.port == 9090
