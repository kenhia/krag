"""Context relevance critic — scores retrieved chunks for relevance.

Scores each chunk individually using an LLM call with a constrained prompt
requesting a single digit 0–5. Chunks below the threshold are filtered out
before LLM synthesis.

Behaviour rules:
- Chunks < 50 chars → bypass scoring, assign threshold score (FR-035)
- LLM error → fail-open, assign threshold score (FR-034)
- Score parse failure → fail-open, assign threshold score (FR-034)
- Disabled → bypass all, no LLM calls (FR-032)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from krag.models.query_result import QueryResult
    from krag.synthesis.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Minimum chunk length for scoring — shorter chunks bypass the critic
_MIN_CHUNK_LENGTH = 50

# Regex to extract a single digit 0-5 from LLM response
_SCORE_PATTERN = re.compile(r"\b([0-5])\b")

# Prompt template per R-03 specification
_CRITIC_PROMPT = (
    "Rate how relevant the following text is to the question on a scale of 0-5.\n"
    "0 = completely irrelevant, 5 = directly answers the question.\n"
    "\n"
    "Question: {query}\n"
    "\n"
    "Text: {chunk_content}\n"
    "\n"
    "Relevance score (respond with ONLY a single number 0-5):"
)


@dataclass
class ScoredChunk:
    """A retrieved chunk annotated with a critic relevance score.

    Attributes:
        chunk: The original QueryResult.
        critic_score: Relevance score 0–5.
        bypassed: True if scoring was skipped (too short, error, or disabled).
        passed: Whether score >= threshold.
    """

    chunk: QueryResult
    critic_score: int
    bypassed: bool
    passed: bool


class RelevanceCritic:
    """Scores retrieved chunks for relevance to the query.

    Each chunk is scored individually via an LLM call. Chunks below the
    threshold are filtered out. The critic fails open: errors result in
    the chunk being assigned the threshold score and included.

    Args:
        llm_client: The LLM used for scoring.
        threshold: Minimum passing score (0–5, default 3).
        enabled: Whether the critic is active. When False, all chunks
            bypass scoring and are included.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        threshold: int = 3,
        enabled: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.threshold = threshold
        self.enabled = enabled

    def score_chunks(
        self,
        query: str,
        chunks: list[QueryResult],
    ) -> list[ScoredChunk]:
        """Score each chunk for relevance to the query.

        Args:
            query: The user's query text.
            chunks: Retrieved chunks to score.

        Returns:
            List of ScoredChunk with scores and pass/fail status.
        """
        if not chunks:
            return []

        # When disabled, bypass all chunks without LLM calls
        if not self.enabled:
            logger.debug("Critic disabled — bypassing all %d chunks", len(chunks))
            return [
                ScoredChunk(
                    chunk=c,
                    critic_score=self.threshold,
                    bypassed=True,
                    passed=True,
                )
                for c in chunks
            ]

        scored: list[ScoredChunk] = []
        for chunk in chunks:
            scored.append(self._score_single(query, chunk))

        return scored

    def filter_chunks(self, scored: list[ScoredChunk]) -> list[QueryResult]:
        """Filter scored chunks, keeping only those that passed.

        Args:
            scored: List of scored chunks from score_chunks().

        Returns:
            List of original QueryResult objects that passed the threshold.
        """
        return [s.chunk for s in scored if s.passed]

    def _score_single(self, query: str, chunk: QueryResult) -> ScoredChunk:
        """Score a single chunk, handling bypass and error cases."""
        # Short-chunk bypass (FR-035)
        if len(chunk.chunk_content) < _MIN_CHUNK_LENGTH:
            logger.debug(
                "Chunk %s too short (%d chars) — bypassing critic",
                chunk.chunk_id,
                len(chunk.chunk_content),
            )
            return ScoredChunk(
                chunk=chunk,
                critic_score=self.threshold,
                bypassed=True,
                passed=True,
            )

        # Build scoring prompt per R-03
        prompt_text = _CRITIC_PROMPT.format(
            query=query,
            chunk_content=chunk.chunk_content,
        )
        messages = [{"role": "user", "content": prompt_text}]

        try:
            response = self.llm_client.generate(
                messages=messages,
                temperature=0.0,
                max_tokens=4,
            )
        except Exception:
            logger.warning(
                "Critic LLM error for chunk %s — fail-open with threshold score",
                chunk.chunk_id,
                exc_info=True,
            )
            return ScoredChunk(
                chunk=chunk,
                critic_score=self.threshold,
                bypassed=True,
                passed=True,
            )

        # Parse score from response
        score = self._parse_score(response)
        if score is None:
            logger.warning(
                "Could not parse critic score from response %r for chunk %s — fail-open",
                response,
                chunk.chunk_id,
            )
            return ScoredChunk(
                chunk=chunk,
                critic_score=self.threshold,
                bypassed=True,
                passed=True,
            )

        passed = score >= self.threshold
        logger.debug(
            "Chunk %s scored %d (threshold %d) — %s",
            chunk.chunk_id,
            score,
            self.threshold,
            "pass" if passed else "fail",
        )
        return ScoredChunk(
            chunk=chunk,
            critic_score=score,
            bypassed=False,
            passed=passed,
        )

    @staticmethod
    def _parse_score(response: str) -> int | None:
        """Parse a relevance score 0-5 from LLM response.

        Uses regex ``\\b([0-5])\\b`` on stripped output. Returns None
        if no valid score can be extracted.
        """
        match = _SCORE_PATTERN.search(response.strip())
        if match:
            return int(match.group(1))
        return None
