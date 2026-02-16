"""Evaluation check implementations.

Evaluates individual checks (substring, source_cited, no_hallucination)
against query answers and sources.
"""

from dataclasses import dataclass

from krag.evaluation.loader import EvalCheck
from krag.models.query_result import QueryResult
from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE

# Phrases that indicate the model acknowledged insufficient context
_INSUFFICIENT_PHRASES = [
    INSUFFICIENT_CONTEXT_PHRASE.lower(),
    "i don't know",
    "not enough information",
    "cannot answer",
    "don't have enough",
]


@dataclass
class CheckResult:
    """Result of a single check evaluation."""

    check: EvalCheck
    passed: bool
    detail: str  # human-readable explanation


def evaluate_check(
    check: EvalCheck,
    answer: str,
    sources: list[QueryResult],
) -> CheckResult:
    """Evaluate a single check against an answer.

    Check types:
    - "substring": case-insensitive substring match of check.value in answer.
    - "source_cited": check.value appears in any source file_path.
    - "no_hallucination": answer acknowledges lack of info, OR answer has
      supporting sources.

    Args:
        check: The check to evaluate.
        answer: The LLM-generated answer string.
        sources: List of retrieved source QueryResult objects.

    Returns:
        CheckResult with pass/fail and detail.
    """
    if check.type == "substring":
        return _check_substring(check, answer)
    elif check.type == "source_cited":
        return _check_source_cited(check, answer, sources)
    elif check.type == "no_hallucination":
        return _check_no_hallucination(check, answer, sources)
    else:
        return CheckResult(
            check=check,
            passed=False,
            detail=f"Unknown check type: {check.type}",
        )


def _check_substring(check: EvalCheck, answer: str) -> CheckResult:
    """Check if value appears as substring in answer (case-insensitive)."""
    if check.value is None:
        return CheckResult(check=check, passed=False, detail="substring check requires a value")

    found = check.value.lower() in answer.lower()
    detail = f"Found '{check.value}' in answer" if found else f"'{check.value}' not found in answer"
    return CheckResult(check=check, passed=found, detail=detail)


def _check_source_cited(check: EvalCheck, answer: str, sources: list[QueryResult]) -> CheckResult:
    """Check if source path appears in any retrieved source."""
    if check.value is None:
        return CheckResult(check=check, passed=False, detail="source_cited check requires a value")

    for source in sources:
        if check.value in str(source.file_path):
            return CheckResult(
                check=check,
                passed=True,
                detail=f"Source '{check.value}' found in {source.file_path}",
            )
    return CheckResult(
        check=check,
        passed=False,
        detail=f"Source '{check.value}' not found in any retrieved source",
    )


def _check_no_hallucination(
    check: EvalCheck, answer: str, sources: list[QueryResult]
) -> CheckResult:
    """Check for hallucination.

    Passes if:
    - Answer acknowledges lack of knowledge ("I don't know", etc.), OR
    - Answer does NOT acknowledge lack of knowledge AND sources are non-empty
      (answer is grounded in retrieved context).

    Fails if:
    - Answer provides substantive info but has no sources backing it.
    """
    answer_lower = answer.lower()
    acknowledges = any(phrase in answer_lower for phrase in _INSUFFICIENT_PHRASES)

    if acknowledges:
        return CheckResult(
            check=check,
            passed=True,
            detail="Answer acknowledges insufficient context",
        )

    if sources:
        return CheckResult(
            check=check,
            passed=True,
            detail=f"Answer has {len(sources)} supporting sources",
        )

    return CheckResult(
        check=check,
        passed=False,
        detail="Answer provides information without supporting sources (possible hallucination)",
    )
