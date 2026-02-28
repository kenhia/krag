"""Unit tests for periodic storage progress logging in ContentIndexer.

Verifies that _store_routed_vectors emits progress log messages roughly
every 30 seconds during large indexing runs, while remaining silent for
short runs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from krag.models.indexing_job import IndexingJob, JobStatus, JobType

# ── fixtures ──────────────────────────────────────────────────────────────────


def _make_job() -> IndexingJob:
    """Minimal IndexingJob suitable for testing _store_routed_vectors."""
    return IndexingJob(
        job_id=str(uuid.uuid4()),
        job_type=JobType.FULL,
        status=JobStatus.RUNNING,
        start_time=datetime.now(),
    )


def _make_indexer() -> MagicMock:
    """Minimal IndexingOrchestrator with a mocked collection_manager.

    Uses ``object.__new__`` to skip ``__init__`` and attaches the attributes
    that _store_routed_vectors needs.
    """
    from krag.orchestration.indexer import IndexingOrchestrator

    indexer = object.__new__(IndexingOrchestrator)

    mock_store = MagicMock()
    mock_store.vector_store.upsert = MagicMock()

    mock_cm = MagicMock()
    mock_cm.get_store.return_value = mock_store

    indexer.collection_manager = mock_cm
    return indexer


def _make_vectors(n: int) -> list[dict]:
    """Return *n* minimal vector dicts."""
    return [{"id": f"v{i}", "vector": [0.1] * 4} for i in range(n)]


# ── tests ─────────────────────────────────────────────────────────────────────


class TestStoragePeriodicLogging:
    """_store_routed_vectors logs progress roughly every 30 seconds."""

    @patch("krag.orchestration.indexer.time")
    def test_logs_progress_after_30s(
        self, mock_time: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Progress line logged when 30 s pass between batches."""
        # 200 vectors → 2 batches of 100
        # monotonic: 0.0 (init), 5.0 (after batch 1: <30s), 35.0 (after batch 2: ≥30s)
        mock_time.monotonic.side_effect = [0.0, 5.0, 35.0]

        indexer = _make_indexer()
        job = _make_job()

        with caplog.at_level(logging.INFO, logger="krag.orchestration.indexer"):
            indexer._store_routed_vectors({"docs": _make_vectors(200)}, job)

        progress_lines = [r for r in caplog.records if "Storing vectors: " in r.message]
        assert len(progress_lines) == 1
        assert "200/200" in progress_lines[0].message
        assert "100%" in progress_lines[0].message

    @patch("krag.orchestration.indexer.time")
    def test_no_log_when_under_30s(
        self, mock_time: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No periodic log when both batches complete before 30 s."""
        # monotonic: 0.0 (init), 5.0, 10.0 — never reaches 30s gap
        mock_time.monotonic.side_effect = [0.0, 5.0, 10.0]

        indexer = _make_indexer()
        job = _make_job()

        with caplog.at_level(logging.INFO, logger="krag.orchestration.indexer"):
            indexer._store_routed_vectors({"docs": _make_vectors(200)}, job)

        progress_lines = [r for r in caplog.records if "Storing vectors: " in r.message]
        assert len(progress_lines) == 0

    @patch("krag.orchestration.indexer.time")
    def test_multiple_logs_across_multiple_intervals(
        self, mock_time: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """One log per 30 s interval means two logs for a 60 s run."""
        # 300 vectors → 3 batches of 100
        # monotonic: 0.0, 35.0 (log #1), 70.0 (log #2), 99.0 (29s gap < 30, no log)
        mock_time.monotonic.side_effect = [0.0, 35.0, 70.0, 99.0]

        indexer = _make_indexer()
        job = _make_job()

        with caplog.at_level(logging.INFO, logger="krag.orchestration.indexer"):
            indexer._store_routed_vectors({"docs": _make_vectors(300)}, job)

        progress_lines = [r for r in caplog.records if "Storing vectors: " in r.message]
        assert len(progress_lines) == 2

    @patch("krag.orchestration.indexer.time")
    def test_partial_progress_shows_correct_counts(
        self, mock_time: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Mid-run progress message shows accurate stored/total count."""
        # 300 vectors → 3 batches; trigger log after the first batch (100 stored)
        mock_time.monotonic.side_effect = [0.0, 35.0, 40.0, 45.0]

        indexer = _make_indexer()
        job = _make_job()

        with caplog.at_level(logging.INFO, logger="krag.orchestration.indexer"):
            indexer._store_routed_vectors({"docs": _make_vectors(300)}, job)

        progress_lines = [r for r in caplog.records if "Storing vectors: " in r.message]
        assert len(progress_lines) == 1
        # First log fires after batch 1 (100/300)
        assert "100/300" in progress_lines[0].message

    @patch("krag.orchestration.indexer.time")
    def test_progress_resets_last_log_time(
        self, mock_time: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """After logging, the 30 s window resets (no immediate re-log)."""
        # 300 vectors → 3 batches
        # batch 1 at 35s → logs, _last_log set to 35
        # batch 2 at 45s → 45-35=10 < 30, no log
        # batch 3 at 50s → 50-35=15 < 30, no log
        mock_time.monotonic.side_effect = [0.0, 35.0, 45.0, 50.0]

        indexer = _make_indexer()
        job = _make_job()

        with caplog.at_level(logging.INFO, logger="krag.orchestration.indexer"):
            indexer._store_routed_vectors({"docs": _make_vectors(300)}, job)

        progress_lines = [r for r in caplog.records if "Storing vectors: " in r.message]
        assert len(progress_lines) == 1
