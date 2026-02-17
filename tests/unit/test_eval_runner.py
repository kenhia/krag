"""Unit tests for EvalRunner.

Tests sequential execution, check aggregation, passed flag.
Should FAIL until runner.py is implemented.
"""

from pathlib import Path
from unittest.mock import MagicMock

from krag.models.query_result import QueryResult


def _make_mock_query_engine(answer: str = "Mock answer", sources: list | None = None) -> MagicMock:
    """Create a mock QueryEngine that returns fixed responses."""
    from krag.orchestration.query_engine import QueryResponse

    mock = MagicMock()
    mock_sources = sources or [
        QueryResult(
            chunk_id="1",
            score=0.9,
            rank=1,
            chunk_content="Content.",
            file_path=Path("/test/doc.md"),
            chunk_index=0,
            file_type="markdown",
        )
    ]
    mock.query.return_value = QueryResponse(
        answer=answer,
        sources=mock_sources,
        query="test",
        prompt="[]",
    )
    return mock


class TestEvalRunner:
    """Tests for EvalRunner.run()."""

    def test_runner_runs_all_queries(self) -> None:
        """Test that runner executes all provided queries."""
        from krag.evaluation.loader import EvalCheck, EvalQuery
        from krag.evaluation.runner import EvalRunner

        mock_engine = _make_mock_query_engine()
        runner = EvalRunner(query_engine=mock_engine)

        queries = [
            EvalQuery(query="Q1", checks=[EvalCheck(type="substring", value="Mock")]),
            EvalQuery(query="Q2", checks=[EvalCheck(type="substring", value="Mock")]),
            EvalQuery(query="Q3", checks=[EvalCheck(type="substring", value="Mock")]),
        ]

        results = runner.run(queries)
        assert len(results) == 3
        assert mock_engine.query.call_count == 3

    def test_runner_result_contains_query(self) -> None:
        """Test that each result records the original query."""
        from krag.evaluation.loader import EvalCheck, EvalQuery
        from krag.evaluation.runner import EvalRunner

        mock_engine = _make_mock_query_engine()
        runner = EvalRunner(query_engine=mock_engine)

        queries = [
            EvalQuery(query="What is RAG?", checks=[EvalCheck(type="substring", value="Mock")])
        ]
        results = runner.run(queries)
        assert results[0].query == "What is RAG?"

    def test_runner_result_contains_answer(self) -> None:
        """Test that each result records the answer."""
        from krag.evaluation.loader import EvalCheck, EvalQuery
        from krag.evaluation.runner import EvalRunner

        mock_engine = _make_mock_query_engine(answer="The answer is 42")
        runner = EvalRunner(query_engine=mock_engine)

        queries = [EvalQuery(query="Q", checks=[EvalCheck(type="substring", value="42")])]
        results = runner.run(queries)
        assert results[0].answer == "The answer is 42"

    def test_runner_passed_true_when_all_checks_pass(self) -> None:
        """Test that passed=True when all checks pass."""
        from krag.evaluation.loader import EvalCheck, EvalQuery
        from krag.evaluation.runner import EvalRunner

        mock_engine = _make_mock_query_engine(answer="Mock answer")
        runner = EvalRunner(query_engine=mock_engine)

        queries = [EvalQuery(query="Q", checks=[EvalCheck(type="substring", value="Mock")])]
        results = runner.run(queries)
        assert results[0].passed is True

    def test_runner_passed_false_when_any_check_fails(self) -> None:
        """Test that passed=False when any check fails."""
        from krag.evaluation.loader import EvalCheck, EvalQuery
        from krag.evaluation.runner import EvalRunner

        mock_engine = _make_mock_query_engine(answer="Mock answer")
        runner = EvalRunner(query_engine=mock_engine)

        queries = [
            EvalQuery(
                query="Q",
                checks=[
                    EvalCheck(type="substring", value="Mock"),
                    EvalCheck(type="substring", value="nonexistent"),
                ],
            )
        ]
        results = runner.run(queries)
        assert results[0].passed is False

    def test_runner_collects_source_paths(self) -> None:
        """Test that source paths are recorded as strings."""
        from krag.evaluation.loader import EvalCheck, EvalQuery
        from krag.evaluation.runner import EvalRunner

        mock_engine = _make_mock_query_engine()
        runner = EvalRunner(query_engine=mock_engine)

        queries = [EvalQuery(query="Q", checks=[EvalCheck(type="substring", value="Mock")])]
        results = runner.run(queries)
        assert isinstance(results[0].sources, list)
        assert all(isinstance(s, str) for s in results[0].sources)
