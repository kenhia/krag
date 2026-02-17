"""Evaluation runner — orchestrates eval queries through QueryEngine.

Runs each query sequentially, evaluates checks, aggregates results.
"""

from dataclasses import dataclass

from krag.evaluation.checks import CheckResult, evaluate_check
from krag.evaluation.loader import EvalQuery
from krag.orchestration.query_engine import QueryEngine


@dataclass
class EvalQueryResult:
    """Result of running a single eval query."""

    query: str
    answer: str
    sources: list[str]  # source paths as strings
    checks: list[CheckResult]
    passed: bool  # all checks passed


class EvalRunner:
    """Runs evaluation queries through QueryEngine and checks results.

    Processes queries sequentially (LLM is not concurrent).
    """

    def __init__(self, query_engine: QueryEngine) -> None:
        """Initialize runner.

        Args:
            query_engine: Configured QueryEngine instance.
        """
        self.query_engine = query_engine

    def run(self, queries: list[EvalQuery]) -> list[EvalQueryResult]:
        """Execute all eval queries and check results.

        Args:
            queries: List of EvalQuery test cases.

        Returns:
            List of EvalQueryResult with pass/fail for each query.
        """
        results: list[EvalQueryResult] = []

        for eval_query in queries:
            # Run query through the engine
            response = self.query_engine.query(eval_query.query)

            # Collect source paths
            source_paths = [str(s.file_path) for s in response.sources]

            # Evaluate each check
            check_results = [
                evaluate_check(check, response.answer, response.sources)
                for check in eval_query.checks
            ]

            # Overall pass = all checks pass
            all_passed = all(cr.passed for cr in check_results)

            results.append(
                EvalQueryResult(
                    query=eval_query.query,
                    answer=response.answer,
                    sources=source_paths,
                    checks=check_results,
                    passed=all_passed,
                )
            )

        return results
