"""CollectionManager — shared Qdrant client with four collection stores.

Manages the lifecycle of a single ``QdrantClient`` and creates one
``QdrantVectorStore`` wrapper per content-type collection (code, tests,
docs, text).  All stores share the same client instance so only one
file-lock is held.

See ``data-model.md`` Entity 2 and ``research.md`` R-01.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from krag.routing.collection_router import CollectionRouter
from krag.routing.rules import ALL_COLLECTIONS, qdrant_collection_name
from krag.storage.qdrant_impl import QdrantVectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectionStore:
    """One of the four content-type-specific Qdrant collections.

    Attributes:
        name: Logical collection name (``code``, ``tests``, ``docs``, ``text``).
        collection_name: Qdrant collection name (``krag_code``, …).
        vector_size: Embedding dimension.
        vector_store: ``QdrantVectorStore`` wrapper sharing the manager's client.
    """

    name: str
    collection_name: str
    vector_size: int
    vector_store: QdrantVectorStore


class CollectionManager:
    """Manages a shared ``QdrantClient`` and four collection stores.

    Lifecycle:
        * Created once at service / indexer startup.
        * Owns the ``QdrantClient`` file-lock.
        * ``close()`` closes the shared client.
    """

    def __init__(
        self,
        storage_path: Path,
        vector_size: int,
        router: CollectionRouter,
        *,
        distance: str = "cosine",
        allow_recreate: bool = True,
    ) -> None:
        self._storage_path = storage_path
        self._vector_size = vector_size
        self.router = router
        self._closed = False

        # Create a single shared client
        storage_path.mkdir(parents=True, exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self._client: QdrantClient = QdrantClient(path=str(storage_path))

        logger.info("CollectionManager: shared QdrantClient at %s", storage_path)

        # Create one QdrantVectorStore per collection, sharing the client
        self.stores: dict[str, CollectionStore] = {}
        for name in sorted(ALL_COLLECTIONS):
            qdrant_name = qdrant_collection_name(name)
            vs = QdrantVectorStore(
                collection_name=qdrant_name,
                vector_size=vector_size,
                storage_path=storage_path,
                distance=distance,
                allow_recreate=allow_recreate,
                client=self._client,
            )
            self.stores[name] = CollectionStore(
                name=name,
                collection_name=qdrant_name,
                vector_size=vector_size,
                vector_store=vs,
            )
            logger.debug("  Created collection store: %s → %s", name, qdrant_name)

    # ── accessors ────────────────────────────────

    def get_store(self, collection: str) -> CollectionStore:
        """Return a ``CollectionStore`` by logical name.

        Raises:
            KeyError: If *collection* is not one of the four known names.
        """
        return self.stores[collection]

    def get_all_stores(self) -> list[CollectionStore]:
        """Return all collection stores."""
        return list(self.stores.values())

    # ── routing ──────────────────────────────────

    def route_file(
        self,
        file_path: Path,
        plugin_name: str | None,
    ) -> str:
        """Route *file_path* to the appropriate collection name.

        Delegates to the internal ``CollectionRouter``.
        """
        ext = file_path.suffix
        return self.router.route(file_path, ext, plugin_name)

    # ── stats ────────────────────────────────────

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-collection statistics.

        Returns:
            ``{collection_name: stats_dict, …}`` for all four collections.
        """
        stats: dict[str, dict[str, Any]] = {}
        for name, store in self.stores.items():
            try:
                stats[name] = store.vector_store.get_stats()
            except Exception:
                logger.warning("Failed to get stats for collection %s", name, exc_info=True)
                stats[name] = {
                    "collection_name": store.collection_name,
                    "count": 0,
                    "status": "error",
                }
        return stats

    # ── lifecycle ────────────────────────────────

    def close(self) -> None:
        """Close the shared ``QdrantClient``.

        Safe to call multiple times (idempotent).
        """
        if self._closed:
            return
        self._closed = True
        logger.info("CollectionManager: closing shared QdrantClient")
        self._client.close()
