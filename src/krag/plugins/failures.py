"""Aggregation and reporting of indexing failures.

This module provides the IndexingFailureCollector for tracking files that could
not be indexed during a run, supporting both core system and plugin failures.
It also provides a public report_indexing_failure() API for use by plugins.
"""

import logging
import threading
from pathlib import Path
from typing import Any

from krag.models.indexing_job import IndexingFailureRecord

logger = logging.getLogger(__name__)


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
        self._lock = threading.Lock()
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
        with self._lock:
            self._failures.append(failure)

    def get_failures(self, plugin_name: str | None = None) -> list[IndexingFailureRecord]:
        """Get all failure records, optionally filtered by plugin.

        Args:
            plugin_name: Filter to failures from specific plugin (None = all)

        Returns:
            list[IndexingFailureRecord]: Matching failure records
        """
        with self._lock:
            if plugin_name is None:
                return self._failures.copy()
            return [f for f in self._failures if f.plugin_name == plugin_name]

    def total_failures(self) -> int:
        """Get total count of failures.

        Returns:
            int: Total number of recorded failures
        """
        with self._lock:
            return len(self._failures)

    def failures_by_plugin(self) -> dict[str | None, int]:
        """Get failure counts grouped by plugin.

        Returns:
            dict[str | None, int]: Mapping of plugin name to failure count,
                                   None key represents core system failures
        """
        with self._lock:
            counts: dict[str | None, int] = {}
            for failure in self._failures:
                counts[failure.plugin_name] = counts.get(failure.plugin_name, 0) + 1
            return counts

    def clear(self) -> None:
        """Clear all recorded failures."""
        with self._lock:
            self._failures.clear()

    def format_summary(self) -> str:
        """Generate human-readable failure summary.

        Returns:
            str: Formatted summary of all failures, grouped by plugin

        Example:
            >>> print(collector.format_summary())
            Indexing Failures Summary:
            - Core system: 2 failures
            - Plugin 'pdf': 3 failures
        """
        with self._lock:
            if not self._failures:
                return "No indexing failures recorded."

            lines = ["Indexing Failures Summary:"]
            lines.append(f"Total failures: {len(self._failures)}")
            lines.append("")

            # Group by plugin
            counts: dict[str | None, int] = {}
            for failure in self._failures:
                counts[failure.plugin_name] = counts.get(failure.plugin_name, 0) + 1

            # Core system failures first
            if None in counts:
                lines.append(f"Core system: {counts[None]} failure(s)")
                for failure in [f for f in self._failures if f.plugin_name is None]:
                    lines.append(f"  - {failure.file_path}: {failure.reason}")
                lines.append("")

            # Plugin failures
            for plugin_name, count in sorted(
                (item for item in counts.items() if item[0] is not None), key=lambda x: x[0]
            ):
                if plugin_name is not None:
                    lines.append(f"Plugin '{plugin_name}': {count} failure(s)")
                    for failure in [f for f in self._failures if f.plugin_name == plugin_name]:
                        lines.append(f"  - {failure.file_path}: {failure.reason}")
                    lines.append("")

            return "\n".join(lines)

    def failures_by_exception_type(self) -> dict[str | None, int]:
        """Get failure counts grouped by exception type.

        Useful for identifying systemic issues (e.g., many 'extraction' errors
        may indicate a plugin bug, while 'dependency' errors indicate missing packages).

        Returns:
            dict[str | None, int]: Mapping of exception type to failure count
        """
        with self._lock:
            counts: dict[str | None, int] = {}
            for failure in self._failures:
                counts[failure.exception_type] = counts.get(failure.exception_type, 0) + 1
            return counts

    def get_error_report(self) -> dict[str, Any]:
        """Generate structured error aggregation report.

        Returns a dictionary suitable for structured logging or JSON output,
        including failure counts by plugin, by exception type, and details.

        Returns:
            dict: Structured error report with aggregated statistics
        """
        with self._lock:
            by_plugin: dict[str | None, int] = {}
            by_exc: dict[str | None, int] = {}
            for failure in self._failures:
                by_plugin[failure.plugin_name] = by_plugin.get(failure.plugin_name, 0) + 1
                by_exc[failure.exception_type] = by_exc.get(failure.exception_type, 0) + 1
            return {
                "total_failures": len(self._failures),
                "by_plugin": {(k or "core"): v for k, v in by_plugin.items()},
                "by_exception_type": {(k or "unknown"): v for k, v in by_exc.items()},
                "failures": [
                    {
                        "file_path": str(f.file_path),
                        "plugin_name": f.plugin_name or "core",
                        "reason": f.reason,
                        "exception_type": f.exception_type,
                    }
                    for f in self._failures
                ],
            }


def report_indexing_failure(
    file_path: Path,
    reason: str,
    plugin_name: str | None = None,
    exception_type: str | None = None,
) -> None:
    """Public API for reporting indexing failures.

    This function provides a standalone API for reporting files that could not
    be indexed. It's intended to be used within a context where an
    IndexingFailureCollector has been set up.

    Note: This function logs the failure but does not directly record it to a
    collector. The actual recording should be done by wrapping this in a closure
    that has access to the active collector instance (as done in IndexingOrchestrator).

    Args:
        file_path: Path of the file that failed to index
        reason: Human-readable description of the failure
        plugin_name: Name of plugin reporting failure (None for core system)
        exception_type: Exception class name if applicable

    Example:
        >>> report_indexing_failure(
        ...     Path("/docs/bad.pdf"),
        ...     "File appears to be corrupted",
        ...     plugin_name="pdf"
        ... )
    """
    logger.warning(
        f"Indexing failure reported: {file_path} (plugin={plugin_name or 'core'}): {reason}"
    )
