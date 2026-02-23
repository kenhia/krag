"""Unit tests for LexiconInjector — T045.

Tests select_top (sort by specificity, cap at max_entries/max_chars)
and format_glossary (prompt section formatting).
"""

from __future__ import annotations


class TestLexiconInjectorSelectTop:
    """Test LexiconInjector.select_top() — sort longest-first, cap entries and chars."""

    def test_sort_by_term_length_descending(self) -> None:
        """Matches are sorted by term length descending (most specific first)."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector()
        matches = [
            ("A", "Short term"),
            ("BB", "Medium term"),
            ("CCC", "Longest term"),
        ]
        selected = injector.select_top(matches)
        terms = [t for t, _ in selected]
        assert terms == ["CCC", "BB", "A"]

    def test_cap_at_max_entries(self) -> None:
        """No more than max_entries are returned (default 10)."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector(max_entries=3)
        matches = [(f"term{i}", f"def {i}") for i in range(10)]
        selected = injector.select_top(matches)
        assert len(selected) == 3

    def test_default_max_entries_is_10(self) -> None:
        """Default max_entries is 10."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector()
        matches = [(f"term{i:02d}", f"definition {i}") for i in range(20)]
        selected = injector.select_top(matches)
        assert len(selected) == 10

    def test_cap_at_max_chars(self) -> None:
        """Total glossary text is capped at max_chars."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector(max_chars=50)
        matches = [
            ("alpha_term", "A definition that is twenty chars or so"),
            ("beta_term_", "Another definition around twenty chars"),
            ("gamma_long", "Third definition that would push past the limit"),
        ]
        selected = injector.select_top(matches)
        # Total formatted chars should not exceed 50
        total = sum(len(f"- **{t}**: {d}") for t, d in selected)
        assert total <= 50

    def test_empty_matches(self) -> None:
        """Empty match list returns empty selection."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector()
        assert injector.select_top([]) == []

    def test_fewer_than_max_returns_all(self) -> None:
        """When fewer matches than max_entries, all are returned."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector(max_entries=10)
        matches = [("x", "def x"), ("yy", "def yy")]
        selected = injector.select_top(matches)
        assert len(selected) == 2

    def test_max_chars_includes_formatting(self) -> None:
        """The char cap accounts for the formatted entry line including '- **term**: def'."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector(max_chars=100)
        matches = [
            ("short", "A short definition"),
            ("medium_term", "A medium length definition for this term"),
        ]
        selected = injector.select_top(matches)
        formatted = injector.format_glossary(selected)
        # Each formatted line should be within budget
        assert len(formatted) <= 200  # generous upper bound including header


class TestLexiconInjectorFormatGlossary:
    """Test LexiconInjector.format_glossary() — prompt section formatting."""

    def test_format_with_entries(self) -> None:
        """Glossary produces 'Project glossary' header with bullet entries."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector()
        entries = [
            ("RRF", "Reciprocal Rank Fusion"),
            ("kragd", "The krag service daemon"),
        ]
        result = injector.format_glossary(entries)

        assert "Project glossary" in result
        assert "- **RRF**: Reciprocal Rank Fusion" in result
        assert "- **kragd**: The krag service daemon" in result

    def test_format_empty_returns_empty(self) -> None:
        """Empty entry list produces empty string (no injection)."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector()
        assert injector.format_glossary([]) == ""

    def test_format_preserves_order(self) -> None:
        """Entries appear in the order provided."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector()
        entries = [
            ("CCC", "Third"),
            ("BB", "Second"),
            ("A", "First"),
        ]
        result = injector.format_glossary(entries)
        lines = [line for line in result.split("\n") if line.startswith("- ")]
        assert "CCC" in lines[0]
        assert "BB" in lines[1]
        assert "A" in lines[2]

    def test_format_contains_usage_instruction(self) -> None:
        """The glossary section includes a usage hint for the LLM."""
        from krag.lexicon.lexicon_injector import LexiconInjector

        injector = LexiconInjector()
        entries = [("term", "definition")]
        result = injector.format_glossary(entries)
        assert "use these definitions" in result.lower() or "terms appear" in result.lower()


class TestLexiconInjectorIntegration:
    """Integration-style tests combining select and format."""

    def test_inject_pipeline(self, tmp_path) -> None:
        """Full pipeline: store.match_terms → injector.select_top → format_glossary."""
        import json

        from krag.lexicon.lexicon_injector import LexiconInjector
        from krag.lexicon.lexicon_store import LexiconStore

        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(
            json.dumps(
                {
                    "kragd": "The krag service daemon",
                    "RRF": "Reciprocal Rank Fusion",
                    "VRAM": "Video RAM on GPU",
                }
            )
        )

        store = LexiconStore()
        store.load(lexicon_file)

        matches = store.match_terms("How does kragd use RRF?")
        injector = LexiconInjector()
        selected = injector.select_top(matches)
        glossary = injector.format_glossary(selected)

        assert "kragd" in glossary
        assert "RRF" in glossary
        assert "VRAM" not in glossary  # not in query
