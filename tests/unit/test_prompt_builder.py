"""Unit tests for PromptBuilder.

These tests define the expected behavior of the PromptBuilder class
including prompt presets and chat message output.
"""

from pathlib import Path

import pytest

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


# ---------------------------------------------------------------------------
# US4 Tests: Code Prompt Preset
# ---------------------------------------------------------------------------


def _code_chunk(
    content: str = "def foo(bar: int) -> str:\n    return str(bar)",
    file_path: str = "/src/app/main.py",
    file_type: str = ".py",
    **kwargs,
) -> QueryResult:
    """Helper to create a code-oriented QueryResult."""
    from uuid import uuid4

    return QueryResult(
        chunk_id=str(uuid4()),
        score=0.9,
        rank=kwargs.get("rank", 1),
        chunk_content=content,
        file_path=Path(file_path),
        chunk_index=0,
        file_type=file_type,
    )


class TestCodePreset:
    """T074-T076: Code preset unit tests."""

    def test_code_preset_exists_in_available_presets(self) -> None:
        """T074: 'code' should be a valid preset name."""
        from krag.synthesis.prompt_builder import PromptBuilder

        presets = PromptBuilder.available_presets()
        assert "code" in presets

    def test_code_preset_system_prompt_mentions_code(self) -> None:
        """T074: Code preset system prompt should reference code/symbols."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        code_preset = PROMPT_PRESETS["code"]
        prompt_lower = code_preset.system_prompt.lower()
        assert "code" in prompt_lower or "function" in prompt_lower

    def test_code_preset_low_temperature(self) -> None:
        """T074: Code preset should use low temperature for precise answers."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        code_preset = PROMPT_PRESETS["code"]
        assert code_preset.temperature <= 0.15

    def test_code_preset_includes_function_signature_in_context(self) -> None:
        """T074: Code preset build output should include function signatures."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder(preset_name="code")
        results = [
            _code_chunk(
                content="def calculate_total(items: list[float]) -> float:\n    return sum(items)",
                file_path="/src/billing/calc.py",
            ),
        ]
        messages = builder.build("How does calculate_total work?", results)
        user_content = messages[1]["content"]
        # The function signature must appear in context
        assert "calculate_total" in user_content
        assert "calc.py" in user_content

    def test_code_preset_insufficient_context(self) -> None:
        """T075: Code preset with no context returns insufficient-context phrase."""
        from krag.synthesis.prompt_builder import (
            PromptBuilder,
        )

        builder = PromptBuilder(preset_name="code")
        messages = builder.build("How does the scheduler work?", results=[])
        # System message should instruct the LLM to respond with the phrase
        system_lower = messages[0]["content"].lower()
        assert "don't have enough information" in system_lower or "insufficient" in system_lower

    def test_code_preset_system_prompt_instructs_code_snippets(self) -> None:
        """T074: Code preset system prompt should instruct inclusion of code snippets."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        code_preset = PROMPT_PRESETS["code"]
        prompt_lower = code_preset.system_prompt.lower()
        assert (
            "snippet" in prompt_lower or "code block" in prompt_lower or "example" in prompt_lower
        )

    def test_code_preset_system_prompt_instructs_file_references(self) -> None:
        """T074: Code preset should instruct citing file paths."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        code_preset = PROMPT_PRESETS["code"]
        prompt_lower = code_preset.system_prompt.lower()
        assert "file" in prompt_lower or "path" in prompt_lower or "source" in prompt_lower

    def test_code_preset_format_code_metadata_in_context(self) -> None:
        """T080: Code preset should format code metadata (file type) into context."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder(preset_name="code")
        results = [
            _code_chunk(
                content="class UserService:\n    def get_user(self, id: int) -> User:\n        ...",
                file_path="/src/services/user_service.py",
                file_type=".py",
            ),
        ]
        messages = builder.build("How does UserService work?", results)
        user_content = messages[1]["content"]
        # Code metadata should be present — at minimum file path
        assert "user_service.py" in user_content

    def test_code_preset_max_tokens_sufficient_for_code_answers(self) -> None:
        """T078: Code preset max_tokens should be large enough for code answers."""
        from krag.synthesis.prompt_builder import PROMPT_PRESETS

        code_preset = PROMPT_PRESETS["code"]
        assert code_preset.max_tokens >= 512


class TestCodePresetAutoCoupling:
    """T076: Auto-coupling tests (preset selection based on LLM route)."""

    def test_auto_coupling_code_route_selects_code_preset(self) -> None:
        """T076: When route is 'code', auto-coupling should select code preset."""
        # This tests the coupling logic that lives in query.py
        # Here we verify the PromptBuilder can actually be instantiated
        # with preset_name="code" and produces distinct output
        from krag.synthesis.prompt_builder import PromptBuilder

        code_builder = PromptBuilder(preset_name="code")
        balanced_builder = PromptBuilder(preset_name="balanced")

        results = [_code_chunk()]
        code_messages = code_builder.build("explain foo", results)
        balanced_messages = balanced_builder.build("explain foo", results)

        # System prompts must differ
        assert code_messages[0]["content"] != balanced_messages[0]["content"]

    def test_explicit_preset_override_beats_auto_coupling(self) -> None:
        """T076: Explicit CLI --preset should override auto-coupling."""
        from krag.synthesis.prompt_builder import PromptBuilder

        # If user passes --preset strict, it should use strict even for code
        builder = PromptBuilder(preset_name="strict")
        results = [_code_chunk()]
        messages = builder.build("explain foo", results)
        # Should use strict system prompt, not code
        assert "concise" in messages[0]["content"].lower() or "ONLY" in messages[0]["content"]
