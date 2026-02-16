"""Unit tests for evaluation checks.

Tests evaluate_check() — substring, source_cited, no_hallucination.
Should FAIL until checks.py is implemented.
"""

from pathlib import Path

from krag.models.query_result import QueryResult


def _make_result(file_path: str = "/test/doc.md", score: float = 0.9) -> QueryResult:
    """Helper to create a QueryResult for testing."""
    return QueryResult(
        chunk_id="1",
        score=score,
        rank=1,
        chunk_content="Some content.",
        file_path=Path(file_path),
        chunk_index=0,
        file_type="markdown",
    )


class TestEvaluateCheck:
    """Tests for evaluate_check()."""

    def test_substring_match_passes(self) -> None:
        """Test substring check passes when value is in answer."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="substring", value="hello world")
        result = evaluate_check(check, answer="The answer is hello world!", sources=[])
        assert result.passed is True

    def test_substring_match_case_insensitive(self) -> None:
        """Test substring check is case-insensitive."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="substring", value="Hello")
        result = evaluate_check(check, answer="HELLO WORLD", sources=[])
        assert result.passed is True

    def test_substring_match_fails(self) -> None:
        """Test substring check fails when value is not in answer."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="substring", value="missing text")
        result = evaluate_check(check, answer="The answer is here.", sources=[])
        assert result.passed is False

    def test_source_cited_passes(self) -> None:
        """Test source_cited check passes when source path matches."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="source_cited", value="doc.md")
        sources = [_make_result("/test/doc.md")]
        result = evaluate_check(check, answer="Some answer", sources=sources)
        assert result.passed is True

    def test_source_cited_fails(self) -> None:
        """Test source_cited check fails when source path not found."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="source_cited", value="missing.md")
        sources = [_make_result("/test/doc.md")]
        result = evaluate_check(check, answer="Some answer", sources=sources)
        assert result.passed is False

    def test_no_hallucination_passes_with_insufficient_context(self) -> None:
        """Test no_hallucination passes when answer acknowledges lack of info."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck
        from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE

        check = EvalCheck(type="no_hallucination", value=None)
        result = evaluate_check(check, answer=INSUFFICIENT_CONTEXT_PHRASE, sources=[])
        assert result.passed is True

    def test_no_hallucination_passes_with_sources(self) -> None:
        """Test no_hallucination passes when answer has sources backing it."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="no_hallucination", value=None)
        sources = [_make_result()]
        result = evaluate_check(check, answer="RAG is great.", sources=sources)
        assert result.passed is True

    def test_no_hallucination_fails_without_sources_or_acknowledgement(self) -> None:
        """Test no_hallucination fails when answer provides info without sources."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="no_hallucination", value=None)
        result = evaluate_check(check, answer="Quantum computing is amazing.", sources=[])
        assert result.passed is False

    def test_check_result_has_detail(self) -> None:
        """Test that CheckResult always has a human-readable detail."""
        from krag.evaluation.checks import evaluate_check
        from krag.evaluation.loader import EvalCheck

        check = EvalCheck(type="substring", value="test")
        result = evaluate_check(check, answer="test string", sources=[])
        assert isinstance(result.detail, str)
        assert len(result.detail) > 0
