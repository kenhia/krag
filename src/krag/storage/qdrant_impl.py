"""Qdrant vector store implementation."""

import hashlib
import logging
import warnings
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from krag.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class _NamedSearchResult:
    """A search result from a named vector space.

    Has .id, .score, .payload attributes matching the ScoredPointLike
    protocol used by reciprocal_rank_fusion().
    """

    __slots__ = ("id", "score", "payload")

    def __init__(self, id: Any, score: float, payload: dict[str, Any]) -> None:
        self.id = id
        self.score = score
        self.payload = payload

    def __repr__(self) -> str:
        return f"_NamedSearchResult(id={self.id!r}, score={self.score:.4f})"


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
        vectors_config: dict[str, VectorParams] | None = None,
        allow_recreate: bool = False,
    ):
        """Initialize Qdrant vector store.

        Args:
            collection_name: Name of the collection
            vector_size: Dimension of vectors (used for single-vector mode)
            storage_path: Path for persistent storage (None for in-memory)
            distance: Distance metric ('cosine', 'euclidean', 'dot')
            vectors_config: Named vectors configuration for multi-model mode.
                If provided, creates collection with named vectors instead
                of a single unnamed vector. E.g.,
                {"text": VectorParams(size=768, distance=COSINE),
                 "code": VectorParams(size=768, distance=COSINE)}.
            allow_recreate: If True, allow dropping and recreating the collection
                when its format does not match the requested configuration.
                Should only be True during indexing; query/eval should leave
                this False so they never destroy stored data.
        """
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.storage_path = Path(storage_path) if storage_path else None
        self._vectors_config = vectors_config
        self._allow_recreate = allow_recreate

        # Initialize client
        if self.storage_path:
            logger.info(f"Initializing Qdrant with storage at {self.storage_path}")
            self.storage_path.mkdir(parents=True, exist_ok=True)
            # Suppress Qdrant's large collection warning for local mode
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
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

    @property
    def is_named_vectors(self) -> bool:
        """Whether this store uses named vectors (multi-model mode)."""
        return self._vectors_config is not None

    def _ensure_collection(self) -> None:
        """Ensure collection exists with correct configuration."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            logger.info(f"Creating collection: {self.collection_name}")
            if self._vectors_config:
                # Named vectors mode: create with multiple vector spaces
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=self._vectors_config,
                )
                logger.info(
                    f"Created collection with named vectors: {list(self._vectors_config.keys())}"
                )
            else:
                # Single vector mode (backward compatible)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=self.distance,
                    ),
                )
        else:
            logger.debug(f"Collection {self.collection_name} already exists")
            # Auto-detect vector size from existing collection if it differs
            collection_info = self.client.get_collection(self.collection_name)
            vectors_cfg = collection_info.config.params.vectors
            if isinstance(vectors_cfg, dict):
                # Existing collection uses named vectors
                existing_named = True
                existing_keys = set(vectors_cfg.keys())
            else:
                existing_named = False
                existing_keys = set()

            want_named = self._vectors_config is not None

            if want_named and not existing_named:
                # Existing collection is single-vector; we need named vectors
                if self._allow_recreate:
                    logger.warning(
                        f"Collection '{self.collection_name}' exists as single-vector format "
                        f"but named vectors {list(self._vectors_config.keys())} are required. "
                        f"Recreating collection."
                    )
                    self.client.delete_collection(self.collection_name)
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=self._vectors_config,
                    )
                    logger.info(
                        f"Recreated collection with named vectors: {list(self._vectors_config.keys())}"
                    )
                else:
                    logger.warning(
                        f"Collection '{self.collection_name}' is single-vector but named vectors "
                        f"{list(self._vectors_config.keys())} are configured. "
                        f"Re-index with 'krag index --full' to upgrade the collection."
                    )
            elif not want_named and existing_named:
                # Existing collection is named-vector; we now want single-vector
                if self._allow_recreate:
                    logger.warning(
                        f"Collection '{self.collection_name}' exists with named vectors {list(existing_keys)} "
                        f"but single-vector mode is required. Recreating collection."
                    )
                    self.client.delete_collection(self.collection_name)
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(
                            size=self.vector_size,
                            distance=self.distance,
                        ),
                    )
                    logger.info(
                        f"Recreated collection in single-vector mode (dim={self.vector_size})"
                    )
                else:
                    logger.debug(
                        f"Collection uses named vectors {list(existing_keys)}; "
                        f"query will use existing vector spaces."
                    )
                    # Adopt existing named-vectors config so is_named_vectors
                    # returns True and search() passes `using="text"`.
                    self._vectors_config = vectors_cfg
            elif want_named and existing_named:
                # Both named — check if new vector names need to be added
                want_keys = set(self._vectors_config.keys())
                missing = want_keys - existing_keys
                if missing and self._allow_recreate:
                    logger.info(
                        f"Collection '{self.collection_name}' missing vector spaces {missing}, "
                        f"recreating with full config."
                    )
                    self.client.delete_collection(self.collection_name)
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=self._vectors_config,
                    )
                    logger.info(
                        f"Recreated collection with named vectors: {list(self._vectors_config.keys())}"
                    )
                elif missing:
                    logger.warning(
                        f"Collection missing vector spaces {missing}. "
                        f"Re-index with 'krag index --full' to add them."
                    )
                else:
                    logger.debug(f"Collection uses named vectors: {list(existing_keys)}")
            else:
                # Both single-vector — check size mismatch
                if hasattr(vectors_cfg, "size"):
                    actual_size = vectors_cfg.size
                    if actual_size != self.vector_size:
                        logger.warning(
                            f"Vector size mismatch: specified {self.vector_size} but "
                            f"collection has {actual_size}. Using collection's vector size."
                        )
                        self.vector_size = actual_size

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

        # Upsert to collection (suppress large collection warning)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.client.upsert(collection_name=self.collection_name, points=points)

        logger.debug(f"Upserted {len(points)} vectors to {self.collection_name}")

    def search(self, query_vector: list[float], limit: int = 10) -> list[dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query_vector: Query vector to search for
            limit: Maximum number of results to return

        Returns:
            List of results with 'id', 'score', and 'payload' fields
        """
        # When the collection uses named vectors we must specify which space to
        # search.  Fall back to the "text" space so single-model queries still
        # work against a multi-model (named-vector) collection.
        #
        # Invariant: the primary embedding model is always stored under the
        # "text" vector space name.  This convention is established in
        # EmbeddingOrchestrator.__init__ and relied upon by Retriever,
        # reciprocal_rank_fusion, and this fallback.  Any additional models
        # (e.g. code-specific) use their own named space but "text" is always
        # present as the default.
        kwargs: dict[str, Any] = {
            "collection_name": self.collection_name,
            "query": query_vector,
            "limit": limit,
        }
        if self.is_named_vectors:
            kwargs["using"] = "text"
            logger.debug("search() falling back to 'text' vector space on named-vector collection")

        results = self.client.query_points(**kwargs)

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

    def search_named(
        self,
        query_vector: list[float],
        vector_name: str,
        limit: int = 10,
    ) -> list[Any]:
        """Search a specific named vector space.

        Returns Qdrant ScoredPoint-like objects with .id, .score, .payload
        attributes, suitable for use with reciprocal_rank_fusion().

        Args:
            query_vector: Query vector to search for
            vector_name: Name of the vector space to search (e.g. "text", "code")
            limit: Maximum number of results to return

        Returns:
            List of ScoredPoint-like objects from the named vector space.
        """
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using=vector_name,
            limit=limit,
        )

        # Restore original IDs in the returned points
        points = []
        for point in results.points:
            # Replace numeric hash ID with original string ID in payload
            original_id = point.payload.get("_original_id", str(point.id))
            # Strip the internal tracking key from payload
            cleaned_payload = {k: v for k, v in point.payload.items() if k != "_original_id"}
            points.append(
                _NamedSearchResult(
                    id=original_id,
                    score=point.score,
                    payload=cleaned_payload,
                )
            )

        logger.debug(f"Named search '{vector_name}' returned {len(points)} results")
        return points

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

        # Delete from collection (suppress large collection warning)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.client.delete(collection_name=self.collection_name, points_selector=int_ids)

        logger.info(f"Deleted {len(ids)} vectors from {self.collection_name}")

    def delete_by_filter(self, filter_dict: dict[str, Any]) -> None:
        """Delete vectors matching the given filter.

        Args:
            filter_dict: Dictionary of filter conditions (e.g., {"file_path": "/path/to/file"})
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        # Build filter conditions
        conditions = []
        for key, value in filter_dict.items():
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        if not conditions:
            logger.warning("No filter conditions provided")
            return

        # Delete using filter (suppress large collection warning)
        filter_obj = Filter(must=conditions)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.client.delete(collection_name=self.collection_name, points_selector=filter_obj)

        logger.info(f"Deleted vectors matching filter {filter_dict} from {self.collection_name}")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
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
            logger.info(f"Closing Qdrant client for collection '{self.collection_name}'...")
            self.client.close()
            logger.debug(f"Qdrant client closed for {self.collection_name}")

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
