"""Unit tests for Retriever deduplication and keyword boost."""

from krag.retrieval.retriever import Retriever

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_store(results: list[dict]):
    """Create a mock vector store returning the given results."""

    class MockVectorStore:
        def __init__(self, data):
            self.data = data

        def search(self, vector, limit=5):
            return self.data

    return MockVectorStore(results)


def _make_embedding():
    class MockEmbedding:
        def generate_single(self, text):
            return [0.1] * 384

    return MockEmbedding()


def _result(
    chunk_id: str,
    score: float,
    content: str,
    file_path: str = "/test/file.py",
    chunk_index: int = 0,
) -> dict:
    """Build a vector-store result dict."""
    return {
        "id": chunk_id,
        "score": score,
        "payload": {
            "content": content,
            "file_path": file_path,
            "chunk_index": chunk_index,
            "file_type": "code",
        },
    }


# ── Deduplication Tests ─────────────────────────────────────────────────


class TestDeduplication:
    """Tests for content-based deduplication."""

    def test_duplicate_content_removed(self):
        """Identical content with different IDs should be deduplicated."""
        results = [
            _result("id-1", 0.9, "The default chunk size is 512"),
            _result("id-2", 0.9, "The default chunk size is 512"),
            _result("id-3", 0.9, "The default chunk size is 512"),
            _result("id-4", 0.8, "Something different here"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("chunk size", top_k=5)
        assert len(got) == 2, "Should deduplicate to 2 unique chunks"

    def test_whitespace_variants_deduplicated(self):
        """Content differing only in whitespace should be deduplicated."""
        results = [
            _result("id-1", 0.9, "foo  bar\n\nbaz"),
            _result("id-2", 0.85, "foo bar baz"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("foo bar", top_k=5)
        assert len(got) == 1, "Whitespace-normalised content should dedup"

    def test_first_occurrence_kept(self):
        """The highest-scoring duplicate should survive."""
        results = [
            _result("id-1", 0.9, "duplicate content"),
            _result("id-2", 0.7, "duplicate content"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("test", top_k=5)
        assert len(got) == 1
        assert got[0].chunk_id == "id-1", "Highest score copy should survive"

    def test_unique_content_preserved(self):
        """Distinct chunks should not be deduplicated."""
        results = [
            _result("id-1", 0.9, "Alpha content"),
            _result("id-2", 0.8, "Beta content"),
            _result("id-3", 0.7, "Gamma content"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("test", top_k=5)
        assert len(got) == 3

    def test_empty_results_handled(self):
        """Empty results should not raise."""
        retriever = Retriever(
            vector_store=_make_store([]),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("test", top_k=5)
        assert got == []


# ── Keyword Boost Tests ────────────────────────────────────────────────


class TestKeywordBoost:
    """Tests for keyword match re-ranking."""

    def test_keyword_match_boosts_score(self):
        """Chunks containing query keywords should rank higher."""
        results = [
            _result("id-1", 0.8, "Using some other settings"),
            _result("id-2", 0.75, "DEFAULT_CHUNK_SIZE = 512 default chunk size"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("default chunk size", top_k=5)
        # id-2 has 3 keyword matches ("default", "chunk", "size") boosted to 0.90
        # id-1 has 0 keyword matches, stays at 0.80
        assert got[0].chunk_id == "id-2", (
            "Chunk with more keyword matches should rank first after boost"
        )

    def test_boost_adds_to_score(self):
        """Boosted score should increase beyond the original score."""
        results = [
            _result("id-1", 0.99, "default chunk size default chunk size"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("default chunk size", top_k=5)
        assert got[0].score > 0.99, "Keyword boost should increase score"

    def test_stop_words_excluded_from_boost(self):
        """Common stop words should not count as keyword matches."""
        results = [
            _result("id-1", 0.8, "the and what"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("what is the", top_k=5)
        # All query words are stop words, so no boost applied
        assert got[0].score == 0.8, "Stop words should not boost score"

    def test_short_words_excluded(self):
        """Words shorter than 3 characters should not boost."""
        results = [
            _result("id-1", 0.8, "a b c is on"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("a b c is on it", top_k=5)
        assert got[0].score == 0.8, "Short words should not boost score"

    def test_case_insensitive_matching(self):
        """Keyword matching should be case-insensitive."""
        results = [
            _result("id-1", 0.7, "DEFAULT_CHUNK_SIZE = 512"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("default chunk size", top_k=5)
        # "default", "chunk", "size" all appear in "DEFAULT_CHUNK_SIZE"
        assert got[0].score > 0.7, "Case-insensitive match should boost"


# ── Over-fetch Tests ───────────────────────────────────────────────────


class TestOverfetch:
    """Tests for the over-fetch → dedup → trim pipeline."""

    def test_overfetch_factor_applied(self):
        """Vector store should receive top_k * overfetch_factor as limit."""

        class TrackingStore:
            def __init__(self):
                self.last_limit = None

            def search(self, vector, limit=5):
                self.last_limit = limit
                return []

        store = TrackingStore()
        retriever = Retriever(
            vector_store=store,
            embedding_generator=_make_embedding(),
        )
        retriever.retrieve("test", top_k=5)
        assert store.last_limit == 5 * Retriever._OVERFETCH_FACTOR

    def test_results_trimmed_to_top_k(self):
        """Final results should be trimmed to top_k after dedup."""
        results = [_result(f"id-{i}", 0.9 - i * 0.01, f"Unique content {i}") for i in range(20)]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("test", top_k=5)
        assert len(got) == 5, "Should trim to top_k"

    def test_ranks_reassigned_after_reranking(self):
        """Rank field should reflect final position (1-based)."""
        results = [
            _result("id-1", 0.9, "Alpha content"),
            _result("id-2", 0.8, "Beta content"),
            _result("id-3", 0.7, "Gamma content"),
        ]
        retriever = Retriever(
            vector_store=_make_store(results),
            embedding_generator=_make_embedding(),
        )
        got = retriever.retrieve("test", top_k=3)
        ranks = [r.rank for r in got]
        assert ranks == [1, 2, 3], "Ranks should be 1-based sequential"
