"""LLM client for answer synthesis."""

import io
import logging
import sys
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
        n_gpu_layers: int = 0,
        model_cache_path: str | Path | None = None,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
        min_p: float = 0.05,
    ):
        """Initialize LLM client.

        Args:
            model: HuggingFace model name (e.g., 'TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF')
                   or local path to GGUF file (None for testing/mock)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            n_ctx: Context window size
            n_threads: Number of threads (None for auto)
            n_gpu_layers: Number of layers to offload to GPU (0=CPU, -1=full, N=partial)
            model_cache_path: Custom path for model cache. If None, uses XDG cache default.
            top_p: Nucleus sampling threshold (0.0-1.0)
            repeat_penalty: Repetition penalty (>=1.0)
            min_p: Minimum probability threshold (0.0-1.0)
        """
        self.model_identifier = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.n_gpu_layers = n_gpu_layers
        self.model_cache_path = Path(model_cache_path) if model_cache_path else None
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self.min_p = min_p
        self.model: Any = None
        self.model_path: Path | None = None

        # Warn if GPU layers requested but CUDA may not be available
        if n_gpu_layers != 0:
            self._check_gpu_availability()

        # Load model if identifier provided
        if model is not None:
            self._resolve_and_load_model()

    def _check_gpu_availability(self) -> None:
        """Check GPU availability and warn if GPU layers requested but unavailable."""
        try:
            import torch

            if not torch.cuda.is_available():
                logger.warning(
                    "n_gpu_layers=%d requested but CUDA is not available. "
                    "Model will run on CPU. Install PyTorch with CUDA support "
                    "and ensure NVIDIA drivers are installed.",
                    self.n_gpu_layers,
                )
        except ImportError:
            logger.warning(
                "n_gpu_layers=%d requested but torch is not installed. "
                "Cannot verify GPU availability. Model may fall back to CPU.",
                self.n_gpu_layers,
            )

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

            # Try to find a GGUF file - use configured path or fall back to XDG default
            if self.model_cache_path:
                cache_dir = self.model_cache_path / "huggingface"
            else:
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

            # Check if we should suppress output
            root_logger = logging.getLogger()
            is_verbose = root_logger.level <= logging.DEBUG

            if not is_verbose:
                # Suppress llama.cpp output by redirecting stderr temporarily
                stderr_backup = sys.stderr
                try:
                    sys.stderr = io.StringIO()
                    self.model = Llama(
                        model_path=str(self.model_path),
                        n_ctx=self.n_ctx,
                        n_threads=self.n_threads,
                        n_gpu_layers=self.n_gpu_layers,
                        verbose=False,
                    )
                finally:
                    sys.stderr = stderr_backup
            else:
                self.model = Llama(
                    model_path=str(self.model_path),
                    n_ctx=self.n_ctx,
                    n_threads=self.n_threads,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=True,
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
        messages: list[dict[str, str]] | str | None = None,
        context: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        repeat_penalty: float | None = None,
    ) -> str:
        """Generate answer from chat messages or legacy query+context.

        Preferred usage (chat messages)::

            client.generate(messages=[
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
            ])

        Legacy usage (backward compatible)::

            client.generate("query", "context")

        Args:
            messages: List of chat message dicts, or legacy query string.
            context: Legacy context string (only used when messages is a query string).
            temperature: Override default temperature.
            max_tokens: Override default max_tokens.
            top_p: Override default top_p.
            repeat_penalty: Override default repeat_penalty.

        Returns:
            Generated answer string.
        """
        # Handle legacy (query, context) call pattern
        if isinstance(messages, str):
            query = messages
            legacy_messages: list[dict[str, str]] = []
            if context:
                legacy_messages.append({"role": "system", "content": context})
            legacy_messages.append({"role": "user", "content": query})
            messages = legacy_messages

        if not messages:
            return self._generate_fallback([])

        logger.debug("Generating response from %d messages", len(messages))

        # Log complete messages at DEBUG for diagnostics
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            logger.debug("  Message[%d] role=%s len=%d", i, role, len(content))

        # Use provided values or defaults
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        t_p = top_p if top_p is not None else self.top_p
        r_p = repeat_penalty if repeat_penalty is not None else self.repeat_penalty

        # If no model loaded (testing mode), return placeholder
        if self.model is None:
            logger.debug("No model loaded, using fallback response")
            return self._generate_fallback(messages)

        # Generate with llama-cpp-python chat completion API
        logger.debug(
            "Generating with temperature=%.2f, max_tokens=%d, top_p=%.2f, repeat_penalty=%.2f",
            temp,
            max_tok,
            t_p,
            r_p,
        )
        try:
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_tok,
                temperature=temp,
                top_p=t_p,
                repeat_penalty=r_p,
                min_p=self.min_p,
            )

            # Extract text from chat completion response
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    answer = message.get("content", "").strip()
                else:
                    answer = ""
            else:
                answer = str(response).strip()

            logger.info("Generated answer: %d characters", len(answer))
            return answer

        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            return f"Error generating response: {e}"

    def _generate_fallback(self, messages: list[dict[str, str]]) -> str:
        """Fallback response when no model is loaded.

        Args:
            messages: Chat messages list

        Returns:
            Fallback message
        """
        # Check if system message indicates no context
        system_content = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_content = msg.get("content", "")
                break

        if not system_content or "did not return any relevant results" in system_content:
            return "I don't have enough context to answer that question."

        return (
            "This is a placeholder response. "
            "To use actual LLM inference, configure a valid model_path."
        )
