"""Contract tests for POST /query and POST /retrieve endpoints.

T020: Validate request/response schemas match OpenAPI spec.
Tests use FastAPI TestClient with a mocked KragService.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kragd.schemas import (
    QueryResponse,
    SourceChunk,
)

# ── Fixtures ─────────────────────────────────────


def _make_source_chunk(rank: int = 1) -> SourceChunk:
    """Create a valid SourceChunk for testing."""
    return SourceChunk(
        chunk_id=f"chunk-{rank}",
        file_path="/home/user/project/file.py",
        score=0.95 - (rank - 1) * 0.1,
        rank=rank,
        chunk_content=f"def example_{rank}(): pass",
        file_type="py",
        language="python",
        function_name=f"example_{rank}",
        class_name=None,
        start_line=rank * 10,
        end_line=rank * 10 + 5,
    )


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

        # Default query response
        mock_service.query.return_value = QueryResponse(
            answer="The answer is 42.",
            sources=[_make_source_chunk(1), _make_source_chunk(2)],
            debug=None,
        )

        # Default retrieve response
        mock_service.retrieve.return_value = [
            _make_source_chunk(1),
            _make_source_chunk(2),
        ]

        MockService.return_value = mock_service

        app = create_app(config)
        # Override service on app state since create_app uses the real constructor
        app.state.service = mock_service

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


# ── POST /query contract ─────────────────────────


class TestQueryContract:
    """POST /query schema contract tests."""

    def test_query_returns_200(self, test_client: TestClient) -> None:
        """POST /query with valid body returns 200."""
        resp = test_client.post("/query", json={"query": "test question"})
        assert resp.status_code == 200

    def test_query_response_has_answer(self, test_client: TestClient) -> None:
        """Response contains 'answer' string field."""
        resp = test_client.post("/query", json={"query": "test question"})
        data = resp.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_query_response_has_sources(self, test_client: TestClient) -> None:
        """Response contains 'sources' array."""
        resp = test_client.post("/query", json={"query": "test question"})
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_query_source_chunk_schema(self, test_client: TestClient) -> None:
        """Each source chunk has all required fields per OpenAPI spec."""
        resp = test_client.post("/query", json={"query": "test question"})
        data = resp.json()
        required_fields = {
            "chunk_id",
            "file_path",
            "score",
            "rank",
            "chunk_content",
            "file_type",
        }
        for source in data["sources"]:
            assert required_fields.issubset(source.keys()), (
                f"Missing fields: {required_fields - source.keys()}"
            )

    def test_query_source_optional_fields(self, test_client: TestClient) -> None:
        """Source chunks may include optional code metadata fields."""
        resp = test_client.post("/query", json={"query": "test question"})
        data = resp.json()
        optional_fields = {"language", "function_name", "class_name", "start_line", "end_line"}
        # At least some optional fields should be present when provided
        source = data["sources"][0]
        present = optional_fields & source.keys()
        assert len(present) > 0

    def test_query_debug_null_by_default(self, test_client: TestClient) -> None:
        """Debug field is null when include_debug=false."""
        resp = test_client.post("/query", json={"query": "test question"})
        data = resp.json()
        assert data.get("debug") is None

    def test_query_accepts_optional_params(self, test_client: TestClient) -> None:
        """POST /query accepts top_k, preset, llm, include_debug."""
        resp = test_client.post(
            "/query",
            json={
                "query": "test",
                "top_k": 5,
                "preset": "code",
                "llm": "text",
                "include_debug": False,
            },
        )
        assert resp.status_code == 200

    def test_query_empty_string_rejected(self, test_client: TestClient) -> None:
        """POST /query rejects empty query string (422)."""
        resp = test_client.post("/query", json={"query": ""})
        assert resp.status_code == 422

    def test_query_missing_body_rejected(self, test_client: TestClient) -> None:
        """POST /query with no body returns 422."""
        resp = test_client.post("/query")
        assert resp.status_code == 422

    def test_query_invalid_llm_slot_rejected(self, test_client: TestClient) -> None:
        """POST /query rejects invalid llm value (422)."""
        resp = test_client.post("/query", json={"query": "test", "llm": "invalid"})
        assert resp.status_code == 422

    def test_query_top_k_validation(self, test_client: TestClient) -> None:
        """POST /query enforces top_k range (1-100)."""
        # top_k=0 invalid
        resp = test_client.post("/query", json={"query": "test", "top_k": 0})
        assert resp.status_code == 422

        # top_k=101 invalid
        resp = test_client.post("/query", json={"query": "test", "top_k": 101})
        assert resp.status_code == 422

    def test_query_score_is_float(self, test_client: TestClient) -> None:
        """Source chunk score is a float."""
        resp = test_client.post("/query", json={"query": "test"})
        data = resp.json()
        for source in data["sources"]:
            assert isinstance(source["score"], (int, float))

    def test_query_rank_is_integer(self, test_client: TestClient) -> None:
        """Source chunk rank is a positive integer."""
        resp = test_client.post("/query", json={"query": "test"})
        data = resp.json()
        for source in data["sources"]:
            assert isinstance(source["rank"], int)
            assert source["rank"] >= 1


# ── POST /retrieve contract ──────────────────────


class TestRetrieveContract:
    """POST /retrieve schema contract tests."""

    def test_retrieve_returns_200(self, test_client: TestClient) -> None:
        """POST /retrieve with valid body returns 200."""
        resp = test_client.post("/retrieve", json={"query": "test question"})
        assert resp.status_code == 200

    def test_retrieve_response_has_sources(self, test_client: TestClient) -> None:
        """Response contains 'sources' array."""
        resp = test_client.post("/retrieve", json={"query": "test question"})
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_retrieve_no_answer_field(self, test_client: TestClient) -> None:
        """Retrieve response does NOT include 'answer' field."""
        resp = test_client.post("/retrieve", json={"query": "test question"})
        data = resp.json()
        assert "answer" not in data

    def test_retrieve_source_chunk_schema(self, test_client: TestClient) -> None:
        """Each source chunk has required fields per OpenAPI spec."""
        resp = test_client.post("/retrieve", json={"query": "test question"})
        data = resp.json()
        required_fields = {
            "chunk_id",
            "file_path",
            "score",
            "rank",
            "chunk_content",
            "file_type",
        }
        for source in data["sources"]:
            assert required_fields.issubset(source.keys())

    def test_retrieve_empty_query_rejected(self, test_client: TestClient) -> None:
        """POST /retrieve rejects empty query string (422)."""
        resp = test_client.post("/retrieve", json={"query": ""})
        assert resp.status_code == 422

    def test_retrieve_accepts_top_k(self, test_client: TestClient) -> None:
        """POST /retrieve accepts optional top_k parameter."""
        resp = test_client.post("/retrieve", json={"query": "test", "top_k": 10})
        assert resp.status_code == 200

    def test_retrieve_top_k_validation(self, test_client: TestClient) -> None:
        """POST /retrieve enforces top_k range (1-100)."""
        resp = test_client.post("/retrieve", json={"query": "test", "top_k": 0})
        assert resp.status_code == 422

    def test_retrieve_content_type_json(self, test_client: TestClient) -> None:
        """Response content-type is application/json."""
        resp = test_client.post("/retrieve", json={"query": "test"})
        assert "application/json" in resp.headers["content-type"]
