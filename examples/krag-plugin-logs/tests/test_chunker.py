"""Unit tests for LogFileChunker."""

from datetime import datetime

import pytest

from krag_plugin_logs.chunker import LogFileChunker


@pytest.fixture
def chunker():
    """Create a LogFileChunker instance with default settings."""
    return LogFileChunker(chunk_window_minutes=5, max_entries_per_chunk=100)


@pytest.fixture
def chunker_small_window():
    """Create a chunker with 1-minute time window."""
    return LogFileChunker(chunk_window_minutes=1, max_entries_per_chunk=10)


class TestLogFileChunker:
    """Test suite for LogFileChunker."""

    def test_initialization(self, chunker):
        """Test chunker initialization."""
        assert chunker.chunk_window_minutes == 5
        assert chunker.max_entries_per_chunk == 100
        assert len(chunker.timestamp_formats) > 0
        assert len(chunker.timestamp_patterns) > 0

    def test_extract_timestamp_iso_format(self, chunker):
        """Test timestamp extraction from ISO format."""
        line = "2024-02-11 10:00:15 INFO Application started"
        timestamp = chunker._extract_timestamp(line)

        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 2
        assert timestamp.day == 11
        assert timestamp.hour == 10
        assert timestamp.minute == 0
        assert timestamp.second == 15

    def test_extract_timestamp_iso_t_format(self, chunker):
        """Test timestamp extraction from ISO 8601 T format."""
        line = "2024-02-11T10:00:15 INFO Application started"
        timestamp = chunker._extract_timestamp(line)

        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.hour == 10

    def test_extract_timestamp_with_microseconds(self, chunker):
        """Test timestamp extraction with microseconds."""
        line = "2024-02-11T10:00:15.123456 DEBUG Detailed message"
        timestamp = chunker._extract_timestamp(line)

        assert timestamp is not None
        assert timestamp.microsecond == 123456

    def test_extract_timestamp_no_timestamp(self, chunker):
        """Test handling of lines without timestamps."""
        line = "    at some.package.Class.method(File.java:123)"
        timestamp = chunker._extract_timestamp(line)

        assert timestamp is None

    def test_parse_log_entries_simple(self, chunker):
        """Test parsing simple log entries."""
        text = """2024-02-11 10:00:15 INFO Application started
2024-02-11 10:00:20 INFO Database connected
2024-02-11 10:00:25 INFO Cache initialized"""

        entries = chunker._parse_log_entries(text)

        assert len(entries) == 3
        assert "Application started" in entries[0]["text"]
        assert "Database connected" in entries[1]["text"]
        assert "Cache initialized" in entries[2]["text"]

    def test_parse_log_entries_multiline(self, chunker):
        """Test parsing multi-line log entries (stack traces)."""
        text = """2024-02-11 10:00:15 INFO Application started
2024-02-11 10:00:20 ERROR Exception occurred
    at some.package.Class.method(File.java:123)
    at some.other.Class.caller(File.java:456)
2024-02-11 10:00:25 INFO Recovery successful"""

        entries = chunker._parse_log_entries(text)

        assert len(entries) == 3
        assert "Exception occurred" in entries[1]["text"]
        assert "at some.package" in entries[1]["text"]
        assert "at some.other" in entries[1]["text"]
        assert entries[1]["text"].count("\n") >= 2  # Multi-line entry

    def test_parse_log_entries_no_timestamps(self, chunker):
        """Test handling of text without timestamps."""
        text = """Some random text
Without any timestamps
At all"""

        entries = chunker._parse_log_entries(text)

        assert len(entries) == 0

    def test_group_by_time_windows_single_window(self, chunker):
        """Test grouping entries within single time window."""
        entries = [
            {
                "timestamp": datetime(2024, 2, 11, 10, 0, 0),
                "text": "Entry 1",
                "line_number": 1,
            },
            {
                "timestamp": datetime(2024, 2, 11, 10, 2, 0),
                "text": "Entry 2",
                "line_number": 2,
            },
            {
                "timestamp": datetime(2024, 2, 11, 10, 4, 0),
                "text": "Entry 3",
                "line_number": 3,
            },
        ]

        chunks = chunker._group_by_time_windows(entries)

        assert len(chunks) == 1  # All within 5-minute window
        assert chunks[0]["metadata"]["entry_count"] == 3

    def test_group_by_time_windows_multiple_windows(self, chunker_small_window):
        """Test grouping entries across multiple time windows."""
        entries = [
            {
                "timestamp": datetime(2024, 2, 11, 10, 0, 0),
                "text": "Entry 1",
                "line_number": 1,
            },
            {
                "timestamp": datetime(2024, 2, 11, 10, 0, 30),
                "text": "Entry 2",
                "line_number": 2,
            },
            {
                "timestamp": datetime(2024, 2, 11, 10, 2, 0),
                "text": "Entry 3",
                "line_number": 3,
            },
        ]

        chunks = chunker_small_window._group_by_time_windows(entries)

        assert len(chunks) == 2  # Split by 1-minute window
        assert chunks[0]["metadata"]["entry_count"] == 2  # 10:00:00 and 10:00:30
        assert chunks[1]["metadata"]["entry_count"] == 1  # 10:02:00

    def test_group_by_time_windows_max_entries_limit(self, chunker_small_window):
        """Test chunking by max entries per chunk limit."""
        # Create 15 entries all within same time window
        entries = [
            {
                "timestamp": datetime(2024, 2, 11, 10, 0, i),
                "text": f"Entry {i}",
                "line_number": i,
            }
            for i in range(15)
        ]

        chunks = chunker_small_window._group_by_time_windows(entries)

        # Should split by max_entries_per_chunk (10)
        assert len(chunks) == 2
        assert chunks[0]["metadata"]["entry_count"] == 10
        assert chunks[1]["metadata"]["entry_count"] == 5

    def test_create_chunk(self, chunker):
        """Test chunk creation from entries."""
        entries = [
            {
                "timestamp": datetime(2024, 2, 11, 10, 0, 0),
                "text": "Entry 1",
                "line_number": 1,
            },
            {
                "timestamp": datetime(2024, 2, 11, 10, 2, 0),
                "text": "Entry 2",
                "line_number": 2,
            },
        ]

        chunk = chunker._create_chunk(entries)

        assert "content" in chunk
        assert "metadata" in chunk
        assert "Entry 1" in chunk["content"]
        assert "Entry 2" in chunk["content"]
        assert chunk["metadata"]["entry_count"] == 2
        assert "time_range_start" in chunk["metadata"]
        assert "time_range_end" in chunk["metadata"]

    def test_chunk_text_with_timestamps(self, chunker):
        """Test end-to-end text chunking with timestamps."""
        text = """2024-02-11 10:00:00 INFO Start
2024-02-11 10:02:00 INFO Middle
2024-02-11 10:06:00 INFO After window
2024-02-11 10:08:00 INFO End"""

        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 2  # At least two time windows
        assert all("content" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)
        assert all("entry_count" in chunk["metadata"] for chunk in chunks)

    def test_chunk_text_without_timestamps_fallback(self, chunker):
        """Test fallback to parent chunking when no timestamps."""
        text = "Plain text without any timestamps.\n" * 100

        chunks = chunker.chunk_text(text)

        # Should fall back to parent TextChunker
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)

    def test_chunk_metadata_includes_time_range(self, chunker):
        """Test that chunk metadata includes time range."""
        text = """2024-02-11 10:00:00 INFO First
2024-02-11 10:04:59 INFO Last"""

        chunks = chunker.chunk_text(text)

        assert len(chunks) == 1
        metadata = chunks[0]["metadata"]
        assert "time_range_start" in metadata
        assert "time_range_end" in metadata
        assert metadata["time_range_start"] == "2024-02-11T10:00:00"
        assert metadata["time_range_end"] == "2024-02-11T10:04:59"

    def test_preserves_log_entry_boundaries(self, chunker):
        """Test that chunker never splits mid-entry."""
        text = """2024-02-11 10:00:00 ERROR Exception
    at line 1
    at line 2
    at line 3
2024-02-11 10:06:00 INFO Recovered"""

        chunks = chunker.chunk_text(text)

        # Multi-line entry should stay together
        first_chunk = chunks[0]["content"]
        assert "Exception" in first_chunk
        assert "at line 1" in first_chunk
        assert "at line 2" in first_chunk
        assert "at line 3" in first_chunk

    def test_custom_timestamp_formats(self):
        """Test chunker with custom timestamp formats."""
        custom_formats = [r"%Y-%m-%d %H:%M:%S", r"%d/%m/%Y %H:%M:%S"]
        chunker = LogFileChunker(timestamp_formats=custom_formats)

        assert chunker.timestamp_formats == custom_formats
