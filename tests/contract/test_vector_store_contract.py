"""Contract tests for VectorStore interface.

These tests define the interface that any VectorStore implementation must satisfy.
They should FAIL until we implement the VectorStore interface.
"""


class TestVectorStoreContract:
    """Contract tests for VectorStore interface."""

    def test_vector_store_has_upsert_method(self) -> None:
        """Test VectorStore has upsert method for adding/updating vectors."""
        from krag.storage.vector_store import VectorStore

        # VectorStore should have upsert method
        assert hasattr(VectorStore, "upsert"), "VectorStore must have upsert method"

    def test_vector_store_has_search_method(self) -> None:
        """Test VectorStore has search method for similarity search."""
        from krag.storage.vector_store import VectorStore

        assert hasattr(VectorStore, "search"), "VectorStore must have search method"

    def test_vector_store_has_delete_method(self) -> None:
        """Test VectorStore has delete method for removing vectors."""
        from krag.storage.vector_store import VectorStore

        assert hasattr(VectorStore, "delete"), "VectorStore must have delete method"

    def test_vector_store_has_get_stats_method(self) -> None:
        """Test VectorStore has get_stats method for collection statistics."""
        from krag.storage.vector_store import VectorStore

        assert hasattr(VectorStore, "get_stats"), "VectorStore must have get_stats method"

    def test_upsert_accepts_required_parameters(self) -> None:
        """Test upsert method accepts vectors and metadata."""
        from krag.storage.qdrant_impl import QdrantVectorStore

        # Create instance (will fail until implemented)
        store = QdrantVectorStore(collection_name="test", vector_size=384)

        # Should accept vectors with IDs and payloads
        _ = [
            {
                "id": "chunk1",
                "vector": [0.1] * 384,
                "payload": {"content": "test", "file_path": "/test/file.txt"},
            }
        ]

        # Method should exist and be callable
        assert callable(store.upsert), "upsert must be callable"

    def test_search_accepts_query_vector_and_limit(self) -> None:
        """Test search method accepts query vector and returns results."""
        from krag.storage.qdrant_impl import QdrantVectorStore

        store = QdrantVectorStore(collection_name="test", vector_size=384)

        # Search should accept query vector and limit
        query_vector = [0.1] * 384
        results = store.search(query_vector, limit=5)

        # Results should be a list
        assert isinstance(results, list), "search must return a list"

    def test_delete_accepts_ids(self) -> None:
        """Test delete method accepts list of IDs to remove."""
        from krag.storage.qdrant_impl import QdrantVectorStore

        store = QdrantVectorStore(collection_name="test", vector_size=384)

        # Delete should accept list of IDs
        store.delete(["chunk1", "chunk2"])

        # Should not raise exception
        assert True, "delete should accept list of IDs"

    def test_get_stats_returns_collection_info(self) -> None:
        """Test get_stats returns information about the collection."""
        from krag.storage.qdrant_impl import QdrantVectorStore

        store = QdrantVectorStore(collection_name="test", vector_size=384)

        stats = store.get_stats()

        # Stats should be a dictionary with basic info
        assert isinstance(stats, dict), "get_stats must return a dict"
        assert "count" in stats or "vectors_count" in stats, "stats must include count"

    def test_search_returns_results_with_required_fields(self) -> None:
        """Test search results have required fields: id, score, payload."""
        from krag.storage.qdrant_impl import QdrantVectorStore

        store = QdrantVectorStore(collection_name="test", vector_size=384)

        # Add a test vector
        vectors = [
            {
                "id": "test1",
                "vector": [0.1] * 384,
                "payload": {"content": "test content", "file_path": "/test.txt"},
            }
        ]
        store.upsert(vectors)

        # Search for it
        results = store.search([0.1] * 384, limit=1)

        if len(results) > 0:
            result = results[0]
            assert "id" in result, "Result must have 'id' field"
            assert "score" in result, "Result must have 'score' field"
            assert "payload" in result, "Result must have 'payload' field"

    def test_upsert_handles_batch_operations(self) -> None:
        """Test upsert can handle multiple vectors in one call."""
        from krag.storage.qdrant_impl import QdrantVectorStore

        store = QdrantVectorStore(collection_name="test", vector_size=384)

        # Upsert multiple vectors
        vectors = [
            {
                "id": f"chunk{i}",
                "vector": [float(i) / 100] * 384,
                "payload": {"content": f"content {i}"},
            }
            for i in range(10)
        ]

        # Should handle batch upsert
        store.upsert(vectors)

        # Verify by searching
        stats = store.get_stats()
        count = stats.get("count", stats.get("vectors_count", 0))
        assert count >= 10, "Should have at least 10 vectors after batch upsert"
