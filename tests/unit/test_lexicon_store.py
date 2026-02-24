"""Unit tests for LexiconStore — T044.

Tests JSON loading, reload, match_terms, validation errors, and edge cases.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from krag.lexicon.lexicon_store import LexiconStore


class TestLexiconStoreLoad:
    """Test LexiconStore.load() with valid JSON files."""

    def test_load_valid_lexicon(self, tmp_path: Path) -> None:
        """A well-formed lexicon JSON loads correctly."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(
            json.dumps(
                {
                    "kragd": "The krag service daemon",
                    "RRF": "Reciprocal Rank Fusion",
                }
            )
        )

        store = LexiconStore()
        count = store.load(lexicon_file)

        assert count == 2
        assert store.entries == {
            "kragd": "The krag service daemon",
            "RRF": "Reciprocal Rank Fusion",
        }

    def test_load_empty_lexicon(self, tmp_path: Path) -> None:
        """An empty JSON object is a valid lexicon with zero entries."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text("{}")

        store = LexiconStore()
        count = store.load(lexicon_file)

        assert count == 0
        assert store.entries == {}

    def test_load_returns_entry_count(self, tmp_path: Path) -> None:
        """load() returns the number of entries loaded."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"a": "1", "b": "2", "c": "3"}))

        store = LexiconStore()
        assert store.load(lexicon_file) == 3

    def test_load_stores_path(self, tmp_path: Path) -> None:
        """After load(), the store remembers the path for reload."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text("{}")

        store = LexiconStore()
        store.load(lexicon_file)

        assert store.path == lexicon_file

    def test_load_precompiles_patterns(self, tmp_path: Path) -> None:
        """After load(), regex patterns are pre-compiled for each term."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"kragd": "daemon", "RRF": "fusion"}))

        store = LexiconStore()
        store.load(lexicon_file)

        assert len(store._patterns) == 2
        for _term, pattern in store._patterns.items():
            assert isinstance(pattern, re.Pattern)


class TestLexiconStoreValidation:
    """Test validation errors on malformed lexicon files."""

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Loading a file that doesn't exist raises LexiconValidationError."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        store = LexiconStore()
        with pytest.raises(LexiconValidationError, match="not found|does not exist"):
            store.load(tmp_path / "missing.json")

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        """Invalid JSON syntax raises LexiconValidationError."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        lexicon_file = tmp_path / "bad.json"
        lexicon_file.write_text("{broken json")

        store = LexiconStore()
        with pytest.raises(LexiconValidationError, match="JSON"):
            store.load(lexicon_file)

    def test_non_dict_json_raises(self, tmp_path: Path) -> None:
        """A JSON array (not object) raises LexiconValidationError."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        lexicon_file = tmp_path / "array.json"
        lexicon_file.write_text('["not", "a", "dict"]')

        store = LexiconStore()
        with pytest.raises(LexiconValidationError, match="dict|object"):
            store.load(lexicon_file)

    def test_non_string_value_raises(self, tmp_path: Path) -> None:
        """A lexicon with non-string values raises LexiconValidationError."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        lexicon_file = tmp_path / "bad_values.json"
        lexicon_file.write_text(json.dumps({"ok": "fine", "bad": 42}))

        store = LexiconStore()
        with pytest.raises(LexiconValidationError, match="string"):
            store.load(lexicon_file)

    def test_empty_string_value_raises(self, tmp_path: Path) -> None:
        """A lexicon with empty-string values raises LexiconValidationError."""
        from krag.lexicon.lexicon_store import LexiconStore, LexiconValidationError

        lexicon_file = tmp_path / "empty_val.json"
        lexicon_file.write_text(json.dumps({"term": ""}))

        store = LexiconStore()
        with pytest.raises(LexiconValidationError, match="empty"):
            store.load(lexicon_file)


class TestLexiconStoreMatchTerms:
    """Test LexiconStore.match_terms() — case-insensitive word-boundary matching."""

    @pytest.fixture()
    def loaded_store(self, tmp_path: Path) -> LexiconStore:
        """Create a store with several terms loaded."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(
            json.dumps(
                {
                    "kragd": "The krag service daemon",
                    "RRF": "Reciprocal Rank Fusion",
                    "LLM pool": "Manages text and code LLMs",
                    "VRAM": "Video RAM on the GPU",
                    "prompt preset": "Named configuration bundling system prompts",
                }
            )
        )
        store = LexiconStore()
        store.load(lexicon_file)
        return store

    def test_match_exact_term(self, loaded_store: LexiconStore) -> None:
        """Exact term match returns (term, definition) tuple."""
        matches = loaded_store.match_terms("What is kragd?")
        terms = [t for t, _ in matches]
        assert "kragd" in terms

    def test_match_case_insensitive(self, loaded_store: LexiconStore) -> None:
        """Matching is case-insensitive."""
        matches = loaded_store.match_terms("Tell me about KRAGD")
        terms = [t for t, _ in matches]
        assert "kragd" in terms

    def test_match_case_insensitive_uppercase_term(self, loaded_store: LexiconStore) -> None:
        """A term stored as uppercase matches lowercase query text."""
        matches = loaded_store.match_terms("what is rrF?")
        terms = [t for t, _ in matches]
        assert "RRF" in terms

    def test_match_word_boundary_only(self, loaded_store: LexiconStore) -> None:
        """Terms only match at word boundaries, not inside other words."""
        # "VRAM" should NOT match inside "programmatic"
        matches = loaded_store.match_terms("programmatic analysis")
        terms = [t for t, _ in matches]
        assert "VRAM" not in terms

    def test_match_multi_word_term(self, loaded_store: LexiconStore) -> None:
        """Multi-word terms like 'LLM pool' are matched."""
        matches = loaded_store.match_terms("The LLM pool manages multiple LLMs")
        terms = [t for t, _ in matches]
        assert "LLM pool" in terms

    def test_no_matches(self, loaded_store: LexiconStore) -> None:
        """A query with no lexicon terms returns an empty list."""
        matches = loaded_store.match_terms("something entirely unrelated")
        assert matches == []

    def test_multiple_matches(self, loaded_store: LexiconStore) -> None:
        """Multiple terms in the same query are all matched."""
        matches = loaded_store.match_terms("kragd uses RRF and VRAM management")
        terms = [t for t, _ in matches]
        assert "kragd" in terms
        assert "RRF" in terms
        assert "VRAM" in terms

    def test_match_returns_definitions(self, loaded_store: LexiconStore) -> None:
        """Matched pairs include the correct definitions."""
        matches = loaded_store.match_terms("What about RRF?")
        match_dict = dict(matches)
        assert match_dict["RRF"] == "Reciprocal Rank Fusion"

    def test_match_empty_query(self, loaded_store: LexiconStore) -> None:
        """An empty query returns no matches."""
        matches = loaded_store.match_terms("")
        assert matches == []

    def test_match_term_at_start_and_end(self, loaded_store: LexiconStore) -> None:
        """Terms at the beginning or end of the query match."""
        matches = loaded_store.match_terms("VRAM is important for kragd")
        terms = [t for t, _ in matches]
        assert "VRAM" in terms
        assert "kragd" in terms


class TestLexiconStoreReload:
    """Test LexiconStore.reload() — picking up file changes."""

    def test_reload_picks_up_changes(self, tmp_path: Path) -> None:
        """After file is modified, reload() loads new entries."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"old_term": "old def"}))

        store = LexiconStore()
        store.load(lexicon_file)
        assert "old_term" in store.entries

        # Modify file
        lexicon_file.write_text(json.dumps({"new_term": "new def"}))

        count = store.reload()
        assert count == 1
        assert "new_term" in store.entries
        assert "old_term" not in store.entries

    def test_reload_without_load_raises(self) -> None:
        """Calling reload() before load() raises RuntimeError."""
        from krag.lexicon.lexicon_store import LexiconStore

        store = LexiconStore()
        with pytest.raises(RuntimeError, match="No lexicon.*loaded"):
            store.reload()

    def test_reload_recompiles_patterns(self, tmp_path: Path) -> None:
        """After reload, regex patterns match new terms."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"alpha": "first"}))

        store = LexiconStore()
        store.load(lexicon_file)
        assert store.match_terms("alpha test") != []

        lexicon_file.write_text(json.dumps({"beta": "second"}))
        store.reload()

        assert store.match_terms("alpha test") == []
        assert store.match_terms("beta test") != []


class TestLexiconStoreEdgeCases:
    """Edge cases and special characters in terms."""

    def test_term_with_special_regex_chars(self, tmp_path: Path) -> None:
        """Terms with regex metacharacters (e.g. C++) are escaped properly."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"C++": "A programming language"}))

        store = LexiconStore()
        store.load(lexicon_file)

        matches = store.match_terms("Is C++ supported?")
        terms = [t for t, _ in matches]
        assert "C++" in terms

    def test_term_with_dots(self, tmp_path: Path) -> None:
        """Terms containing dots are matched literally."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"v2.0": "Version two"}))

        store = LexiconStore()
        store.load(lexicon_file)

        matches = store.match_terms("What changed in v2.0?")
        assert len(matches) == 1
        assert matches[0][0] == "v2.0"

    def test_hyphenated_term(self, tmp_path: Path) -> None:
        """Hyphenated terms like 'krag-direct' match properly."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"krag-direct": "In-process CLI"}))

        store = LexiconStore()
        store.load(lexicon_file)

        matches = store.match_terms("Use krag-direct for quick queries")
        terms = [t for t, _ in matches]
        assert "krag-direct" in terms

    def test_unicode_terms(self, tmp_path: Path) -> None:
        """Unicode characters in terms are handled correctly."""
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"naïve": "Simple approach"}), encoding="utf-8")

        store = LexiconStore()
        store.load(lexicon_file)

        matches = store.match_terms("This is a naïve implementation")
        terms = [t for t, _ in matches]
        assert "naïve" in terms
