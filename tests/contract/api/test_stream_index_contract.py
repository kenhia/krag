"""Contract tests for GET /index/stream SSE endpoint (US5).

T029: Verify that:
- SSE stream sends index:idle when no job is running
- SSE stream sends index:progress events during indexing
- SSE stream sends index:complete when job finishes
- SSE stream sends index:error when job fails
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from tests.conftest import parse_sse_stream


def _make_test_client(mock_service: MagicMock) -> TestClient:
    """Create a TestClient with a pre-configured mock service."""
    from krag.models.configuration import Configuration
    from kragd.app import create_app
    from kragd.schemas import HealthResponse

    config = Configuration(directory_paths=[Path("/test").absolute()])

    with patch("kragd.app.KragService") as MockService:
        mock_service.start = AsyncMock()
        mock_service.shutdown = AsyncMock()
        mock_service.get_health.return_value = HealthResponse(status="healthy", version="0.0.0")
        MockService.return_value = mock_service

        app = create_app(config)
        app.state.service = mock_service
        return TestClient(app, raise_server_exceptions=False)


async def _async_gen_from_list(items: list[dict]) -> AsyncGenerator[dict, None]:
    """Helper: create an async generator yielding items from a list."""
    for item in items:
        yield item


class TestIndexStreamIdle:
    """GET /index/stream when no job is running."""

    def test_idle_event_when_no_job(self) -> None:
        """Should send an index:idle event and close when nothing is running."""
        idle_event = {"type": "index:idle", "data": {"message": "No active indexing job"}}
        mock_service = MagicMock()
        mock_service.subscribe_index_events.return_value = _async_gen_from_list([idle_event])

        client = _make_test_client(mock_service)
        with client:
            resp = client.get("/index/stream")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events = parse_sse_stream(resp.text)
            idle_events = [e for e in events if e.event == "index:idle"]
            assert len(idle_events) >= 1
            data = idle_events[0].json()
            assert "message" in data

    def test_idle_event_has_no_active_job_message(self) -> None:
        """The idle event message should indicate no active job."""
        idle_event = {"type": "index:idle", "data": {"message": "No active indexing job"}}
        mock_service = MagicMock()
        mock_service.subscribe_index_events.return_value = _async_gen_from_list([idle_event])

        client = _make_test_client(mock_service)
        with client:
            resp = client.get("/index/stream")
            events = parse_sse_stream(resp.text)
            idle_events = [e for e in events if e.event == "index:idle"]
            assert len(idle_events) >= 1
            data = idle_events[0].json()
            assert "no active" in data["message"].lower()


class TestIndexStreamProgress:
    """GET /index/stream during an active indexing job."""

    def test_progress_events_during_indexing(self) -> None:
        """Should receive progress events pushed to the stream."""
        events_to_send = [
            {
                "type": "index:progress",
                "data": {"current": 5, "total": 10, "stage": "Processing files"},
            },
            {
                "type": "index:complete",
                "data": {"job_id": "test-123", "status": "completed"},
            },
        ]
        mock_service = MagicMock()
        mock_service.subscribe_index_events.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.get("/index/stream")
            assert resp.status_code == 200
            events = parse_sse_stream(resp.text)
            event_types = [e.event for e in events]
            assert "index:progress" in event_types
            assert "index:complete" in event_types

    def test_progress_event_contains_current_and_total(self) -> None:
        """Progress events should have current, total, and stage fields."""
        events_to_send = [
            {
                "type": "index:progress",
                "data": {"current": 3, "total": 7, "stage": "Processing files"},
            },
            {
                "type": "index:complete",
                "data": {"job_id": "test-456", "status": "completed"},
            },
        ]
        mock_service = MagicMock()
        mock_service.subscribe_index_events.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.get("/index/stream")
            events = parse_sse_stream(resp.text)
            progress = [e for e in events if e.event == "index:progress"]
            assert len(progress) >= 1
            data = progress[0].json()
            assert data["current"] == 3
            assert data["total"] == 7
            assert data["stage"] == "Processing files"


class TestIndexStreamComplete:
    """Completion event tests."""

    def test_complete_event_closes_stream(self) -> None:
        """After index:complete, the stream should close."""
        events_to_send = [
            {
                "type": "index:complete",
                "data": {"job_id": "test-789", "status": "completed", "files_processed": 42},
            },
        ]
        mock_service = MagicMock()
        mock_service.subscribe_index_events.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.get("/index/stream")
            assert resp.status_code == 200
            events = parse_sse_stream(resp.text)
            complete = [e for e in events if e.event == "index:complete"]
            assert len(complete) == 1
            data = complete[0].json()
            assert data["status"] == "completed"


class TestIndexStreamError:
    """Error event tests."""

    def test_error_event_closes_stream(self) -> None:
        """After index:error, the stream should close."""
        events_to_send = [
            {
                "type": "index:error",
                "data": {"job_id": "test-err", "error": "Failed to connect to vector store"},
            },
        ]
        mock_service = MagicMock()
        mock_service.subscribe_index_events.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.get("/index/stream")
            assert resp.status_code == 200
            events = parse_sse_stream(resp.text)
            errors = [e for e in events if e.event == "index:error"]
            assert len(errors) == 1
            data = errors[0].json()
            assert "error" in data
