"""Text embedding generation using sentence-transformers."""

import logging
from typing import Any

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates text embeddings using sentence-transformers models.

    Uses HuggingFace sentence-transformers for generating dense vector
    representations of text. Supports batch processing and multiple devices.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        """Initialize embedding generator.

        Args:
            model_name: Name of sentence-transformers model to use
            device: Device to run model on ('cpu', 'cuda', 'mps')
        """
        self.model_name = model_name
        self.device = device

        logger.info(f"Loading embedding model: {model_name} on device: {device}")
        self.model = SentenceTransformer(model_name, device=device)

        # Get model dimension
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.dimension}")

    def generate_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        # Handle empty text
        if not text or not text.strip():
            # Return zero vector for empty text
            logger.warning("Empty text provided, returning zero vector")
            return [0.0] * self.dimension

        # Generate embedding
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Normalize for cosine similarity
            show_progress_bar=False,
        )

        # Convert numpy array to list
        return embedding.tolist()

    def generate_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Generate embeddings in batches
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Normalize for cosine similarity
            batch_size=batch_size,
            show_progress_bar=show_progress,
        )

        # Convert numpy arrays to lists
        return [emb.tolist() for emb in embeddings]

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            Number of dimensions in embedding vectors
        """
        return self.dimension

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model.

        Returns:
            Dictionary with model information
        """
        return {
            "model_name": self.model_name,
            "device": self.device,
            "dimension": self.dimension,
            "max_seq_length": self.model.max_seq_length,
        }
