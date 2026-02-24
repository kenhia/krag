"""Contract tests for POST /index and GET /index/status endpoints.

T045: Validate IndexResponse schema against OpenAPI spec.
Tests use FastAPI TestClient with a mocked KragService.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kragd.schemas import IndexResponse

# ── Fixtures ─────────────────────────────────────


def _make_index_response(**overrides) -> IndexResponse:
    """Create a valid IndexResponse for testing."""
    defaults = {
        "job_id": "test-job-001",
        "status": "completed",
        "mode": "incremental",
        "files_scanned": 150,
        "files_processed": 45,
        "files_skipped": 100,
        "files_errored": 5,
        "chunks_created": 320,
        "vectors_stored": 320,
        "duration_seconds": 12.5,
        "dry_run": False,
        "errors": [],
    }
    defaults.update(overrides)
    return IndexResponse(**defaults)


@pytest.fixture
def test_client() -> TestClient:
    """Create a TestClient with a mocked KragService."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app

    config = Configuration(directory_paths=[Path("/test").absolute()])

    with patch("kragd.app.KragService") as MockService:
        mock_service = MagicMock()
        mock_service.start = AsyncMock()
        mock_service.shutdown = AsyncMock()

        # Default index response
        mock_service.index.return_value = _make_index_response()

        # Default index_status response
        mock_service.get_index_status.return_value = _make_index_response(
            status="none", job_id="none", files_scanned=0, files_processed=0,
            files_skipped=0, files_errored=0, chunks_created=0, vectors_stored=0,
            duration_seconds=0.0,
        )

        MockService.return_value = mock_service

        app = create_app(config)
        app.state.service = mock_service

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


# ── POST /index contract ────────────────────────


class TestIndexContract:
    """Contract tests for POST /index."""

    def test_index_returns_200(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        assert resp.status_code == 200

    def test_index_response_has_job_id(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "job_id" in data
        assert isinstance(data["job_id"], str)

    def test_index_response_has_status(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("completed", "failed", "none", "running")

    def test_index_response_has_mode(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "mode" in data
        assert data["mode"] in ("full", "incremental")

    def test_index_response_file_counts(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "files_scanned" in data
        assert "files_processed" in data
        assert "files_skipped" in data
        assert "files_errored" in data
        assert isinstance(data["files_scanned"], int)

    def test_index_response_chunk_counts(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "chunks_created" in data
        assert "vectors_stored" in data
        assert isinstance(data["chunks_created"], int)

    def test_index_response_duration(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "duration_seconds" in data
        assert isinstance(data["duration_seconds"], (int, float))
        assert data["duration_seconds"] >= 0

    def test_index_response_dry_run(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "dry_run" in data
        assert isinstance(data["dry_run"], bool)

    def test_index_response_errors(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert "errors" in data
        assert isinstance(data["errors"], list)

    def test_index_with_full_mode(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={"mode": "full"})
        assert resp.status_code == 200

    def test_index_with_incremental_mode(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={"mode": "incremental"})
        assert resp.status_code == 200

    def test_index_with_dry_run(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={"dry_run": True})
        assert resp.status_code == 200

    def test_index_with_directories(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={"directories": ["/home/user/src"]})
        assert resp.status_code == 200

    def test_index_with_file_types(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={"file_types": [".py", ".js"]})
        assert resp.status_code == 200

    def test_index_with_exclude_patterns(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={"exclude_patterns": ["**/test_*"]})
        assert resp.status_code == 200

    def test_index_invalid_mode_rejected(self, test_client: TestClient) -> None:
        resp = test_client.post("/index", json={"mode": "invalid"})
        assert resp.status_code == 422

    def test_index_with_errors_in_response(self, test_client: TestClient) -> None:
        """IndexResponse with file errors."""
        from kragd.schemas import IndexError as IndexErr

        test_client.app.state.service.index.return_value = _make_index_response(
            files_errored=1,
            errors=[
                IndexErr(
                    file_path="/home/user/bad.py",
                    error_type="UnicodeDecodeError",
                    error_message="codec can't decode byte 0xff",
                )
            ],
        )
        resp = test_client.post("/index", json={})
        data = resp.json()
        assert data["files_errored"] == 1
        assert len(data["errors"]) == 1
        err = data["errors"][0]
        assert "file_path" in err
        assert "error_type" in err
        assert "error_message" in err


# ── GET /index/status contract ──────────────────


class TestIndexStatusContract:
    """Contract tests for GET /index/status."""

    def test_index_status_returns_200(self, test_client: TestClient) -> None:
        resp = test_client.get("/index/status")
        assert resp.status_code == 200

    def test_index_status_has_job_id(self, test_client: TestClient) -> None:
        resp = test_client.get("/index/status")
        data = resp.json()
        assert "job_id" in data

    def test_index_status_has_status(self, test_client: TestClient) -> None:
        resp = test_client.get("/index/status")
        data = resp.json()
        assert "status" in data

    def test_index_status_schema_matches_index_response(self, test_client: TestClient) -> None:
        """GET /index/status should return the same schema as POST /index."""
        resp = test_client.get("/index/status")
        data = resp.json()
        required_fields = [
            "job_id",
            "status",
            "mode",
            "files_scanned",
            "files_processed",
            "files_skipped",
            "files_errored",
            "chunks_created",
            "vectors_stored",
            "duration_seconds",
            "dry_run",
            "errors",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
