"""Retriever for similarity search in vector store."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from krag.models.query_result import QueryResult
from krag.retrieval.rrf import reciprocal_rank_fusion

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

    # Weight given to metadata symbol match bonus
    _METADATA_BOOST_WEIGHT = 0.08

    def __init__(
        self,
        vector_store: Any,  # VectorStore protocol/interface
        embedding_generator: Any,  # EmbeddingGenerator protocol/interface
        embedding_orchestrator: Any | None = None,  # EmbeddingOrchestrator (optional)
    ):
        """Initialize retriever.

        Args:
            vector_store: Vector store for similarity search
            embedding_generator: Generator for query embeddings (single-model)
            embedding_orchestrator: Multi-model orchestrator (optional).
                When provided, queries use all loaded models and results
                are merged via Reciprocal Rank Fusion.
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.embedding_orchestrator = embedding_orchestrator

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

        # Multi-model path: embed with all models and merge via RRF
        using_rrf = (
            self.embedding_orchestrator is not None
            and self.embedding_orchestrator.is_multi_model
            and hasattr(self.vector_store, "search_named")
        )
        if using_rrf:
            query_results = self._multi_model_retrieve(query, fetch_limit)
        else:
            # Single-model path (backward compatible)
            query_embedding = self.embedding_generator.generate_single(query)
            logger.debug(f"Generated query embedding with dimension {len(query_embedding)}")

            results = self.vector_store.search(query_embedding, limit=fetch_limit)
            logger.debug(
                f"Vector store returned {len(results)} results (fetch_limit={fetch_limit})"
            )

            query_results = self._results_to_query_results(results)

        # Step 3: Deduplicate by content
        query_results = self._deduplicate(query_results)

        # Step 4a: Metadata boost (function_name / class_name matches)
        query_results = self._metadata_boost(query, query_results)

        # Step 4b: Keyword boost
        query_results = self._keyword_boost(query, query_results)

        # Step 5: Apply similarity threshold filtering
        # Skip threshold for RRF results: RRF scores are rank-fusion values
        # (~1/61 ≈ 0.016) that are not comparable to cosine similarity thresholds.
        # RRF already ensures only relevant results are included.
        if similarity_threshold is not None and not using_rrf:
            pre_count = len(query_results)
            query_results = [r for r in query_results if r.score >= similarity_threshold]
            logger.info(
                "Retrieved %d, kept %d after threshold %.2f",
                pre_count,
                len(query_results),
                similarity_threshold,
            )
        elif similarity_threshold is not None and using_rrf:
            logger.debug(
                "Skipping similarity threshold (%.2f) — RRF scores are rank-fusion "
                "values, not cosine similarity. Retrieved %d results.",
                similarity_threshold,
                len(query_results),
            )

        # Step 6: Trim to top_k and re-rank
        query_results = query_results[:top_k]
        for i, r in enumerate(query_results, start=1):
            r.rank = i

        return query_results

    @staticmethod
    def _results_to_query_results(results: list[dict[str, Any]]) -> list[QueryResult]:
        """Convert raw vector store results to QueryResult objects.

        Args:
            results: List of dicts with 'id', 'score', and 'payload' keys

        Returns:
            List of QueryResult objects with assigned ranks
        """
        query_results: list[QueryResult] = []
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
                language=payload.get("language"),
                function_name=payload.get("function_name"),
                class_name=payload.get("class_name"),
                start_line=payload.get("start_line"),
                end_line=payload.get("end_line"),
            )
            query_results.append(query_result)
            logger.debug(
                "  [%d] score=%.4f file=%s",
                rank,
                score,
                payload.get("file_path", ""),
            )
        return query_results

    def _multi_model_retrieve(self, query: str, fetch_limit: int) -> list[QueryResult]:
        """Retrieve using all embedding models and merge via RRF.

        Embeds the query with every active model, searches each named
        vector space, then merges using Reciprocal Rank Fusion.

        Args:
            query: User query string
            fetch_limit: Number of results to fetch per vector space

        Returns:
            Merged and re-ranked QueryResult list
        """
        assert self.embedding_orchestrator is not None

        # Embed query with all models
        query_embeddings = self.embedding_orchestrator.embed_query(query)
        logger.debug(
            f"Multi-model query: {len(query_embeddings)} vector spaces "
            f"({list(query_embeddings.keys())})"
        )

        # Search each named vector space
        all_result_lists: list[list[Any]] = []
        for vector_name, embedding in query_embeddings.items():
            results = self.vector_store.search_named(
                query_vector=embedding,
                vector_name=vector_name,
                limit=fetch_limit,
            )
            logger.debug(f"  Vector space '{vector_name}': {len(results)} results")
            all_result_lists.append(results)

        # Merge via RRF
        merged = reciprocal_rank_fusion(all_result_lists, k=60, limit=fetch_limit)
        logger.debug(f"RRF merged {len(merged)} unique results")

        # Convert RRFScoredPoint objects to QueryResult
        query_results: list[QueryResult] = []
        for rank, point in enumerate(merged, start=1):
            payload = point.payload
            query_result = QueryResult(
                chunk_id=str(point.id),
                score=point.score,
                rank=rank,
                chunk_content=payload.get("content", ""),
                file_path=Path(payload.get("file_path", "")),
                chunk_index=payload.get("chunk_index", 0),
                file_type=payload.get("file_type", "unknown"),
                language=payload.get("language"),
                function_name=payload.get("function_name"),
                class_name=payload.get("class_name"),
                start_line=payload.get("start_line"),
                end_line=payload.get("end_line"),
            )
            query_results.append(query_result)

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

    def _metadata_boost(self, query: str, results: list[QueryResult]) -> list[QueryResult]:
        """Boost scores for results whose function/class name matches query terms.

        Extracts meaningful words from the query and checks whether they
        appear in each result's ``function_name`` or ``class_name``.  A
        small bonus is added per match, and results are re-sorted.

        Args:
            query: Original user query
            results: Deduplicated results

        Returns:
            Results re-sorted by boosted score (descending)
        """
        words = re.findall(r"[a-zA-Z0-9_]+", query.lower())
        keywords = [w for w in words if len(w) >= 2]

        if not keywords:
            return results

        boosted: list[tuple[float, QueryResult]] = []
        for r in results:
            matches = 0
            fn = (r.function_name or "").lower()
            cn = (r.class_name or "").lower()
            # Split snake_case / camelCase identifiers into sub-tokens
            fn_tokens = re.findall(r"[a-z0-9]+", fn)
            cn_tokens = re.findall(r"[a-z0-9]+", cn)
            for kw in keywords:
                if kw in fn_tokens or kw in fn:
                    matches += 1
                if kw in cn_tokens or kw in cn:
                    matches += 1

            bonus = matches * self._METADATA_BOOST_WEIGHT
            boosted_score = min(r.score + bonus, 1.0)

            if bonus > 0:
                logger.debug(
                    "  Metadata boost +%.3f (%d symbol matches) for %s",
                    bonus,
                    matches,
                    r.file_path.name,
                )
                r.score = boosted_score

            boosted.append((boosted_score, r))

        boosted.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in boosted]

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
