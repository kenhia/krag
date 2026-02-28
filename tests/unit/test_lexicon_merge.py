"""Tests for LexiconStore.merge_entries() (T011).

T011: merge_entries() adds new terms without overwriting existing entries.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from krag.lexicon.lexicon_store import LexiconStore


class TestMergeEntries:
    """LexiconStore.merge_entries() behavior."""

    def test_adds_new_terms(self) -> None:
        store = LexiconStore()
        count = store.merge_entries(
            {"backlink": "A link between notes", "vault": "Root folder"},
            source="obsidian",
        )
        assert count == 2
        assert "backlink" in store.entries
        assert "vault" in store.entries

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        store = LexiconStore()
        # Load initial entries
        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(json.dumps({"vault": "User-defined vault meaning"}))
        store.load(lexicon_file)

        count = store.merge_entries(
            {"vault": "Plugin vault definition", "backlink": "A link"},
            source="obsidian",
        )
        # vault should NOT be overwritten; backlink is new
        assert count == 1
        assert store.entries["vault"] == "User-defined vault meaning"
        assert store.entries["backlink"] == "A link"

    def test_empty_entries_returns_zero(self) -> None:
        store = LexiconStore()
        count = store.merge_entries({}, source="test")
        assert count == 0

    def test_skips_non_string_values_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        store = LexiconStore()
        count = store.merge_entries(
            {"good": "valid definition", "bad": 123},  # type: ignore[dict-item]
            source="test",
        )
        assert count == 1
        assert "good" in store.entries
        assert "bad" not in store.entries
        assert "bad" in caplog.text

    def test_patterns_recompiled_after_merge(self) -> None:
        store = LexiconStore()
        store.merge_entries({"wikilink": "Double bracket link"}, source="test")
        # Pattern should exist and match
        matches = store.match_terms("I use a wikilink in my notes")
        assert len(matches) == 1
        assert matches[0][0] == "wikilink"

    def test_multiple_merges_accumulate(self) -> None:
        store = LexiconStore()
        store.merge_entries({"term1": "def1"}, source="plugin1")
        store.merge_entries({"term2": "def2"}, source="plugin2")
        assert len(store.entries) == 2
        assert "term1" in store.entries
        assert "term2" in store.entries
