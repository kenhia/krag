"""Contract tests for POST /debug/query and POST /debug/qdrant endpoints.

T037: Validate DebugQueryResponse has ≥10 debug metadata fields.
T041: Validate QdrantSearchResponse schema.
Tests use FastAPI TestClient with a mocked KragService.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kragd.schemas import (
    DebugMetadata,
    DebugQueryResponse,
    QdrantSearchResponse,
    QdrantSearchResult,
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


def _make_debug_metadata() -> DebugMetadata:
    """Create a valid DebugMetadata for testing."""
    return DebugMetadata(
        llm_used="text",
        llm_model="qwen2.5-7b-instruct-q4_k_m.gguf",
        route="text",
        auto_routed=True,
        route_reason="No code-heavy chunks detected",
        preset="default",
        retrieval_time_ms=42.5,
        generation_time_ms=1250.3,
        embedding_models_used=["all-MiniLM-L6-v2"],
        vector_spaces_searched=["text"],
        total_candidates_before_dedup=25,
        total_candidates_after_dedup=10,
        similarity_threshold=0.3,
        per_space_result_counts={"text": 10},
    )


def _make_qdrant_result(rank: int = 1) -> QdrantSearchResult:
    """Create a valid QdrantSearchResult for testing."""
    return QdrantSearchResult(
        chunk_id=f"point-{rank}",
        score=0.98 - (rank - 1) * 0.05,
        file_path=f"/home/user/project/file_{rank}.py",
        file_type="py",
        chunk_content=f"def raw_example_{rank}(): pass",
        chunk_index=rank - 1,
        start_line=rank * 5,
        end_line=rank * 5 + 3,
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

        # Default debug_query response
        mock_service.debug_query.return_value = DebugQueryResponse(
            answer="Debug answer to the question.",
            sources=[_make_source_chunk(1), _make_source_chunk(2)],
            debug=_make_debug_metadata(),
        )

        # Default debug_qdrant response
        mock_service.debug_qdrant.return_value = QdrantSearchResponse(
            results=[_make_qdrant_result(1), _make_qdrant_result(2), _make_qdrant_result(3)],
            total_results=3,
            vector_space="text",
        )

        MockService.return_value = mock_service

        app = create_app(config)
        app.state.service = mock_service

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


# ── POST /debug/query contract ───────────────────


class TestDebugQueryContract:
    """Contract tests for POST /debug/query."""

    def test_debug_query_returns_200(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "what is krag?"})
        assert resp.status_code == 200

    def test_debug_query_has_answer(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "what is krag?"})
        data = resp.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_debug_query_has_sources(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "what is krag?"})
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_debug_query_has_debug_always(self, test_client: TestClient) -> None:
        """Debug metadata must ALWAYS be present (not nullable)."""
        resp = test_client.post("/debug/query", json={"query": "what is krag?"})
        data = resp.json()
        assert "debug" in data
        assert data["debug"] is not None

    def test_debug_metadata_has_minimum_10_fields(self, test_client: TestClient) -> None:
        """SC-003: DebugMetadata must have ≥10 fields."""
        resp = test_client.post("/debug/query", json={"query": "what is krag?"})
        debug = resp.json()["debug"]
        assert len(debug) >= 10, (
            f"Expected ≥10 debug fields, got {len(debug)}: {list(debug.keys())}"
        )

    def test_debug_metadata_required_fields(self, test_client: TestClient) -> None:
        """All required DebugMetadata fields present."""
        resp = test_client.post("/debug/query", json={"query": "test"})
        debug = resp.json()["debug"]
        required = [
            "llm_used",
            "llm_model",
            "route",
            "auto_routed",
            "preset",
            "retrieval_time_ms",
            "generation_time_ms",
            "embedding_models_used",
            "vector_spaces_searched",
            "total_candidates_before_dedup",
            "total_candidates_after_dedup",
            "similarity_threshold",
            "per_space_result_counts",
        ]
        for field in required:
            assert field in debug, f"Missing required debug field: {field}"

    def test_debug_metadata_field_types(self, test_client: TestClient) -> None:
        """Debug metadata fields have correct types."""
        resp = test_client.post("/debug/query", json={"query": "test"})
        debug = resp.json()["debug"]
        assert isinstance(debug["llm_used"], str)
        assert isinstance(debug["llm_model"], str)
        assert isinstance(debug["route"], str)
        assert isinstance(debug["auto_routed"], bool)
        assert isinstance(debug["preset"], str)
        assert isinstance(debug["retrieval_time_ms"], (int, float))
        assert isinstance(debug["generation_time_ms"], (int, float))
        assert isinstance(debug["embedding_models_used"], list)
        assert isinstance(debug["vector_spaces_searched"], list)
        assert isinstance(debug["total_candidates_before_dedup"], int)
        assert isinstance(debug["total_candidates_after_dedup"], int)
        assert isinstance(debug["similarity_threshold"], (int, float))
        assert isinstance(debug["per_space_result_counts"], dict)

    def test_debug_query_with_top_k(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "test", "top_k": 5})
        assert resp.status_code == 200

    def test_debug_query_with_preset(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "test", "preset": "concise"})
        assert resp.status_code == 200

    def test_debug_query_with_llm_override(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "test", "llm": "code"})
        assert resp.status_code == 200

    def test_debug_query_empty_query_rejected(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": ""})
        assert resp.status_code == 422

    def test_debug_query_missing_query_rejected(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={})
        assert resp.status_code == 422

    def test_debug_query_invalid_llm_rejected(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "test", "llm": "invalid"})
        assert resp.status_code == 422

    def test_debug_query_source_chunk_schema(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "test"})
        sources = resp.json()["sources"]
        assert len(sources) > 0
        src = sources[0]
        assert "chunk_id" in src
        assert "file_path" in src
        assert "score" in src
        assert "rank" in src
        assert "chunk_content" in src
        assert "file_type" in src

    def test_debug_query_timing_non_negative(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/query", json={"query": "test"})
        debug = resp.json()["debug"]
        assert debug["retrieval_time_ms"] >= 0
        assert debug["generation_time_ms"] >= 0


# ── POST /debug/qdrant contract ──────────────────


class TestDebugQdrantContract:
    """Contract tests for POST /debug/qdrant."""

    def test_qdrant_search_returns_200(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test search"})
        assert resp.status_code == 200

    def test_qdrant_response_has_results(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test"})
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_qdrant_response_has_total_results(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test"})
        data = resp.json()
        assert "total_results" in data
        assert isinstance(data["total_results"], int)

    def test_qdrant_response_has_vector_space(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test"})
        data = resp.json()
        assert "vector_space" in data

    def test_qdrant_result_schema(self, test_client: TestClient) -> None:
        """Each result should have required fields."""
        resp = test_client.post("/debug/qdrant", json={"query": "test"})
        results = resp.json()["results"]
        assert len(results) > 0
        r = results[0]
        assert "chunk_id" in r
        assert "score" in r
        assert "file_path" in r
        assert "file_type" in r
        assert "chunk_index" in r

    def test_qdrant_result_score_is_raw(self, test_client: TestClient) -> None:
        """Scores should be raw similarity (not RRF-fused)."""
        resp = test_client.post("/debug/qdrant", json={"query": "test"})
        results = resp.json()["results"]
        for r in results:
            assert isinstance(r["score"], (int, float))

    def test_qdrant_search_with_vector_space(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test", "vector_space": "text"})
        assert resp.status_code == 200

    def test_qdrant_search_with_top_k(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test", "top_k": 20})
        assert resp.status_code == 200

    def test_qdrant_search_with_threshold(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test", "score_threshold": 0.5})
        assert resp.status_code == 200

    def test_qdrant_search_with_filters(self, test_client: TestClient) -> None:
        resp = test_client.post(
            "/debug/qdrant",
            json={
                "query": "test",
                "filters": {"file_type": "py", "file_path_contains": "src/"},
            },
        )
        assert resp.status_code == 200

    def test_qdrant_search_empty_query_rejected(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": ""})
        assert resp.status_code == 422

    def test_qdrant_search_missing_query_rejected(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={})
        assert resp.status_code == 422

    def test_qdrant_search_top_k_too_large(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test", "top_k": 5000})
        assert resp.status_code == 422

    def test_qdrant_search_payload_toggle(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test", "with_payload": False})
        assert resp.status_code == 200

    def test_qdrant_total_results_matches(self, test_client: TestClient) -> None:
        resp = test_client.post("/debug/qdrant", json={"query": "test"})
        data = resp.json()
        assert data["total_results"] == len(data["results"])
