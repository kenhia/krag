"""Unit tests for RelevanceCritic.score_chunks() — T056.

Tests scoring, regex parsing, fail-open behaviour, and short-chunk bypass.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from krag.models.query_result import QueryResult


def _make_result(
    content: str = "A meaningful chunk about query engines and retrieval.",
    path: str = "/test/file.py",
    score: float = 0.9,
    rank: int = 1,
) -> QueryResult:
    """Create a minimal QueryResult for testing."""
    return QueryResult(
        chunk_content=content,
        file_path=path,
        score=score,
        chunk_id=f"chunk-{rank}",
        rank=rank,
        chunk_index=0,
        file_type=".py",
    )


def _mock_llm(response: str = "4") -> MagicMock:
    """Create a mock LLMClient that returns the given response."""
    llm = MagicMock()
    llm.generate.return_value = response
    return llm


class TestScoreChunks:
    """Test RelevanceCritic.score_chunks() — core scoring logic."""

    def test_score_chunks_returns_scored_list(self) -> None:
        """score_chunks returns a list of ScoredChunk for each input chunk."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("4")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        results = [_make_result(rank=1), _make_result(rank=2)]
        scored = critic.score_chunks("test query", results)

        assert len(scored) == 2
        assert all(s.critic_score == 4 for s in scored)
        assert all(not s.bypassed for s in scored)

    def test_score_chunks_calls_llm_per_chunk(self) -> None:
        """Each chunk gets its own LLM call for individual scoring."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("3")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        results = [_make_result(rank=i) for i in range(1, 6)]
        critic.score_chunks("test query", results)

        assert llm.generate.call_count == 5

    def test_score_chunks_uses_correct_prompt(self) -> None:
        """The scoring prompt matches the R-03 template format."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("5")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        result = _make_result(
            content="How does vector search work in modern retrieval systems today?"
        )
        critic.score_chunks("explain retrieval", [result])

        call_kwargs = llm.generate.call_args
        messages = call_kwargs.kwargs["messages"]
        # Find user message containing the prompt
        prompt_text = " ".join(m["content"] for m in messages)
        assert "explain retrieval" in prompt_text
        assert "How does vector search work in modern retrieval systems today?" in prompt_text
        assert "0-5" in prompt_text

    def test_score_chunks_passes_low_temperature(self) -> None:
        """Critic uses temperature=0.0 and max_tokens=4 for deterministic output."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("3")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        critic.score_chunks("query", [_make_result()])

        call_kwargs = llm.generate.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.0
        assert call_kwargs.kwargs.get("max_tokens") == 4

    def test_score_chunks_marks_passed_true_when_above_threshold(self) -> None:
        """Chunks with scores >= threshold have passed=True."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("4")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].passed is True
        assert scored[0].critic_score == 4

    def test_score_chunks_marks_passed_false_when_below_threshold(self) -> None:
        """Chunks with scores < threshold have passed=False."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("1")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].passed is False
        assert scored[0].critic_score == 1

    def test_score_chunks_threshold_boundary_passes(self) -> None:
        """A chunk scored exactly at threshold passes."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("3")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].passed is True
        assert scored[0].critic_score == 3

    def test_score_chunks_empty_input(self) -> None:
        """Scoring an empty list returns an empty list."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("3")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [])
        assert scored == []
        assert llm.generate.call_count == 0


class TestScoreParsing:
    """Test regex parsing of LLM responses into score integers."""

    @pytest.mark.parametrize(
        ("response", "expected_score"),
        [
            ("3", 3),
            ("5", 5),
            ("0", 0),
            (" 4 ", 4),
            ("I'd rate this a 4", 4),
            ("Score: 2", 2),
            ("The relevance is 5 out of 5", 5),
            ("\n3\n", 3),
        ],
    )
    def test_parse_various_responses(self, response: str, expected_score: int) -> None:
        """Regex parser extracts scores from various LLM response formats."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm(response)
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].critic_score == expected_score

    def test_parse_takes_first_match(self) -> None:
        """When multiple digits 0-5 are present, the first one is used."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("I give it 4 out of 5")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].critic_score == 4


class TestFailOpen:
    """Test fail-open behaviour — include chunk on errors."""

    def test_llm_error_assigns_threshold_score(self) -> None:
        """When LLM raises an exception, chunk gets threshold score and bypassed=True."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("LLM crashed")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].critic_score == 3
        assert scored[0].bypassed is True
        assert scored[0].passed is True

    def test_unparseable_response_assigns_threshold_score(self) -> None:
        """When LLM returns gibberish, chunk gets threshold score and bypassed=True."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("I cannot rate this text properly")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].critic_score == 3
        assert scored[0].bypassed is True
        assert scored[0].passed is True

    def test_empty_response_assigns_threshold_score(self) -> None:
        """Empty LLM response fails open with threshold score."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        scored = critic.score_chunks("query", [_make_result()])
        assert scored[0].critic_score == 3
        assert scored[0].bypassed is True

    def test_fail_open_does_not_prevent_other_chunks(self) -> None:
        """An error on one chunk does not affect scoring of other chunks."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = MagicMock()
        llm.generate.side_effect = [RuntimeError("boom"), "5"]
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        results = [_make_result(rank=1), _make_result(rank=2)]
        scored = critic.score_chunks("query", results)

        assert scored[0].bypassed is True
        assert scored[0].critic_score == 3
        assert scored[1].bypassed is False
        assert scored[1].critic_score == 5


class TestShortChunkBypass:
    """Test chunks < 50 chars bypass scoring (FR-035)."""

    def test_chunk_under_50_chars_bypassed(self) -> None:
        """Chunks shorter than 50 characters skip LLM call."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("5")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        short_result = _make_result(content="Short chunk text")  # 16 chars
        scored = critic.score_chunks("query", [short_result])

        assert scored[0].bypassed is True
        assert scored[0].critic_score == 3  # threshold score
        assert scored[0].passed is True
        assert llm.generate.call_count == 0

    def test_chunk_exactly_50_chars_not_bypassed(self) -> None:
        """Chunk with exactly 50 chars is scored normally."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("4")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        content = "x" * 50
        result = _make_result(content=content)
        scored = critic.score_chunks("query", [result])

        assert scored[0].bypassed is False
        assert scored[0].critic_score == 4
        assert llm.generate.call_count == 1

    def test_chunk_49_chars_bypassed(self) -> None:
        """Chunk with 49 chars is bypassed (< 50 threshold)."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("5")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        content = "x" * 49
        result = _make_result(content=content)
        scored = critic.score_chunks("query", [result])

        assert scored[0].bypassed is True
        assert llm.generate.call_count == 0

    def test_mixed_short_and_long_chunks(self) -> None:
        """Short chunks bypass, long chunks are scored — both in same call."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("4")
        critic = RelevanceCritic(llm_client=llm, threshold=3)

        short = _make_result(content="tiny", rank=1)
        long = _make_result(content="x" * 100, rank=2)
        scored = critic.score_chunks("query", [short, long])

        assert scored[0].bypassed is True  # short
        assert scored[0].critic_score == 3
        assert scored[1].bypassed is False  # long
        assert scored[1].critic_score == 4
        assert llm.generate.call_count == 1  # only long was scored


class TestFilterChunks:
    """Test RelevanceCritic.filter_chunks() — keeps only passing chunks."""

    def test_filter_keeps_passing_chunks(self) -> None:
        """Only chunks with passed=True are kept in the output."""
        from krag.critic.relevance_critic import RelevanceCritic, ScoredChunk

        critic = RelevanceCritic(llm_client=MagicMock(), threshold=3)

        r1 = _make_result(rank=1)
        r2 = _make_result(rank=2)
        r3 = _make_result(rank=3)

        scored = [
            ScoredChunk(chunk=r1, critic_score=5, bypassed=False, passed=True),
            ScoredChunk(chunk=r2, critic_score=1, bypassed=False, passed=False),
            ScoredChunk(chunk=r3, critic_score=3, bypassed=True, passed=True),
        ]

        filtered = critic.filter_chunks(scored)
        assert len(filtered) == 2
        assert filtered[0] is r1
        assert filtered[1] is r3

    def test_filter_all_failing_returns_empty(self) -> None:
        """When all chunks fail, filter_chunks returns an empty list."""
        from krag.critic.relevance_critic import RelevanceCritic, ScoredChunk

        critic = RelevanceCritic(llm_client=MagicMock(), threshold=3)

        scored = [
            ScoredChunk(chunk=_make_result(rank=1), critic_score=0, bypassed=False, passed=False),
            ScoredChunk(chunk=_make_result(rank=2), critic_score=2, bypassed=False, passed=False),
        ]

        filtered = critic.filter_chunks(scored)
        assert filtered == []

    def test_filter_empty_input(self) -> None:
        """Filtering empty list returns empty list."""
        from krag.critic.relevance_critic import RelevanceCritic

        critic = RelevanceCritic(llm_client=MagicMock(), threshold=3)
        assert critic.filter_chunks([]) == []

    def test_filter_preserves_order(self) -> None:
        """Filtered chunks maintain their original order."""
        from krag.critic.relevance_critic import RelevanceCritic, ScoredChunk

        critic = RelevanceCritic(llm_client=MagicMock(), threshold=3)

        r1 = _make_result(
            content="First chunk content here is longer than fifty characters yes", rank=1
        )
        r2 = _make_result(
            content="Second chunk content here is loooooong enough text yes it is", rank=2
        )
        r3 = _make_result(
            content="Third chunk content here is also pretty long enough for test", rank=3
        )

        scored = [
            ScoredChunk(chunk=r1, critic_score=5, bypassed=False, passed=True),
            ScoredChunk(chunk=r2, critic_score=4, bypassed=False, passed=True),
            ScoredChunk(chunk=r3, critic_score=3, bypassed=False, passed=True),
        ]

        filtered = critic.filter_chunks(scored)
        assert [f.rank for f in filtered] == [1, 2, 3]


class TestCriticDisabled:
    """Test that when critic is not enabled, it's a no-op."""

    def test_disabled_critic_returns_all_chunks(self) -> None:
        """When enabled=False, score_chunks still works but bypasses all."""
        from krag.critic.relevance_critic import RelevanceCritic

        llm = _mock_llm("5")
        critic = RelevanceCritic(llm_client=llm, threshold=3, enabled=False)

        results = [_make_result(rank=1), _make_result(rank=2)]
        scored = critic.score_chunks("query", results)

        # All should be bypassed with threshold score when disabled
        assert len(scored) == 2
        assert all(s.bypassed for s in scored)
        assert all(s.passed for s in scored)
        assert llm.generate.call_count == 0
