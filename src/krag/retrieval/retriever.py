"""Retriever for similarity search in vector store."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from krag.models.query_result import QueryResult
from krag.retrieval.rrf import RRFScoredPoint, reciprocal_rank_fusion

if TYPE_CHECKING:
    from krag.embeddings.generator import EmbeddingGenerator
    from krag.embeddings.orchestrator import EmbeddingOrchestrator
    from krag.storage.collection_manager import CollectionManager
    from krag.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Common stop words filtered from boost keyword extraction
_STOP_WORDS: frozenset[str] = frozenset(
    {
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
)

# Minimum keyword length for boost extraction (shared by both boost methods)
_MIN_KEYWORD_LENGTH = 3


def _weighted_rrf(
    result_lists: list[list[Any]],
    weights: list[float],
    k: int = 60,
    limit: int = 10,
) -> list[RRFScoredPoint]:
    """Weighted Reciprocal Rank Fusion across multiple result lists.

    Each list contributes ``weight * 1/(k + rank)`` per document.
    This extends standard RRF to support per-collection weighting.

    Args:
        result_lists: One result list per collection.  Each element must
            have ``.id``, ``.score``, and ``.payload`` attributes.
        weights: Per-list weight (same length as *result_lists*).
        k: RRF ranking constant (default 60).
        limit: Maximum results to return.

    Returns:
        Merged and re-ranked results as ``RRFScoredPoint`` objects.
    """
    if not result_lists:
        return []

    scores: dict[str, float] = {}
    point_map: dict[str, Any] = {}

    for results, weight in zip(result_lists, weights, strict=True):
        for rank, point in enumerate(results):
            pid = str(point.id)
            scores[pid] = scores.get(pid, 0.0) + weight * (1.0 / (k + rank + 1))
            if pid not in point_map:
                point_map[pid] = point

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    merged: list[RRFScoredPoint] = []
    for pid, rrf_score in ranked[:limit]:
        original = point_map[pid]
        merged.append(
            RRFScoredPoint(
                id=original.id,
                score=rrf_score,
                payload=getattr(original, "payload", {}),
            )
        )
    return merged


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

    # RRF scores are much smaller (~0.01–0.03), so boosts must be proportional
    _KEYWORD_BOOST_WEIGHT_RRF = 0.002
    _METADATA_BOOST_WEIGHT_RRF = 0.003

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        embedding_orchestrator: EmbeddingOrchestrator | None = None,
        collection_manager: CollectionManager | None = None,
    ):
        """Initialize retriever.

        Args:
            vector_store: Vector store for similarity search
            embedding_generator: Generator for query embeddings (single-model)
            embedding_orchestrator: Multi-model orchestrator (optional).
                When provided, queries use all loaded models and results
                are merged via Reciprocal Rank Fusion.
            collection_manager: Multi-collection manager (optional).
                When provided with ``target_collections`` in ``retrieve()``,
                queries each collection separately and merges via weighted RRF.
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.embedding_orchestrator = embedding_orchestrator
        self.collection_manager = collection_manager

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float | None = None,
        target_collections: dict[str, float] | None = None,
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
            target_collections: Optional mapping of collection name → weight for
                multi-collection queries.  Requires ``collection_manager`` to be
                set.  When ``None``, uses the single ``vector_store``.

        Returns:
            List of QueryResult objects ranked by relevance
        """
        logger.debug(f"Retrieving top {top_k} results for query: {query[:50]}...")

        # Step 1: Over-fetch to have enough results after dedup
        fetch_limit = top_k * self._OVERFETCH_FACTOR

        # Multi-collection path: query each collection and merge
        # When collection_manager is available but no explicit targets,
        # auto-target all managed collections with equal weight so the
        # retriever searches where data was actually indexed.
        if self.collection_manager is not None and not target_collections:
            target_collections = dict.fromkeys(self.collection_manager.stores, 1.0)
        if target_collections and self.collection_manager is not None:
            query_results = self._multi_collection_retrieve(query, fetch_limit, target_collections)
            using_rrf = True
        else:
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
        query_results = self._metadata_boost(query, query_results, is_rrf=using_rrf)

        # Step 4b: Keyword boost
        query_results = self._keyword_boost(query, query_results, is_rrf=using_rrf)

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
    def _payload_to_query_result(
        point_id: str | int,
        score: float,
        rank: int,
        payload: dict[str, Any],
    ) -> QueryResult | None:
        """Convert a point payload to a QueryResult.

        Returns None if the payload is invalid (missing/empty file_path),
        logging a warning instead of crashing.
        """
        file_path_raw = payload.get("file_path", "")
        if not file_path_raw:
            logger.warning(
                "Skipping result %s (rank %d): empty or missing file_path in payload",
                point_id,
                rank,
            )
            return None

        try:
            return QueryResult(
                chunk_id=str(point_id) if not isinstance(point_id, str) else point_id,
                score=score,
                rank=rank,
                chunk_content=payload.get("content", ""),
                file_path=Path(file_path_raw),
                chunk_index=payload.get("chunk_index", 0),
                file_type=payload.get("file_type", "unknown"),
                language=payload.get("language"),
                function_name=payload.get("function_name"),
                class_name=payload.get("class_name"),
                start_line=payload.get("start_line"),
                end_line=payload.get("end_line"),
            )
        except Exception:
            logger.warning(
                "Skipping result %s (rank %d): failed to construct QueryResult",
                point_id,
                rank,
                exc_info=True,
            )
            return None

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

            qr = Retriever._payload_to_query_result(result["id"], score, rank, payload)
            if qr is not None:
                query_results.append(qr)
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
        self._last_per_space_counts: dict[str, int] = {}
        for vector_name, embedding in query_embeddings.items():
            try:
                results = self.vector_store.search_named(
                    query_vector=embedding,
                    vector_name=vector_name,
                    limit=fetch_limit,
                )
            except Exception:
                logger.warning(
                    "Search failed for vector space '%s', skipping",
                    vector_name,
                    exc_info=True,
                )
                results = []
            logger.debug(f"  Vector space '{vector_name}': {len(results)} results")
            self._last_per_space_counts[vector_name] = len(results)
            if results:
                all_result_lists.append(results)

        # Merge via RRF
        merged = reciprocal_rank_fusion(all_result_lists, k=60, limit=fetch_limit)
        logger.debug(f"RRF merged {len(merged)} unique results")

        # Convert RRFScoredPoint objects to QueryResult
        query_results: list[QueryResult] = []
        for rank, point in enumerate(merged, start=1):
            qr = self._payload_to_query_result(str(point.id), point.score, rank, point.payload)
            if qr is not None:
                query_results.append(qr)

        return query_results

    def _multi_collection_retrieve(
        self,
        query: str,
        fetch_limit: int,
        target_collections: dict[str, float],
    ) -> list[QueryResult]:
        """Retrieve from multiple collections and merge via weighted RRF.

        Two-level fusion:
          Level 1: Within each collection, if multi-model, merge via RRF.
          Level 2: Across collections, merge via weighted RRF.

        Args:
            query: User query string
            fetch_limit: Number of results to fetch per collection
            target_collections: Mapping of collection name → weight

        Returns:
            Merged and re-ranked QueryResult list tagged with collection name.
        """
        assert self.collection_manager is not None

        # Determine embedding strategy
        use_multi_model = (
            self.embedding_orchestrator is not None and self.embedding_orchestrator.is_multi_model
        )

        if use_multi_model:
            query_embeddings = self.embedding_orchestrator.embed_query(query)
            logger.debug(
                "Multi-collection multi-model query: %d collections %s, %d vector spaces %s",
                len(target_collections),
                list(target_collections.keys()),
                len(query_embeddings),
                list(query_embeddings.keys()),
            )
        else:
            query_embedding = self.embedding_generator.generate_single(query)
            logger.debug(
                "Multi-collection query: %d collections %s",
                len(target_collections),
                list(target_collections.keys()),
            )

        # Collect per-collection result lists with their weights
        all_result_lists: list[list[Any]] = []
        collection_weights: list[float] = []
        collection_tags: list[str] = []
        self._last_per_space_counts: dict[str, int] = {}
        self._last_collections_searched: list[str] = []

        for collection_name, weight in target_collections.items():
            try:
                store = self.collection_manager.get_store(collection_name)
            except KeyError:
                logger.warning("Unknown collection '%s', skipping", collection_name)
                continue

            self._last_collections_searched.append(collection_name)
            vs = store.vector_store

            if use_multi_model and getattr(vs, "is_named_vectors", False):
                # Multi-model path: search each named vector space, inner RRF
                per_space_lists: list[list[Any]] = []
                for vector_name, embedding in query_embeddings.items():
                    try:
                        results = vs.search_named(embedding, vector_name, limit=fetch_limit)
                    except Exception:
                        logger.warning(
                            "search_named failed for collection '%s' space '%s', skipping",
                            collection_name,
                            vector_name,
                            exc_info=True,
                        )
                        results = []
                    self._last_per_space_counts[f"{collection_name}:{vector_name}"] = len(results)
                    if results:
                        per_space_lists.append(results)

                # Level 1: Inner RRF merge within this collection
                if not per_space_lists:
                    logger.debug("  Collection '%s': 0 results across all spaces", collection_name)
                    continue

                inner_merged = reciprocal_rank_fusion(per_space_lists, k=60, limit=fetch_limit)
                # Tag with collection name for outer merge
                for point in inner_merged:
                    point.payload["_collection"] = collection_name

                logger.debug(
                    "  Collection '%s': %d results after inner RRF (weight=%.2f)",
                    collection_name,
                    len(inner_merged),
                    weight,
                )
                all_result_lists.append(inner_merged)
                collection_weights.append(weight)
                collection_tags.append(collection_name)
            else:
                # Single-model path: search unnamed vector space
                single_embedding = (
                    query_embeddings.get("text", next(iter(query_embeddings.values())))
                    if use_multi_model
                    else query_embedding
                )
                try:
                    results = vs.search(single_embedding, limit=fetch_limit)
                except Exception:
                    logger.warning(
                        "Search failed for collection '%s', returning empty",
                        collection_name,
                        exc_info=True,
                    )
                    results = []

                self._last_per_space_counts[collection_name] = len(results)

                if not results:
                    logger.debug("  Collection '%s': 0 results (empty)", collection_name)
                    continue

                # Convert dicts to ScoredPointLike objects for RRF
                points: list[RRFScoredPoint] = []
                for r in results:
                    points.append(
                        RRFScoredPoint(
                            id=r["id"],
                            score=r["score"],
                            payload={**r.get("payload", {}), "_collection": collection_name},
                        )
                    )

                logger.debug(
                    "  Collection '%s': %d results (weight=%.2f)",
                    collection_name,
                    len(points),
                    weight,
                )
                all_result_lists.append(points)
                collection_weights.append(weight)
                collection_tags.append(collection_name)

        if not all_result_lists:
            logger.debug("No results from any collection")
            return []

        # Level 2: Weighted RRF across collections
        merged = _weighted_rrf(all_result_lists, collection_weights, k=60, limit=fetch_limit)
        logger.debug("Cross-collection RRF merged %d unique results", len(merged))

        # Convert to QueryResult with collection tag
        query_results: list[QueryResult] = []
        for rank, point in enumerate(merged, start=1):
            collection_tag = point.payload.pop("_collection", None)
            qr = self._payload_to_query_result(str(point.id), point.score, rank, point.payload)
            if qr is not None:
                qr.collection = collection_tag
                query_results.append(qr)

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
        self._last_total_before_dedup = len(results)
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

    def _metadata_boost(
        self, query: str, results: list[QueryResult], *, is_rrf: bool = False
    ) -> list[QueryResult]:
        """Boost scores for results whose function/class name matches query terms.

        Extracts meaningful words (3+ chars, no stop words) from the query
        and checks whether they appear in each result's ``function_name``
        or ``class_name``.  A small bonus is added per match, and results
        are re-sorted.

        Args:
            query: Original user query
            results: Deduplicated results
            is_rrf: True if scores are RRF-fused (use smaller weights)

        Returns:
            Results re-sorted by boosted score (descending)
        """
        boost_weight = self._METADATA_BOOST_WEIGHT_RRF if is_rrf else self._METADATA_BOOST_WEIGHT
        words = re.findall(r"[a-zA-Z0-9_]+", query.lower())
        keywords = [w for w in words if len(w) >= _MIN_KEYWORD_LENGTH and w not in _STOP_WORDS]

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

            bonus = matches * boost_weight
            boosted_score = r.score + bonus

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

    def _keyword_boost(
        self, query: str, results: list[QueryResult], *, is_rrf: bool = False
    ) -> list[QueryResult]:
        """Boost scores for results containing query keywords.

        Extracts meaningful words (3+ chars, no stop words) from the query
        and adds a small bonus for each keyword found (case-insensitive) in
        the chunk content. Results are re-sorted by boosted score.

        Args:
            query: Original user query
            results: Deduplicated results
            is_rrf: True if scores are RRF-fused (use smaller weights)

        Returns:
            Results re-sorted by boosted score (descending)
        """
        boost_weight = self._KEYWORD_BOOST_WEIGHT_RRF if is_rrf else self._KEYWORD_BOOST_WEIGHT
        # Extract keywords using shared stop-word list and min-length
        words = re.findall(r"[a-zA-Z0-9_]+", query.lower())
        keywords = [w for w in words if len(w) >= _MIN_KEYWORD_LENGTH and w not in _STOP_WORDS]

        if not keywords:
            return results

        logger.debug("Keyword boost terms: %s", keywords)

        boosted: list[tuple[float, QueryResult]] = []
        for r in results:
            content_lower = r.chunk_content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            bonus = matches * boost_weight
            boosted_score = r.score + bonus

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
