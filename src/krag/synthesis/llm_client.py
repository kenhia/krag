"""LLM client for answer synthesis."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for local LLM inference using llama-cpp-python.

    Generates answers based on retrieved context and user queries.
    Supports both HuggingFace model names and local file paths.
    """

    def __init__(
        self,
        model: str | Path | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        n_ctx: int = 2048,
        n_threads: int | None = None,
    ):
        """Initialize LLM client.

        Args:
            model: HuggingFace model name (e.g., 'TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF')
                   or local path to GGUF file (None for testing/mock)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            n_ctx: Context window size
            n_threads: Number of threads (None for auto)
        """
        self.model_identifier = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.model: Any = None
        self.model_path: Path | None = None

        # Load model if identifier provided
        if model is not None:
            self._resolve_and_load_model()

    def _resolve_and_load_model(self) -> None:
        """Resolve model identifier to path and load the model."""
        if self.model_identifier is None:
            return

        # Check if it's already a local path
        if isinstance(self.model_identifier, Path) or Path(str(self.model_identifier)).exists():
            self.model_path = Path(self.model_identifier)
            self._load_model()
            return

        # Check if it looks like a HuggingFace model name (contains /)
        model_str = str(self.model_identifier)
        if "/" in model_str and not model_str.startswith("/"):
            # It's a HuggingFace model name - download it
            self.model_path = self._download_from_huggingface(model_str)
            if self.model_path:
                self._load_model()
        else:
            # Treat as local path
            path = Path(model_str)
            if path.exists():
                self.model_path = path
                self._load_model()
            else:
                logger.warning(f"Model file not found: {path}")

    def _download_from_huggingface(self, model_name: str) -> Path | None:
        """Download GGUF model from HuggingFace.

        Args:
            model_name: HuggingFace model identifier (e.g., 'TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF')

        Returns:
            Path to downloaded model file, or None if download failed
        """
        try:
            from huggingface_hub import hf_hub_download

            from krag.config.xdg import get_krag_cache_dir

            logger.info(f"Downloading LLM model from HuggingFace: {model_name}")

            # Parse model name and file
            # For GGUF models, typically the file is named like tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
            # We'll try to find the smallest quantized version first

            # Common GGUF quantization patterns (smallest to largest)
            quant_patterns = [
                "Q2_K.gguf",
                "Q3_K_S.gguf",
                "Q3_K_M.gguf",
                "Q3_K_L.gguf",
                "Q4_K_S.gguf",
                "Q4_K_M.gguf",
                "Q4_0.gguf",
                "Q4_K.gguf",
                "Q5_K_S.gguf",
                "Q5_K_M.gguf",
                "Q5_0.gguf",
                "Q5_K.gguf",
            ]

            # Try to find a GGUF file
            cache_dir = get_krag_cache_dir() / "models" / "huggingface"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Try each quantization pattern
            for pattern in quant_patterns:
                try:
                    # List files in the repo to find matching GGUF
                    from huggingface_hub import list_repo_files

                    files = list_repo_files(model_name)
                    matching_files = [f for f in files if f.endswith(pattern)]

                    if matching_files:
                        filename = matching_files[0]
                        logger.info(f"Found GGUF file: {filename}")

                        model_path = hf_hub_download(
                            repo_id=model_name,
                            filename=filename,
                            cache_dir=str(cache_dir),
                        )
                        return Path(model_path)
                except Exception as e:
                    logger.debug(f"Pattern {pattern} not found: {e}")
                    continue

            # If no specific pattern found, try to download any .gguf file
            try:
                from huggingface_hub import list_repo_files

                files = list_repo_files(model_name)
                gguf_files = [f for f in files if f.endswith(".gguf")]

                if gguf_files:
                    filename = gguf_files[0]
                    logger.info(f"Downloading GGUF file: {filename}")

                    model_path = hf_hub_download(
                        repo_id=model_name,
                        filename=filename,
                        cache_dir=str(cache_dir),
                    )
                    return Path(model_path)
                else:
                    logger.error(f"No GGUF files found in repository: {model_name}")
                    return None

            except Exception as e:
                logger.error(f"Failed to list repository files: {e}")
                return None

        except ImportError:
            logger.error("huggingface_hub not installed. Install with: pip install huggingface-hub")
            return None
        except Exception as e:
            logger.error(f"Failed to download model from HuggingFace: {e}")
            return None

    def _load_model(self) -> None:
        """Load the LLM model."""
        if self.model_path is None:
            logger.warning("No model path available for loading")
            return

        logger.info(f"Loading LLM model from {self.model_path}")
        try:
            from llama_cpp import Llama

            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                verbose=False,
            )
            logger.info("LLM model loaded successfully")
        except ImportError as e:
            logger.error("llama-cpp-python not installed")
            raise ImportError(
                "llama-cpp-python is required for LLM inference. "
                "Install with: uv add llama-cpp-python"
            ) from e
        except Exception as e:
            logger.error(f"Failed to load LLM model: {e}")
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
        logger.debug(f"Generating response for query: {query[:50]}...")
        # Use provided values or defaults
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        # If no model loaded (testing mode), return placeholder
        if self.model is None:
            logger.debug("No model loaded, using fallback response")
            return self._generate_fallback(query, context)

        # Generate with llama-cpp-python
        logger.debug(f"Generating with temperature={temp}, max_tokens={max_tok}")
        try:
            response = self.model(
                context,
                max_tokens=max_tok,
                temperature=temp,
                stop=["User Question:", "\n\n\n"],  # Stop sequences
            )

            # Extract text from response
            if isinstance(response, dict):
                answer = response.get("choices", [{}])[0].get("text", "").strip()
            else:
                answer = str(response).strip()

            logger.info(f"Generated answer: {len(answer)} characters")
            return answer

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return f"Error generating response: {e}"
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
