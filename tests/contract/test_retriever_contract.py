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
        """Test that retrieve over-fetches for dedup then trims to top_k."""
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
        # The retriever over-fetches by _OVERFETCH_FACTOR to allow dedup
        expected = 10 * Retriever._OVERFETCH_FACTOR
        assert mock_store.last_limit == expected, (
            f"Should over-fetch {Retriever._OVERFETCH_FACTOR}x top_k "
            f"(expected {expected}, got {mock_store.last_limit})"
        )

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


class TestRetrieverSimilarityThreshold:
    """Contract tests for Retriever similarity_threshold filtering."""

    def _make_mock_store(self, results: list[dict]) -> object:
        """Create a mock vector store returning the given results."""

        class MockVectorStore:
            def __init__(self, data: list[dict]) -> None:
                self.data = data

            def search(self, vector: list[float], limit: int = 5) -> list[dict]:
                return self.data

        return MockVectorStore(results)

    def _make_mock_embedding(self) -> object:
        class MockEmbedding:
            def generate_single(self, text: str) -> list[float]:
                return [0.1] * 384

        return MockEmbedding()

    def _sample_results(self) -> list[dict]:
        """Return sample vector store results with diverse scores."""
        return [
            {
                "id": f"chunk{i}",
                "score": score,
                "payload": {
                    "content": f"Content at score {score}",
                    "file_path": f"/test/doc{i}.md",
                    "chunk_index": 0,
                    "file_type": "markdown",
                },
            }
            for i, score in enumerate([0.95, 0.7, 0.4, 0.2, 0.05])
        ]

    def test_threshold_filters_low_scoring_results(self) -> None:
        """Test that similarity_threshold removes results below it."""
        from krag.retrieval.retriever import Retriever

        retriever = Retriever(
            vector_store=self._make_mock_store(self._sample_results()),
            embedding_generator=self._make_mock_embedding(),
        )

        results = retriever.retrieve("test query", top_k=5, similarity_threshold=0.5)
        assert len(results) == 2, "Only scores 0.95 and 0.7 should pass threshold 0.5"
        assert all(r.score >= 0.5 for r in results)

    def test_threshold_zero_returns_all(self) -> None:
        """Test that threshold=0.0 keeps all results."""
        from krag.retrieval.retriever import Retriever

        retriever = Retriever(
            vector_store=self._make_mock_store(self._sample_results()),
            embedding_generator=self._make_mock_embedding(),
        )

        results = retriever.retrieve("test query", top_k=5, similarity_threshold=0.0)
        assert len(results) == 5, "threshold=0.0 should keep everything"

    def test_threshold_returns_empty_when_all_below(self) -> None:
        """Test that all results filtered returns empty list."""
        from krag.retrieval.retriever import Retriever

        retriever = Retriever(
            vector_store=self._make_mock_store(self._sample_results()),
            embedding_generator=self._make_mock_embedding(),
        )

        results = retriever.retrieve("test query", top_k=5, similarity_threshold=0.99)
        assert len(results) == 0, "No results should pass threshold 0.99"

    def test_threshold_preserves_score_ordering(self) -> None:
        """Test that filtered results maintain descending score order."""
        from krag.retrieval.retriever import Retriever

        retriever = Retriever(
            vector_store=self._make_mock_store(self._sample_results()),
            embedding_generator=self._make_mock_embedding(),
        )

        results = retriever.retrieve("test query", top_k=5, similarity_threshold=0.3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be in descending score order"

    def test_threshold_none_returns_all(self) -> None:
        """Test that no threshold (None) returns all results unchanged."""
        from krag.retrieval.retriever import Retriever

        retriever = Retriever(
            vector_store=self._make_mock_store(self._sample_results()),
            embedding_generator=self._make_mock_embedding(),
        )

        results = retriever.retrieve("test query", top_k=5)
        assert len(results) == 5, "No threshold should return all results"

    def test_threshold_logs_filtering_summary(self, caplog: object) -> None:
        """Test that filtering logs an INFO-level summary."""
        import logging

        from krag.retrieval.retriever import Retriever

        retriever = Retriever(
            vector_store=self._make_mock_store(self._sample_results()),
            embedding_generator=self._make_mock_embedding(),
        )

        with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
            retriever.retrieve("test query", top_k=5, similarity_threshold=0.5)

        # Should log something mentioning the filtering outcome
        log_text = caplog.text  # type: ignore[union-attr]
        assert "kept" in log_text.lower() or "threshold" in log_text.lower(), (
            "Should log filtering summary at INFO level"
        )
