"""Contract tests for LLMClient interface.

These tests define the expected behavior of any LLMClient implementation.
They should FAIL until we implement the actual LLMClient class.
"""


class TestLLMClientContract:
    """Contract tests for LLMClient implementations."""

    def test_llm_client_has_generate_method(self) -> None:
        """Test that LLMClient has a generate method."""
        # This will fail until we implement LLMClient
        from krag.synthesis.llm_client import LLMClient

        assert hasattr(LLMClient, "generate"), "LLMClient must have generate method"

    def test_generate_accepts_query_and_context(self) -> None:
        """Test that generate method accepts query and context."""
        from krag.synthesis.llm_client import LLMClient

        # Should be able to instantiate with model path
        client = LLMClient(model_path=None)  # None for testing

        # Should accept query and context
        # Will fail if not implemented
        response = client.generate(
            query="What is RAG?",
            context="RAG is Retrieval-Augmented Generation.",
        )
        assert isinstance(response, str), "generate must return string"

    def test_generate_returns_string(self) -> None:
        """Test that generate returns a string response."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model_path=None)
        response = client.generate("test query", "test context")

        assert isinstance(response, str), "Response must be a string"
        assert len(response) > 0, "Response should not be empty"

    def test_generate_handles_empty_context(self) -> None:
        """Test that generate handles empty context gracefully."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model_path=None)
        response = client.generate("test query", "")

        assert isinstance(response, str), "Should return string even with empty context"

    def test_generate_handles_long_context(self) -> None:
        """Test that generate handles long context (truncation/chunking)."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model_path=None)
        long_context = "test " * 10000  # Very long context

        # Should not crash with long context
        response = client.generate("test query", long_context)
        assert isinstance(response, str), "Should handle long context"

    def test_llm_client_accepts_temperature(self) -> None:
        """Test that LLMClient accepts temperature parameter."""
        from krag.synthesis.llm_client import LLMClient

        # Should accept temperature in constructor or generate
        client = LLMClient(model_path=None, temperature=0.7)
        assert client.temperature == 0.7, "Should store temperature"

    def test_llm_client_accepts_max_tokens(self) -> None:
        """Test that LLMClient accepts max_tokens parameter."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model_path=None, max_tokens=512)
        assert client.max_tokens == 512, "Should store max_tokens"
