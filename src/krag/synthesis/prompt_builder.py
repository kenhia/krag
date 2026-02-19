"""Prompt builder for LLM synthesis with named presets.

Builds structured chat messages for LLM from query and retrieved context.
Supports named presets (strict, balanced, verbose) that bundle system prompts
with generation parameters for coherent behavior.
"""

from dataclasses import dataclass

from krag.config.path_reducer import PathReducer
from krag.models.query_result import QueryResult

# Canonical fallback phrase for "insufficient context" responses.
# Used in prompts and testable by the evaluation harness.
INSUFFICIENT_CONTEXT_PHRASE = (
    "I don't have enough information to answer that based on the available documents."
)


@dataclass(frozen=True)
class PromptPreset:
    """A named prompt configuration bundling system prompt and generation params.

    Each preset provides a coherent combination of prompt text and LLM
    generation parameters optimized for a specific use case.
    """

    name: str
    system_prompt: str
    temperature: float
    top_p: float
    repeat_penalty: float
    max_tokens: int
    description: str = ""


# Built-in preset definitions per research.md decisions
PROMPT_PRESETS: dict[str, PromptPreset] = {
    "strict": PromptPreset(
        name="strict",
        description="Concise, source-grounded answers only",
        system_prompt=(
            "You MUST answer ONLY using the provided context. "
            "Do NOT use any outside knowledge. "
            "Cite sources by number using parenthetical style, e.g. (1). "
            "Be concise and factual. "
            f'If the context does not contain the answer, respond exactly: "{INSUFFICIENT_CONTEXT_PHRASE}"'
        ),
        temperature=0.1,
        top_p=0.9,
        repeat_penalty=1.1,
        max_tokens=256,
    ),
    "balanced": PromptPreset(
        name="balanced",
        description="Detailed answers with numbered citations (default)",
        system_prompt=(
            "You are a helpful assistant that answers questions based on provided context "
            "from the user's personal knowledge base. "
            "Answer ONLY using the provided context. Do NOT use outside knowledge. "
            "Cite sources by number using parenthetical style, e.g. (1). "
            f'If the context does not contain enough information, respond exactly: "{INSUFFICIENT_CONTEXT_PHRASE}"'
        ),
        temperature=0.2,
        top_p=0.9,
        repeat_penalty=1.1,
        max_tokens=512,
    ),
    "verbose": PromptPreset(
        name="verbose",
        description="Exploratory answers with full context",
        system_prompt=(
            "You are a knowledgeable assistant that provides thorough answers based on "
            "the provided context from the user's personal knowledge base. "
            "Use ONLY the provided context. Cite sources by number, e.g. (1). "
            "Provide detailed explanations and include relevant quotes where helpful. "
            f'If the context does not contain the answer, respond exactly: "{INSUFFICIENT_CONTEXT_PHRASE}"'
        ),
        temperature=0.3,
        top_p=0.95,
        repeat_penalty=1.05,
        max_tokens=1024,
    ),
    "code": PromptPreset(
        name="code",
        description="Code-focused answers with snippets, symbols, and file references",
        system_prompt=(
            "You are a code-aware assistant that answers questions about source code. "
            "Answer ONLY using the provided context. Do NOT use outside knowledge. "
            "Include relevant code snippets in fenced code blocks when they help explain the answer. "
            "Reference function names, class names, and other symbols precisely. "
            "Cite source files by number, e.g. (1), including file paths. "
            "Keep answers technically precise and concise. "
            f'If the context does not contain enough information, respond exactly: "{INSUFFICIENT_CONTEXT_PHRASE}"'
        ),
        temperature=0.1,
        top_p=0.9,
        repeat_penalty=1.1,
        max_tokens=768,
    ),
}


class PromptBuilder:
    """Builds structured chat messages for LLM from query and retrieved context.

    Supports named presets and optional system prompt override.
    """

    def __init__(
        self,
        max_context_length: int = 4000,
        path_aliases: list[str] | None = None,
        preset_name: str = "balanced",
        system_prompt_override: str | None = None,
    ) -> None:
        """Initialize prompt builder.

        Args:
            max_context_length: Maximum characters for context section.
            path_aliases: Optional path aliases for display reduction.
            preset_name: Name of the built-in preset to use.
            system_prompt_override: Custom system prompt that replaces the preset's prompt.

        Raises:
            ValueError: If preset_name is not a known preset.
        """
        if preset_name not in PROMPT_PRESETS:
            raise ValueError(
                f"Unknown preset: '{preset_name}'. Available: {sorted(PROMPT_PRESETS.keys())}"
            )
        self.max_context_length = max_context_length
        self.path_aliases = path_aliases
        self.path_reducer = PathReducer(path_aliases)
        self.preset_name = preset_name
        self.preset = PROMPT_PRESETS[preset_name]
        self.system_prompt_override = system_prompt_override

    def build(self, query: str, results: list[QueryResult]) -> list[dict[str, str]]:
        """Build chat messages from query and retrieved results.

        Returns a list of two message dicts: system and user.
        Context chunks are numbered [1], [2], etc. with reduced paths.

        Args:
            query: User's query string.
            results: Retrieved context chunks.

        Returns:
            List of message dicts with "role" and "content" keys.
        """
        if not results:
            return self._build_no_context_messages(query)

        system_prompt = self.get_system_prompt()
        context = self._format_context(results)

        # Place context in the user message alongside the query.
        # Many models ground better when context is in the user turn rather
        # than buried in the system message.
        user_content = (
            f"Context from relevant documents:\n{context}\n\n"
            "---\n"
            "Using ONLY the context above, answer the following question. "
            "Cite sources by number, e.g. (1). "
            f'If the context does not contain the answer, respond exactly: "{INSUFFICIENT_CONTEXT_PHRASE}"\n\n'
            f"Question: {query}"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def get_system_prompt(self) -> str:
        """Return the active system prompt (override or preset).

        Returns:
            The system prompt string.
        """
        if self.system_prompt_override:
            return self.system_prompt_override
        return self.preset.system_prompt

    @staticmethod
    def available_presets() -> list[str]:
        """Return names of built-in presets.

        Returns:
            Sorted list of preset names.
        """
        return sorted(PROMPT_PRESETS.keys())

    def _format_context(self, results: list[QueryResult]) -> str:
        """Format results into numbered context string.

        Chunks are labeled [1] (path), [2] (path), etc.

        Args:
            results: Retrieved chunks.

        Returns:
            Formatted context string.
        """
        context_parts: list[str] = []
        total_length = 0

        for idx, result in enumerate(results, start=1):
            reduced_path = self.path_reducer.reduce(result.file_path)
            header = f"[{idx}] ({reduced_path})"
            content = result.chunk_content.strip()
            chunk_text = f"{header}\n{content}\n"
            chunk_length = len(chunk_text)

            if total_length + chunk_length > self.max_context_length:
                remaining = self.max_context_length - total_length
                if remaining > 100:
                    context_parts.append(chunk_text[:remaining] + "...")
                break

            context_parts.append(chunk_text)
            total_length += chunk_length

        return "\n".join(context_parts)

    def _build_no_context_messages(self, query: str) -> list[dict[str, str]]:
        """Build messages when no context is available.

        Instructs the LLM to respond with the canonical insufficient context phrase.

        Args:
            query: User's query.

        Returns:
            List of two message dicts.
        """
        system_content = (
            "You are a helpful assistant. "
            "The knowledge base search did not return any relevant results for this question. "
            f'Respond exactly: "{INSUFFICIENT_CONTEXT_PHRASE}"'
        )
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]
