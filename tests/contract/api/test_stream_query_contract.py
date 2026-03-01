"""Contract tests for POST /query/stream SSE endpoint (US6).

T032: Verify that:
- SSE stream sends query:sources event with retrieved chunks
- SSE stream sends query:token events with partial answer tokens
- SSE stream sends query:done event with complete response
- SSE stream sends query:error event on failure
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


# ── Sample event data ────────────────────────────

_SOURCES_EVENT = {
    "type": "query:sources",
    "data": {
        "sources": [
            {
                "chunk_id": "abc-123",
                "file_path": "src/main.py",
                "score": 0.92,
                "rank": 1,
                "chunk_content": "def main(): ...",
                "file_type": "python",
                "collection": "code",
            }
        ]
    },
}

_TOKEN_EVENTS = [
    {"type": "query:token", "data": {"token": "The krag "}},
    {"type": "query:token", "data": {"token": "architecture "}},
    {"type": "query:token", "data": {"token": "uses a modular pipeline."}},
]

_DONE_EVENT = {
    "type": "query:done",
    "data": {
        "answer": "The krag architecture uses a modular pipeline.",
        "sources": [
            {
                "chunk_id": "abc-123",
                "file_path": "src/main.py",
                "score": 0.92,
                "rank": 1,
                "chunk_content": "def main(): ...",
                "file_type": "python",
                "collection": "code",
            }
        ],
        "debug": None,
    },
}

_ERROR_EVENT = {
    "type": "query:error",
    "data": {"error": "LLM generation failed: out of memory"},
}

_QUERY_BODY = {"query": "What is the krag architecture?"}


# ── Sources event ────────────────────────────────


class TestQueryStreamSources:
    """POST /query/stream should send sources before tokens."""

    def test_sources_event_sent_first(self) -> None:
        """First event should be query:sources with chunk data."""
        events_to_send = [_SOURCES_EVENT, *_TOKEN_EVENTS, _DONE_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            events = parse_sse_stream(resp.text)
            typed_events = [e for e in events if e.event and e.event.startswith("query:")]
            assert len(typed_events) >= 1
            assert typed_events[0].event == "query:sources"
            data = typed_events[0].json()
            assert "sources" in data
            assert len(data["sources"]) >= 1

    def test_sources_event_contains_chunk_fields(self) -> None:
        """Source chunks should contain required fields."""
        events_to_send = [_SOURCES_EVENT, _DONE_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            events = parse_sse_stream(resp.text)
            sources_events = [e for e in events if e.event == "query:sources"]
            assert len(sources_events) == 1
            chunk = sources_events[0].json()["sources"][0]
            assert "chunk_id" in chunk
            assert "file_path" in chunk
            assert "score" in chunk
            assert "chunk_content" in chunk


# ── Token events ─────────────────────────────────


class TestQueryStreamTokens:
    """POST /query/stream should send tokens as they are generated."""

    def test_token_events_contain_text(self) -> None:
        """Each token event should have a 'token' field with text."""
        events_to_send = [_SOURCES_EVENT, *_TOKEN_EVENTS, _DONE_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            events = parse_sse_stream(resp.text)
            tokens = [e for e in events if e.event == "query:token"]
            assert len(tokens) == 3
            for tok in tokens:
                data = tok.json()
                assert "token" in data
                assert isinstance(data["token"], str)
                assert len(data["token"]) > 0

    def test_tokens_arrive_between_sources_and_done(self) -> None:
        """Tokens should come after sources and before done."""
        events_to_send = [_SOURCES_EVENT, *_TOKEN_EVENTS, _DONE_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            events = parse_sse_stream(resp.text)
            typed = [e.event for e in events if e.event and e.event.startswith("query:")]
            sources_idx = typed.index("query:sources")
            done_idx = typed.index("query:done")
            token_indices = [i for i, t in enumerate(typed) if t == "query:token"]
            assert all(sources_idx < ti < done_idx for ti in token_indices)


# ── Done event ───────────────────────────────────


class TestQueryStreamDone:
    """POST /query/stream should send a done event with the complete response."""

    def test_done_event_has_answer_and_sources(self) -> None:
        """Done event should contain the full answer and sources."""
        events_to_send = [_SOURCES_EVENT, *_TOKEN_EVENTS, _DONE_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            events = parse_sse_stream(resp.text)
            done = [e for e in events if e.event == "query:done"]
            assert len(done) == 1
            data = done[0].json()
            assert "answer" in data
            assert "sources" in data
            assert isinstance(data["answer"], str)
            assert len(data["answer"]) > 0

    def test_done_event_closes_stream(self) -> None:
        """After query:done, no more events should follow."""
        events_to_send = [_SOURCES_EVENT, _DONE_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            events = parse_sse_stream(resp.text)
            typed = [e.event for e in events if e.event and e.event.startswith("query:")]
            done_idx = typed.index("query:done")
            # Done should be the last query event
            assert done_idx == len(typed) - 1


# ── Error event ──────────────────────────────────


class TestQueryStreamError:
    """POST /query/stream should send an error event on failure."""

    def test_error_event_has_message(self) -> None:
        """Error event should contain an 'error' field."""
        events_to_send = [_ERROR_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            assert resp.status_code == 200
            events = parse_sse_stream(resp.text)
            errors = [e for e in events if e.event == "query:error"]
            assert len(errors) == 1
            data = errors[0].json()
            assert "error" in data
            assert len(data["error"]) > 0

    def test_error_after_sources_is_valid(self) -> None:
        """Error can occur mid-stream (after sources, during generation)."""
        events_to_send = [_SOURCES_EVENT, _ERROR_EVENT]
        mock_service = MagicMock()
        mock_service.query_stream.return_value = _async_gen_from_list(events_to_send)

        client = _make_test_client(mock_service)
        with client:
            resp = client.post("/query/stream", json=_QUERY_BODY)
            events = parse_sse_stream(resp.text)
            event_types = [e.event for e in events if e.event and e.event.startswith("query:")]
            assert "query:sources" in event_types
            assert "query:error" in event_types
