"""Unit tests for index-status accuracy (US2).

T021: Validates that:
- get_index_status() always returns list[IndexResponse]
- get_index_status() returns 'running' status when indexing is active,
  even if there are cached results from a prior run
- get_index_status() returns cached results when NOT indexing
- get_index_status() returns empty list when cache is empty and not indexing
"""

from __future__ import annotations

from pathlib import Path


def _make_config():
    """Create a minimal Configuration for testing."""
    from krag.models.configuration import Configuration

    return Configuration(directory_paths=[Path("/test/path").absolute()])


def _make_index_response(**overrides):
    """Create a mock IndexResponse."""
    from kragd.schemas import IndexResponse

    defaults = {
        "job_id": "test-job",
        "status": "completed",
        "mode": "full",
        "files_scanned": 10,
        "files_processed": 8,
        "files_skipped": 0,
        "files_skipped_unchanged": 0,
        "files_skipped_other": 2,
        "files_errored": 0,
        "chunks_created": 50,
        "vectors_stored": 50,
        "duration_seconds": 5.0,
        "dry_run": False,
        "errors": [],
    }
    defaults.update(overrides)
    return IndexResponse(**defaults)


class TestIndexStatusRunningPriority:
    """Active indexing must take priority over cached results."""

    def test_returns_running_when_indexing_active_and_cache_empty(self) -> None:
        """When _indexing=True and cache is empty, returns single-element list with running status."""
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = True
        service._indexing = True
        service._index_job_cache = []

        result = service.get_index_status()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].status == "running"

    def test_returns_running_when_indexing_active_and_cache_has_results(self) -> None:
        """When _indexing=True and cache has previous results, returns running status.

        This is the core US2 bug fix: previously, cached results were returned
        even while a new indexing run was in progress.
        """
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = True
        service._indexing = True
        service._index_job_cache = [_make_index_response(job_id="old-job", status="completed")]

        result = service.get_index_status()
        assert isinstance(result, list)
        assert len(result) == 1
        # Must be the running status, NOT the cached completed result
        assert result[0].status == "running"
        assert result[0].job_id != "old-job"

    def test_returns_cached_when_not_indexing(self) -> None:
        """When _indexing=False and cache has results, returns cached results as list."""
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = True
        service._indexing = False
        service._index_job_cache = [_make_index_response(job_id="completed-job")]

        result = service.get_index_status()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].job_id == "completed-job"

    def test_returns_none_when_not_indexing_and_cache_empty(self) -> None:
        """When _indexing=False and cache is empty, returns empty list."""
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = True
        service._indexing = False
        service._index_job_cache = []

        result = service.get_index_status()
        assert isinstance(result, list)
        assert len(result) == 0
