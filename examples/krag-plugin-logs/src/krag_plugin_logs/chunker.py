"""Custom chunker for log files with timestamp-based windowing."""

import re
from datetime import datetime, timedelta
from typing import Any

from krag.extraction.chunker import TextChunker


class LogFileChunker(TextChunker):
    """Custom chunker that groups log entries by time windows.

    This chunker demonstrates advanced chunking strategy by:
    1. Parsing timestamps from log entries
    2. Grouping entries within configurable time windows
    3. Respecting log entry boundaries (never splitting mid-entry)
    4. Adding temporal metadata to each chunk

    This preserves temporal coherence for better semantic search
    and debugging workflows.
    """

    def __init__(
        self,
        chunk_window_minutes: int = 5,
        max_entries_per_chunk: int = 100,
        timestamp_formats: list[str] | None = None,
    ):
        """Initialize the log file chunker.

        Args:
            chunk_window_minutes: Time window in minutes for grouping log entries
            max_entries_per_chunk: Maximum number of log entries per chunk
            timestamp_formats: List of strptime format strings for parsing timestamps
        """
        # Call parent with reasonable defaults for log files
        # We'll override chunk_text() entirely, but parent settings matter for fallback
        super().__init__(
            chunk_size=2000,  # Fallback if no timestamps detected
            chunk_overlap=200,
        )

        self.chunk_window_minutes = chunk_window_minutes
        self.max_entries_per_chunk = max_entries_per_chunk

        # Default timestamp formats (common log patterns)
        self.timestamp_formats = timestamp_formats or [
            r"%Y-%m-%d %H:%M:%S",  # 2024-02-11 10:00:15
            r"%Y-%m-%dT%H:%M:%S",  # 2024-02-11T10:00:15
            r"%Y-%m-%dT%H:%M:%S.%f",  # 2024-02-11T10:00:15.123456
            r"%d/%b/%Y:%H:%M:%S",  # 11/Feb/2024:10:00:15 (Apache)
            r"%b %d %H:%M:%S",  # Feb 11 10:00:15 (syslog)
        ]

        # Compiled regex patterns for timestamp detection
        self.timestamp_patterns = [
            re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"),  # ISO 8601-like
            re.compile(r"\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}"),  # Apache
            re.compile(r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"),  # syslog
        ]

    def chunk_text(self, text: str, metadata: dict[str, Any] | None = None) -> list[dict]:
        """Chunk log text by time windows.

        Parses log entries, detects timestamps, and groups entries within
        configurable time windows while respecting entry boundaries.

        Args:
            text: Log file content
            metadata: Optional metadata dict (unused, kept for compatibility)

        Returns:
            List of chunk dicts with 'content' and 'metadata' keys.
            Each chunk's metadata includes:
            - time_range_start: ISO timestamp of first entry
            - time_range_end: ISO timestamp of last entry
            - entry_count: Number of log entries in chunk
        """
        # Parse log entries with timestamps
        entries = self._parse_log_entries(text)

        if not entries:
            # No timestamps detected, return single chunk with all content
            return [
                {
                    "content": text,
                    "metadata": {
                        "entry_count": 0,
                        "note": "No timestamps detected in log file",
                    },
                }
            ]

        # Group entries by time windows
        chunks = self._group_by_time_windows(entries)

        return chunks

    def _parse_log_entries(self, text: str) -> list[dict[str, Any]]:
        """Parse log text into entries with timestamps.

        Args:
            text: Log file content

        Returns:
            List of dicts with 'timestamp' (datetime), 'text' (str), and
            'line_number' (int) keys. Returns empty list if no timestamps found.
        """
        entries = []
        lines = text.split("\n")

        current_entry_lines = []
        current_timestamp = None
        current_line_number = 0

        for line_number, line in enumerate(lines, start=1):
            # Try to detect timestamp at start of line
            timestamp = self._extract_timestamp(line)

            if timestamp:
                # New log entry detected
                if current_entry_lines:
                    # Save previous entry
                    entries.append(
                        {
                            "timestamp": current_timestamp,
                            "text": "\n".join(current_entry_lines),
                            "line_number": current_line_number,
                        }
                    )
                # Start new entry
                current_entry_lines = [line]
                current_timestamp = timestamp
                current_line_number = line_number
            else:
                # Continuation of previous entry (stack trace, multi-line message)
                if current_entry_lines:
                    current_entry_lines.append(line)
                # Else: leading lines before first timestamp (skip)

        # Save last entry
        if current_entry_lines and current_timestamp:
            entries.append(
                {
                    "timestamp": current_timestamp,
                    "text": "\n".join(current_entry_lines),
                    "line_number": current_line_number,
                }
            )

        return entries

    def _extract_timestamp(self, line: str) -> datetime | None:
        """Extract timestamp from a log line.

        Args:
            line: Single line from log file

        Returns:
            datetime object if timestamp found, None otherwise
        """
        # Try each timestamp pattern
        for pattern in self.timestamp_patterns:
            match = pattern.search(line)
            if match:
                timestamp_str = match.group(0)
                # Try parsing with known formats
                for fmt in self.timestamp_formats:
                    try:
                        # Handle year-less formats (syslog) - assume current year
                        if "%Y" not in fmt:
                            current_year = datetime.now().year
                            timestamp_str_with_year = f"{current_year} {timestamp_str}"
                            fmt_with_year = f"%Y {fmt}"
                            return datetime.strptime(timestamp_str_with_year, fmt_with_year)
                        else:
                            return datetime.strptime(timestamp_str, fmt)
                    except ValueError:
                        continue

        return None

    def _group_by_time_windows(self, entries: list[dict[str, Any]]) -> list[dict]:
        """Group log entries by time windows.

        Args:
            entries: List of parsed log entries with timestamps

        Returns:
            List of chunk dicts with 'content' and 'metadata' keys
        """
        if not entries:
            return []

        chunks = []
        current_chunk_entries = []
        window_start = entries[0]["timestamp"]

        window_delta = timedelta(minutes=self.chunk_window_minutes)

        for entry in entries:
            timestamp = entry["timestamp"]

            # Check if entry exceeds time window or entry limit
            if (
                timestamp - window_start > window_delta
                or len(current_chunk_entries) >= self.max_entries_per_chunk
            ):
                # Finalize current chunk
                if current_chunk_entries:
                    chunks.append(self._create_chunk(current_chunk_entries))

                # Start new chunk
                current_chunk_entries = [entry]
                window_start = timestamp
            else:
                current_chunk_entries.append(entry)

        # Finalize last chunk
        if current_chunk_entries:
            chunks.append(self._create_chunk(current_chunk_entries))

        return chunks

    def _create_chunk(self, entries: list[dict[str, Any]]) -> dict:
        """Create a chunk dict from log entries.

        Args:
            entries: List of log entries for this chunk

        Returns:
            Dict with 'content' and 'metadata' keys
        """
        # Concatenate entry texts
        content = "\n".join(entry["text"] for entry in entries)

        # Build metadata
        timestamps = [entry["timestamp"] for entry in entries]
        metadata = {
            "time_range_start": min(timestamps).isoformat(),
            "time_range_end": max(timestamps).isoformat(),
            "entry_count": len(entries),
            "line_numbers": [entry["line_number"] for entry in entries],
        }

        return {"content": content, "metadata": metadata}
