"""Abstract interface for vector storage."""

from abc import ABC, abstractmethod
from typing import Any


class VectorStore(ABC):
    """Abstract interface for vector storage operations.

    Defines the contract that all vector store implementations must follow.
    """

    @abstractmethod
    def upsert(self, vectors: list[dict[str, Any]]) -> None:
        """Add or update vectors in the store.

        Args:
            vectors: List of dictionaries with 'id', 'vector', and 'payload' keys
        """
        pass

    @abstractmethod
    def search(self, query_vector: list[float], limit: int = 10) -> list[dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query_vector: Query vector to search for
            limit: Maximum number of results to return

        Returns:
            List of results with 'id', 'score', and 'payload' fields
        """
        pass

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Delete vectors by their IDs.

        Args:
            ids: List of vector IDs to delete
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection statistics (e.g., count, size)
        """
        pass
