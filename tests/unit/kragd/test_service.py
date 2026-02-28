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
        """Calling query() before start() raises ServiceNotReadyError."""
        from krag.models.exceptions import ServiceNotReadyError
        from kragd.schemas import QueryRequest
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(ServiceNotReadyError, match="not started"):
            service.query(QueryRequest(query="test"))

    def test_retrieve_before_start_raises(self) -> None:
        """Calling retrieve() before start() raises ServiceNotReadyError."""
        from krag.models.exceptions import ServiceNotReadyError
        from kragd.schemas import RetrieveRequest
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(ServiceNotReadyError, match="not started"):
            service.retrieve(RetrieveRequest(query="test"))

    def test_get_status_before_start_raises(self) -> None:
        """Calling get_status() before start() raises ServiceNotReadyError."""
        from krag.models.exceptions import ServiceNotReadyError
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(ServiceNotReadyError, match="not started"):
            service.get_status()

    def test_get_health_before_start_raises(self) -> None:
        """Calling get_health() before start() raises ServiceNotReadyError."""
        from krag.models.exceptions import ServiceNotReadyError
        from kragd.service import KragService

        service = KragService(_make_config())
        with pytest.raises(ServiceNotReadyError, match="not started"):
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


class TestDebugQueryCritic:
    """Test that debug_query correctly invokes the relevance critic."""

    def _make_started_service(self):
        """Create a KragService with enough mocks to call debug_query."""
        from kragd.service import KragService

        service = KragService(_make_config())
        service._started = True
        service._indexing = False

        # Mock query engine
        service.query_engine = MagicMock()

        # Mock LLM pool — _slot_for(slot).instance provides the critic LLM
        mock_llm_client = MagicMock()
        mock_pool = MagicMock()
        mock_slot = MagicMock()
        mock_slot.instance = mock_llm_client
        mock_slot.model_path = "/fake/model.gguf"
        mock_pool._slot_for.return_value = mock_slot
        mock_pool.route_and_generate.return_value = ("test answer", "text")
        service.llm_pool = mock_pool

        # Mock retriever results
        mock_result = MagicMock()
        mock_result.chunk_id = "chunk-1"
        mock_result.file_path = "/test/file.py"
        mock_result.score = 0.9
        mock_result.chunk_content = "def hello(): pass  # some code content that is long enough"
        mock_result.file_type = "python"
        mock_result.collection = "code"
        mock_result.critic_score = 4
        mock_result.language = "python"
        mock_result.function_name = "hello"
        mock_result.class_name = None
        mock_result.start_line = 1
        mock_result.end_line = 1

        # Mock embedding/vector/collection components
        service.vector_store = MagicMock()
        service.embedding_generator = MagicMock()
        service.embedding_orchestrator = MagicMock()
        service.collection_manager = MagicMock()
        service.lexicon_store = None
        service.lifecycle_manager = None

        # Mock mode registry to return a mode with critic enabled
        from krag.models.configuration import ModeConfiguration

        mode_config = ModeConfiguration(
            name="test-critic",
            critic_enabled=True,
            critic_threshold=3,
            top_k=5,
        )
        service.mode_registry = MagicMock()
        service.mode_registry.get.return_value = mode_config

        return service, mock_result, mock_llm_client

    @patch("krag.retrieval.retriever.Retriever")
    def test_debug_query_with_critic_uses_active_slot(self, MockRetriever: MagicMock) -> None:
        """debug_query with critic_enabled uses the active LLM slot for critic scoring."""
        from kragd.schemas import DebugQueryRequest

        service, mock_result, mock_llm_client = self._make_started_service()

        # Configure mock retriever
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = [mock_result]
        mock_retriever_instance._last_total_before_dedup = 1
        MockRetriever.return_value = mock_retriever_instance

        # Mock the critic to pass chunks through
        with patch("krag.critic.relevance_critic.RelevanceCritic") as MockCritic:
            mock_critic = MagicMock()
            scored_chunk = MagicMock()
            scored_chunk.critic_score = 4
            scored_chunk.chunk = mock_result
            scored_chunk.passed = True
            mock_critic.score_chunks.return_value = [scored_chunk]
            mock_critic.filter_chunks.return_value = [mock_result]
            MockCritic.return_value = mock_critic

            # Mock query engine for synthesis phase
            synth_result = MagicMock()
            synth_result.answer = "test answer"
            synth_result.sources = []
            service.query_engine.query_with_chunks.return_value = synth_result

            request = DebugQueryRequest(query="test query", mode="test-critic")
            service.debug_query(request)

            # Verify critic was created with the active slot's LLM instance
            MockCritic.assert_called_once_with(
                llm_client=mock_llm_client,
                threshold=3,
                enabled=True,
            )

    @patch("krag.retrieval.retriever.Retriever")
    def test_debug_query_critic_uses_code_slot_when_mode_says_code(
        self, MockRetriever: MagicMock
    ) -> None:
        """When mode.llm_slot='code', critic uses the code LLM (not text)."""
        from krag.models.configuration import ModeConfiguration
        from kragd.schemas import DebugQueryRequest

        service, mock_result, mock_llm_client = self._make_started_service()

        # Override mode to have llm_slot="code" + critic enabled
        mode_config = ModeConfiguration(
            name="code-critic",
            llm_slot="code",
            critic_enabled=True,
            critic_threshold=3,
            top_k=5,
        )
        service.mode_registry.get.return_value = mode_config

        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = [mock_result]
        mock_retriever_instance._last_total_before_dedup = 1
        MockRetriever.return_value = mock_retriever_instance

        with patch("krag.critic.relevance_critic.RelevanceCritic") as MockCritic:
            mock_critic = MagicMock()
            scored_chunk = MagicMock()
            scored_chunk.critic_score = 4
            scored_chunk.chunk = mock_result
            scored_chunk.passed = True
            mock_critic.score_chunks.return_value = [scored_chunk]
            mock_critic.filter_chunks.return_value = [mock_result]
            MockCritic.return_value = mock_critic

            request = DebugQueryRequest(query="test query", mode="code-critic")
            service.debug_query(request)

            # _slot_for should have been called with "code"
            service.llm_pool._slot_for.assert_any_call("code")
            MockCritic.assert_called_once_with(
                llm_client=mock_llm_client,
                threshold=3,
                enabled=True,
            )

    @patch("krag.retrieval.retriever.Retriever")
    def test_debug_query_without_critic_skips_scoring(self, MockRetriever: MagicMock) -> None:
        """debug_query without critic_enabled does not instantiate RelevanceCritic."""
        from krag.models.configuration import ModeConfiguration
        from kragd.schemas import DebugQueryRequest

        service, mock_result, _ = self._make_started_service()

        # Override mode to have critic disabled
        mode_config = ModeConfiguration(
            name="test-no-critic",
            critic_enabled=False,
            top_k=5,
        )
        service.mode_registry.get.return_value = mode_config

        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = [mock_result]
        mock_retriever_instance._last_total_before_dedup = 1
        MockRetriever.return_value = mock_retriever_instance

        synth_result = MagicMock()
        synth_result.answer = "test answer"
        synth_result.sources = []
        service.query_engine.query_with_chunks.return_value = synth_result

        with patch("krag.critic.relevance_critic.RelevanceCritic") as MockCritic:
            request = DebugQueryRequest(query="test query", mode="test-no-critic")
            service.debug_query(request)

            MockCritic.assert_not_called()
