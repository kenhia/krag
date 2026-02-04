"""Contract tests for Retriever interface.

These tests define the expected behavior of any Retriever implementation.
They should FAIL until we implement the actual Retriever class.
"""

from krag.models.query_result import QueryResult


class TestRetrieverContract:
    """Contract tests for Retriever implementations."""

    def test_retriever_has_retrieve_method(self) -> None:
        """Test that Retriever has a retrieve method."""
        # This will fail until we implement Retriever
        from krag.retrieval.retriever import Retriever

        assert hasattr(Retriever, "retrieve"), "Retriever must have retrieve method"

    def test_retrieve_accepts_query_string(self) -> None:
        """Test that retrieve method accepts query string."""
        from krag.retrieval.retriever import Retriever

        # Mock vector store for testing
        class MockVectorStore:
            def search(self, vector, limit=5):
                return []

        # Mock embedding generator
        class MockEmbedding:
            def generate_single(self, text):
                return [0.1] * 384

        retriever = Retriever(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbedding(),
        )

        # Should accept string query
        results = retriever.retrieve("test query", top_k=5)
        assert isinstance(results, list), "retrieve must return a list"

    def test_retrieve_returns_query_results(self) -> None:
        """Test that retrieve returns list of QueryResult objects."""
        from krag.retrieval.retriever import Retriever

        class MockVectorStore:
            def search(self, vector, limit=5):
                return [
                    {
                        "id": "chunk1",
                        "score": 0.95,
                        "payload": {
                            "content": "test content",
                            "file_path": "/test/file.txt",
                            "chunk_index": 0,
                            "file_type": "text",
                        },
                    }
                ]

        class MockEmbedding:
            def generate_single(self, text):
                return [0.1] * 384

        retriever = Retriever(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbedding(),
        )

        results = retriever.retrieve("test query", top_k=5)
        assert len(results) > 0, "Should return results"
        assert isinstance(results[0], QueryResult), "Results must be QueryResult objects"

    def test_retrieve_respects_top_k_parameter(self) -> None:
        """Test that retrieve respects the top_k parameter."""
        from krag.retrieval.retriever import Retriever

        class MockVectorStore:
            def __init__(self):
                self.last_limit = None

            def search(self, vector, limit=5):
                self.last_limit = limit
                return []

        class MockEmbedding:
            def generate_single(self, text):
                return [0.1] * 384

        mock_store = MockVectorStore()
        retriever = Retriever(
            vector_store=mock_store,
            embedding_generator=MockEmbedding(),
        )

        retriever.retrieve("test", top_k=10)
        assert mock_store.last_limit == 10, "Should pass top_k to vector store"

    def test_retrieve_handles_empty_results(self) -> None:
        """Test that retrieve handles empty results gracefully."""
        from krag.retrieval.retriever import Retriever

        class MockVectorStore:
            def search(self, vector, limit=5):
                return []

        class MockEmbedding:
            def generate_single(self, text):
                return [0.1] * 384

        retriever = Retriever(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbedding(),
        )

        results = retriever.retrieve("test query")
        assert isinstance(results, list), "Should return empty list"
        assert len(results) == 0, "Should return empty list for no results"
