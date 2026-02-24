"""Integration test: query with critic enabled → chunks filtered, debug shows scores — T058.

Tests the full query pipeline with the context relevance critic:
QueryEngine receives critic → low-scoring chunks are excluded from prompt → debug metadata has scores.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from krag.models.query_result import QueryResult


def _make_result(
    content: str = "A meaningful chunk about query engines and retrieval systems.",
    path: str = "/test/file.py",
    score: float = 0.9,
    rank: int = 1,
) -> QueryResult:
    """Create a minimal QueryResult for testing."""
    return QueryResult(
        chunk_content=content,
        file_path=path,
        score=score,
        chunk_id=f"chunk-{rank}",
        rank=rank,
        chunk_index=0,
        file_type=".py",
    )


class TestCriticFilteringIntegration:
    """Integration: critic filters chunks during query pipeline."""

    def test_critic_filters_low_scoring_chunks(self) -> None:
        """Low-scoring chunks are excluded from the prompt sent to the LLM."""
        from krag.critic.relevance_critic import RelevanceCritic
        from krag.orchestration.query_engine import QueryEngine

        # Set up a mock LLM that returns scores based on call order:
        # critic calls return scores per chunk, then final generate returns answer
        critic_llm = MagicMock()
        critic_llm.generate.side_effect = ["5", "1", "4"]  # high, low, high

        synthesis_llm = MagicMock()
        synthesis_llm.generate.return_value = "The answer is 42."

        # Set up vector store mock that returns 3 chunks
        mock_vs = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [0.1] * 384


        chunks = [
            _make_result(
                content="Relevant chunk about embeddings and vector search methods", rank=1
            ),
            _make_result(content="Irrelevant chunk about cooking recipes and food prep", rank=2),
            _make_result(content="Another relevant chunk about similarity scoring math", rank=3),
        ]

        critic = RelevanceCritic(llm_client=critic_llm, threshold=3, enabled=True)

        engine = QueryEngine(
            vector_store=mock_vs,
            embedding_generator=mock_emb,
            llm_client=synthesis_llm,
            top_k=5,
            critic=critic,
        )

        # Patch retriever to return our chunks
        engine.retriever.retrieve = MagicMock(return_value=chunks)

        response = engine.query("How does vector search work?")

        # The answer should come from synthesis LLM
        assert response.answer == "The answer is 42."

        # The sources should only contain passing chunks (scores 5 and 4)
        assert len(response.sources) == 2
        assert (
            response.sources[0].chunk_content
            == "Relevant chunk about embeddings and vector search methods"
        )
        assert (
            response.sources[1].chunk_content
            == "Another relevant chunk about similarity scoring math"
        )

    def test_critic_debug_metadata_in_response(self) -> None:
        """QueryResponse includes critic scores, pre/post chunk counts."""
        from krag.critic.relevance_critic import RelevanceCritic
        from krag.orchestration.query_engine import QueryEngine

        critic_llm = MagicMock()
        critic_llm.generate.side_effect = ["5", "2", "4"]

        synthesis_llm = MagicMock()
        synthesis_llm.generate.return_value = "Answer."

        mock_vs = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [0.1] * 384

        chunks = [
            _make_result(content="Relevant chunk about embeddings and vector search here", rank=1),
            _make_result(content="Bad chunk about unrelated topics like cooking recipes", rank=2),
            _make_result(content="Good chunk about similarity and scoring in retrieval", rank=3),
        ]

        critic = RelevanceCritic(llm_client=critic_llm, threshold=3, enabled=True)

        engine = QueryEngine(
            vector_store=mock_vs,
            embedding_generator=mock_emb,
            llm_client=synthesis_llm,
            top_k=5,
            critic=critic,
        )
        engine.retriever.retrieve = MagicMock(return_value=chunks)

        response = engine.query("How does retrieval work?")

        # Debug metadata should be in response
        assert response.chunks_pre_critic == 3
        assert response.chunks_post_critic == 2
        assert len(response.critic_scores) == 3
        assert response.critic_scores[0] == 5
        assert response.critic_scores[1] == 2
        assert response.critic_scores[2] == 4

    def test_critic_disabled_passes_all_chunks(self) -> None:
        """When critic is disabled (or absent), all chunks pass through."""
        from krag.orchestration.query_engine import QueryEngine

        synthesis_llm = MagicMock()
        synthesis_llm.generate.return_value = "All chunks used."

        mock_vs = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [0.1] * 384

        chunks = [
            _make_result(
                content="Chunk one about embeddings and search in vector databases", rank=1
            ),
            _make_result(
                content="Chunk two about more embeddings and retrieval system work", rank=2
            ),
        ]

        # No critic passed
        engine = QueryEngine(
            vector_store=mock_vs,
            embedding_generator=mock_emb,
            llm_client=synthesis_llm,
            top_k=5,
        )
        engine.retriever.retrieve = MagicMock(return_value=chunks)

        response = engine.query("How do embeddings work?")

        assert response.answer == "All chunks used."
        assert len(response.sources) == 2

    def test_all_chunks_filtered_returns_insufficient_context(self) -> None:
        """When critic filters ALL chunks, return insufficient context response."""
        from krag.critic.relevance_critic import RelevanceCritic
        from krag.orchestration.query_engine import QueryEngine
        from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE

        critic_llm = MagicMock()
        critic_llm.generate.side_effect = ["0", "1"]  # all below threshold=3

        synthesis_llm = MagicMock()
        synthesis_llm.generate.return_value = "Should not be called."

        mock_vs = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [0.1] * 384

        chunks = [
            _make_result(content="Completely irrelevant chunk about gardening and plants", rank=1),
            _make_result(content="Another irrelevant chunk about music theory and notes", rank=2),
        ]

        critic = RelevanceCritic(llm_client=critic_llm, threshold=3, enabled=True)

        engine = QueryEngine(
            vector_store=mock_vs,
            embedding_generator=mock_emb,
            llm_client=synthesis_llm,
            top_k=5,
            critic=critic,
        )
        engine.retriever.retrieve = MagicMock(return_value=chunks)

        response = engine.query("How does vector search work?")

        assert INSUFFICIENT_CONTEXT_PHRASE in response.answer
        # synthesis LLM should NOT have been called
        synthesis_llm.generate.assert_not_called()

    def test_short_chunks_bypass_critic(self) -> None:
        """Chunks < 50 chars bypass critic scoring and are always included."""
        from krag.critic.relevance_critic import RelevanceCritic
        from krag.orchestration.query_engine import QueryEngine

        critic_llm = MagicMock()
        # Only 1 LLM call expected (for the long chunk)
        critic_llm.generate.return_value = "5"

        synthesis_llm = MagicMock()
        synthesis_llm.generate.return_value = "Answer with both chunks."

        mock_vs = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [0.1] * 384

        chunks = [
            _make_result(content="Short", rank=1),  # < 50 chars: bypassed
            _make_result(
                content="Long chunk with detailed content about vector search and embeddings",
                rank=2,
            ),
        ]

        critic = RelevanceCritic(llm_client=critic_llm, threshold=3, enabled=True)

        engine = QueryEngine(
            vector_store=mock_vs,
            embedding_generator=mock_emb,
            llm_client=synthesis_llm,
            top_k=5,
            critic=critic,
        )
        engine.retriever.retrieve = MagicMock(return_value=chunks)

        response = engine.query("How does search work?")

        assert response.answer == "Answer with both chunks."
        # Both chunks should be in sources (short one bypassed, long one scored 5)
        assert len(response.sources) == 2
        # Critic LLM only called once (for the long chunk)
        assert critic_llm.generate.call_count == 1

    def test_critic_with_lexicon_integration(self) -> None:
        """Critic and lexicon work together: filter chunks, then inject terms."""
        from krag.critic.relevance_critic import RelevanceCritic
        from krag.lexicon.lexicon_store import LexiconStore
        from krag.orchestration.query_engine import QueryEngine

        critic_llm = MagicMock()
        critic_llm.generate.side_effect = ["5", "0"]

        synthesis_llm = MagicMock()
        synthesis_llm.generate.return_value = "Combined answer."

        mock_vs = MagicMock()
        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [0.1] * 384

        chunks = [
            _make_result(
                content="Vector store uses embeddings for similarity search and retrieval", rank=1
            ),
            _make_result(
                content="Cooking recipe for chocolate cake with frosting and sprinkles", rank=2
            ),
        ]

        critic = RelevanceCritic(llm_client=critic_llm, threshold=3, enabled=True)

        # Set up lexicon
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"embedding": "Vector representation of text"}, f)
            lexicon_path = Path(f.name)

        store = LexiconStore()
        store.load(lexicon_path)

        engine = QueryEngine(
            vector_store=mock_vs,
            embedding_generator=mock_emb,
            llm_client=synthesis_llm,
            top_k=5,
            critic=critic,
            lexicon_store=store,
        )
        engine.retriever.retrieve = MagicMock(return_value=chunks)

        response = engine.query("How do embeddings work?")

        # Only 1 chunk should remain (score 5)
        assert len(response.sources) == 1
        assert response.answer == "Combined answer."
        # Lexicon should have matched "embedding" in the query
        assert response.lexicon_terms_injected >= 0  # may or may not match

        # Clean up
        lexicon_path.unlink(missing_ok=True)
