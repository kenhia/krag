"""Retriever for similarity search in vector store."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from krag.models.query_result import QueryResult

logger = logging.getLogger(__name__)


class Retriever:
    """Retrieves relevant chunks from vector store based on query similarity.

    Converts queries to embeddings and performs similarity search.
    Applies deduplication and keyword boosting to improve result quality.
    """

    # Multiplier for over-fetching before dedup (fetch 3x top_k, dedup down)
    _OVERFETCH_FACTOR = 3

    # Weight given to keyword match bonus (added to semantic score)
    _KEYWORD_BOOST_WEIGHT = 0.05

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

        Pipeline:
          1. Over-fetch from vector store (top_k * 3)
          2. Deduplicate by content hash (keep highest-scoring copy)
          3. Apply keyword boost (bonus for exact query-term matches)
          4. Re-sort by boosted score
          5. Apply similarity threshold filter
          6. Trim to top_k

        Args:
            query: User query string
            top_k: Number of results to return after dedup
            similarity_threshold: Minimum similarity score to keep (None = no filtering)

        Returns:
            List of QueryResult objects ranked by relevance
        """
        logger.debug(f"Retrieving top {top_k} results for query: {query[:50]}...")

        # Step 1: Over-fetch to have enough results after dedup
        fetch_limit = top_k * self._OVERFETCH_FACTOR
        query_embedding = self.embedding_generator.generate_single(query)
        logger.debug(f"Generated query embedding with dimension {len(query_embedding)}")

        results = self.vector_store.search(query_embedding, limit=fetch_limit)
        logger.debug(f"Vector store returned {len(results)} results (fetch_limit={fetch_limit})")

        # Step 2: Convert to QueryResult objects
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

        # Step 3: Deduplicate by content
        query_results = self._deduplicate(query_results)

        # Step 4: Keyword boost
        query_results = self._keyword_boost(query, query_results)

        # Step 5: Apply similarity threshold filtering
        if similarity_threshold is not None:
            pre_count = len(query_results)
            query_results = [r for r in query_results if r.score >= similarity_threshold]
            logger.info(
                "Retrieved %d, kept %d after threshold %.2f",
                pre_count,
                len(query_results),
                similarity_threshold,
            )

        # Step 6: Trim to top_k and re-rank
        query_results = query_results[:top_k]
        for i, r in enumerate(query_results, start=1):
            r.rank = i

        return query_results

    @staticmethod
    def _content_hash(text: str) -> str:
        """Generate a short hash of chunk content for deduplication."""
        # Normalize whitespace before hashing to catch near-duplicates
        normalized = re.sub(r"\s+", " ", text.strip())
        return hashlib.md5(normalized.encode(), usedforsecurity=False).hexdigest()

    def _deduplicate(self, results: list[QueryResult]) -> list[QueryResult]:
        """Remove duplicate chunks, keeping the highest-scoring copy.

        Two chunks are considered duplicates if their normalized content
        produces the same MD5 hash (whitespace-insensitive).

        Args:
            results: Ranked list of QueryResult objects

        Returns:
            Deduplicated list, preserving score ordering
        """
        seen_hashes: dict[str, int] = {}  # hash → index of first occurrence
        unique: list[QueryResult] = []

        for r in results:
            h = self._content_hash(r.chunk_content)
            if h not in seen_hashes:
                seen_hashes[h] = len(unique)
                unique.append(r)

        removed = len(results) - len(unique)
        if removed > 0:
            logger.info(
                "Dedup: %d results → %d unique (%d duplicates removed)",
                len(results),
                len(unique),
                removed,
            )
        return unique

    def _keyword_boost(self, query: str, results: list[QueryResult]) -> list[QueryResult]:
        """Boost scores for results containing query keywords.

        Extracts meaningful words (3+ chars) from the query and adds a
        small bonus for each keyword found (case-insensitive) in the chunk
        content. Results are re-sorted by boosted score.

        Args:
            query: Original user query
            results: Deduplicated results

        Returns:
            Results re-sorted by boosted score (descending)
        """
        # Extract keywords: words with 3+ chars, lowercased, no stop words
        stop_words = {
            "the",
            "and",
            "for",
            "are",
            "was",
            "were",
            "been",
            "being",
            "have",
            "has",
            "had",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "need",
            "use",
            "used",
            "using",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "these",
            "those",
            "how",
            "when",
            "where",
            "why",
            "not",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "than",
            "too",
            "very",
            "just",
            "about",
            "into",
            "from",
            "with",
        }

        words = re.findall(r"[a-zA-Z0-9_]+", query.lower())
        keywords = [w for w in words if len(w) >= 3 and w not in stop_words]

        if not keywords:
            return results

        logger.debug("Keyword boost terms: %s", keywords)

        boosted: list[tuple[float, QueryResult]] = []
        for r in results:
            content_lower = r.chunk_content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            bonus = matches * self._KEYWORD_BOOST_WEIGHT
            boosted_score = min(r.score + bonus, 1.0)  # cap at 1.0

            if bonus > 0:
                logger.debug(
                    "  Keyword boost +%.3f (%d/%d matches) for %s",
                    bonus,
                    matches,
                    len(keywords),
                    r.file_path.name,
                )
                # Update score on the result object
                r.score = boosted_score

            boosted.append((boosted_score, r))

        # Sort by boosted score descending
        boosted.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in boosted]
