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

        # Should be able to instantiate with model
        client = LLMClient(model=None)  # None for testing

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

        client = LLMClient(model=None)
        response = client.generate("test query", "test context")

        assert isinstance(response, str), "Response must be a string"
        assert len(response) > 0, "Response should not be empty"

    def test_generate_handles_empty_context(self) -> None:
        """Test that generate handles empty context gracefully."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        response = client.generate("test query", "")

        assert isinstance(response, str), "Should return string even with empty context"

    def test_generate_handles_long_context(self) -> None:
        """Test that generate handles long context (truncation/chunking)."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        long_context = "test " * 10000  # Very long context

        # Should not crash with long context
        response = client.generate("test query", long_context)
        assert isinstance(response, str), "Should handle long context"

    def test_llm_client_accepts_temperature(self) -> None:
        """Test that LLMClient accepts temperature parameter."""
        from krag.synthesis.llm_client import LLMClient

        # Should accept temperature in constructor or generate
        client = LLMClient(model=None, temperature=0.7)
        assert client.temperature == 0.7, "Should store temperature"

    def test_llm_client_accepts_max_tokens(self) -> None:
        """Test that LLMClient accepts max_tokens parameter."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, max_tokens=512)
        assert client.max_tokens == 512, "Should store max_tokens"

    # --- T033: LLMClient passes n_gpu_layers to Llama() init ---

    def test_llm_client_accepts_n_gpu_layers(self) -> None:
        """Test that LLMClient accepts n_gpu_layers parameter."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, n_gpu_layers=-1)
        assert client.n_gpu_layers == -1, "Should store n_gpu_layers"

    # --- T034: LLMClient with n_gpu_layers=0 uses CPU only ---

    def test_llm_client_default_n_gpu_layers_is_zero(self) -> None:
        """Test that n_gpu_layers defaults to 0 (CPU only)."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        assert client.n_gpu_layers == 0, "n_gpu_layers should default to 0 (CPU only)"

    # --- T035: LLMClient with n_gpu_layers=-1 attempts full GPU offload ---

    def test_llm_client_full_gpu_offload(self) -> None:
        """Test that LLMClient accepts -1 for full GPU offload."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, n_gpu_layers=-1)
        assert client.n_gpu_layers == -1, "Should accept -1 for full GPU offload"

    def test_llm_client_partial_gpu_offload(self) -> None:
        """Test that LLMClient accepts positive values for partial GPU offload."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, n_gpu_layers=24)
        assert client.n_gpu_layers == 24, "Should accept partial GPU layer count"
