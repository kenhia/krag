"""End-to-end integration test for the evaluation pipeline.

Tests the complete flow: TOML loading → query execution → check evaluation → reporting.
"""

import json
import textwrap
from pathlib import Path


class TestEvaluationPipelineIntegration:
    """Integration tests for the complete evaluation pipeline."""

    def _make_engine(self):
        """Create a QueryEngine with mock components."""
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def search(self, vector, limit=5):
                return [
                    {
                        "id": "chunk1",
                        "score": 0.95,
                        "payload": {
                            "content": "RAG combines retrieval with generation for accurate answers.",
                            "file_path": "/test/rag-overview.md",
                            "chunk_index": 0,
                            "file_type": "markdown",
                        },
                    }
                ]

        return QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
        )

    def test_full_eval_pipeline(self, tmp_path: Path) -> None:
        """Test complete evaluation from TOML file to JSON report."""
        from krag.evaluation.loader import load_eval_file
        from krag.evaluation.reporter import format_json, generate_report
        from krag.evaluation.runner import EvalRunner

        # Create evaluation TOML
        toml_content = textwrap.dedent("""\
            [[queries]]
            query = "What is RAG?"

            [[queries.checks]]
            type = "substring"
            value = "RAG"
        """)
        eval_file = tmp_path / "eval.toml"
        eval_file.write_text(toml_content)

        # Load queries
        queries = load_eval_file(eval_file)
        assert len(queries) == 1

        # Run evaluation
        engine = self._make_engine()
        runner = EvalRunner(query_engine=engine)
        results = runner.run(queries)

        # Generate report
        report = generate_report(results)
        assert report.total == 1
        assert report.passed == 1
        assert report.failed == 0

        # Verify JSON output
        json_str = format_json(report)
        parsed = json.loads(json_str)
        assert parsed["total"] == 1
        assert parsed["passed"] == 1

    def test_eval_pipeline_with_failing_check(self, tmp_path: Path) -> None:
        """Test evaluation pipeline when a check fails."""
        from krag.evaluation.loader import load_eval_file
        from krag.evaluation.reporter import format_summary, generate_report
        from krag.evaluation.runner import EvalRunner

        toml_content = textwrap.dedent("""\
            [[queries]]
            query = "What is RAG?"

            [[queries.checks]]
            type = "substring"
            value = "this text does not exist in any answer"
        """)
        eval_file = tmp_path / "eval.toml"
        eval_file.write_text(toml_content)

        queries = load_eval_file(eval_file)
        engine = self._make_engine()
        runner = EvalRunner(query_engine=engine)
        results = runner.run(queries)

        report = generate_report(results)
        assert report.failed == 1
        assert report.pass_rate == 0.0

        summary = format_summary(report)
        assert "fail" in summary.lower()

    def test_eval_pipeline_multiple_check_types(self, tmp_path: Path) -> None:
        """Test evaluation with all check types in one query."""
        from krag.evaluation.loader import load_eval_file
        from krag.evaluation.reporter import generate_report
        from krag.evaluation.runner import EvalRunner

        toml_content = textwrap.dedent("""\
            [[queries]]
            query = "What is RAG?"

            [[queries.checks]]
            type = "substring"
            value = "RAG"

            [[queries.checks]]
            type = "source_cited"
            value = "rag-overview.md"

            [[queries.checks]]
            type = "no_hallucination"
        """)
        eval_file = tmp_path / "eval.toml"
        eval_file.write_text(toml_content)

        queries = load_eval_file(eval_file)
        engine = self._make_engine()
        runner = EvalRunner(query_engine=engine)
        results = runner.run(queries)

        report = generate_report(results)
        assert report.total == 1
        assert report.passed == 1, "All check types should pass with matching mock data"
