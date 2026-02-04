"""Prompt builder for LLM synthesis."""

from krag.models.query_result import QueryResult


class PromptBuilder:
    """Builds prompts for LLM from query and retrieved context."""

    def __init__(self, max_context_length: int = 4000):
        """Initialize prompt builder.

        Args:
            max_context_length: Maximum characters for context section
        """
        self.max_context_length = max_context_length

    def build(self, query: str, results: list[QueryResult]) -> str:
        """Build prompt from query and results.

        Args:
            query: User's query
            results: Retrieved context chunks

        Returns:
            Formatted prompt for LLM
        """
        if not results:
            return self._build_no_context_prompt(query)

        context = self._format_context(results)

        prompt = f"""You are a helpful assistant that answers questions based on provided context from the user's personal knowledge base.

Context from relevant documents:
{context}

User Question: {query}

Instructions: Answer the user's question based solely on the context provided above. If the context doesn't contain enough information to answer the question, say so clearly. Be concise and accurate."""

        return prompt

    def _format_context(self, results: list[QueryResult]) -> str:
        """Format results into context string.

        Args:
            results: Retrieved chunks

        Returns:
            Formatted context string
        """
        context_parts = []
        total_length = 0

        for result in results:
            # Format source info
            source = f"[Source: {result.file_path.name}]"
            content = result.chunk_content.strip()

            chunk_text = f"{source}\n{content}\n"
            chunk_length = len(chunk_text)

            # Check if adding this chunk exceeds limit
            if total_length + chunk_length > self.max_context_length:
                # Add what we can and stop
                remaining = self.max_context_length - total_length
                if remaining > 100:  # Only add if meaningful space remains
                    context_parts.append(chunk_text[:remaining] + "...")
                break

            context_parts.append(chunk_text)
            total_length += chunk_length

        return "\n".join(context_parts)

    def _build_no_context_prompt(self, query: str) -> str:
        """Build prompt when no context is available.

        Args:
            query: User's query

        Returns:
            Prompt indicating no context
        """
        return f"""You are a helpful assistant.

User Question: {query}

Instructions: The knowledge base search did not return any relevant results for this question. Politely inform the user that you don't have enough context to answer their question based on their indexed documents."""
