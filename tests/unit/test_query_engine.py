"""Unit tests for QueryEngine."""

from unittest.mock import MagicMock

import pytest

from krag.models.query_result import QueryResult
from krag.orchestration.query_engine import QueryEngine, QueryResponse
from krag.synthesis.llm_client import LLMClient
from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
from tests.fixtures.mock_llm import MockLLMClient


@pytest.fixture
def mock_vector_store():
    """Create mock vector store."""
    store = MagicMock()
    # Return empty results by default
    store.search.return_value = []
    return store


@pytest.fixture
def embedding_generator():
    """Create mock embedding generator."""
    return MockEmbeddingGenerator()


@pytest.fixture
def llm_client():
    """Create mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def query_engine(mock_vector_store, embedding_generator, llm_client):
    """Create QueryEngine instance with mocks."""
    return QueryEngine(
        vector_store=mock_vector_store,
        embedding_generator=embedding_generator,
        llm_client=llm_client,
        top_k=3,
    )


def test_query_engine_initialization(mock_vector_store, embedding_generator, llm_client):
    """Test QueryEngine initializes with correct dependencies."""
    engine = QueryEngine(
        vector_store=mock_vector_store,
        embedding_generator=embedding_generator,
        llm_client=llm_client,
        top_k=5,
        max_context_length=2000,
    )

    assert engine.top_k == 5
    assert engine.prompt_builder.max_context_length == 2000
    assert engine.llm_client == llm_client


def test_query_returns_response(query_engine):
    """Test query returns QueryResponse object."""
    response = query_engine.query("test query")

    assert isinstance(response, QueryResponse)
    assert response.query == "test query"
    assert isinstance(response.answer, str)
    assert isinstance(response.sources, list)


def test_query_with_empty_string(query_engine):
    """Test query handles empty string gracefully."""
    response = query_engine.query("")

    assert response.answer == "Please provide a valid question."
    assert response.sources == []
    assert response.query == ""


def test_query_with_whitespace_only(query_engine):
    """Test query handles whitespace-only string."""
    response = query_engine.query("   \n\t  ")

    assert response.answer == "Please provide a valid question."
    assert response.sources == []


def test_query_with_top_k_override(query_engine, mock_vector_store):
    """Test query respects top_k override parameter (with over-fetch for dedup)."""
    from krag.retrieval.retriever import Retriever

    query_engine.query("test query", top_k=10)

    # Retriever over-fetches by _OVERFETCH_FACTOR for dedup headroom
    mock_vector_store.search.assert_called_once()
    call_args = mock_vector_store.search.call_args
    expected = 10 * Retriever._OVERFETCH_FACTOR
    assert call_args[1]["limit"] == expected


def test_query_uses_default_top_k(query_engine, mock_vector_store):
    """Test query uses default top_k when not overridden (with over-fetch for dedup)."""
    from krag.retrieval.retriever import Retriever

    query_engine.query("test query")

    # Should use default top_k=3 * over-fetch factor
    mock_vector_store.search.assert_called_once()
    call_args = mock_vector_store.search.call_args
    expected = 3 * Retriever._OVERFETCH_FACTOR
    assert call_args[1]["limit"] == expected


def test_query_with_no_results(query_engine, mock_vector_store):
    """Test query handles case with no search results."""
    mock_vector_store.search.return_value = []

    response = query_engine.query("test query")

    assert isinstance(response, QueryResponse)
    assert len(response.sources) == 0
    # Should still generate an answer (explaining no context found)
    assert len(response.answer) > 0


def test_query_with_multiple_results(query_engine, mock_vector_store):
    """Test query handles multiple search results."""
    from pathlib import Path

    # Mock search results
    mock_vector_store.search.return_value = [
        {
            "id": "chunk1",
            "payload": {
                "file_path": str(Path("/test/file1.txt")),
                "content": "Content 1",
                "chunk_index": 0,
                "file_type": "text",
            },
            "score": 0.95,
        },
        {
            "id": "chunk2",
            "payload": {
                "file_path": str(Path("/test/file2.txt")),
                "content": "Content 2",
                "chunk_index": 0,
                "file_type": "text",
            },
            "score": 0.85,
        },
    ]

    response = query_engine.query("test query")

    assert len(response.sources) == 2
    assert response.sources[0].file_path == Path("/test/file1.txt")
    assert response.sources[1].file_path == Path("/test/file2.txt")


def test_query_calls_llm_with_context(query_engine, mock_vector_store):
    """Test query passes context to LLM client."""
    from pathlib import Path

    mock_vector_store.search.return_value = [
        {
            "id": "chunk1",
            "payload": {
                "file_path": str(Path("/test/file.txt")),
                "content": "Test content",
                "chunk_index": 0,
                "file_type": "text",
            },
            "score": 0.95,
        }
    ]

    # Use a mock LLM that we can track calls on
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.generate.return_value = "Test answer"
    query_engine.llm_client = mock_llm

    query_engine.query("test query")

    # Verify LLM was called with chat messages
    mock_llm.generate.assert_called_once()
    call_args = mock_llm.generate.call_args
    messages = call_args.kwargs.get("messages", call_args[0][0] if call_args[0] else None)
    assert isinstance(messages, list), "generate should receive a messages list"
    # User message should contain the chunk content and the query
    user_content = messages[1]["content"]
    assert "Test content" in user_content
    assert "test query" in user_content


def test_query_response_contains_sources(query_engine, mock_vector_store):
    """Test QueryResponse includes source information."""
    from pathlib import Path

    mock_vector_store.search.return_value = [
        {
            "id": "chunk1",
            "payload": {
                "file_path": str(Path("/test/source.md")),
                "content": "Source content",
                "chunk_index": 0,
                "file_type": "markdown",
            },
            "score": 0.92,
        }
    ]

    response = query_engine.query("test query")

    assert len(response.sources) == 1
    assert isinstance(response.sources[0], QueryResult)
    assert response.sources[0].chunk_content == "Source content"
    assert response.sources[0].score == 0.92
