"""Query engine for orchestrating retrieval and synthesis."""

import logging
from dataclasses import dataclass
from typing import Any

from krag.models.query_result import QueryResult
from krag.retrieval.retriever import Retriever
from krag.synthesis.llm_client import LLMClient
from krag.synthesis.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


@dataclass
class QueryResponse:
    """Response from query engine containing answer and sources."""

    answer: str
    sources: list[QueryResult]
    query: str


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
    ):
        """Initialize query engine.

        Args:
            vector_store: Vector store for search
            embedding_generator: Embedding generator for queries
            llm_client: LLM client for synthesis
            top_k: Number of results to retrieve
            max_context_length: Max context characters
        """
        self.retriever = Retriever(vector_store, embedding_generator)
        self.prompt_builder = PromptBuilder(max_context_length=max_context_length)
        self.llm_client = llm_client
        self.top_k = top_k

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
            QueryResponse with answer and sources
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

        # Retrieve relevant chunks
        k = top_k if top_k is not None else self.top_k
        logger.debug(f"Retrieving top {k} results")
        results = self.retriever.retrieve(query_text, top_k=k)
        logger.info(f"Retrieved {len(results)} results")

        # Build prompt
        prompt = self.prompt_builder.build(query_text, results)
        logger.debug(f"Built prompt with {len(prompt)} characters")

        # Generate answer
        logger.debug("Generating LLM response")
        answer = self.llm_client.generate(query_text, prompt)
        logger.info(f"Query completed, answer length: {len(answer)} characters")

        return QueryResponse(
            answer=answer,
            sources=results,
            query=query_text,
        )
