"""Unit tests for LLMClient chat message generation.

Tests the new generate(messages) signature using chat completion API.
Should FAIL until LLMClient is migrated from text completion to chat completion.
"""


class TestLLMClientChatGeneration:
    """Tests for LLMClient.generate() with chat messages."""

    def test_generate_accepts_messages_list(self) -> None:
        """Test that generate() accepts a list of message dicts."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is RAG?"},
        ]
        response = client.generate(messages=messages)
        assert isinstance(response, str), "generate must return string"

    def test_generate_returns_nonempty_for_mock(self) -> None:
        """Test that generate returns non-empty string with no model loaded."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        messages = [
            {"role": "system", "content": "Answer based on context."},
            {"role": "user", "content": "test query"},
        ]
        response = client.generate(messages=messages)
        assert len(response) > 0, "Should return non-empty fallback"

    def test_generate_per_call_temperature_override(self) -> None:
        """Test that generate accepts per-call temperature override."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, temperature=0.2)
        messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"},
        ]
        # Should not raise with temperature override
        response = client.generate(messages=messages, temperature=0.0)
        assert isinstance(response, str)

    def test_generate_per_call_max_tokens_override(self) -> None:
        """Test that generate accepts per-call max_tokens override."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"},
        ]
        response = client.generate(messages=messages, max_tokens=100)
        assert isinstance(response, str)

    def test_generate_per_call_top_p_override(self) -> None:
        """Test that generate accepts per-call top_p override."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"},
        ]
        response = client.generate(messages=messages, top_p=0.5)
        assert isinstance(response, str)

    def test_generate_per_call_repeat_penalty_override(self) -> None:
        """Test that generate accepts per-call repeat_penalty override."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"},
        ]
        response = client.generate(messages=messages, repeat_penalty=1.2)
        assert isinstance(response, str)

    def test_constructor_accepts_top_p(self) -> None:
        """Test that constructor accepts top_p parameter."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, top_p=0.9)
        assert client.top_p == 0.9

    def test_constructor_accepts_repeat_penalty(self) -> None:
        """Test that constructor accepts repeat_penalty parameter."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, repeat_penalty=1.1)
        assert client.repeat_penalty == 1.1

    def test_constructor_accepts_min_p(self) -> None:
        """Test that constructor accepts min_p parameter."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None, min_p=0.05)
        assert client.min_p == 0.05

    def test_generate_returns_empty_string_on_no_model(self) -> None:
        """Test fallback behavior when no model is loaded."""
        from krag.synthesis.llm_client import LLMClient

        client = LLMClient(model=None)
        messages = [
            {"role": "system", "content": "No context available."},
            {"role": "user", "content": "What is quantum computing?"},
        ]
        response = client.generate(messages=messages)
        assert isinstance(response, str)
        # Fallback should mention lack of context or be a placeholder
        assert len(response) > 0
