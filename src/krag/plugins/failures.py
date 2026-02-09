"""Aggregation and reporting of indexing failures.

This module provides the IndexingFailureCollector for tracking files that could
not be indexed during a run, supporting both core system and plugin failures.
"""

from pathlib import Path

from krag.models.indexing_job import IndexingFailureRecord


class IndexingFailureCollector:
    """Collects and aggregates indexing failure records.

    Provides thread-safe collection of failures during indexing runs, with
    methods to categorize and report failures by plugin or overall.

    Example:
        >>> collector = IndexingFailureCollector()
        >>> collector.record_failure(
        ...     file_path=Path("/docs/bad.pdf"),
        ...     plugin_name="pdf",
        ...     reason="Corrupted file"
        ... )
        >>> print(f"Total failures: {collector.total_failures()}")
        >>> for failure in collector.get_failures():
        ...     print(f"{failure.file_path}: {failure.reason}")
    """

    def __init__(self) -> None:
        """Initialize failure collector with empty records."""
        self._failures: list[IndexingFailureRecord] = []

    def record_failure(
        self,
        file_path: Path,
        reason: str,
        plugin_name: str | None = None,
        exception_type: str | None = None,
    ) -> None:
        """Record a file that failed to index.

        Args:
            file_path: Path of the file that failed
            reason: Human-readable description of failure
            plugin_name: Plugin that reported failure (None for core system)
            exception_type: Exception class name if applicable
        """
        failure = IndexingFailureRecord(
            file_path=file_path,
            plugin_name=plugin_name,
            reason=reason,
            exception_type=exception_type,
        )
        self._failures.append(failure)

    def get_failures(self, plugin_name: str | None = None) -> list[IndexingFailureRecord]:
        """Get all failure records, optionally filtered by plugin.

        Args:
            plugin_name: Filter to failures from specific plugin (None = all)

        Returns:
            list[IndexingFailureRecord]: Matching failure records
        """
        if plugin_name is None:
            return self._failures.copy()
        return [f for f in self._failures if f.plugin_name == plugin_name]

    def total_failures(self) -> int:
        """Get total count of failures.

        Returns:
            int: Total number of recorded failures
        """
        return len(self._failures)

    def failures_by_plugin(self) -> dict[str | None, int]:
        """Get failure counts grouped by plugin.

        Returns:
            dict[str | None, int]: Mapping of plugin name to failure count,
                                   None key represents core system failures
        """
        counts: dict[str | None, int] = {}
        for failure in self._failures:
            counts[failure.plugin_name] = counts.get(failure.plugin_name, 0) + 1
        return counts

    def clear(self) -> None:
        """Clear all recorded failures."""
        self._failures.clear()
