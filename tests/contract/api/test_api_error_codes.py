"""Contract tests for HTTP error code dispatch via isinstance (US8).

T009: Validates that:
- ServiceNotReadyError → 503
- IndexingInProgressError → 409
- ResourceNotConfiguredError → 500
- Generic KragError → 500
- No string matching in exception handler
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client() -> TestClient:
    """Create TestClient with mocked KragService for error dispatch tests."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app

    config = Configuration(directory_paths=[Path("/test").absolute()])

    with patch("kragd.app.KragService") as MockService:
        mock_service = MagicMock()
        mock_service.start = AsyncMock()
        mock_service.shutdown = AsyncMock()
        MockService.return_value = mock_service

        app = create_app(config)
        app.state.service = mock_service

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


class TestExceptionToHTTPStatusDispatch:
    """Exception types must map to correct HTTP status codes via isinstance."""

    def test_service_not_ready_returns_503(self, test_client: TestClient) -> None:
        from krag.models.exceptions import ServiceNotReadyError

        test_client.app.state.service.query.side_effect = ServiceNotReadyError(
            "Service not started — call start() first"
        )
        response = test_client.post("/query", json={"query": "test"})
        assert response.status_code == 503
        assert "Service not started" in response.json()["detail"]

    def test_indexing_in_progress_returns_409(self, test_client: TestClient) -> None:
        from krag.models.exceptions import IndexingInProgressError

        test_client.app.state.service.query.side_effect = IndexingInProgressError(
            "Indexing is in progress — queries are unavailable"
        )
        response = test_client.post("/query", json={"query": "test"})
        assert response.status_code == 409
        assert "Indexing is in progress" in response.json()["detail"]

    def test_resource_not_configured_returns_500(self, test_client: TestClient) -> None:
        from krag.models.exceptions import ResourceNotConfiguredError

        test_client.app.state.service.query.side_effect = ResourceNotConfiguredError(
            "LLM", "No LLM model configured"
        )
        response = test_client.post("/query", json={"query": "test"})
        assert response.status_code == 500
        assert "No LLM model configured" in response.json()["detail"]

    def test_generic_krag_error_returns_500(self, test_client: TestClient) -> None:
        from krag.models.exceptions import KragError

        test_client.app.state.service.query.side_effect = KragError("Something went wrong")
        response = test_client.post("/query", json={"query": "test"})
        assert response.status_code == 500
        assert "Something went wrong" in response.json()["detail"]

    def test_indexing_already_in_progress_returns_409(self, test_client: TestClient) -> None:
        """The 'already in progress' variant also gets 409."""
        from krag.models.exceptions import IndexingInProgressError

        test_client.app.state.service.index.side_effect = IndexingInProgressError(
            "Indexing is already in progress"
        )
        response = test_client.post(
            "/index",
            json={"directory_paths": ["/tmp/test"], "mode": "full"},
        )
        assert response.status_code == 409

    def test_service_not_ready_on_status_returns_503(self, test_client: TestClient) -> None:
        from krag.models.exceptions import ServiceNotReadyError

        test_client.app.state.service.get_status.side_effect = ServiceNotReadyError(
            "Service not started"
        )
        response = test_client.get("/status")
        assert response.status_code == 503

    def test_error_response_format(self, test_client: TestClient) -> None:
        """All error responses must have a 'detail' field."""
        from krag.models.exceptions import ServiceNotReadyError

        test_client.app.state.service.query.side_effect = ServiceNotReadyError(
            "Service not started"
        )
        response = test_client.post("/query", json={"query": "test"})
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)


class TestNoStringMatching:
    """Verify the exception handler does NOT use string matching."""

    def test_app_py_has_no_string_matching_handler(self) -> None:
        """The app.py source must not contain string-matching patterns."""
        import inspect

        from kragd import app as app_module

        source = inspect.getsource(app_module)
        # These patterns were in the old string-matching handler
        assert '"indexing is in progress" in msg' not in source
        assert '"already in progress" in msg' not in source
        assert '"not started" in msg' not in source
        assert "msg = str(exc).lower()" not in source
