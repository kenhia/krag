"""Unit tests for Retriever metadata-based score boosting.

T081: Chunk with matching function_name gets score boost.
T086: Retriever._metadata_boost() boosts on function_name/class_name matches.
"""

from __future__ import annotations

from krag.retrieval.retriever import Retriever


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
    function_name: str | None = None,
    class_name: str | None = None,
    language: str | None = None,
) -> dict:
    """Build a vector-store result dict with optional code metadata."""
    payload = {
        "content": content,
        "file_path": file_path,
        "chunk_index": chunk_index,
        "file_type": ".py",
    }
    if function_name is not None:
        payload["function_name"] = function_name
    if class_name is not None:
        payload["class_name"] = class_name
    if language is not None:
        payload["language"] = language
    return {
        "id": chunk_id,
        "score": score,
        "payload": payload,
    }


class TestMetadataBoost:
    """T081/T086: Metadata-based score boosting tests."""

    def test_function_name_match_gets_boost(self) -> None:
        """T081: Querying 'deduplicate' boosts chunk with function_name='_deduplicate'."""
        store = _make_store(
            [
                _result("a", 0.80, "def _deduplicate(self):", function_name="_deduplicate"),
                _result("b", 0.85, "Results are sorted by score"),
            ]
        )
        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("how does deduplicate work", top_k=5)

        # Chunk "a" should be boosted above "b" despite lower base score
        assert results[0].chunk_id == "a"
        assert results[0].score > 0.80  # score should be boosted

    def test_class_name_match_gets_boost(self) -> None:
        """T081: Querying 'Retriever' boosts chunk with class_name='Retriever'."""
        store = _make_store(
            [
                _result("a", 0.80, "class Retriever:", class_name="Retriever"),
                _result("b", 0.85, "Some generic content with no class reference"),
            ]
        )
        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("what does Retriever do", top_k=5)

        assert results[0].chunk_id == "a"

    def test_combined_function_and_class_boost(self) -> None:
        """T086: Both function_name and class_name matching gives larger boost."""
        store = _make_store(
            [
                _result(
                    "a",
                    0.75,
                    "class Retriever:\n    def retrieve(self):",
                    function_name="retrieve",
                    class_name="Retriever",
                ),
                _result("b", 0.85, "some unrelated content about retrievers"),
            ]
        )
        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("Retriever retrieve method", top_k=5)

        assert results[0].chunk_id == "a"

    def test_no_metadata_no_extra_boost(self) -> None:
        """T086: Chunks without metadata don't get metadata boost."""
        store = _make_store(
            [
                _result("a", 0.90, "highest scoring generic content"),
                _result("b", 0.70, "lower scoring content"),
            ]
        )
        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("generic question", top_k=5)

        # Order preserved — no metadata boost to change anything
        assert results[0].chunk_id == "a"
        assert results[1].chunk_id == "b"

    def test_partial_name_match_still_boosts(self) -> None:
        """T086: Query containing part of function_name still triggers boost."""
        store = _make_store(
            [
                _result("a", 0.80, "def calculate_total(items):", function_name="calculate_total"),
                _result("b", 0.85, "The total is computed differently"),
            ]
        )
        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("calculate total", top_k=5)

        # "calculate" and "total" both appear in function_name and content
        assert results[0].chunk_id == "a"

    def test_metadata_boost_capped_at_one(self) -> None:
        """T086: Boosted score never exceeds 1.0."""
        store = _make_store(
            [
                _result(
                    "a",
                    0.99,
                    "def foo(): pass foo foo foo",
                    function_name="foo",
                ),
            ]
        )
        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("foo foo foo", top_k=5)

        assert results[0].score <= 1.0
