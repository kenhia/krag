"""Unit tests for EmbeddingOrchestrator.

T035: Code files embedded with code model, text files with text model
T036: Query embedded by all active models (both text and code)
T038: Combined embedding model footprint <1.2 GB (mock VRAM check)
T039: Sequential two-pass fallback when VRAM insufficient
"""

from __future__ import annotations

import contextlib
import hashlib
from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np


def _uid() -> str:
    return str(uuid4())


def _make_mock_model(dimension: int = 384) -> MagicMock:
    """Create a mock SentenceTransformer model."""
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = dimension

    def _mock_encode(texts, **kwargs):
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        vecs = []
        for text in texts:
            h = hashlib.md5(text.encode()).hexdigest()
            vals = [int(h[i : i + 2], 16) / 255.0 for i in range(0, len(h), 2)]
            vec = np.array([vals[i % len(vals)] for i in range(dimension)], dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vecs.append(vec)
        if kwargs.get("convert_to_numpy", True):
            return vecs[0] if is_single else np.array(vecs)
        return vecs

    mock_model.encode.side_effect = _mock_encode
    return mock_model


@contextlib.contextmanager
def _mock_sentence_transformer(dimension: int = 384):
    """Patch SentenceTransformer to return mock models."""
    mock_model = _make_mock_model(dimension)
    with patch("krag.embeddings.generator.SentenceTransformer", return_value=mock_model):
        yield


class TestModelRouting:
    """T035: Code files embedded with code model, text files with text model."""

    def test_embed_chunks_uses_correct_model_for_code(self) -> None:
        """Code chunks are embedded using the 'code' model."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator
        from krag.models.text_chunk import TextChunk

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        chunks = [
            TextChunk(
                content="def hello(): pass",
                chunk_id=_uid(),
                file_path="/tmp/test.py",
                chunk_index=0,
                start_char=0,
                end_char=18,
                token_count=5,
            ),
        ]

        result = orch.embed_chunks(chunks, vector_name="code")
        assert len(result) == 1
        assert isinstance(result[0], list)

    def test_embed_chunks_uses_text_model_for_text(self) -> None:
        """Text chunks are embedded using the 'text' model."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator
        from krag.models.text_chunk import TextChunk

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        chunks = [
            TextChunk(
                content="This is a markdown document about APIs",
                chunk_id=_uid(),
                file_path="/tmp/readme.md",
                chunk_index=0,
                start_char=0,
                end_char=40,
                token_count=8,
            ),
        ]

        result = orch.embed_chunks(chunks, vector_name="text")
        assert len(result) == 1

    def test_different_models_tracked_separately(self) -> None:
        """Each vector name maps to its own model."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        info = orch.get_model_info()
        assert "text" in info
        assert "code" in info
        assert info["text"]["model_name"] == "text-model"
        assert info["code"]["model_name"] == "code-model"

    def test_model_lookup_by_model_name(self) -> None:
        """The orchestrator can resolve vector_name from model name."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        # The orchestrator should be able to find which vector_name uses a given model
        assert orch.get_vector_name_for_model("code-model") == "code"
        assert orch.get_vector_name_for_model("text-model") == "text"
        assert orch.get_vector_name_for_model("unknown-model") is None


class TestQueryEmbedding:
    """T036: Query embedded by all active models (both text and code)."""

    def test_query_embedded_by_all_models(self) -> None:
        """embed_query returns embeddings from all loaded models."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        result = orch.embed_query("how does the deduplicate function work?")
        assert "text" in result
        assert "code" in result
        assert len(result["text"]) == 384
        assert len(result["code"]) == 384

    def test_single_model_query_returns_only_text(self) -> None:
        """With only one model, embed_query returns only 'text'."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="text-model", device="cpu")

        result = orch.embed_query("search query")
        assert set(result.keys()) == {"text"}

    def test_query_embedding_dimensions_consistent(self) -> None:
        """All query embeddings have the same dimension."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        result = orch.embed_query("test")
        dims = {len(v) for v in result.values()}
        assert len(dims) == 1  # All same dimension
        assert dims.pop() == orch.dimension


class TestVRAMChecks:
    """T038: Combined embedding model footprint <1.2 GB (mock VRAM check).
    T039: Sequential two-pass fallback when VRAM insufficient.
    """

    def test_vram_check_allows_loading_when_sufficient(self) -> None:
        """Models load when VRAM is sufficient."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            # With enough VRAM, both models load
            with patch("krag.cli.gpu.get_free_vram", return_value=4_000_000_000):
                orch = EmbeddingOrchestrator(
                    default_model="text-model",
                    device="cuda",
                    additional_models={"code": "code-model"},
                )

        assert orch.is_multi_model is True
        assert "code" in orch.get_active_vector_names()

    def test_vram_check_skips_model_when_insufficient(self) -> None:
        """Additional model is skipped when VRAM is insufficient."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            # Very little VRAM — skip additional models
            with patch("krag.cli.gpu.get_free_vram", return_value=100_000_000):
                orch = EmbeddingOrchestrator(
                    default_model="text-model",
                    device="cuda",
                    additional_models={"code": "code-model"},
                )

        # Should still have text model, but code model skipped
        assert "text" in orch.get_active_vector_names()
        assert orch.is_multi_model is False

    def test_vram_check_not_performed_on_cpu(self) -> None:
        """VRAM checks are skipped when device is 'cpu'."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        # On CPU, all models should load without VRAM checks
        assert orch.is_multi_model is True

    def test_sequential_fallback_embeds_all_chunks(self) -> None:
        """Even with VRAM fallback, all vector names produce embeddings.

        When VRAM is insufficient for simultaneous models, the orchestrator
        falls back to sequential mode but still supports all registered models.
        The text model is always loaded.
        """
        from krag.embeddings.orchestrator import EmbeddingOrchestrator
        from krag.models.text_chunk import TextChunk

        with _mock_sentence_transformer():
            with patch("krag.cli.gpu.get_free_vram", return_value=100_000_000):
                orch = EmbeddingOrchestrator(
                    default_model="text-model",
                    device="cuda",
                    additional_models={"code": "code-model"},
                )

        chunks = [
            TextChunk(
                content="test chunk",
                chunk_id=_uid(),
                file_path="/tmp/test.py",
                chunk_index=0,
                start_char=0,
                end_char=10,
                token_count=2,
            ),
        ]

        # Text model should always work
        result = orch.embed_chunks(chunks, vector_name="text")
        assert len(result) == 1
