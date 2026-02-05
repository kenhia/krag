"""Qdrant vector store implementation."""

import hashlib
import logging
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from krag.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class QdrantVectorStore(VectorStore):
    """Vector store implementation using Qdrant.

    Provides persistent vector storage with similarity search capabilities.
    Supports both in-memory and disk-based storage.
    """

    def __init__(
        self,
        collection_name: str,
        vector_size: int,
        storage_path: str | Path | None = None,
        distance: str = "cosine",
    ):
        """Initialize Qdrant vector store.

        Args:
            collection_name: Name of the collection
            vector_size: Dimension of vectors
            storage_path: Path for persistent storage (None for in-memory)
            distance: Distance metric ('cosine', 'euclidean', 'dot')
        """
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.storage_path = Path(storage_path) if storage_path else None

        # Initialize client
        if self.storage_path:
            logger.info(f"Initializing Qdrant with storage at {self.storage_path}")
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(self.storage_path))
        else:
            logger.info("Initializing Qdrant in-memory")
            self.client = QdrantClient(":memory:")

        # Map distance names to Qdrant constants
        distance_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot": Distance.DOT,
        }
        self.distance = distance_map.get(distance.lower(), Distance.COSINE)

        # Create or recreate collection
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensure collection exists with correct configuration."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            logger.info(f"Creating collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=self.distance,
                ),
            )
        else:
            logger.debug(f"Collection {self.collection_name} already exists")

    def upsert(self, vectors: list[dict[str, Any]]) -> None:
        """Add or update vectors in the store.

        Args:
            vectors: List of dicts with 'id', 'vector', and 'payload' keys
        """
        if not vectors:
            logger.warning("Empty vector list provided to upsert")
            return

        # Convert to Qdrant points
        # Qdrant requires IDs to be integers or UUIDs
        # Convert string IDs to integer hashes
        points = [
            PointStruct(
                id=self._id_to_int(vec["id"]),
                vector=vec["vector"],
                payload={**vec.get("payload", {}), "_original_id": vec["id"]},
            )
            for vec in vectors
        ]

        # Upsert to collection
        self.client.upsert(collection_name=self.collection_name, points=points)

        logger.info(f"Upserted {len(points)} vectors to {self.collection_name}")

    def search(self, query_vector: list[float], limit: int = 10) -> list[dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query_vector: Query vector to search for
            limit: Maximum number of results to return

        Returns:
            List of results with 'id', 'score', and 'payload' fields
        """
        # Perform search
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
        )

        # Format results
        formatted = [
            {
                "id": result.payload.get("_original_id", str(result.id)),
                "score": result.score,
                "payload": {k: v for k, v in result.payload.items() if k != "_original_id"},
            }
            for result in results.points
        ]

        logger.debug(f"Search returned {len(formatted)} results")
        return formatted

    def delete(self, ids: list[str]) -> None:
        """Delete vectors by their IDs.

        Args:
            ids: List of vector IDs to delete
        """
        if not ids:
            logger.warning("Empty ID list provided to delete")
            return

        # Convert string IDs to integer hashes
        int_ids = [self._id_to_int(id_) for id_ in ids]

        # Delete from collection
        self.client.delete(collection_name=self.collection_name, points_selector=int_ids)

        logger.info(f"Deleted {len(ids)} vectors from {self.collection_name}")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        collection_info = self.client.get_collection(self.collection_name)

        # Extract count from collection info
        count = 0
        if hasattr(collection_info, "points_count"):
            count = collection_info.points_count or 0
        elif hasattr(collection_info, "vectors_count"):
            count = collection_info.vectors_count or 0

        stats = {
            "collection_name": self.collection_name,
            "count": count,
            "vectors_count": count,
            "status": collection_info.status.value
            if hasattr(collection_info.status, "value")
            else str(collection_info.status),
        }

        logger.debug(f"Collection stats: {stats}")
        return stats

    def clear(self) -> None:
        """Clear all vectors from the collection."""
        logger.warning(f"Clearing collection: {self.collection_name}")
        self.client.delete_collection(self.collection_name)
        self._ensure_collection()

    def close(self) -> None:
        """Close the Qdrant client and release resources."""
        if hasattr(self, "client") and self.client:
            logger.debug(f"Closing Qdrant client for {self.collection_name}")
            self.client.close()

    @staticmethod
    def _id_to_int(id_str: str) -> int:
        """Convert string ID to integer hash for Qdrant.

        Args:
            id_str: String ID

        Returns:
            Integer hash of the ID
        """
        # Use SHA256 hash and take first 8 bytes as integer
        hash_bytes = hashlib.sha256(id_str.encode()).digest()[:8]
        return int.from_bytes(hash_bytes, byteorder="big", signed=False)
