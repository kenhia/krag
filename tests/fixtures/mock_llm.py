"""Mock LLM client for testing."""

from typing import Any


class MockLLMClient:
    """Mock LLM client that generates predictable responses for testing.

    Returns responses based on simple rules rather than actual LLM inference.
    """

    def __init__(self, default_response: str | None = None):
        """Initialize mock LLM client.

        Args:
            default_response: Default response to return if no pattern matches
        """
        self.default_response = (
            default_response or "This is a mock response based on the provided context."
        )
        self.call_count = 0
        self.last_prompt = None
        self.last_context = None

    def generate(self, prompt: str, context: str, **kwargs: Any) -> str:
        """Generate a mock response.

        Args:
            prompt: The user's query/prompt
            context: Retrieved context chunks
            **kwargs: Additional generation parameters (ignored in mock)

        Returns:
            Mock generated response
        """
        self.call_count += 1
        self.last_prompt = prompt
        self.last_context = context

        # Simple pattern matching for test assertions
        if "fibonacci" in prompt.lower():
            return "The Fibonacci function calculates the nth Fibonacci number using recursion."

        if "RAG" in context or "Retrieval-Augmented Generation" in context:
            return "RAG (Retrieval-Augmented Generation) combines information retrieval with LLM generation to produce accurate, grounded responses."

        if "vector store" in prompt.lower() or "vector store" in context.lower():
            return "A vector store maintains embeddings and performs similarity search to find relevant chunks."

        if not context or context.strip() == "":
            return "I don't have enough context to answer that question."

        return self.default_response

    def generate_stream(self, prompt: str, context: str, **kwargs: Any) -> list[str]:
        """Generate streaming response (returns list of chunks for testing).

        Args:
            prompt: The user's query/prompt
            context: Retrieved context chunks
            **kwargs: Additional generation parameters

        Returns:
            List of response chunks (simulating streaming)
        """
        response = self.generate(prompt, context, **kwargs)
        # Split into word-level chunks to simulate streaming
        words = response.split()
        return [word + " " for word in words]


def create_mock_llm_response(query: str, context: str = "") -> str:
    """Helper function to create a mock LLM response without instantiating the class.

    Args:
        query: User query
        context: Retrieved context

    Returns:
        Mock response string
    """
    client = MockLLMClient()
    return client.generate(query, context)
