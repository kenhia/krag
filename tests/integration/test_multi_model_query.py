"""Integration test: Multi-model query pipeline + RRF merge.

T040: End-to-end test of the multi-model embedding and retrieval pipeline.

Tests the full flow:
1. EmbeddingOrchestrator with text + code models
2. QdrantVectorStore with named vectors
3. Upsert with per-model vector names
4. Query with multi-model embedding
5. RRF merge of results from both vector spaces
"""

from __future__ import annotations

import contextlib
import hashlib
from unittest.mock import MagicMock, patch

import numpy as np


def _uid() -> str:
    from uuid import uuid4

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


class TestMultiModelQueryPipeline:
    """T040: End-to-end multi-model query pipeline."""

    def test_index_and_query_with_named_vectors(self) -> None:
        """Index text + code chunks with named vectors, query returns merged results."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator
        from krag.models.text_chunk import TextChunk
        from krag.retrieval.rrf import reciprocal_rank_fusion
        from krag.storage.qdrant_impl import QdrantVectorStore

        # 1. Create orchestrator with text + code models
        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(
                default_model="text-model",
                device="cpu",
                additional_models={"code": "code-model"},
            )

        # 2. Create vector store with named vectors
        vector_config = orch.get_vector_config()
        store = QdrantVectorStore(
            collection_name="test_multi",
            vector_size=orch.dimension,
            storage_path=None,  # in-memory
            vectors_config=vector_config,
        )

        # 3. Create text chunks (markdown)
        text_chunks = [
            TextChunk(
                content="The retriever uses similarity search to find relevant documents.",
                chunk_id=_uid(),
                file_path="/tmp/readme.md",
                chunk_index=0,
                start_char=0,
                end_char=65,
                token_count=10,
            ),
            TextChunk(
                content="Configuration is loaded from TOML files in the config directory.",
                chunk_id=_uid(),
                file_path="/tmp/config.md",
                chunk_index=0,
                start_char=0,
                end_char=65,
                token_count=10,
            ),
        ]

        # 4. Create code chunks (Python)
        code_chunks = [
            TextChunk(
                content="def retrieve(self, query: str) -> list[QueryResult]: ...",
                chunk_id=_uid(),
                file_path="/tmp/retriever.py",
                chunk_index=0,
                start_char=0,
                end_char=55,
                token_count=12,
            ),
            TextChunk(
                content="class QdrantVectorStore(VectorStore): ...",
                chunk_id=_uid(),
                file_path="/tmp/qdrant.py",
                chunk_index=0,
                start_char=0,
                end_char=42,
                token_count=8,
            ),
        ]

        # 5. Embed text chunks with text model
        text_embeddings = orch.embed_chunks(text_chunks, vector_name="text")
        for chunk, emb in zip(text_chunks, text_embeddings, strict=True):
            store.upsert(
                [
                    {
                        "id": chunk.chunk_id,
                        "vector": {"text": emb},
                        "payload": {
                            "content": chunk.content,
                            "file_path": str(chunk.file_path),
                            "file_type": ".md",
                        },
                    }
                ]
            )

        # 6. Embed code chunks with code model
        code_embeddings = orch.embed_chunks(code_chunks, vector_name="code")
        for chunk, emb in zip(code_chunks, code_embeddings, strict=True):
            store.upsert(
                [
                    {
                        "id": chunk.chunk_id,
                        "vector": {"code": emb},
                        "payload": {
                            "content": chunk.content,
                            "file_path": str(chunk.file_path),
                            "file_type": ".py",
                        },
                    }
                ]
            )

        # 7. Query with both models
        query_embeddings = orch.embed_query("how does the retriever work?")
        assert "text" in query_embeddings
        assert "code" in query_embeddings

        # 8. Search both vector spaces
        text_results = store.search_named(
            query_vector=query_embeddings["text"],
            vector_name="text",
            limit=5,
        )
        code_results = store.search_named(
            query_vector=query_embeddings["code"],
            vector_name="code",
            limit=5,
        )

        # 9. Merge via RRF
        merged = reciprocal_rank_fusion(
            [text_results, code_results],
            k=60,
            limit=4,
        )

        # Should have results from both vector spaces
        assert len(merged) > 0
        assert len(merged) <= 4

    def test_single_model_backward_compatible(self) -> None:
        """Single-model orchestrator works like the old EmbeddingGenerator."""
        from krag.embeddings.orchestrator import EmbeddingOrchestrator
        from krag.models.text_chunk import TextChunk

        with _mock_sentence_transformer():
            orch = EmbeddingOrchestrator(default_model="text-model", device="cpu")

        chunks = [
            TextChunk(
                content="test document content",
                chunk_id=_uid(),
                file_path="/tmp/test.txt",
                chunk_index=0,
                start_char=0,
                end_char=20,
                token_count=3,
            ),
        ]

        embeddings = orch.embed_chunks(chunks, vector_name="text")
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 384

        query_result = orch.embed_query("test query")
        assert set(query_result.keys()) == {"text"}
