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


class TestQueryPipelineDiagnosticLogging:
    """Integration tests for DEBUG-level diagnostic logging (US5)."""

    def _make_engine(self, similarity_threshold: float | None = None):
        """Create a QueryEngine with mock components."""
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def search(self, vector, limit=5):
                return [
                    {
                        "id": f"chunk{i}",
                        "score": score,
                        "payload": {
                            "content": f"Content for chunk {i}.",
                            "file_path": f"/test/doc{i}.md",
                            "chunk_index": 0,
                            "file_type": "markdown",
                        },
                    }
                    for i, score in enumerate([0.95, 0.7, 0.3], start=1)
                ]

        return QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
            similarity_threshold=similarity_threshold,
        )

    def test_debug_log_contains_chunk_scores(self, caplog) -> None:
        """Test that DEBUG log includes retrieved chunk scores."""
        import logging

        engine = self._make_engine()

        with caplog.at_level(logging.DEBUG):
            engine.query("Test query")

        log_text = caplog.text
        # Should log about retrieval
        assert "retriev" in log_text.lower(), "Should log retrieval activity"

    def test_debug_log_contains_threshold_filtering(self, caplog) -> None:
        """Test that INFO log shows threshold filtering when threshold is set."""
        import logging

        engine = self._make_engine(similarity_threshold=0.5)

        with caplog.at_level(logging.DEBUG):
            engine.query("Test query")

        log_text = caplog.text
        # Should mention threshold filtering
        assert "threshold" in log_text.lower() or "kept" in log_text.lower(), (
            "Should log threshold filtering"
        )

    def test_debug_log_contains_prompt_info(self, caplog) -> None:
        """Test that DEBUG log includes prompt building information."""
        import logging

        engine = self._make_engine()

        with caplog.at_level(logging.DEBUG):
            engine.query("Test query")

        log_text = caplog.text
        assert "prompt" in log_text.lower() or "messages" in log_text.lower(), (
            "Should log prompt building"
        )

    def test_debug_log_contains_generation_summary(self, caplog) -> None:
        """Test that log includes generation duration/length information."""
        import logging

        engine = self._make_engine()

        with caplog.at_level(logging.DEBUG):
            engine.query("Test query")

        log_text = caplog.text
        # Should log generation results
        assert "characters" in log_text.lower() or "generat" in log_text.lower(), (
            "Should log generation summary"
        )
