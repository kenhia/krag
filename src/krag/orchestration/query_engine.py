"""Query engine for orchestrating retrieval and synthesis."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from krag.models.query_result import QueryResult
from krag.retrieval.retriever import Retriever
from krag.synthesis.llm_client import LLMClient
from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE, PromptBuilder

logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """Response from query engine containing answer, sources, and prompt."""

    answer: str
    sources: list[QueryResult]
    query: str
    prompt: str = ""


class QueryEngine:
    """Orchestrates the complete query pipeline.

    Combines retrieval, prompt building, and LLM synthesis.
    """

    def __init__(
        self,
        vector_store: Any,
        embedding_generator: Any,
        llm_client: LLMClient,
        top_k: int = 5,
        max_context_length: int = 4000,
        path_aliases: list[str] | None = None,
        preset_name: str = "balanced",
        system_prompt_override: str | None = None,
        similarity_threshold: float | None = None,
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
        """
        self.retriever = Retriever(vector_store, embedding_generator)
        self.prompt_builder = PromptBuilder(
            max_context_length=max_context_length,
            path_aliases=path_aliases,
            preset_name=preset_name,
            system_prompt_override=system_prompt_override,
        )
        self.llm_client = llm_client
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def query(
        self,
        query_text: str,
        top_k: int | None = None,
    ) -> QueryResponse:
        """Execute complete query pipeline.

        Args:
            query_text: User's query string
            top_k: Override default top_k

        Returns:
            QueryResponse with answer, sources, and prompt
        """
        logger.info(f"Processing query: {query_text[:100]}...")

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

        # Build chat messages
        messages = self.prompt_builder.build(query_text, results)
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
            )

        # Generate answer via chat completion
        logger.debug("Generating LLM response")
        answer = self.llm_client.generate(messages=messages)
        logger.info(f"Query completed, answer length: {len(answer)} characters")

        return QueryResponse(
            answer=answer,
            sources=results,
            query=query_text,
            prompt=prompt_str,
        )
