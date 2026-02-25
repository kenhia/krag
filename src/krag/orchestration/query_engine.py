"""Query engine for orchestrating retrieval and synthesis."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from krag.models.query_result import QueryResult
from krag.retrieval.retriever import Retriever
from krag.synthesis.llm_client import LLMClient
from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE, PromptBuilder

if TYPE_CHECKING:
    from krag.critic.relevance_critic import RelevanceCritic
    from krag.embeddings.generator import EmbeddingGenerator
    from krag.embeddings.orchestrator import EmbeddingOrchestrator
    from krag.lexicon.lexicon_injector import LexiconInjector
    from krag.lexicon.lexicon_store import LexiconStore
    from krag.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Sentinel to distinguish "no critic argument passed" from "critic=None"
_SENTINEL = object()


@dataclass
class QueryResponse:
    """Response from query engine containing answer, sources, and prompt."""

    answer: str
    sources: list[QueryResult]
    query: str
    prompt: str = ""
    lexicon_terms_injected: int = 0
    critic_scores: list[int] = field(default_factory=list)
    chunks_pre_critic: int = 0
    chunks_post_critic: int = 0


class QueryEngine:
    """Orchestrates the complete query pipeline.

    Combines retrieval, prompt building, and LLM synthesis.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        llm_client: LLMClient,
        top_k: int = 5,
        max_context_length: int = 4000,
        path_aliases: list[str] | None = None,
        preset_name: str = "balanced",
        system_prompt_override: str | None = None,
        similarity_threshold: float | None = None,
        embedding_orchestrator: EmbeddingOrchestrator | None = None,
        lexicon_store: LexiconStore | None = None,
        critic: RelevanceCritic | None = None,
    ):
        """Initialize query engine.

        Args:
            vector_store: Vector store for search
            embedding_generator: Embedding generator for queries
            llm_client: LLM client for synthesis
            top_k: Number of results to retrieve
            max_context_length: Max context characters
            path_aliases: Optional path aliases for display reduction
            preset_name: Prompt preset name (strict, balanced, verbose)
            system_prompt_override: Custom system prompt that replaces preset prompt
            similarity_threshold: Minimum similarity score for retrieval results
            embedding_orchestrator: Multi-model orchestrator for named-vector search
            lexicon_store: Optional lexicon store for term injection
            critic: Optional relevance critic for chunk filtering
        """
        self.retriever = Retriever(
            vector_store, embedding_generator, embedding_orchestrator=embedding_orchestrator
        )
        self.prompt_builder = PromptBuilder(
            max_context_length=max_context_length,
            path_aliases=path_aliases,
            preset_name=preset_name,
            system_prompt_override=system_prompt_override,
        )
        self.llm_client = llm_client
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.lexicon_store = lexicon_store
        self._lexicon_injector: LexiconInjector | None = None
        self.critic = critic

        if lexicon_store is not None:
            from krag.lexicon.lexicon_injector import LexiconInjector

            self._lexicon_injector = LexiconInjector()

    def query(
        self,
        query_text: str,
        top_k: int | None = None,
        llm_client: LLMClient | None = None,
        critic: RelevanceCritic | None = _SENTINEL,
    ) -> QueryResponse:
        """Execute complete query pipeline.

        Args:
            query_text: User's query string
            top_k: Override default top_k
            llm_client: Per-request LLM client (defaults to self.llm_client)
            critic: Per-request relevance critic (defaults to self.critic).
                Pass ``None`` explicitly to disable critic.

        Returns:
            QueryResponse with answer, sources, and prompt
        """
        logger.info(f"Processing query: {query_text[:100]}...")

        # Resolve per-request overrides (avoid mutating shared state)
        effective_llm = llm_client if llm_client is not None else self.llm_client
        effective_critic = self.critic if critic is _SENTINEL else critic

        # Validate query
        if not query_text or not query_text.strip():
            logger.warning("Empty query received")
            return QueryResponse(
                answer="Please provide a valid question.",
                sources=[],
                query=query_text,
            )

        # Retrieve relevant chunks (with threshold filtering if configured)
        k = top_k if top_k is not None else self.top_k
        logger.debug(f"Retrieving top {k} results")
        results = self.retriever.retrieve(
            query_text, top_k=k, similarity_threshold=self.similarity_threshold
        )
        logger.info(f"Retrieved {len(results)} results")

        # Apply context relevance critic (T060: after retrieval, before prompt)
        critic_scores: list[int] = []
        chunks_pre_critic = len(results)
        chunks_post_critic = len(results)

        if effective_critic is not None and effective_critic.enabled and results:
            scored_chunks = effective_critic.score_chunks(query_text, results)
            critic_scores = [s.critic_score for s in scored_chunks]
            filtered_results = effective_critic.filter_chunks(scored_chunks)
            chunks_post_critic = len(filtered_results)
            logger.info(
                "Critic: %d/%d chunks passed (threshold %d)",
                chunks_post_critic,
                chunks_pre_critic,
                effective_critic.threshold,
            )
            results = filtered_results

            # T061: Handle all-chunks-filtered case
            if not results:
                logger.info("All chunks filtered by critic — returning insufficient context")
                return QueryResponse(
                    answer=INSUFFICIENT_CONTEXT_PHRASE,
                    sources=[],
                    query=query_text,
                    prompt="",
                    lexicon_terms_injected=0,
                    critic_scores=critic_scores,
                    chunks_pre_critic=chunks_pre_critic,
                    chunks_post_critic=0,
                )

        # Match lexicon terms and build glossary for prompt injection
        lexicon_glossary: str | None = None
        lexicon_terms_count = 0
        if self.lexicon_store is not None and self._lexicon_injector is not None:
            matches = self.lexicon_store.match_terms(query_text)
            if matches:
                selected = self._lexicon_injector.select_top(matches)
                lexicon_glossary = self._lexicon_injector.format_glossary(selected)
                lexicon_terms_count = len(selected)
                logger.debug("Injecting %d lexicon terms into prompt", lexicon_terms_count)

        # Build chat messages
        messages = self.prompt_builder.build(query_text, results, lexicon_glossary=lexicon_glossary)
        prompt_str = json.dumps(messages, indent=2)
        logger.debug("Built prompt with %d messages", len(messages))

        # Skip LLM call if no results (empty retrieval → insufficient context)
        if not results:
            logger.info("No results after retrieval/filtering, returning insufficient context")
            return QueryResponse(
                answer=INSUFFICIENT_CONTEXT_PHRASE,
                sources=[],
                query=query_text,
                prompt=prompt_str,
                lexicon_terms_injected=0,
                critic_scores=critic_scores,
                chunks_pre_critic=chunks_pre_critic,
                chunks_post_critic=chunks_post_critic,
            )

        # Generate answer via chat completion
        logger.debug("Generating LLM response")
        answer = effective_llm.generate(messages=messages)
        logger.info(f"Query completed, answer length: {len(answer)} characters")

        return QueryResponse(
            answer=answer,
            sources=results,
            query=query_text,
            prompt=prompt_str,
            lexicon_terms_injected=lexicon_terms_count,
            critic_scores=critic_scores,
            chunks_pre_critic=chunks_pre_critic,
            chunks_post_critic=chunks_post_critic,
        )
