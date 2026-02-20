"""Evaluation runner — orchestrates eval queries through QueryEngine.

Runs each query sequentially, evaluates checks, aggregates results.
Supports optional LLM pool routing (per-query or global override).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from krag.evaluation.checks import CheckResult, evaluate_check
from krag.evaluation.loader import EvalQuery
from krag.orchestration.query_engine import QueryEngine

if TYPE_CHECKING:
    from krag.synthesis.llm_pool import LLMPool

logger = logging.getLogger(__name__)


@dataclass
class EvalQueryResult:
    """Result of running a single eval query."""

    query: str
    answer: str
    sources: list[str]  # source paths as strings
    checks: list[CheckResult]
    passed: bool  # all checks passed
    llm_used: str | None = None  # "text", "code", or None (default engine)
    route_reason: str | None = None  # why this LLM was selected


class EvalRunner:
    """Runs evaluation queries through QueryEngine and checks results.

    Processes queries sequentially (LLM is not concurrent).
    Supports optional LLM pool routing for multi-model evaluation.
    """

    def __init__(
        self,
        query_engine: QueryEngine,
        llm_pool: LLMPool | None = None,
        llm_override: str | None = None,
    ) -> None:
        """Initialize runner.

        Args:
            query_engine: Configured QueryEngine instance.
            llm_pool: Optional LLM pool for multi-model routing.
            llm_override: Global LLM override ("text" or "code").
                Per-query llm field takes precedence over this.
        """
        self.query_engine = query_engine
        self.llm_pool = llm_pool
        self.llm_override = llm_override

    def run(self, queries: list[EvalQuery]) -> list[EvalQueryResult]:
        """Execute all eval queries and check results.

        Args:
            queries: List of EvalQuery test cases.

        Returns:
            List of EvalQueryResult with pass/fail for each query.
        """
        results: list[EvalQueryResult] = []

        for eval_query in queries:
            # Determine effective LLM override: per-query > global > None
            effective_llm = eval_query.llm or self.llm_override

            if self.llm_pool is not None:
                result = self._run_with_pool(eval_query, effective_llm)
            else:
                result = self._run_default(eval_query)

            results.append(result)

        return results

    def _run_default(self, eval_query: EvalQuery) -> EvalQueryResult:
        """Run query through default QueryEngine (single-LLM path)."""
        response = self.query_engine.query(eval_query.query)
        source_paths = [str(s.file_path) for s in response.sources]

        check_results = [
            evaluate_check(check, response.answer, response.sources) for check in eval_query.checks
        ]
        all_passed = all(cr.passed for cr in check_results)

        return EvalQueryResult(
            query=eval_query.query,
            answer=response.answer,
            sources=source_paths,
            checks=check_results,
            passed=all_passed,
            llm_used=None,
            route_reason="default query engine",
        )

    def _run_with_pool(self, eval_query: EvalQuery, llm_override: str | None) -> EvalQueryResult:
        """Run query through LLMPool with routing."""
        assert self.llm_pool is not None  # noqa: S101

        # Retrieve chunks first (needed for routing decision)
        retriever = self.query_engine.retriever
        results = retriever.retrieve(
            eval_query.query,
            top_k=self.query_engine.top_k,
            similarity_threshold=self.query_engine.similarity_threshold,
        )
        source_paths = [str(s.file_path) for s in results]

        if not results:
            from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE

            check_results = [
                evaluate_check(check, INSUFFICIENT_CONTEXT_PHRASE, [])
                for check in eval_query.checks
            ]
            return EvalQueryResult(
                query=eval_query.query,
                answer=INSUFFICIENT_CONTEXT_PHRASE,
                sources=[],
                checks=check_results,
                passed=all(cr.passed for cr in check_results),
                llm_used=None,
                route_reason="no results retrieved",
            )

        # Determine route
        route = self.llm_pool.determine_route(results, override=llm_override)
        route_reason = f"override={llm_override}" if llm_override else "auto-routed"

        # Auto-couple preset for code route
        preset_name = self.query_engine.prompt_builder.preset_name
        if not llm_override and route == "code":
            preset_name = "code"

        # Build prompt & generate
        from krag.synthesis.prompt_builder import PromptBuilder

        prompt_builder = PromptBuilder(
            max_context_length=self.query_engine.prompt_builder.max_context_length,
            path_aliases=self.query_engine.prompt_builder.path_aliases,
            preset_name=preset_name,
            system_prompt_override=self.query_engine.prompt_builder.system_prompt_override,
        )
        messages = prompt_builder.build(eval_query.query, results)
        answer, llm_used = self.llm_pool.route_and_generate(
            messages, results, llm_override=llm_override
        )

        logger.info("Eval query routed to %s LLM: %s", llm_used, eval_query.query[:60])

        check_results = [evaluate_check(check, answer, results) for check in eval_query.checks]
        all_passed = all(cr.passed for cr in check_results)

        return EvalQueryResult(
            query=eval_query.query,
            answer=answer,
            sources=source_paths,
            checks=check_results,
            passed=all_passed,
            llm_used=llm_used,
            route_reason=route_reason,
        )
