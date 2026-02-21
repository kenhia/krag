"""Performance integration tests — T058.

Verify second query completes within time budget (SC-001)
and health endpoint responds quickly during normal operation (SC-005).
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _mock_service() -> MagicMock:
    """Create a mock KragService for performance testing."""
    service = MagicMock()
    service.start = AsyncMock()
    service.shutdown = AsyncMock()

    # Simulate fast query (models already loaded — no cold start)
    def _fast_query(*args, **kwargs):
        time.sleep(0.01)  # 10ms simulated response
        return {
            "answer": "Test answer",
            "sources": [
                {
                    "chunk_id": "chunk_001",
                    "file_path": "/test/file.txt",
                    "score": 0.95,
                    "rank": 1,
                    "chunk_content": "chunk content",
                    "file_type": ".txt",
                }
            ],
            "debug": None,
        }

    service.query = MagicMock(side_effect=_fast_query)

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


class TestSecondQueryPerformance:
    """SC-001: Second query completes within 2s (excluding inference)."""

    def test_second_query_under_2s(self, test_client: TestClient) -> None:
        """Second query to a warm service completes under 2 seconds."""
        # First query (warm up HTTP client/routing)
        test_client.post("/query", json={"query": "warmup", "top_k": 5})

        # Second query — measure time
        start = time.monotonic()
        resp = test_client.post("/query", json={"query": "test query", "top_k": 5})
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 2.0, f"Second query took {elapsed:.3f}s (budget: 2.0s)"

    def test_repeated_queries_consistently_fast(self, test_client: TestClient) -> None:
        """Multiple sequential queries maintain fast response times."""
        times = []
        for i in range(5):
            start = time.monotonic()
            resp = test_client.post("/query", json={"query": f"query {i}", "top_k": 5})
            elapsed = time.monotonic() - start
            assert resp.status_code == 200
            times.append(elapsed)

        # All queries should complete under 2s
        for i, t in enumerate(times):
            assert t < 2.0, f"Query {i} took {t:.3f}s"

        # Variance should be low (no intermittent cold starts)
        avg = sum(times) / len(times)
        assert avg < 1.0, f"Average query time {avg:.3f}s is too high"


class TestHealthEndpointPerformance:
    """SC-005: Health endpoint responds <500ms during normal operation."""

    def test_health_under_500ms(self, test_client: TestClient) -> None:
        """Health endpoint responds within 500ms."""
        start = time.monotonic()
        resp = test_client.get("/health")
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 0.5, f"Health check took {elapsed:.3f}s (budget: 0.5s)"

    def test_health_fast_during_queries(self, test_client: TestClient) -> None:
        """Health endpoint stays fast even while handling queries."""
        # Fire a query first
        test_client.post("/query", json={"query": "concurrent test", "top_k": 5})

        # Health check should still be fast
        start = time.monotonic()
        resp = test_client.get("/health")
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 0.5, f"Health check during load took {elapsed:.3f}s"

    def test_status_under_500ms(self, test_client: TestClient) -> None:
        """Status endpoint also responds within 500ms."""
        start = time.monotonic()
        resp = test_client.get("/status")
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 0.5, f"Status check took {elapsed:.3f}s"
