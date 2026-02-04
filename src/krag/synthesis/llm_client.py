"""LLM client for answer synthesis."""

from pathlib import Path
from typing import Any


class LLMClient:
    """Client for local LLM inference using llama-cpp-python.

    Generates answers based on retrieved context and user queries.
    """

    def __init__(
        self,
        model_path: Path | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        n_ctx: int = 2048,
        n_threads: int | None = None,
    ):
        """Initialize LLM client.

        Args:
            model_path: Path to GGUF model file (None for testing/mock)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            n_ctx: Context window size
            n_threads: Number of threads (None for auto)
        """
        self.model_path = model_path
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.model: Any = None

        # Load model if path provided
        if model_path is not None and Path(model_path).exists():
            self._load_model()

    def _load_model(self) -> None:
        """Load the LLM model."""
        try:
            from llama_cpp import Llama

            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                verbose=False,
            )
        except ImportError as e:
            raise ImportError(
                "llama-cpp-python is required for LLM inference. "
                "Install with: uv add llama-cpp-python"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Failed to load LLM model: {e}") from e

    def generate(
        self,
        query: str,
        context: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate answer based on query and context.

        Args:
            query: User's query
            context: Retrieved context (formatted prompt)
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Generated answer string
        """
        # Use provided values or defaults
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        # If no model loaded (testing mode), return placeholder
        if self.model is None:
            return self._generate_fallback(query, context)

        # Generate with llama-cpp-python
        try:
            response = self.model(
                context,
                max_tokens=max_tok,
                temperature=temp,
                stop=["User Question:", "\n\n\n"],  # Stop sequences
            )

            # Extract text from response
            if isinstance(response, dict):
                return response.get("choices", [{}])[0].get("text", "").strip()
            return str(response).strip()

        except Exception as e:
            return f"Error generating response: {str(e)}"

    def _generate_fallback(self, query: str, context: str) -> str:
        """Fallback response when no model is loaded.

        Args:
            query: User query
            context: Context string

        Returns:
            Fallback message
        """
        if not context or "did not return any relevant results" in context:
            return "I don't have enough context to answer that question."

        return (
            "This is a placeholder response. "
            "To use actual LLM inference, configure a valid model_path."
        )
