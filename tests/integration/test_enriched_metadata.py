"""Integration tests for enriched chunk metadata in retrieval.

T083: End-to-end query with metadata boosting and enhanced display.
"""

from __future__ import annotations

from pathlib import Path

from krag.models.query_result import QueryResult


def _make_store(results: list[dict]):
    """Mock vector store."""

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


def _result_with_metadata(
    chunk_id: str,
    score: float,
    content: str,
    file_path: str,
    function_name: str | None = None,
    class_name: str | None = None,
    language: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict:
    """Build a vector-store result dict with full code metadata."""
    payload = {
        "content": content,
        "file_path": file_path,
        "chunk_index": 0,
        "file_type": ".py",
    }
    if function_name is not None:
        payload["function_name"] = function_name
    if class_name is not None:
        payload["class_name"] = class_name
    if language is not None:
        payload["language"] = language
    if start_line is not None:
        payload["start_line"] = start_line
    if end_line is not None:
        payload["end_line"] = end_line
    return {
        "id": chunk_id,
        "score": score,
        "payload": payload,
    }


class TestEnrichedMetadataIntegration:
    """T083: End-to-end enriched metadata tests."""

    def test_retriever_populates_extended_fields(self) -> None:
        """T083a: Retriever populates language, function_name, etc. from payload."""
        from krag.retrieval.retriever import Retriever

        store = _make_store(
            [
                _result_with_metadata(
                    "chunk-1",
                    0.92,
                    "def _deduplicate(self, results):\n    seen = {}",
                    "/src/krag/retrieval/retriever.py",
                    function_name="_deduplicate",
                    class_name="Retriever",
                    language="python",
                    start_line=45,
                    end_line=68,
                ),
            ]
        )

        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("deduplicate", top_k=5)

        assert len(results) >= 1
        r = results[0]
        assert r.function_name == "_deduplicate"
        assert r.class_name == "Retriever"
        assert r.language == "python"
        assert r.start_line == 45
        assert r.end_line == 68

    def test_format_source_ref_with_full_metadata(self) -> None:
        """T083b: format_source_ref() produces structured reference from enriched result."""
        from krag.retrieval.retriever import Retriever

        store = _make_store(
            [
                _result_with_metadata(
                    "chunk-2",
                    0.88,
                    "class QueryEngine:\n    def query(self, text):\n        ...",
                    "/src/krag/orchestration/query_engine.py",
                    function_name="query",
                    class_name="QueryEngine",
                    language="python",
                    start_line=30,
                    end_line=55,
                ),
            ]
        )

        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("QueryEngine query", top_k=5)

        r = results[0]
        ref = r.format_source_ref()
        assert "QueryEngine.query()" in ref
        assert "query_engine.py" in ref
        assert "L30" in ref
        assert "L55" in ref

    def test_metadata_boosting_changes_ranking(self) -> None:
        """T083c: Metadata boosting re-ranks results with matching symbols."""
        from krag.retrieval.retriever import Retriever

        store = _make_store(
            [
                _result_with_metadata(
                    "generic",
                    0.88,
                    "Documentation about the query system",
                    "/docs/query.md",
                ),
                _result_with_metadata(
                    "code-match",
                    0.82,
                    "def execute_query(self):\n    return self.engine.run()",
                    "/src/krag/query.py",
                    function_name="execute_query",
                    class_name=None,
                    start_line=10,
                    end_line=15,
                ),
            ]
        )

        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("execute_query function", top_k=5)

        # Code chunk with function_name match should be boosted to top
        assert results[0].chunk_id == "code-match"

    def test_mixed_results_some_with_metadata(self) -> None:
        """T083d: Mix of results with and without metadata works cleanly."""
        from krag.retrieval.retriever import Retriever

        store = _make_store(
            [
                _result_with_metadata(
                    "doc",
                    0.90,
                    "# Architecture\nThe system uses...",
                    "/docs/arch.md",
                ),
                _result_with_metadata(
                    "code",
                    0.85,
                    "class Indexer:\n    def index(self):",
                    "/src/indexer.py",
                    function_name="index",
                    class_name="Indexer",
                    language="python",
                    start_line=1,
                    end_line=20,
                ),
            ]
        )

        retriever = Retriever(store, _make_embedding())
        results = retriever.retrieve("architecture overview", top_k=5)

        # All results should be valid QueryResult objects
        for r in results:
            assert isinstance(r, QueryResult)
            ref = r.format_source_ref()
            assert isinstance(ref, str)
            assert "None" not in ref

    def test_display_format_uses_source_ref(self) -> None:
        """T083e: format_source_ref() output is suitable for query display."""
        result = QueryResult(
            chunk_id="test-1",
            score=0.95,
            rank=1,
            chunk_content="def validate(self, data): ...",
            file_path=Path("/src/app/validator.py"),
            chunk_index=0,
            file_type=".py",
            function_name="validate",
            class_name="Validator",
            start_line=15,
            end_line=30,
        )

        ref = result.format_source_ref()
        # Should produce something like: "Validator.validate() at validator.py:L15-L30"
        assert "Validator.validate()" in ref
        assert "validator.py" in ref
        assert "L15" in ref
        assert "L30" in ref
