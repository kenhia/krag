"""Integration test: query with lexicon → definitions injected into prompt — T047.

Tests the full flow: LexiconStore + LexiconInjector + PromptBuilder integration.
Verifies that matching lexicon terms appear in the system prompt sent to the LLM.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from krag.models.query_result import QueryResult


def _make_result(content: str = "Test content", path: str = "/test/file.py") -> QueryResult:
    """Create a minimal QueryResult for testing."""
    return QueryResult(
        chunk_content=content,
        file_path=path,
        score=0.9,
        chunk_id="test-chunk-1",
        rank=1,
        chunk_index=0,
        file_type=".py",
    )


class TestLexiconPromptInjection:
    """Integration: lexicon terms are injected into the system prompt."""

    @pytest.fixture()
    def lexicon_file(self, tmp_path: Path) -> Path:
        """Create a lexicon JSON file with test entries."""
        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(
            json.dumps(
                {
                    "kragd": "The krag service daemon — a FastAPI server that loads models once and serves queries over HTTP",
                    "RRF": "Reciprocal Rank Fusion — a score merging algorithm",
                    "LLM pool": "The component managing text and code LLMs with hot-swap",
                    "VRAM": "Video RAM on the GPU",
                    "prompt preset": "A named configuration bundling system prompts with generation parameters",
                }
            )
        )
        return lexicon_file

    def test_matching_terms_appear_in_system_prompt(self, lexicon_file: Path) -> None:
        """When query contains lexicon terms, they appear in the system prompt."""
        from krag.lexicon.lexicon_injector import LexiconInjector
        from krag.lexicon.lexicon_store import LexiconStore
        from krag.synthesis.prompt_builder import PromptBuilder

        store = LexiconStore()
        store.load(lexicon_file)
        injector = LexiconInjector()

        matches = store.match_terms("How does kragd use RRF?")
        selected = injector.select_top(matches)
        glossary = injector.format_glossary(selected)

        builder = PromptBuilder()
        results = [_make_result()]
        messages = builder.build("How does kragd use RRF?", results, lexicon_glossary=glossary)

        system_msg = messages[0]["content"]
        assert "kragd" in system_msg
        assert "RRF" in system_msg
        assert "Project glossary" in system_msg

    def test_no_matching_terms_no_glossary(self, lexicon_file: Path) -> None:
        """When query has no matching terms, no glossary section is added."""
        from krag.lexicon.lexicon_injector import LexiconInjector
        from krag.lexicon.lexicon_store import LexiconStore
        from krag.synthesis.prompt_builder import PromptBuilder

        store = LexiconStore()
        store.load(lexicon_file)
        injector = LexiconInjector()

        matches = store.match_terms("something unrelated entirely")
        selected = injector.select_top(matches)
        glossary = injector.format_glossary(selected)

        builder = PromptBuilder()
        results = [_make_result()]
        messages = builder.build("something unrelated entirely", results, lexicon_glossary=glossary)

        system_msg = messages[0]["content"]
        assert "Project glossary" not in system_msg

    def test_glossary_not_in_user_message(self, lexicon_file: Path) -> None:
        """Glossary should be in the system message, not user message."""
        from krag.lexicon.lexicon_injector import LexiconInjector
        from krag.lexicon.lexicon_store import LexiconStore
        from krag.synthesis.prompt_builder import PromptBuilder

        store = LexiconStore()
        store.load(lexicon_file)
        injector = LexiconInjector()

        matches = store.match_terms("How does kragd work?")
        selected = injector.select_top(matches)
        glossary = injector.format_glossary(selected)

        builder = PromptBuilder()
        results = [_make_result()]
        messages = builder.build("How does kragd work?", results, lexicon_glossary=glossary)

        user_msg = messages[1]["content"]
        assert "Project glossary" not in user_msg

    def test_without_lexicon_prompt_unchanged(self) -> None:
        """When no lexicon glossary is provided, prompt is unchanged from baseline."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder()
        results = [_make_result()]

        # Without glossary (empty string)
        messages_without = builder.build("test query", results, lexicon_glossary="")
        # Without glossary (None)
        messages_none = builder.build("test query", results, lexicon_glossary=None)
        # Without parameter
        messages_default = builder.build("test query", results)

        # All three should produce the same system prompt
        assert messages_without[0]["content"] == messages_default[0]["content"]
        assert messages_none[0]["content"] == messages_default[0]["content"]

    def test_unmatched_terms_not_injected(self, lexicon_file: Path) -> None:
        """Only terms that match the query are in the glossary."""
        from krag.lexicon.lexicon_injector import LexiconInjector
        from krag.lexicon.lexicon_store import LexiconStore
        from krag.synthesis.prompt_builder import PromptBuilder

        store = LexiconStore()
        store.load(lexicon_file)
        injector = LexiconInjector()

        # Query only mentions kragd, not RRF or VRAM
        matches = store.match_terms("Tell me about kragd")
        selected = injector.select_top(matches)
        glossary = injector.format_glossary(selected)

        builder = PromptBuilder()
        results = [_make_result()]
        messages = builder.build("Tell me about kragd", results, lexicon_glossary=glossary)

        system_msg = messages[0]["content"]
        assert "kragd" in system_msg
        assert "VRAM" not in system_msg
        assert "RRF" not in system_msg


class TestLexiconQueryEngineIntegration:
    """Integration: lexicon wired through QueryEngine."""

    @pytest.fixture()
    def lexicon_file(self, tmp_path: Path) -> Path:
        """Create a lexicon JSON file."""
        lexicon_file = tmp_path / "lexicon.json"
        lexicon_file.write_text(
            json.dumps(
                {
                    "kragd": "The krag service daemon",
                    "RRF": "Reciprocal Rank Fusion",
                }
            )
        )
        return lexicon_file

    def test_query_engine_with_lexicon_injects_terms(self, lexicon_file: Path) -> None:
        """QueryEngine with lexicon_store injects matching terms into prompt."""
        from krag.lexicon.lexicon_store import LexiconStore
        from krag.orchestration.query_engine import QueryEngine

        store = LexiconStore()
        store.load(lexicon_file)

        # Create mocks for QueryEngine dependencies
        mock_vector_store = MagicMock()
        mock_embedding_gen = MagicMock()
        mock_llm_client = MagicMock()
        mock_llm_client.generate.return_value = "Test answer about kragd"

        # Mock retriever to return results
        mock_results = [_make_result("kragd is the service daemon")]

        engine = QueryEngine(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
            llm_client=mock_llm_client,
            lexicon_store=store,
        )

        # Mock the retriever to return our results
        engine.retriever = MagicMock()
        engine.retriever.retrieve.return_value = mock_results

        engine.query("How does kragd work?")

        # Verify LLM was called with messages containing the glossary
        call_args = mock_llm_client.generate.call_args
        messages = (
            call_args[1].get("messages") or call_args[0][0]
            if call_args[0]
            else call_args[1]["messages"]
        )
        system_content = messages[0]["content"]
        assert "kragd" in system_content
        assert "Project glossary" in system_content

    def test_query_engine_without_lexicon_works(self) -> None:
        """QueryEngine without lexicon_store works normally (no injection)."""
        from krag.orchestration.query_engine import QueryEngine

        mock_vector_store = MagicMock()
        mock_embedding_gen = MagicMock()
        mock_llm_client = MagicMock()
        mock_llm_client.generate.return_value = "Test answer"

        engine = QueryEngine(
            vector_store=mock_vector_store,
            embedding_generator=mock_embedding_gen,
            llm_client=mock_llm_client,
        )

        engine.retriever = MagicMock()
        engine.retriever.retrieve.return_value = [_make_result()]

        response = engine.query("test query")

        # Should still work
        assert response.answer == "Test answer"
