"""Mock embedding generator for testing."""

import hashlib


class MockEmbeddingGenerator:
    """Mock embedding generator that produces deterministic embeddings for testing.

    Uses a hash of the text to generate consistent but unique embeddings.
    """

    def __init__(self, dimension: int = 384):
        """Initialize mock generator.

        Args:
            dimension: Dimension of embedding vectors
        """
        self.dimension = dimension
        self.call_count = 0

    def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (one per text)
        """
        self.call_count += 1
        embeddings = []

        for text in texts:
            # Generate deterministic embedding based on text hash
            text_hash = hashlib.md5(text.encode()).hexdigest()
            # Convert hash to list of floats
            hash_ints = [int(text_hash[i : i + 2], 16) for i in range(0, len(text_hash), 2)]
            # Extend to desired dimension
            embedding = []
            for i in range(self.dimension):
                embedding.append(float(hash_ints[i % len(hash_ints)]) / 255.0)
            embeddings.append(embedding)

        return embeddings

    def generate_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector
        """
        return self.generate([text])[0]


def create_mock_embeddings(texts: list[str], dimension: int = 384) -> list[list[float]]:
    """Helper function to create mock embeddings without instantiating the class.

    Args:
        texts: List of texts to embed
        dimension: Vector dimension

    Returns:
        List of embedding vectors
    """
    generator = MockEmbeddingGenerator(dimension=dimension)
    return generator.generate(texts)
