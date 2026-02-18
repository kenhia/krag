"""Contract tests for EmbeddingOrchestrator.

T033: embed_chunks() returns list[list[float]]
T034: embed_query() returns dict[str, list[float]]

These verify the interface contract of EmbeddingOrchestrator — return types,
required methods, and structural guarantees. Uses mock embedding generators
to avoid downloading real models.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


def _uid() -> str:
    return str(uuid4())


class TestEmbeddingOrchestratorContract:
    """Contract tests for EmbeddingOrchestrator interface."""

    # -- T033: embed_chunks() contract --

    def test_embed_chunks_returns_list_of_float_lists(self) -> None:
        """embed_chunks() must return list[list[float]]."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        from krag.models.text_chunk import TextChunk

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

        result = orch.embed_chunks(chunks, vector_name="text")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])

    def test_embed_chunks_returns_one_vector_per_chunk(self) -> None:
        """embed_chunks() must return exactly one embedding per input chunk."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        from krag.models.text_chunk import TextChunk

        chunks = [
            TextChunk(
                content=f"chunk {i}",
                chunk_id=_uid(),
                file_path="/tmp/test.py",
                chunk_index=i,
                start_char=0,
                end_char=10,
                token_count=2,
            )
            for i in range(5)
        ]

        result = orch.embed_chunks(chunks, vector_name="text")
        assert len(result) == len(chunks)

    def test_embed_chunks_raises_key_error_for_unknown_vector_name(self) -> None:
        """embed_chunks() must raise KeyError for unregistered vector names."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        from krag.models.text_chunk import TextChunk

        chunks = [
            TextChunk(
                content="test",
                chunk_id=_uid(),
                file_path="/tmp/test.py",
                chunk_index=0,
                start_char=0,
                end_char=4,
                token_count=1,
            ),
        ]

        with pytest.raises(KeyError):
            orch.embed_chunks(chunks, vector_name="nonexistent")

    def test_embed_chunks_default_vector_name_is_text(self) -> None:
        """embed_chunks() with vector_name='text' uses the default model."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        from krag.models.text_chunk import TextChunk

        chunks = [
            TextChunk(
                content="test content",
                chunk_id=_uid(),
                file_path="/tmp/test.py",
                chunk_index=0,
                start_char=0,
                end_char=12,
                token_count=2,
            ),
        ]

        result = orch.embed_chunks(chunks, vector_name="text")
        assert isinstance(result, list)
        assert len(result) == 1

    # -- T034: embed_query() contract --

    def test_embed_query_returns_dict_of_str_to_float_list(self) -> None:
        """embed_query() must return dict[str, list[float]]."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        result = orch.embed_query("what does this function do?")
        assert isinstance(result, dict)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, list)
            assert all(isinstance(v, float) for v in value)

    def test_embed_query_always_includes_text_vector(self) -> None:
        """embed_query() must always include 'text' in the result."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        result = orch.embed_query("search query")
        assert "text" in result

    def test_embed_query_includes_all_loaded_models(self) -> None:
        """embed_query() must embed with ALL active models."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="mock-model",
                device="cpu",
                additional_models={"code": "mock-code-model"},
            )

        result = orch.embed_query("search query")
        assert "text" in result
        assert "code" in result

    def test_has_required_methods(self) -> None:
        """EmbeddingOrchestrator must have all contract-required methods."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        assert hasattr(EmbeddingOrchestrator, "embed_chunks")
        assert hasattr(EmbeddingOrchestrator, "embed_query")
        assert hasattr(EmbeddingOrchestrator, "get_vector_config")
        assert hasattr(EmbeddingOrchestrator, "get_active_vector_names")
        assert hasattr(EmbeddingOrchestrator, "get_model_info")
        assert hasattr(EmbeddingOrchestrator, "dimension")
        assert hasattr(EmbeddingOrchestrator, "is_multi_model")

    def test_dimension_property_returns_int(self) -> None:
        """dimension property must return an int."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        assert isinstance(orch.dimension, int)
        assert orch.dimension > 0

    def test_is_multi_model_property(self) -> None:
        """is_multi_model returns False for single model, True for multiple."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            single = EmbeddingOrchestrator(default_model="mock-model", device="cpu")
        assert single.is_multi_model is False

        with _mock_sentence_transformer():
            multi = EmbeddingOrchestrator(
                default_model="mock-model",
                device="cpu",
                additional_models={"code": "mock-code-model"},
            )
        assert multi.is_multi_model is True

    def test_get_vector_config_returns_dict(self) -> None:
        """get_vector_config() must return a dict mapping names to VectorParams."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="mock-model",
                device="cpu",
                additional_models={"code": "mock-code-model"},
            )

        config = orch.get_vector_config()
        assert isinstance(config, dict)
        assert "text" in config
        assert "code" in config

    def test_get_active_vector_names_includes_text(self) -> None:
        """get_active_vector_names() always includes 'text'."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="mock-model", device="cpu")

        names = orch.get_active_vector_names()
        assert isinstance(names, list)
        assert "text" in names


def _mock_sentence_transformer():
    """Context manager that patches SentenceTransformer to return a mock model.

    The mock model has consistent behavior:
    - encode() returns deterministic vectors
    - get_sentence_embedding_dimension() returns 384
    """
    import contextlib
    import hashlib

    import numpy as np

    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 384

    def _mock_encode(texts, **kwargs):
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        vecs = []
        for text in texts:
            h = hashlib.md5(text.encode()).hexdigest()
            vals = [int(h[i : i + 2], 16) / 255.0 for i in range(0, len(h), 2)]
            vec = np.array([(vals[i % len(vals)]) for i in range(384)], dtype=np.float32)
            # Normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vecs.append(vec)
        if kwargs.get("convert_to_numpy", True):
            return vecs[0] if is_single else np.array(vecs)
        return vecs

    mock_model.encode.side_effect = _mock_encode

    @contextlib.contextmanager
    def _ctx():
        with patch("krag.embeddings.generator.SentenceTransformer", return_value=mock_model):
            yield

    return _ctx()
