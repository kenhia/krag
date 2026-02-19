"""Integration tests for LLM routing through the query pipeline.

T062: End-to-end routing: code-heavy retrieval results → code LLM → response.
Validates that the full query flow routes through LLMPool correctly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from krag.models.query_result import QueryResult


def _uid() -> str:
    from uuid import uuid4

    return str(uuid4())


def _make_query_result(
    file_type: str = ".py",
    file_path: str = "/tmp/test.py",
    content: str = "def foo(): pass",
) -> QueryResult:
    return QueryResult(
        chunk_id=_uid(),
        score=0.85,
        rank=1,
        chunk_content=content,
        file_path=Path(file_path),
        chunk_index=0,
        file_type=file_type,
    )


@pytest.fixture
def _mock_llama():
    """Patch Llama to avoid loading real models."""
    mock_llama_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "LLM response from mock"}}]
    }
    mock_llama_cls.return_value = mock_instance
    with patch("llama_cpp.Llama", mock_llama_cls):
        yield mock_llama_cls


@pytest.fixture
def tmp_model_files(tmp_path: Path) -> tuple[Path, Path]:
    """Create temporary GGUF model files."""
    text_model = tmp_path / "text-model.gguf"
    text_model.write_bytes(b"\x00" * 1024)
    code_model = tmp_path / "code-model.gguf"
    code_model.write_bytes(b"\x00" * 1024)
    return text_model, code_model


class TestLLMRoutingIntegration:
    """T062: End-to-end LLM routing integration tests."""

    def test_code_heavy_query_routes_to_code_llm(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T062a: Code-heavy retrieval results route to code LLM."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, code_path = tmp_model_files

        with patch(
            "krag.cli.gpu.get_free_vram",
            return_value=32_000_000_000,
        ):
            pool = LLMPool(
                text_model_path=text_path,
                code_model_path=code_path,
                load_multi_llm=True,
            )

        # Simulate code-heavy retrieval results
        chunks = [
            _make_query_result(file_type=".py", file_path="/tmp/main.py"),
            _make_query_result(file_type=".py", file_path="/tmp/utils.py"),
            _make_query_result(file_type=".ts", file_path="/tmp/app.ts"),
            _make_query_result(file_type=".md", file_path="/tmp/README.md"),
        ]

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "How does the main function work?"},
        ]

        response, llm_used = pool.route_and_generate(messages, chunks)

        assert isinstance(response, str)
        assert len(response) > 0
        assert llm_used == "code"

        pool.close()

    def test_text_heavy_query_routes_to_text_llm(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T062b: Text-heavy retrieval results route to text LLM."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, code_path = tmp_model_files

        with patch(
            "krag.cli.gpu.get_free_vram",
            return_value=32_000_000_000,
        ):
            pool = LLMPool(
                text_model_path=text_path,
                code_model_path=code_path,
                load_multi_llm=True,
            )

        # Text-heavy retrieval results (no code files → markdown not boosted)
        chunks = [
            _make_query_result(file_type=".md", file_path="/tmp/docs.md", content="# Docs"),
            _make_query_result(file_type=".txt", file_path="/tmp/notes.txt", content="Notes"),
            _make_query_result(file_type=".md", file_path="/tmp/FAQ.md", content="FAQ"),
            _make_query_result(file_type=".txt", file_path="/tmp/other.txt", content="Other"),
        ]

        messages = [
            {"role": "user", "content": "What does the documentation say?"},
        ]

        response, llm_used = pool.route_and_generate(messages, chunks)

        assert isinstance(response, str)
        assert llm_used == "text"

        pool.close()

    def test_override_bypasses_routing(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T062c: llm_override directly selects LLM regardless of chunks."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, code_path = tmp_model_files

        with patch(
            "krag.cli.gpu.get_free_vram",
            return_value=32_000_000_000,
        ):
            pool = LLMPool(
                text_model_path=text_path,
                code_model_path=code_path,
                load_multi_llm=True,
            )

        # Text-heavy chunks, but override forces code
        text_chunks = [
            _make_query_result(file_type=".md", file_path="/tmp/readme.md"),
            _make_query_result(file_type=".txt", file_path="/tmp/notes.txt"),
        ]

        messages = [{"role": "user", "content": "Analyze this."}]

        response, llm_used = pool.route_and_generate(messages, text_chunks, llm_override="code")

        assert llm_used == "code"  # Override wins despite text-heavy chunks
        assert isinstance(response, str)

        pool.close()

    def test_hot_swap_route_and_generate(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T062d: Hot-swap mode generates response after swapping."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, code_path = tmp_model_files

        # Force hot-swap mode by setting low VRAM
        with patch(
            "krag.cli.gpu.get_free_vram",
            return_value=1_000_000_000,
        ):
            pool = LLMPool(
                text_model_path=text_path,
                code_model_path=code_path,
                load_multi_llm=True,  # Will fall back to hot-swap
            )

        # Code-heavy chunks
        code_chunks = [
            _make_query_result(file_type=".py", file_path=f"/tmp/{i}.py") for i in range(5)
        ]

        messages = [{"role": "user", "content": "What does this code do?"}]

        response, llm_used = pool.route_and_generate(messages, code_chunks)

        assert isinstance(response, str)
        # In hot-swap mode, routing still works
        assert llm_used in ("text", "code")

        pool.close()

    def test_pool_status_reflects_mode(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T062e: get_status accurately reflects the pool operational mode."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, code_path = tmp_model_files

        # Simultaneous mode
        with patch(
            "krag.cli.gpu.get_free_vram",
            return_value=32_000_000_000,
        ):
            pool_sim = LLMPool(
                text_model_path=text_path,
                code_model_path=code_path,
                load_multi_llm=True,
            )

        status = pool_sim.get_status()
        assert status["mode"] == "simultaneous"
        assert "text" in status
        assert "code" in status
        pool_sim.close()

        # Single mode
        pool_single = LLMPool(
            text_model_path=text_path,
            code_model_path=None,
        )

        status = pool_single.get_status()
        assert status["mode"] == "single"
        pool_single.close()
