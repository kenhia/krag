"""Multi-model embedding orchestrator.

Manages multiple embedding models for plugin-declared routing.
Wraps one or more EmbeddingGenerator instances, each associated with
a named vector space in Qdrant.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from qdrant_client.models import Distance, VectorParams

from krag.embeddings.generator import EmbeddingGenerator

if TYPE_CHECKING:
    from krag.models.text_chunk import TextChunk

logger = logging.getLogger(__name__)


class EmbeddingOrchestrator:
    """Manages multiple embedding models for plugin-declared routing.

    Wraps one or more EmbeddingGenerator instances, each associated with
    a named vector space in Qdrant. Routes files to the correct model
    during indexing and embeds queries with all active models during retrieval.
    """

    def __init__(
        self,
        default_model: str = "BAAI/bge-base-en-v1.5",
        device: str = "cpu",
        additional_models: dict[str, str] | None = None,
    ) -> None:
        """Initialize with default model and optional additional models.

        Args:
            default_model: HuggingFace model name for the default (text) embedder.
            device: Device for model loading ("cpu", "cuda", "cuda:0").
            additional_models: Mapping of vector_name -> model_name for additional
                embedding models. E.g., {"code": "jinaai/jina-embeddings-v2-base-code"}.

        Raises:
            ValueError: If any model has a different vector dimension than the default.
            RuntimeError: If the default model fails to load.
        """
        self._device = device
        self._models: dict[str, EmbeddingGenerator] = {}
        self._model_names: dict[str, str] = {}
        self._default_vector_name = "text"

        # Always load the default (text) model
        logger.info(f"Loading default embedding model: {default_model}")
        self._models["text"] = EmbeddingGenerator(model_name=default_model, device=device)
        self._model_names["text"] = default_model

        # Load additional models if provided
        if additional_models:
            for vector_name, model_name in additional_models.items():
                self._load_additional_model(vector_name, model_name)

    def register_model(self, vector_name: str, model_name: str) -> bool:
        """Register an additional model after initialization.

        Attempts to load the model, subject to VRAM checks and dimension
        validation. Safe to call multiple times with the same vector_name;
        duplicates are silently ignored.

        Args:
            vector_name: Named vector key (e.g., "code").
            model_name: HuggingFace model name or path.

        Returns:
            True if the model was loaded (or already loaded), False if skipped.
        """
        if vector_name in self._models:
            logger.debug(f"Model for vector '{vector_name}' already loaded, skipping")
            return True
        self._load_additional_model(vector_name, model_name)
        return vector_name in self._models

    def _load_additional_model(self, vector_name: str, model_name: str) -> None:
        """Attempt to load an additional embedding model.

        Checks VRAM budget on GPU devices before loading. Skips with
        a warning if VRAM is insufficient.

        Args:
            vector_name: Named vector key (e.g., "code").
            model_name: HuggingFace model name or path.
        """
        # VRAM check for GPU devices
        if self._device != "cpu" and not self._check_vram_budget(model_name):
            logger.warning(
                f"Insufficient VRAM to load model '{model_name}' for vector "
                f"'{vector_name}'. Skipping — only text model will be used."
            )
            return

        try:
            logger.info(f"Loading additional embedding model: {model_name} as '{vector_name}'")
            gen = EmbeddingGenerator(model_name=model_name, device=self._device)

            self._models[vector_name] = gen
            self._model_names[vector_name] = model_name
            new_dim = gen.get_dimension()
            logger.info(
                f"Model '{model_name}' loaded as '{vector_name}' "
                f"(dim={new_dim}, device={self._device})"
            )

        except Exception as e:
            logger.warning(
                f"Failed to load model '{model_name}' for vector "
                f"'{vector_name}': {e}. Continuing with text model only."
            )

    def _check_vram_budget(self, model_name: str) -> bool:
        """Check if there's enough VRAM to load an additional model.

        Uses torch.cuda.mem_get_info() for accurate post-context-init free VRAM.
        Estimates model VRAM need as ~2x model file size heuristic for
        SentenceTransformer models (~300-700 MB → ~600 MB - 1.4 GB).

        Returns:
            True if model can fit, False otherwise.
            Always returns True for non-CUDA devices.
        """
        if self._device == "cpu":
            return True

        from krag.cli.gpu import get_free_vram

        free_vram = get_free_vram()
        if free_vram is None:
            # Can't determine VRAM — be optimistic
            logger.debug("Cannot determine VRAM availability, allowing model load")
            return True

        # Conservative estimate: embedding models typically need ~600 MB - 1.4 GB
        # Use 1.2 GB as a threshold for an additional model
        estimated_need = 1_200_000_000  # 1.2 GB conservative estimate
        available = int(free_vram * 0.8)  # 20% safety margin

        can_fit = available >= estimated_need
        logger.info(
            f"VRAM check for '{model_name}': free={free_vram / 1e9:.1f} GB, "
            f"available (80%)={available / 1e9:.1f} GB, "
            f"estimated need={estimated_need / 1e9:.1f} GB → "
            f"{'OK' if can_fit else 'SKIP'}"
        )
        return can_fit

    def embed_chunks(
        self,
        chunks: list[TextChunk],
        vector_name: str = "text",
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Embed chunks using the specified model.

        Args:
            chunks: List of TextChunk objects to embed.
            vector_name: Which embedding model to use ("text", "code", etc.).
            batch_size: Batch size for embedding generation.

        Returns:
            List of embedding vectors (one per chunk).

        Raises:
            KeyError: If vector_name is not a loaded model.
        """
        if vector_name not in self._models:
            raise KeyError(
                f"No model loaded for vector name '{vector_name}'. "
                f"Available: {list(self._models.keys())}"
            )

        generator = self._models[vector_name]
        texts = [chunk.content for chunk in chunks]
        return generator.generate_batch(texts, batch_size=batch_size)

    def embed_query(self, query: str) -> dict[str, list[float]]:
        """Embed a query with ALL active embedding models.

        Used during retrieval to search all vector spaces.

        Args:
            query: User query string.

        Returns:
            Dict mapping vector_name to embedding vector.
            E.g., {"text": [...], "code": [...]}.
        """
        result: dict[str, list[float]] = {}
        for vector_name, generator in self._models.items():
            result[vector_name] = generator.generate_single(query)
        return result

    def get_vector_config(self) -> dict[str, VectorParams]:
        """Return Qdrant-compatible vectors_config for collection creation.

        Returns:
            Dict mapping vector_name to VectorParams.
        """
        config: dict[str, VectorParams] = {}
        for vector_name, generator in self._models.items():
            config[vector_name] = VectorParams(
                size=generator.get_dimension(),
                distance=Distance.COSINE,
            )
        return config

    def get_active_vector_names(self) -> list[str]:
        """Return names of all currently loaded vector spaces.

        Returns:
            List of vector names, e.g., ["text", "code"].
            Always includes "text" (the default).
        """
        return list(self._models.keys())

    def get_model_info(self) -> dict[str, dict[str, Any]]:
        """Return info about all managed models.

        Returns:
            Dict with model details per vector name.
        """
        info: dict[str, dict[str, Any]] = {}
        for vector_name, generator in self._models.items():
            info[vector_name] = {
                "model_name": self._model_names[vector_name],
                "dimension": generator.get_dimension(),
                "device": self._device,
            }
        return info

    def get_vector_name_for_model(self, model_name: str) -> str | None:
        """Look up the vector_name for a given model name.

        Args:
            model_name: HuggingFace model name.

        Returns:
            The vector_name that uses this model, or None if not found.
        """
        for vname, mname in self._model_names.items():
            if mname == model_name:
                return vname
        return None

    @property
    def dimension(self) -> int:
        """Return the common vector dimension for all models."""
        return self._models["text"].get_dimension()

    @property
    def is_multi_model(self) -> bool:
        """Return True if more than one model is loaded."""
        return len(self._models) > 1
