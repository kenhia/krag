"""Evaluation report generation.

Produces JSON output for stdout and human-readable summary for stderr.
"""

import json
from dataclasses import dataclass

from krag.evaluation.runner import EvalQueryResult


@dataclass
class EvalReport:
    """Complete evaluation report."""

    total: int
    passed: int
    failed: int
    pass_rate: float
    results: list[EvalQueryResult]


def generate_report(results: list[EvalQueryResult]) -> EvalReport:
    """Generate summary report from eval results.

    Args:
        results: List of per-query evaluation results.

    Returns:
        EvalReport with aggregate counts and pass rate.
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = passed / total if total > 0 else 0.0

    return EvalReport(
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=pass_rate,
        results=results,
    )


def format_json(report: EvalReport) -> str:
    """Format report as JSON for stdout.

    Args:
        report: The evaluation report.

    Returns:
        JSON string with report data.
    """
    data = {
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "pass_rate": report.pass_rate,
        "results": [
            {
                "query": r.query,
                "answer": r.answer,
                "sources": r.sources,
                "llm_used": r.llm_used,
                "route_reason": r.route_reason,
                "passed": r.passed,
                "checks": [
                    {
                        "type": c.check.type,
                        "value": c.check.value,
                        "passed": c.passed,
                        "detail": c.detail,
                    }
                    for c in r.checks
                ],
            }
            for r in report.results
        ],
    }
    return json.dumps(data, indent=2)


def format_summary(report: EvalReport) -> str:
    """Format human-readable summary for stderr.

    Args:
        report: The evaluation report.

    Returns:
        Multi-line summary string.
    """
    lines: list[str] = []
    lines.append(f"Evaluation: {report.passed}/{report.total} passed ({report.pass_rate:.0%})")

    if report.failed > 0:
        lines.append(f"  {report.failed} failed:")
        for r in report.results:
            if not r.passed:
                failed_checks = [c for c in r.checks if not c.passed]
                check_details = "; ".join(c.detail for c in failed_checks)
                llm_info = f" [llm={r.llm_used}]" if r.llm_used else ""
                lines.append(f"    - {r.query}{llm_info}: {check_details}")

    return "\n".join(lines)
