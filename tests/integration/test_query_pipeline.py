"""Integration test for query pipeline.

This tests the complete query flow from user query to synthesized answer.
Should FAIL until we implement all components.
"""

from pathlib import Path

from krag.models.query_result import QueryResult


class TestQueryPipeline:
    """Integration tests for end-to-end query pipeline."""

    def test_query_pipeline_with_mocks(self) -> None:
        """Test complete query pipeline with mock components."""
        # This will fail until we implement QueryEngine
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        # Mock vector store with test data
        class MockVectorStore:
            def search(self, vector, limit=5):
                return [
                    {
                        "id": "chunk1",
                        "score": 0.95,
                        "payload": {
                            "content": "RAG combines retrieval with generation.",
                            "file_path": "/test/doc.md",
                            "chunk_index": 0,
                            "file_type": "markdown",
                        },
                    },
                    {
                        "id": "chunk2",
                        "score": 0.85,
                        "payload": {
                            "content": "Vector stores maintain embeddings.",
                            "file_path": "/test/doc2.md",
                            "chunk_index": 0,
                            "file_type": "markdown",
                        },
                    },
                ]

        # Create query engine with mocks
        engine = QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
        )

        # Execute query
        response = engine.query("What is RAG?")

        # Verify response structure
        assert hasattr(response, "answer"), "Response should have answer"
        assert hasattr(response, "sources"), "Response should have sources"
        assert isinstance(response.answer, str), "Answer should be string"
        assert len(response.answer) > 0, "Answer should not be empty"
        assert isinstance(response.sources, list), "Sources should be list"

    def test_query_pipeline_handles_no_results(self) -> None:
        """Test pipeline when no relevant results are found."""
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def search(self, vector, limit=5):
                return []  # No results

        engine = QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
        )

        response = engine.query("Nonexistent topic")

        # Should still return a response
        assert hasattr(response, "answer"), "Should have answer even with no results"
        assert "context" in response.answer.lower() or "don't" in response.answer.lower(), (
            "Should indicate no context available"
        )

    def test_query_pipeline_returns_sources(self) -> None:
        """Test that pipeline returns source information."""
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def search(self, vector, limit=5):
                return [
                    {
                        "id": "chunk1",
                        "score": 0.95,
                        "payload": {
                            "content": "Test content",
                            "file_path": "/test/file.txt",
                            "chunk_index": 0,
                            "file_type": "text",
                        },
                    }
                ]

        engine = QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
        )

        response = engine.query("test")

        # Verify sources are populated
        assert len(response.sources) > 0, "Should return sources"
        source = response.sources[0]
        assert isinstance(source, QueryResult), "Sources should be QueryResult objects"
        assert source.file_path == Path("/test/file.txt"), "Should have correct file path"

    def test_query_pipeline_respects_top_k(self) -> None:
        """Test that pipeline respects top_k parameter."""
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def __init__(self):
                self.last_limit = None

            def search(self, vector, limit=5):
                self.last_limit = limit
                return []

        mock_store = MockVectorStore()
        engine = QueryEngine(
            vector_store=mock_store,
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
            top_k=10,
        )

        engine.query("test")
        assert mock_store.last_limit == 10, "Should use configured top_k"
