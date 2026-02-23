"""Unit tests for KragService lifecycle (init, start, shutdown, started-guard).

T007: Tests written before implementation (TDD Red phase).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from krag.models.configuration import Configuration


def _make_config() -> Configuration:
    """Create a minimal Configuration for testing."""
    return Configuration(directory_paths=[Path("/test/path").absolute()])


class TestKragServiceInit:
    """Test KragService initialization."""

    def test_init_accepts_config(self) -> None:
        """KragService accepts a Configuration object."""
        from kragd.service import KragService

        config = _make_config()
        service = KragService(config)
        assert service.config is config

    def test_init_not_started(self) -> None:
        """Service is not started after construction."""
        from kragd.service import KragService

        service = KragService(_make_config())
        assert service._started is False


class TestKragServiceStartedGuard:
    """Test that methods raise before start() is called."""

    def test_query_before_start_raises(self) -> None:
        """Calling query() before start() raises RuntimeError."""
        from kragd.schemas import QueryRequest
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(RuntimeError, match="not started"):
            service.query(QueryRequest(query="test"))

    def test_retrieve_before_start_raises(self) -> None:
        """Calling retrieve() before start() raises RuntimeError."""
        from kragd.schemas import RetrieveRequest
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(RuntimeError, match="not started"):
            service.retrieve(RetrieveRequest(query="test"))

    def test_get_status_before_start_raises(self) -> None:
        """Calling get_status() before start() raises RuntimeError."""
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(RuntimeError, match="not started"):
            service.get_status()

    def test_get_health_before_start_raises(self) -> None:
        """Calling get_health() before start() raises RuntimeError."""
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(RuntimeError, match="not started"):
            service.get_health()


class TestKragServiceStartShutdown:
    """Test start/shutdown lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_started_flag(self) -> None:
        """start() sets _started to True."""
        from kragd.service import KragService

        service = KragService(_make_config())
        with (
            patch.object(service, "_init_embeddings"),
            patch.object(service, "_init_vector_store"),
            patch.object(service, "_init_collection_manager"),
            patch.object(service, "_init_llm_pool"),
            patch.object(service, "_init_query_engine"),
        ):
            await service.start()
            assert service._started is True

    @pytest.mark.asyncio
    async def test_shutdown_clears_started_flag(self) -> None:
        """shutdown() sets _started to False."""
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = True
        service.llm_pool = MagicMock()
        service.llm_pool.close = MagicMock()
        service.vector_store = MagicMock()
        service.vector_store.close = MagicMock()

        await service.shutdown()
        assert service._started is False

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self) -> None:
        """shutdown() can be called multiple times safely."""
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = False
        # Should not raise
        await service.shutdown()
        await service.shutdown()

    @pytest.mark.asyncio
    async def test_start_records_start_time(self) -> None:
        """start() records the service start time."""
        from kragd.service import KragService

        service = KragService(_make_config())
        with (
            patch.object(service, "_init_embeddings"),
            patch.object(service, "_init_vector_store"),
            patch.object(service, "_init_collection_manager"),
            patch.object(service, "_init_llm_pool"),
            patch.object(service, "_init_query_engine"),
        ):
            await service.start()
            assert service._start_time is not None

    @pytest.mark.asyncio
    async def test_shutdown_closes_llm_pool(self) -> None:
        """shutdown() calls pool.close()."""
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = True
        mock_pool = MagicMock()
        service.llm_pool = mock_pool
        service.vector_store = MagicMock()

        await service.shutdown()
        mock_pool.close.assert_called_once()
