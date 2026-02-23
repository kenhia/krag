"""Integration tests for mode-driven query pipeline — T031.

Validates that selecting a mode correctly applies its collections,
LLM slot, preset, and retrieval parameters to the query pipeline.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


class TestModeQueryIntegration:
    """Mode selection wires retrieval parameters end-to-end."""

    def test_code_mode_applies_preset_and_top_k(self) -> None:
        """Querying in 'code' mode uses preset='code' and top_k=10."""
        from krag.modes.mode_registry import ModeRegistry
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def search(self, vector, limit=5):
                return [
                    {
                        "id": "c1",
                        "score": 0.9,
                        "payload": {
                            "content": "def hello(): pass",
                            "file_path": "/src/hello.py",
                            "chunk_index": 0,
                            "file_type": "python",
                        },
                    }
                ]

        registry = ModeRegistry()
        registry.load_builtins()
        code_mode = registry.get("code")

        engine = QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
            top_k=code_mode.top_k,
            preset_name=code_mode.preset,
            similarity_threshold=code_mode.similarity_threshold,
        )

        assert engine.top_k == 10
        assert engine.prompt_builder.preset_name == "code"
        assert engine.similarity_threshold == 0.15

    def test_default_mode_applies_balanced_preset(self) -> None:
        """Querying in 'default' mode uses preset='balanced' and top_k=5."""
        from krag.modes.mode_registry import ModeRegistry
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def search(self, vector, limit=5):
                return []

        registry = ModeRegistry()
        registry.load_builtins()
        default_mode = registry.get("default")

        engine = QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
            top_k=default_mode.top_k,
            preset_name=default_mode.preset,
            similarity_threshold=default_mode.similarity_threshold,
        )

        assert engine.top_k == 5
        assert engine.prompt_builder.preset_name == "balanced"
        assert engine.similarity_threshold == 0.2

    def test_mode_collections_exposed(self) -> None:
        """A mode's collections dict is available for routing decisions."""
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        registry.load_builtins()

        code_mode = registry.get("code")
        assert "code" in code_mode.collections
        assert "tests" in code_mode.collections
        assert "docs" not in code_mode.collections

    def test_user_mode_in_query_pipeline(self, tmp_path: Path) -> None:
        """A user-defined mode is also usable in the query pipeline."""
        from krag.modes.mode_registry import ModeRegistry
        from krag.orchestration.query_engine import QueryEngine
        from tests.fixtures.mock_embeddings import MockEmbeddingGenerator
        from tests.fixtures.mock_llm import MockLLMClient

        class MockVectorStore:
            def search(self, vector, limit=5):
                return []

        toml_file = tmp_path / "verbose-docs.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "verbose-docs"
            description = "Verbose docs mode"

            [collections]
            docs = 1.0

            [llm]
            slot = "text"

            [prompt]
            preset = "verbose"

            [retrieval]
            top_k = 20
            similarity_threshold = 0.1
        """)
        )

        registry = ModeRegistry()
        registry.load_builtins()
        registry.load_user_modes(tmp_path)

        mode = registry.get("verbose-docs")

        engine = QueryEngine(
            vector_store=MockVectorStore(),
            embedding_generator=MockEmbeddingGenerator(),
            llm_client=MockLLMClient(),
            top_k=mode.top_k,
            preset_name=mode.preset,
            similarity_threshold=mode.similarity_threshold,
        )

        assert engine.top_k == 20
        assert engine.prompt_builder.preset_name == "verbose"
        assert engine.similarity_threshold == 0.1
