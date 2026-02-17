"""Unit tests for evaluation reporter.

Tests generate_report(), format_json(), format_summary().
Should FAIL until reporter.py is implemented.
"""

import json


class TestEvalReporter:
    """Tests for evaluation reporting functions."""

    def _make_results(self, passed_count: int = 2, failed_count: int = 1) -> list:
        """Create mock EvalQueryResult list."""
        from krag.evaluation.checks import CheckResult
        from krag.evaluation.loader import EvalCheck
        from krag.evaluation.runner import EvalQueryResult

        results = []
        for i in range(passed_count):
            results.append(
                EvalQueryResult(
                    query=f"passed_q{i}",
                    answer=f"answer{i}",
                    sources=["/test/doc.md"],
                    checks=[
                        CheckResult(
                            check=EvalCheck(type="substring", value="answer"),
                            passed=True,
                            detail="Found",
                        )
                    ],
                    passed=True,
                )
            )
        for i in range(failed_count):
            results.append(
                EvalQueryResult(
                    query=f"failed_q{i}",
                    answer=f"wrong{i}",
                    sources=[],
                    checks=[
                        CheckResult(
                            check=EvalCheck(type="substring", value="expected"),
                            passed=False,
                            detail="Not found",
                        )
                    ],
                    passed=False,
                )
            )
        return results

    def test_generate_report_counts(self) -> None:
        """Test that generate_report computes correct counts."""
        from krag.evaluation.reporter import generate_report

        results = self._make_results(passed_count=3, failed_count=2)
        report = generate_report(results)
        assert report.total == 5
        assert report.passed == 3
        assert report.failed == 2
        assert report.pass_rate == 0.6

    def test_generate_report_all_pass(self) -> None:
        """Test report when all queries pass."""
        from krag.evaluation.reporter import generate_report

        results = self._make_results(passed_count=3, failed_count=0)
        report = generate_report(results)
        assert report.pass_rate == 1.0
        assert report.failed == 0

    def test_format_json_is_valid_json(self) -> None:
        """Test that format_json produces valid JSON."""
        from krag.evaluation.reporter import format_json, generate_report

        results = self._make_results()
        report = generate_report(results)
        json_str = format_json(report)
        parsed = json.loads(json_str)
        assert "total" in parsed
        assert "passed" in parsed
        assert "failed" in parsed
        assert "results" in parsed

    def test_format_json_includes_results(self) -> None:
        """Test that JSON output includes per-query results."""
        from krag.evaluation.reporter import format_json, generate_report

        results = self._make_results(passed_count=1, failed_count=1)
        report = generate_report(results)
        json_str = format_json(report)
        parsed = json.loads(json_str)
        assert len(parsed["results"]) == 2

    def test_format_summary_is_string(self) -> None:
        """Test that format_summary returns a human-readable string."""
        from krag.evaluation.reporter import format_summary, generate_report

        results = self._make_results()
        report = generate_report(results)
        summary = format_summary(report)
        assert isinstance(summary, str)
        assert "3" in summary  # total count
        assert "2" in summary  # passed count

    def test_format_summary_shows_failures(self) -> None:
        """Test that summary highlights failed queries."""
        from krag.evaluation.reporter import format_summary, generate_report

        results = self._make_results(passed_count=0, failed_count=2)
        report = generate_report(results)
        summary = format_summary(report)
        assert "fail" in summary.lower()
