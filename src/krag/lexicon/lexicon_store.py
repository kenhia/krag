"""LexiconStore — load and match project-specific terminology from JSON.

Loads a glossary from a JSON file (dict[str, str]), validates conformance to
contracts/lexicon-schema.json, pre-compiles word-boundary regex patterns, and
provides case-insensitive matching of terms against query text.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class LexiconValidationError(Exception):
    """Raised when a lexicon JSON file is malformed or violates the schema."""


class LexiconStore:
    """Project-specific terminology glossary loaded from a JSON file.

    Attributes:
        path: Source JSON file path (set after load).
        entries: Term → definition mapping.
    """

    def __init__(self) -> None:
        self.path: Path | None = None
        self.entries: dict[str, str] = {}
        self._patterns: dict[str, re.Pattern[str]] = {}

    def load(self, path: Path) -> int:
        """Load and validate a lexicon JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            Number of entries loaded.

        Raises:
            LexiconValidationError: If the file is missing, malformed, or
                violates the schema (non-dict, non-string values, empty values).
        """
        path = Path(path)
        if not path.exists():
            raise LexiconValidationError(f"Lexicon file does not exist: {path}")

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LexiconValidationError(f"Cannot read lexicon file: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LexiconValidationError(f"Invalid JSON in lexicon file: {exc}") from exc

        if not isinstance(data, dict):
            raise LexiconValidationError(
                f"Lexicon must be a JSON object (dict), got {type(data).__name__}"
            )

        # Validate all values are non-empty strings (per schema: additionalProperties.string.minLength=1)
        for key, value in data.items():
            if not isinstance(value, str):
                raise LexiconValidationError(
                    f"All lexicon values must be strings, "
                    f"but '{key}' has type {type(value).__name__}"
                )
            if len(value) < 1:
                raise LexiconValidationError(
                    f"Lexicon definition for '{key}' is empty (minLength=1 required)"
                )

        self.path = path
        self.entries = data
        self._compile_patterns()

        logger.info("Loaded lexicon with %d entries from %s", len(self.entries), path)
        return len(self.entries)

    def reload(self) -> int:
        """Reload the lexicon from the same path.

        Returns:
            Number of entries after reload.

        Raises:
            RuntimeError: If no lexicon has been loaded yet.
            LexiconValidationError: If the file is now invalid.
        """
        if self.path is None:
            raise RuntimeError("No lexicon file loaded — call load() first")
        return self.load(self.path)

    def match_terms(self, query: str) -> list[tuple[str, str]]:
        """Find all lexicon terms that appear in the query text.

        Uses case-insensitive word-boundary matching per R-04.

        Args:
            query: The query text to search for terms.

        Returns:
            List of (term, definition) tuples for matched terms.
        """
        if not query or not self._patterns:
            return []

        matches: list[tuple[str, str]] = []
        query_lower = query.lower()

        for term, pattern in self._patterns.items():
            if pattern.search(query_lower):
                matches.append((term, self.entries[term]))

        return matches

    def _compile_patterns(self) -> None:
        """Pre-compile word-boundary regex patterns for each term.

        Uses \\b + re.escape(term) + \\b for safe matching of terms that
        may contain regex metacharacters (e.g. C++, v2.0).
        """
        self._patterns = {}
        for term in self.entries:
            escaped = re.escape(term.lower())
            # Use word boundary when the term starts/ends with word chars,
            # otherwise just use the escaped pattern directly
            if term[0].isalnum() or term[0] == "_":
                pattern_str = r"\b" + escaped
            else:
                pattern_str = escaped

            if term[-1].isalnum() or term[-1] == "_":
                pattern_str += r"\b"

            self._patterns[term] = re.compile(pattern_str, re.IGNORECASE)
