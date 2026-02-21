"""Integration tests for query round-trip via FastAPI TestClient.

T021: Tests verify end-to-end query flow with mocked LLM, validating
response structure matches the OpenAPI spec.
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

# ── Helpers ──────────────────────────────────────


def _make_source_chunk(rank: int = 1, file_path: str = "/home/user/project/file.py") -> SourceChunk:
    """Create a valid SourceChunk for testing."""
    return SourceChunk(
        chunk_id=f"chunk-{rank}",
        file_path=file_path,
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


def _make_mock_service() -> MagicMock:
    """Create a fully mocked KragService."""
    mock = MagicMock()
    mock.start = AsyncMock()
    mock.shutdown = AsyncMock()

    sources = [_make_source_chunk(1), _make_source_chunk(2), _make_source_chunk(3)]

    mock.query.return_value = QueryResponse(
        answer="Based on the code, the function does X.",
        sources=sources,
        debug=None,
    )
    mock.retrieve.return_value = sources
    return mock


@pytest.fixture
def mock_service() -> MagicMock:
    """Provide a mocked KragService."""
    return _make_mock_service()


@pytest.fixture
def test_client(mock_service: MagicMock) -> TestClient:
    """Create TestClient with mocked service."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app

    config = Configuration(directory_paths=[Path("/test").absolute()])

    with patch("kragd.app.KragService") as MockService:
        MockService.return_value = mock_service
        app = create_app(config)
        app.state.service = mock_service

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


# ── Query round-trip tests ───────────────────────


class TestQueryRoundTrip:
    """Test full query → response pipeline via HTTP."""

    def test_query_roundtrip_returns_answer(
        self, test_client: TestClient, mock_service: MagicMock
    ) -> None:
        """POST /query returns the synthesized answer from KragService."""
        resp = test_client.post("/query", json={"query": "How does X work?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Based on the code, the function does X."

    def test_query_roundtrip_returns_sources(
        self, test_client: TestClient, mock_service: MagicMock
    ) -> None:
        """POST /query returns ranked source chunks."""
        resp = test_client.post("/query", json={"query": "test"})
        data = resp.json()
        assert len(data["sources"]) == 3
        assert data["sources"][0]["rank"] == 1
        assert data["sources"][1]["rank"] == 2
        assert data["sources"][2]["rank"] == 3

    def test_query_passes_top_k(self, test_client: TestClient, mock_service: MagicMock) -> None:
        """top_k parameter is forwarded to KragService.query()."""
        test_client.post("/query", json={"query": "test", "top_k": 20})
        call_args = mock_service.query.call_args
        req = call_args[0][0]
        assert req.top_k == 20

    def test_query_passes_preset(self, test_client: TestClient, mock_service: MagicMock) -> None:
        """preset parameter is forwarded to KragService.query()."""
        test_client.post("/query", json={"query": "test", "preset": "code"})
        call_args = mock_service.query.call_args
        req = call_args[0][0]
        assert req.preset == "code"

    def test_query_passes_llm(self, test_client: TestClient, mock_service: MagicMock) -> None:
        """llm parameter is forwarded to KragService.query()."""
        test_client.post("/query", json={"query": "test", "llm": "code"})
        call_args = mock_service.query.call_args
        req = call_args[0][0]
        assert req.llm == "code"

    def test_query_source_scores_ordered(self, test_client: TestClient) -> None:
        """Sources are returned in rank order (highest score first)."""
        resp = test_client.post("/query", json={"query": "test"})
        data = resp.json()
        scores = [s["score"] for s in data["sources"]]
        assert scores == sorted(scores, reverse=True)

    def test_query_source_file_paths_populated(self, test_client: TestClient) -> None:
        """Source chunks have absolute file paths."""
        resp = test_client.post("/query", json={"query": "test"})
        data = resp.json()
        for source in data["sources"]:
            assert source["file_path"].startswith("/")


# ── Retrieve round-trip tests ────────────────────


class TestRetrieveRoundTrip:
    """Test retrieval-only pipeline via HTTP."""

    def test_retrieve_roundtrip_returns_sources(
        self, test_client: TestClient, mock_service: MagicMock
    ) -> None:
        """POST /retrieve returns source chunks without answer."""
        resp = test_client.post("/retrieve", json={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert len(data["sources"]) == 3

    def test_retrieve_passes_top_k(self, test_client: TestClient, mock_service: MagicMock) -> None:
        """top_k parameter is forwarded to KragService.retrieve()."""
        test_client.post("/retrieve", json={"query": "test", "top_k": 15})
        call_args = mock_service.retrieve.call_args
        req = call_args[0][0]
        assert req.top_k == 15

    def test_retrieve_no_llm_synthesis(
        self, test_client: TestClient, mock_service: MagicMock
    ) -> None:
        """POST /retrieve does not call KragService.query()."""
        test_client.post("/retrieve", json={"query": "test"})
        mock_service.query.assert_not_called()
        mock_service.retrieve.assert_called_once()

    def test_retrieve_source_has_content(self, test_client: TestClient) -> None:
        """Each source chunk has non-empty chunk_content."""
        resp = test_client.post("/retrieve", json={"query": "test"})
        data = resp.json()
        for source in data["sources"]:
            assert len(source["chunk_content"]) > 0


# ── Error handling ───────────────────────────────


class TestQueryErrorHandling:
    """Test error responses match expected HTTP status codes."""

    def test_query_service_error_returns_500(
        self, test_client: TestClient, mock_service: MagicMock
    ) -> None:
        """Internal errors from KragService.query() result in 500."""
        mock_service.query.side_effect = RuntimeError("LLM failed")
        resp = test_client.post("/query", json={"query": "test"})
        assert resp.status_code == 500

    def test_retrieve_service_error_returns_500(
        self, test_client: TestClient, mock_service: MagicMock
    ) -> None:
        """Internal errors from KragService.retrieve() result in 500."""
        mock_service.retrieve.side_effect = RuntimeError("Vector store down")
        resp = test_client.post("/retrieve", json={"query": "test"})
        assert resp.status_code == 500
