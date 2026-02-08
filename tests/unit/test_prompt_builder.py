"""Unit tests for PromptBuilder.

These tests define the expected behavior of the PromptBuilder class.
Should FAIL until we implement PromptBuilder.
"""

from pathlib import Path

from krag.models.query_result import QueryResult


class TestPromptBuilder:
    """Unit tests for PromptBuilder class."""

    def test_prompt_builder_exists(self) -> None:
        """Test that PromptBuilder class exists."""
        # This will fail until we implement PromptBuilder
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        assert builder is not None, "PromptBuilder should be instantiable"

    def test_build_prompt_with_query_and_context(self) -> None:
        """Test building prompt with query and context chunks."""
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

        prompt = builder.build(query=query, results=results)

        assert isinstance(prompt, str), "Prompt should be string"
        assert query in prompt, "Prompt should contain query"
        assert "RAG combines" in prompt, "Prompt should contain context"

    def test_build_prompt_includes_instructions(self) -> None:
        """Test that prompt includes system instructions."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        query = "test query"
        results = []

        prompt = builder.build(query=query, results=results)

        # Should have some instruction about answering based on context
        assert "answer" in prompt.lower() or "respond" in prompt.lower(), (
            "Prompt should include instructions"
        )

    def test_build_prompt_with_multiple_results(self) -> None:
        """Test building prompt with multiple context chunks."""
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

        prompt = builder.build(query="test", results=results)

        assert "First chunk" in prompt, "Should include first chunk"
        assert "Second chunk" in prompt, "Should include second chunk"

    def test_build_prompt_with_empty_results(self) -> None:
        """Test building prompt when no results found."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        prompt = builder.build(query="test query", results=[])

        assert isinstance(prompt, str), "Should return string even with no results"
        assert len(prompt) > 0, "Should return non-empty prompt"

    def test_build_prompt_includes_source_info(self) -> None:
        """Test that prompt includes source file information."""
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

        prompt = builder.build(query="test", results=results)

        # Should reference the source file
        assert "important.md" in prompt or "/test/important.md" in prompt, (
            "Should include source file info"
        )

    def test_build_prompt_limits_total_length(self) -> None:
        """Test that prompt builder limits total context length."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder(max_context_length=100)

        # Create results with very long content
        results = [
            QueryResult(
                chunk_id=str(i),
                score=0.9,
                rank=i + 1,
                chunk_content="x" * 1000,  # Very long content
                file_path=Path(f"/test/doc{i}.md"),
                chunk_index=0,
                file_type="markdown",
            )
            for i in range(10)
        ]

        prompt = builder.build(query="test", results=results)

        # Prompt should be truncated/limited
        # This is a rough check - actual limit may include other text
        assert len(prompt) < 10000, "Should limit total prompt length"
