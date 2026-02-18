"""Contract tests for LLMPool interface.

T054: LLMPool.route_and_generate() returns tuple[str, str]
T055: LLMPool.swap_to() completes without error
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from krag.models.query_result import QueryResult


def _make_query_result(file_path: str = "/tmp/test.py", file_type: str = ".py") -> QueryResult:
    """Create a minimal QueryResult for testing."""
    from uuid import uuid4

    return QueryResult(
        chunk_id=str(uuid4()),
        score=0.85,
        rank=1,
        chunk_content="def hello(): pass",
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
        "choices": [{"message": {"content": "Test response"}}]
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


class TestLLMPoolContract:
    """T054-T055: Contract tests for LLMPool interface."""

    def test_route_and_generate_returns_tuple_str_str(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T054: route_and_generate() returns (response_text, llm_name_used)."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, _ = tmp_model_files
        pool = LLMPool(text_model_path=text_path)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"},
        ]
        chunks = [_make_query_result()]

        result = pool.route_and_generate(messages, chunks)

        assert isinstance(result, tuple)
        assert len(result) == 2
        response_text, llm_name = result
        assert isinstance(response_text, str)
        assert isinstance(llm_name, str)
        assert llm_name in ("text", "code")

        pool.close()

    def test_route_and_generate_with_override(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T054: route_and_generate() respects llm_override parameter."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, _ = tmp_model_files
        pool = LLMPool(text_model_path=text_path)

        messages = [{"role": "user", "content": "test"}]
        chunks = [_make_query_result()]

        _, llm_name = pool.route_and_generate(messages, chunks, llm_override="text")
        assert llm_name == "text"

        pool.close()

    def test_swap_to_completes_without_error(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T055: swap_to() returns swap duration without raising."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, code_path = tmp_model_files
        pool = LLMPool(
            text_model_path=text_path,
            code_model_path=code_path,
        )

        duration = pool.swap_to("code")
        assert isinstance(duration, float)
        assert duration >= 0.0

        pool.close()

    def test_swap_to_raises_for_invalid_name(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T055: swap_to() raises ValueError for unknown LLM name."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, _ = tmp_model_files
        pool = LLMPool(text_model_path=text_path)

        with pytest.raises(ValueError):
            pool.swap_to("unknown")

        pool.close()

    def test_swap_to_raises_when_no_code_model(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T055: swap_to('code') raises ValueError if code model not configured."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, _ = tmp_model_files
        pool = LLMPool(text_model_path=text_path)

        with pytest.raises(ValueError, match="not configured"):
            pool.swap_to("code")

        pool.close()

    def test_has_required_public_methods(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """LLMPool exposes all contract-required methods."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, _ = tmp_model_files
        pool = LLMPool(text_model_path=text_path)

        required = [
            "route_and_generate",
            "determine_route",
            "swap_to",
            "get_active_llm",
            "get_status",
            "close",
        ]
        for method_name in required:
            assert hasattr(pool, method_name), f"Missing method: {method_name}"
            assert callable(getattr(pool, method_name))

        pool.close()

    def test_get_status_returns_dict(self, _mock_llama, tmp_model_files: tuple[Path, Path]) -> None:
        """get_status() returns a dict with required keys."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, _ = tmp_model_files
        pool = LLMPool(text_model_path=text_path)

        status = pool.get_status()
        assert isinstance(status, dict)
        assert "mode" in status
        assert status["mode"] in ("simultaneous", "hot-swap", "single")

        pool.close()

    def test_get_active_llm_returns_str_or_none(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """get_active_llm() returns a valid string."""
        from krag.synthesis.llm_pool import LLMPool

        text_path, _ = tmp_model_files
        pool = LLMPool(text_model_path=text_path)

        active = pool.get_active_llm()
        assert active in ("text", "code", "both", None)

        pool.close()
