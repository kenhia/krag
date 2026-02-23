"""Contract test: critic prompt format and score parsing — T057.

Validates that:
1. The critic prompt template follows R-03 specification
2. Score parsing regex correctly handles all expected response formats
3. LLM call parameters (temperature, max_tokens) conform to spec
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from krag.models.query_result import QueryResult


def _make_result(
    content: str = "A meaningful chunk about query engines and retrieval systems.",
    rank: int = 1,
) -> QueryResult:
    """Create a minimal QueryResult for testing."""
    return QueryResult(
        chunk_content=content,
        file_path="/test/file.py",
        score=0.9,
        chunk_id=f"chunk-{rank}",
        rank=rank,
        chunk_index=0,
        file_type=".py",
    )


class TestCriticPromptContract:
    """Contract: critic prompt template matches R-03 specification."""

    def test_prompt_contains_query(self) -> None:
        """The scoring prompt includes the user's query text."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = "3"
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        critic.score_chunks("How does embedding work?", [_make_result()])

        call_kwargs = llm.generate.call_args
        messages = call_kwargs.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert "How does embedding work?" in prompt_text

    def test_prompt_contains_chunk_content(self) -> None:
        """The scoring prompt includes the chunk text being evaluated."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = "4"
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        result = _make_result(
            content="Vector similarity search uses cosine distance to find nearest neighbours"
        )
        critic.score_chunks("query", [result])

        call_kwargs = llm.generate.call_args
        messages = call_kwargs.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert (
            "Vector similarity search uses cosine distance to find nearest neighbours"
            in prompt_text
        )

    def test_prompt_contains_scale_reference(self) -> None:
        """The scoring prompt references the 0-5 scale."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = "3"
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        critic.score_chunks("query", [_make_result()])

        call_kwargs = llm.generate.call_args
        messages = call_kwargs.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert "0-5" in prompt_text

    def test_prompt_includes_score_anchors(self) -> None:
        """The prompt includes anchor descriptions for 0 and 5."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = "3"
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        critic.score_chunks("query", [_make_result()])

        call_kwargs = llm.generate.call_args
        messages = call_kwargs.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert "completely irrelevant" in prompt_text.lower() or "irrelevant" in prompt_text.lower()

    def test_prompt_instructs_single_number(self) -> None:
        """The prompt asks for ONLY a single number response."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = "3"
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        critic.score_chunks("query", [_make_result()])

        call_kwargs = llm.generate.call_args
        messages = call_kwargs.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        # R-03: "respond with ONLY a single number 0-5"
        assert "only" in prompt_text.lower()
        assert "number" in prompt_text.lower() or "digit" in prompt_text.lower()


class TestCriticLLMParameters:
    """Contract: LLM parameters match R-03 specification."""

    def test_temperature_is_zero(self) -> None:
        """Critic uses temperature=0.0 for deterministic scoring (R-03)."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = "3"
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        critic.score_chunks("query", [_make_result()])

        call_kwargs = llm.generate.call_args
        assert call_kwargs.kwargs["temperature"] == 0.0

    def test_max_tokens_is_four(self) -> None:
        """Critic uses max_tokens=4 for fast output (R-03)."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = "3"
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        critic.score_chunks("query", [_make_result()])

        call_kwargs = llm.generate.call_args
        assert call_kwargs.kwargs["max_tokens"] == 4


class TestScoreParsingContract:
    """Contract: score parsing regex handles all R-03 specified scenarios."""

    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            # Clean digit responses
            ("0", 0),
            ("1", 1),
            ("2", 2),
            ("3", 3),
            ("4", 4),
            ("5", 5),
            # Whitespace variations
            (" 3 ", 3),
            ("\n4\n", 4),
            ("\t2\t", 2),
            # Verbose LLM responses (R-03: regex handles these)
            ("I'd rate this a 4", 4),
            ("Score: 2", 2),
            ("The relevance is 5 out of 5", 5),
            ("I would give this a 3 on the scale", 3),
        ],
    )
    def test_valid_scores_parsed(self, response: str, expected: int) -> None:
        """Valid responses in various formats parse to correct scores."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = response
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].critic_score == expected
        assert scored[0].bypassed is False

    @pytest.mark.parametrize(
        "response",
        [
            "",  # empty
            "I cannot rate this",  # no digit 0-5
            "high",  # text only
            "ten",  # spelled out number
            "6",  # out of range (only 0-5 valid)
            "7",  # out of range
        ],
    )
    def test_invalid_responses_fail_open(self, response: str) -> None:
        """Unparseable responses result in threshold score and bypassed=True."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.return_value = response
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].critic_score == 3  # threshold score
        assert scored[0].bypassed is True
        assert scored[0].passed is True  # fail-open


class TestScoredChunkContract:
    """Contract: ScoredChunk dataclass has required fields."""

    def test_scored_chunk_has_required_fields(self) -> None:
        """ScoredChunk exposes chunk, critic_score, bypassed, passed."""
        from krag.critic.relevance_critic import ScoredChunk

        result = _make_result()
        sc = ScoredChunk(chunk=result, critic_score=4, bypassed=False, passed=True)

        assert sc.chunk is result
        assert sc.critic_score == 4
        assert sc.bypassed is False
        assert sc.passed is True

    def test_scored_chunk_preserves_original_chunk(self) -> None:
        """The original QueryResult is accessible through the chunk field."""
        from krag.critic.relevance_critic import ScoredChunk

        result = _make_result(content="Original text preserved through critic scoring")
        sc = ScoredChunk(chunk=result, critic_score=3, bypassed=False, passed=True)

        assert sc.chunk.chunk_content == "Original text preserved through critic scoring"
        assert sc.chunk.score == 0.9
