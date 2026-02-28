"""Unit tests for concurrency safety (US6).

T038: Validates thread-safe access to shared state:
- QueryEngine.query() accepts per-request llm_client/critic parameters
- IndexingFailureCollector is thread-safe under concurrent access
- _resolve_mode() does not reload on every call (TTL cache)
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock


class TestQueryEngineParameterIsolation:
    """QueryEngine.query() should accept per-request llm_client/critic."""

    def test_query_accepts_llm_client_kwarg(self) -> None:
        """query() uses the llm_client keyword argument instead of self.llm_client."""
        from krag.orchestration.query_engine import QueryEngine

        default_llm = MagicMock()
        default_llm.generate.return_value = "default answer"
        override_llm = MagicMock()
        override_llm.generate.return_value = "override answer"

        engine = QueryEngine(
            vector_store=MagicMock(),
            embedding_generator=MagicMock(),
            llm_client=default_llm,
        )
        # Make retriever return empty so we hit the no-results path
        engine.retriever = MagicMock()
        engine.retriever.retrieve.return_value = [
            MagicMock(
                chunk_id="c1",
                file_path="/f.py",
                score=0.9,
                chunk_content="code",
                file_type="py",
                language=None,
                function_name=None,
                class_name=None,
                start_line=None,
                end_line=None,
                collection=None,
            )
        ]
        engine.prompt_builder = MagicMock()
        engine.prompt_builder.build.return_value = [{"role": "user", "content": "q"}]

        result = engine.query("test", llm_client=override_llm)

        override_llm.generate.assert_called_once()
        default_llm.generate.assert_not_called()
        assert result.answer == "override answer"

    def test_query_accepts_critic_kwarg(self) -> None:
        """query() uses the critic keyword argument instead of self.critic."""
        from krag.orchestration.query_engine import QueryEngine

        default_llm = MagicMock()
        default_llm.generate.return_value = "answer"
        override_critic = MagicMock()
        override_critic.enabled = True
        # Critic that filters everything out
        override_critic.score_chunks.return_value = []
        override_critic.filter_chunks.return_value = []
        override_critic.threshold = 3

        engine = QueryEngine(
            vector_store=MagicMock(),
            embedding_generator=MagicMock(),
            llm_client=default_llm,
            critic=None,  # Default: no critic
        )
        engine.retriever = MagicMock()
        engine.retriever.retrieve.return_value = [MagicMock()]

        result = engine.query("test", critic=override_critic)

        override_critic.score_chunks.assert_called_once()
        # All chunks filtered → insufficient context
        assert "insufficient" in result.answer.lower() or result.sources == []


class TestFailureCollectorThreadSafety:
    """IndexingFailureCollector should be safe under concurrent access."""

    def test_concurrent_record_and_read(self) -> None:
        """Concurrent record_failure + get_failures doesn't raise."""
        from krag.plugins.failures import IndexingFailureCollector

        collector = IndexingFailureCollector()
        errors: list[Exception] = []

        def writer(n: int) -> None:
            try:
                for i in range(50):
                    collector.record_failure(
                        file_path=Path(f"/file_{n}_{i}.py"),
                        reason=f"Error {n}-{i}",
                        plugin_name=f"plugin_{n}",
                    )
            except Exception as exc:
                errors.append(exc)

        def reader() -> None:
            try:
                for _ in range(50):
                    collector.get_failures()
                    collector.total_failures()
                    collector.failures_by_plugin()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        threads.append(threading.Thread(target=reader))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread safety violations: {errors}"
        assert collector.total_failures() == 250  # 5 writers × 50 each


class TestModeResolveTTL:
    """_resolve_mode() should not reload user modes on every call."""

    def test_resolve_mode_caches_reload(self) -> None:
        """Consecutive _resolve_mode() calls within TTL don't reload from disk."""
        from krag.models.configuration import Configuration, ModeConfiguration
        from kragd.service import KragService

        config = Configuration(
            directory_paths=[Path("/test").absolute()],
            modes_dir="/tmp/modes",
        )
        service = KragService(config)
        service._started = True
        service._indexing = False

        # Set up mode registry mock
        from krag.modes.mode_registry import ModeRegistry

        service.mode_registry = MagicMock(spec=ModeRegistry)
        service.mode_registry.get.return_value = ModeConfiguration(name="test")

        # Call twice in quick succession
        service._resolve_mode("test")
        service._resolve_mode("test")

        # load_user_modes should be called at most once (TTL prevents reload)
        assert service.mode_registry.load_user_modes.call_count <= 1
