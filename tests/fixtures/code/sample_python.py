"""Sample Python file for testing code-aware chunking.

This file contains various Python constructs that the AST chunker
should handle: functions, classes, methods, decorators, imports.
"""

import os
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3


def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number.

    Args:
        n: The position in the Fibonacci sequence (0-indexed).

    Returns:
        The nth Fibonacci number.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def read_config(path: Path) -> dict[str, Any]:
    """Read configuration from a file.

    Args:
        path: Path to the configuration file.

    Returns:
        Dictionary of configuration values.
    """
    if not path.exists():
        return {}
    with open(path) as f:
        import json

        return json.load(f)


class DataProcessor:
    """Processes and transforms data records.

    Handles validation, transformation, and output of structured data.
    """

    def __init__(self, source: str, max_records: int = 1000) -> None:
        """Initialize the data processor.

        Args:
            source: Data source identifier.
            max_records: Maximum number of records to process.
        """
        self.source = source
        self.max_records = max_records
        self._records: list[dict[str, Any]] = []
        self._processed_count = 0

    def validate_record(self, record: dict[str, Any]) -> bool:
        """Validate a single data record.

        Args:
            record: The record to validate.

        Returns:
            True if the record is valid.
        """
        required_fields = ["id", "name", "value"]
        return all(field in record for field in required_fields)

    def transform_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Transform a record for output.

        Args:
            record: The record to transform.

        Returns:
            Transformed record with normalized values.
        """
        return {
            "id": str(record["id"]),
            "name": record["name"].strip().lower(),
            "value": float(record["value"]),
            "source": self.source,
        }

    def process_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process a batch of records.

        Validates and transforms each record, skipping invalid ones.

        Args:
            records: List of records to process.

        Returns:
            List of successfully processed records.
        """
        results = []
        for record in records[: self.max_records]:
            if self.validate_record(record):
                transformed = self.transform_record(record)
                results.append(transformed)
                self._processed_count += 1
        self._records.extend(results)
        return results

    @property
    def processed_count(self) -> int:
        """Return the total number of processed records."""
        return self._processed_count

    @staticmethod
    def merge_records(
        records_a: list[dict[str, Any]], records_b: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge two lists of records by ID.

        Args:
            records_a: First list of records.
            records_b: Second list of records.

        Returns:
            Merged list with duplicates removed (keeping first occurrence).
        """
        seen_ids: set[str] = set()
        merged: list[dict[str, Any]] = []
        for record in records_a + records_b:
            rid = record.get("id", "")
            if rid not in seen_ids:
                seen_ids.add(rid)
                merged.append(record)
        return merged


def helper_function() -> str:
    """A simple standalone helper function."""
    return "helper"
