"""Unit tests for PromptBuilder.

These tests define the expected behavior of the PromptBuilder class
including prompt presets and chat message output.
"""

from pathlib import Path

from krag.models.query_result import QueryResult


class TestPromptPreset:
    """Tests for PromptPreset dataclass and built-in presets."""

    def test_available_presets_returns_list(self) -> None:
        """Test that available_presets() returns list of preset names."""
        from krag.synthesis.prompt_builder import PromptBuilder

        presets = PromptBuilder.available_presets()
        assert isinstance(presets, list)
        assert "strict" in presets
        assert "balanced" in presets
        assert "verbose" in presets

    def test_preset_strict_has_low_temperature(self) -> None:
        """Test that strict preset uses low temperature."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        strict = PROMPT_PRESETS["strict"]
        assert strict.temperature == 0.1
        assert strict.max_tokens == 256

    def test_preset_balanced_is_default(self) -> None:
        """Test that balanced preset has expected defaults."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        balanced = PROMPT_PRESETS["balanced"]
        assert balanced.temperature == 0.2
        assert balanced.top_p == 0.9
        assert balanced.repeat_penalty == 1.1
        assert balanced.max_tokens == 512

    def test_preset_verbose_has_higher_temperature(self) -> None:
        """Test that verbose preset allows more exploratory answers."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        verbose = PROMPT_PRESETS["verbose"]
        assert verbose.temperature == 0.3
        assert verbose.max_tokens == 1024

    def test_unknown_preset_raises_error(self) -> None:
        """Test that unknown preset name raises ValueError."""
        import pytest

        from krag.synthesis.prompt_builder import PromptBuilder

        with pytest.raises(ValueError, match="Unknown preset"):
            PromptBuilder(preset_name="nonexistent")


class TestPromptBuilder:
    """Unit tests for PromptBuilder class."""

    def test_prompt_builder_exists(self) -> None:
        """Test that PromptBuilder class exists."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        assert builder is not None, "PromptBuilder should be instantiable"

    def test_build_returns_chat_messages(self) -> None:
        """Test building prompt returns list of chat message dicts."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()

        query = "What is RAG?"
        results = [
            QueryResult(
                chunk_id="1",
                score=0.95,
                rank=1,
                chunk_content="RAG combines retrieval with generation.",
                file_path=Path("/test/doc.md"),
                chunk_index=0,
                file_type="markdown",
            )
        ]

        messages = builder.build(query=query, results=results)

        assert isinstance(messages, list), "build() should return a list"
        assert len(messages) == 2, "Should return exactly 2 messages (system + user)"
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert query in messages[1]["content"]
        assert "RAG combines" in messages[1]["content"]

    def test_build_includes_numbered_sources(self) -> None:
        """Test that context chunks are numbered [1], [2] etc."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()

        results = [
            QueryResult(
                chunk_id="1",
                score=0.95,
                rank=1,
                chunk_content="First chunk content.",
                file_path=Path("/test/doc1.md"),
                chunk_index=0,
                file_type="markdown",
            ),
            QueryResult(
                chunk_id="2",
                score=0.85,
                rank=2,
                chunk_content="Second chunk content.",
                file_path=Path("/test/doc2.md"),
                chunk_index=0,
                file_type="markdown",
            ),
        ]

        messages = builder.build(query="test", results=results)
        user_content = messages[1]["content"]

        assert "[1]" in user_content, "Should have numbered source [1]"
        assert "[2]" in user_content, "Should have numbered source [2]"
        assert "First chunk" in user_content
        assert "Second chunk" in user_content

    def test_build_empty_results_returns_insufficient_context_message(self) -> None:
        """Test that empty results produce an 'insufficient context' message."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        messages = builder.build(query="test query", results=[])

        assert isinstance(messages, list)
        assert len(messages) == 2
        system_content = messages[0]["content"].lower()
        assert "don't have enough information" in system_content or "insufficient" in system_content

    def test_build_includes_source_path(self) -> None:
        """Test that prompt includes source file paths."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()

        results = [
            QueryResult(
                chunk_id="1",
                score=0.95,
                rank=1,
                chunk_content="Content here.",
                file_path=Path("/test/important.md"),
                chunk_index=0,
                file_type="markdown",
            )
        ]

        messages = builder.build(query="test", results=results)
        user_content = messages[1]["content"]

        assert "important.md" in user_content, "Should include source file path"

    def test_build_limits_total_context_length(self) -> None:
        """Test that prompt builder limits total context length."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder(max_context_length=100)

        results = [
            QueryResult(
                chunk_id=str(i),
                score=0.9,
                rank=i + 1,
                chunk_content="x" * 1000,
                file_path=Path(f"/test/doc{i}.md"),
                chunk_index=0,
                file_type="markdown",
            )
            for i in range(10)
        ]

        messages = builder.build(query="test", results=results)
        # Context should be truncated
        user_content = messages[1]["content"]
        assert len(user_content) < 10000, "Should limit total prompt length"

    def test_get_system_prompt_returns_preset_prompt(self) -> None:
        """Test get_system_prompt returns the active preset's system prompt."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder(preset_name="strict")
        prompt = builder.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_prompt_override(self) -> None:
        """Test that system_prompt_override replaces preset system prompt."""
        from krag.synthesis.prompt_builder import PromptBuilder

        custom_prompt = "You are a custom assistant."
        builder = PromptBuilder(system_prompt_override=custom_prompt)
        assert builder.get_system_prompt() == custom_prompt

    def test_build_with_different_presets(self) -> None:
        """Test that different presets produce different system prompts."""
        from krag.synthesis.prompt_builder import PromptBuilder

        strict_builder = PromptBuilder(preset_name="strict")
        verbose_builder = PromptBuilder(preset_name="verbose")

        strict_prompt = strict_builder.get_system_prompt()
        verbose_prompt = verbose_builder.get_system_prompt()

        assert strict_prompt != verbose_prompt, "Different presets should have different prompts"
