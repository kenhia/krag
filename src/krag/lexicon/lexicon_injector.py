"""LexiconInjector — select top matches and format for prompt injection.

Selects the most specific term matches (longest first), caps at max_entries
and max_chars, and formats them as a "Project glossary" section suitable
for appending to an LLM system prompt.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class LexiconInjector:
    """Selects and formats lexicon entries for prompt injection.

    Attributes:
        max_entries: Maximum number of glossary entries per query (default 10).
        max_chars: Maximum total characters of glossary text per query (default 1500).
    """

    def __init__(self, max_entries: int = 10, max_chars: int = 1500) -> None:
        self.max_entries = max_entries
        self.max_chars = max_chars

    def select_top(self, matches: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Select the top-N most specific matches within character budget.

        Sorts matches by term length descending (most specific first),
        then caps at max_entries and max_chars.

        Args:
            matches: List of (term, definition) tuples from LexiconStore.match_terms().

        Returns:
            Filtered and sorted list of (term, definition) tuples.
        """
        if not matches:
            return []

        # Sort by term length descending (most specific = longest first)
        sorted_matches = sorted(matches, key=lambda m: len(m[0]), reverse=True)

        selected: list[tuple[str, str]] = []
        total_chars = 0

        for term, definition in sorted_matches:
            if len(selected) >= self.max_entries:
                break

            # Calculate formatted line length: "- **term**: definition"
            line_len = len(f"- **{term}**: {definition}")

            if total_chars + line_len > self.max_chars:
                break

            selected.append((term, definition))
            total_chars += line_len

        return selected

    def format_glossary(self, entries: list[tuple[str, str]]) -> str:
        """Format selected entries as a prompt glossary section.

        Args:
            entries: List of (term, definition) tuples to format.

        Returns:
            Formatted glossary string, or empty string if no entries.
        """
        if not entries:
            return ""

        lines = [
            "Project glossary (use these definitions when the terms appear):",
        ]
        for term, definition in entries:
            lines.append(f"- **{term}**: {definition}")

        return "\n".join(lines)
