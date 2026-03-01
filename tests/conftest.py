"""Shared pytest fixtures for all tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from tests.fixtures.mock_plugin import MockFileTypeHandler


@pytest.fixture
def mock_file_handler() -> MockFileTypeHandler:
    """Provide a mock FileTypeHandler for testing."""
    return MockFileTypeHandler()


# ── SSE test utilities ──────────────────────────


@dataclass
class SSEEvent:
    """A parsed Server-Sent Event."""

    event: str | None = None
    data: str = ""
    id: str | None = None
    retry: int | None = None
    parsed_data: dict | list | str | None = field(default=None, repr=False)

    def json(self) -> dict | list:
        """Parse data as JSON, caching the result."""
        if self.parsed_data is None:
            self.parsed_data = json.loads(self.data)
        return self.parsed_data  # type: ignore[return-value]


def parse_sse_stream(text: str) -> list[SSEEvent]:
    """Parse raw SSE text into a list of SSEEvent objects.

    Handles multi-line data fields, event types, id fields,
    and comment lines (prefixed with ':').

    Args:
        text: Raw SSE response body text.

    Returns:
        List of parsed SSEEvent objects, one per event block.
    """
    events: list[SSEEvent] = []
    current = SSEEvent()
    data_lines: list[str] = []

    for line in text.split("\n"):
        line = line.rstrip("\r")  # Handle \r\n line endings from SSE streams
        # Blank line = end of event block
        if line.strip() == "":
            if data_lines or current.event is not None:
                current.data = "\n".join(data_lines)
                events.append(current)
                current = SSEEvent()
                data_lines = []
            continue

        # Comment lines (keep-alive pings, etc.)
        if line.startswith(":"):
            continue

        if ":" in line:
            field_name, _, value = line.partition(":")
            value = value.lstrip(" ")  # SSE spec: strip single leading space

            if field_name == "event":
                current.event = value
            elif field_name == "data":
                data_lines.append(value)
            elif field_name == "id":
                current.id = value
            elif field_name == "retry":
                try:
                    current.retry = int(value)
                except ValueError:
                    pass

    # Handle trailing event without final blank line
    if data_lines or current.event is not None:
        current.data = "\n".join(data_lines)
        events.append(current)

    return events
