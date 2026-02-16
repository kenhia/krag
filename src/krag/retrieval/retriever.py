"""Retriever for similarity search in vector store."""

import logging
from pathlib import Path
from typing import Any

from krag.models.query_result import QueryResult

logger = logging.getLogger(__name__)


class Retriever:
    """Retrieves relevant chunks from vector store based on query similarity.

    Converts queries to embeddings and performs similarity search.
    """

    def __init__(
        self,
        vector_store: Any,  # VectorStore protocol/interface
        embedding_generator: Any,  # EmbeddingGenerator protocol/interface
    ):
        """Initialize retriever.

        Args:
            vector_store: Vector store for similarity search
            embedding_generator: Generator for query embeddings
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float | None = None,
    ) -> list[QueryResult]:
        """Retrieve most relevant chunks for a query.

        Fetches top_k results from vector store, then optionally filters
        by similarity_threshold in Python. This post-retrieval filtering
        approach is compatible with all vector store backends.

        Args:
            query: User query string
            top_k: Number of results to retrieve from vector store
            similarity_threshold: Minimum similarity score to keep (None = no filtering)

        Returns:
            List of QueryResult objects ranked by relevance
        """
        logger.debug(f"Retrieving top {top_k} results for query: {query[:50]}...")

        # Generate embedding for query
        query_embedding = self.embedding_generator.generate_single(query)
        logger.debug(f"Generated query embedding with dimension {len(query_embedding)}")

        # Perform similarity search
        results = self.vector_store.search(query_embedding, limit=top_k)
        logger.debug(f"Vector store returned {len(results)} results")

        # Convert to QueryResult objects
        query_results = []
        for rank, result in enumerate(results, start=1):
            payload = result.get("payload", {})
            score = float(result["score"])

            query_result = QueryResult(
                chunk_id=result["id"],
                score=score,
                rank=rank,
                chunk_content=payload.get("content", ""),
                file_path=Path(payload.get("file_path", "")),
                chunk_index=payload.get("chunk_index", 0),
                file_type=payload.get("file_type", "unknown"),
            )
            query_results.append(query_result)
            logger.debug(
                "  [%d] score=%.4f file=%s",
                rank,
                score,
                payload.get("file_path", ""),
            )

        # Apply similarity threshold filtering
        if similarity_threshold is not None:
            pre_count = len(query_results)
            query_results = [r for r in query_results if r.score >= similarity_threshold]
            logger.info(
                "Retrieved %d, kept %d after threshold %.2f",
                pre_count,
                len(query_results),
                similarity_threshold,
            )

        return query_results
