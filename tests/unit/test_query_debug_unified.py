"""Unit tests for unified query / debug-query code path (US3).

T034: Validates that query(include_debug=True) produces the same answer and
sources as debug_query(), and that debug_query() is a thin wrapper around
query().
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from krag.models.configuration import Configuration


def _make_config() -> Configuration:
    return Configuration(directory_paths=[Path("/test/path").absolute()])


def _make_started_service() -> MagicMock:
    """Create a started KragService with mocked internals."""
    from kragd.service import KragService

    service = KragService(_make_config())
    service._started = True
    service._indexing = False

    # Mock query engine
    service.query_engine = MagicMock()
    service.query_engine.prompt_builder = MagicMock()
    service.query_engine.prompt_builder.build.return_value = [{"role": "user", "content": "test"}]

    # Mock LLM pool with route_and_generate
    mock_llm_client = MagicMock()
    service.llm_pool = MagicMock()
    slot = MagicMock()
    slot.instance = mock_llm_client
    slot.is_loaded = True
    slot.model_path = "/models/text.gguf"
    service.llm_pool._slot_for.return_value = slot
    service.llm_pool.route_and_generate.return_value = ("Answer text", "text")

    # Mock vector store and embeddings
    service.vector_store = MagicMock()
    service.embedding_generator = MagicMock()
    service.embedding_orchestrator = MagicMock()
    service.embedding_orchestrator._model_names = {"default": "test-model"}
    service.collection_manager = MagicMock()
    service.lexicon_store = None
    service.lifecycle_manager = None
    service.mode_registry = None

    return service


class TestUnifiedQueryPath:
    """Verify query() and debug_query() use the same code path."""

    @patch("krag.retrieval.retriever.Retriever")
    def test_query_without_debug_returns_none_debug(self, MockRetriever: MagicMock) -> None:
        """query(include_debug=False) returns debug=None."""
        from kragd.schemas import QueryRequest

        service = _make_started_service()

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []
        mock_retriever._last_total_before_dedup = 0
        mock_retriever._last_per_space_counts = None
        MockRetriever.return_value = mock_retriever

        request = QueryRequest(query="test query", include_debug=False)
        result = service.query(request)

        assert result.debug is None

    @patch("krag.retrieval.retriever.Retriever")
    def test_query_with_debug_populates_debug_metadata(self, MockRetriever: MagicMock) -> None:
        """query(include_debug=True) populates debug with timing and routing info."""
        from kragd.schemas import QueryRequest

        service = _make_started_service()

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []
        mock_retriever._last_total_before_dedup = 0
        mock_retriever._last_per_space_counts = None
        MockRetriever.return_value = mock_retriever

        request = QueryRequest(query="test query", include_debug=True)
        result = service.query(request)

        assert result.debug is not None
        assert result.debug.retrieval_time_ms >= 0
        assert result.debug.generation_time_ms >= 0
        assert result.debug.llm_used == "text"

    @patch("krag.retrieval.retriever.Retriever")
    def test_query_and_debug_query_produce_identical_answer(self, MockRetriever: MagicMock) -> None:
        """query(include_debug=True) and debug_query() produce the same answer."""
        from kragd.schemas import DebugQueryRequest, QueryRequest

        service = _make_started_service()

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []
        mock_retriever._last_total_before_dedup = 0
        mock_retriever._last_per_space_counts = None
        MockRetriever.return_value = mock_retriever

        query_result = service.query(QueryRequest(query="test query", include_debug=True))
        debug_result = service.debug_query(DebugQueryRequest(query="test query"))

        assert query_result.answer == debug_result.answer

    @patch("krag.retrieval.retriever.Retriever")
    def test_debug_query_delegates_to_query(self, MockRetriever: MagicMock) -> None:
        """debug_query() internally calls self.query() — thin wrapper."""
        from kragd.schemas import DebugQueryRequest

        service = _make_started_service()

        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []
        mock_retriever._last_total_before_dedup = 0
        mock_retriever._last_per_space_counts = None
        MockRetriever.return_value = mock_retriever

        with patch.object(service, "query", wraps=service.query) as mock_query:
            service.debug_query(DebugQueryRequest(query="wrapped call"))
            mock_query.assert_called_once()
            # The call should have include_debug=True
            call_args = mock_query.call_args
            assert call_args[0][0].include_debug is True
