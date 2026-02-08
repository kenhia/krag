"""Contract tests for EmbeddingGenerator interface.

These tests define the interface for embedding generation.
They should FAIL until we implement the EmbeddingGenerator.
"""


class TestEmbeddingGeneratorContract:
    """Contract tests for EmbeddingGenerator interface."""

    def test_embedding_generator_has_generate_single_method(self) -> None:
        """Test EmbeddingGenerator has generate_single method."""
        from krag.embeddings.generator import EmbeddingGenerator

        # Should have generate_single method for single text
        assert hasattr(EmbeddingGenerator, "generate_single"), (
            "EmbeddingGenerator must have generate_single method"
        )

    def test_embedding_generator_has_generate_batch_method(self) -> None:
        """Test EmbeddingGenerator has generate_batch method."""
        from krag.embeddings.generator import EmbeddingGenerator

        assert hasattr(EmbeddingGenerator, "generate_batch"), (
            "EmbeddingGenerator must have generate_batch method"
        )

    def test_generate_single_returns_vector(self) -> None:
        """Test generate_single returns a vector embedding."""
        from krag.embeddings.generator import EmbeddingGenerator

        generator = EmbeddingGenerator()

        # Generate embedding for text
        embedding = generator.generate_single("test text")

        # Should return a list/array of floats
        assert isinstance(embedding, (list, tuple)), "Embedding must be a sequence"
        assert len(embedding) > 0, "Embedding must not be empty"
        assert all(isinstance(x, (int, float)) for x in embedding), (
            "Embedding values must be numeric"
        )

    def test_generate_single_consistent_dimension(self) -> None:
        """Test generate_single returns consistent vector dimensions."""
        from krag.embeddings.generator import EmbeddingGenerator

        generator = EmbeddingGenerator()

        # Generate multiple embeddings
        emb1 = generator.generate_single("first text")
        emb2 = generator.generate_single("second text")

        # Dimensions should be consistent
        assert len(emb1) == len(emb2), "All embeddings must have same dimension"

    def test_generate_batch_returns_list_of_vectors(self) -> None:
        """Test generate_batch returns list of embeddings."""
        from krag.embeddings.generator import EmbeddingGenerator

        generator = EmbeddingGenerator()

        texts = ["text one", "text two", "text three"]
        embeddings = generator.generate_batch(texts)

        # Should return list of embeddings
        assert isinstance(embeddings, list), "generate_batch must return a list"
        assert len(embeddings) == len(texts), "Should return one embedding per text"

    def test_generate_batch_all_same_dimension(self) -> None:
        """Test generate_batch returns embeddings with consistent dimensions."""
        from krag.embeddings.generator import EmbeddingGenerator

        generator = EmbeddingGenerator()

        texts = ["text one", "text two", "text three"]
        embeddings = generator.generate_batch(texts)

        # All should have same dimension
        first_dim = len(embeddings[0])
        assert all(len(emb) == first_dim for emb in embeddings), (
            "All batch embeddings must have same dimension"
        )

    def test_embedding_generator_accepts_model_name(self) -> None:
        """Test EmbeddingGenerator can be initialized with model name."""
        from krag.embeddings.generator import EmbeddingGenerator

        # Should accept model parameter
        generator = EmbeddingGenerator(model_name="all-MiniLM-L6-v2")

        # Should still work
        embedding = generator.generate_single("test")
        assert len(embedding) > 0, "Should generate embeddings with custom model"

    def test_embedding_generator_accepts_device(self) -> None:
        """Test EmbeddingGenerator can be initialized with device."""
        from krag.embeddings.generator import EmbeddingGenerator

        # Should accept device parameter (cpu, cuda, mps)
        generator = EmbeddingGenerator(device="cpu")

        # Should work on specified device
        embedding = generator.generate_single("test")
        assert len(embedding) > 0, "Should generate embeddings on specified device"

    def test_generate_handles_empty_string(self) -> None:
        """Test generate_single handles empty string gracefully."""
        from krag.embeddings.generator import EmbeddingGenerator

        generator = EmbeddingGenerator()

        # Should handle empty string without crashing
        embedding = generator.generate_single("")

        # Should still return a valid embedding (possibly zero vector)
        assert isinstance(embedding, (list, tuple)), "Should return embedding for empty string"
        assert len(embedding) > 0, "Empty string should still produce embedding"

    def test_generate_handles_long_text(self) -> None:
        """Test generate_single handles text longer than model's context window."""
        from krag.embeddings.generator import EmbeddingGenerator

        generator = EmbeddingGenerator()

        # Generate very long text (typical models have 512 token limit)
        long_text = "word " * 1000

        # Should handle long text (truncate or split)
        embedding = generator.generate_single(long_text)

        # Should still return valid embedding
        assert isinstance(embedding, (list, tuple)), "Should handle long text"
        assert len(embedding) > 0, "Long text should produce embedding"

    def test_embedding_values_normalized(self) -> None:
        """Test embeddings are normalized (unit vectors for cosine similarity)."""
        from krag.embeddings.generator import EmbeddingGenerator

        generator = EmbeddingGenerator()

        embedding = generator.generate_single("test text")

        # Calculate magnitude
        magnitude = sum(x**2 for x in embedding) ** 0.5

        # Should be normalized (magnitude close to 1.0)
        # Allow some floating point tolerance
        assert 0.99 <= magnitude <= 1.01, "Embeddings should be normalized for cosine similarity"
