"""Unit tests for LLMPool routing and lifecycle management.

T056: Simultaneous mode auto-routes code-heavy chunks to code LLM
T057: Simultaneous mode auto-routes text-heavy chunks to text LLM
T058: Hot-swap mode loads selected LLM via --llm switch
T059: Insufficient VRAM for multi-LLM logs warning, falls back to hot-swap
T060: Hot-swap between LLMs completes in <60s (mock timing)
T061: No --llm switch + single LLM loaded uses current LLM + logs suggestion
"""

from __future__ import annotations

import logging
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
        "choices": [{"message": {"content": "Generated response"}}]
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


def _make_pool(
    text_path: Path,
    code_path: Path | None = None,
    load_multi_llm: bool = False,
):
    from krag.synthesis.llm_pool import LLMPool

    return LLMPool(
        text_model_path=text_path,
        code_model_path=code_path,
        load_multi_llm=load_multi_llm,
    )


class TestSimultaneousRouting:
    """T056-T057: Simultaneous mode auto-routing tests."""

    def test_code_heavy_chunks_route_to_code_llm(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T056: >40% code chunks routes to code LLM."""
        text_path, code_path = tmp_model_files

        # Mock VRAM check to allow simultaneous loading
        with patch(
            "krag.synthesis.llm_pool._get_free_vram",
            return_value=32_000_000_000,  # 32 GB
        ):
            pool = _make_pool(text_path, code_path, load_multi_llm=True)

        # 3 code chunks, 1 text chunk → >40% code
        chunks = [
            _make_query_result(file_type=".py", file_path="/tmp/a.py"),
            _make_query_result(file_type=".py", file_path="/tmp/b.py"),
            _make_query_result(file_type=".py", file_path="/tmp/c.py"),
            _make_query_result(file_type=".md", file_path="/tmp/readme.md"),
        ]

        route = pool.determine_route(chunks)
        assert route == "code"

        pool.close()

    def test_text_heavy_chunks_route_to_text_llm(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T057: <=40% code chunks routes to text LLM."""
        text_path, code_path = tmp_model_files

        with patch(
            "krag.synthesis.llm_pool._get_free_vram",
            return_value=32_000_000_000,
        ):
            pool = _make_pool(text_path, code_path, load_multi_llm=True)

        # 1 code chunk, 3 text chunks → 25% code, below 40% threshold
        chunks = [
            _make_query_result(file_type=".py", file_path="/tmp/a.py"),
            _make_query_result(file_type=".md", file_path="/tmp/readme.md"),
            _make_query_result(file_type=".txt", file_path="/tmp/notes.txt"),
            _make_query_result(file_type=".md", file_path="/tmp/docs.md"),
        ]

        route = pool.determine_route(chunks)
        assert route == "text"

        pool.close()

    def test_tie_routes_to_text(self, _mock_llama, tmp_model_files: tuple[Path, Path]) -> None:
        """T057: exactly 40% code routes to text LLM (threshold is strictly >40%)."""
        text_path, code_path = tmp_model_files

        with patch(
            "krag.synthesis.llm_pool._get_free_vram",
            return_value=32_000_000_000,
        ):
            pool = _make_pool(text_path, code_path, load_multi_llm=True)

        # Exactly 40% code (2 of 5) — does NOT exceed threshold
        chunks = [
            _make_query_result(file_type=".py", file_path="/tmp/a.py"),
            _make_query_result(file_type=".py", file_path="/tmp/b.py"),
            _make_query_result(file_type=".md", file_path="/tmp/readme.md"),
            _make_query_result(file_type=".txt", file_path="/tmp/notes.txt"),
            _make_query_result(file_type=".md", file_path="/tmp/docs.md"),
        ]

        route = pool.determine_route(chunks)
        assert route == "text"  # exactly 40% does not exceed threshold

        pool.close()


class TestHotSwapMode:
    """T058, T060: Hot-swap mode tests."""

    def test_llm_switch_triggers_swap(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T058: --llm code triggers hot-swap from text to code."""
        text_path, code_path = tmp_model_files
        pool = _make_pool(text_path, code_path, load_multi_llm=False)

        # Initially text is loaded
        assert pool.get_active_llm() == "text"

        # Override to code triggers swap
        messages = [{"role": "user", "content": "explain this code"}]
        chunks = [_make_query_result()]

        _, llm_used = pool.route_and_generate(messages, chunks, llm_override="code")
        assert llm_used == "code"

        pool.close()

    def test_hot_swap_completes_within_60s(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T060: Hot-swap duration is within acceptable range."""
        text_path, code_path = tmp_model_files
        pool = _make_pool(text_path, code_path, load_multi_llm=False)

        duration = pool.swap_to("code")
        # With mocked Llama, swap should be near-instant
        assert duration < 60.0

        pool.close()

    def test_swap_back_to_text(self, _mock_llama, tmp_model_files: tuple[Path, Path]) -> None:
        """Hot-swap to code then back to text works."""
        text_path, code_path = tmp_model_files
        pool = _make_pool(text_path, code_path, load_multi_llm=False)

        pool.swap_to("code")
        assert pool.get_active_llm() == "code"

        pool.swap_to("text")
        assert pool.get_active_llm() == "text"

        pool.close()


class TestVRAMFallback:
    """T059: VRAM insufficient triggers hot-swap fallback."""

    def test_insufficient_vram_falls_back_to_hot_swap(
        self, _mock_llama, tmp_model_files: tuple[Path, Path], caplog
    ) -> None:
        """T059: When VRAM is too low, load_multi_llm falls back to hot-swap."""
        text_path, code_path = tmp_model_files

        # Mock very low VRAM (less than KV cache alone)
        with patch(
            "krag.synthesis.llm_pool._get_free_vram",
            return_value=100,  # 100 bytes — far too low
        ):
            with caplog.at_level(logging.WARNING):
                pool = _make_pool(text_path, code_path, load_multi_llm=True)

        status = pool.get_status()
        assert status["mode"] in ("hot-swap", "single")

        pool.close()

    def test_no_gpu_falls_back_gracefully(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T059: No GPU available doesn't crash, uses hot-swap."""
        text_path, code_path = tmp_model_files

        with patch(
            "krag.synthesis.llm_pool._get_free_vram",
            return_value=None,  # No GPU
        ):
            pool = _make_pool(text_path, code_path, load_multi_llm=True)

        # Should still work in hot-swap mode
        status = pool.get_status()
        assert status["mode"] in ("hot-swap", "single")

        pool.close()


class TestSingleModelMode:
    """T061: Single LLM mode behavior."""

    def test_single_model_uses_text_llm(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T061: Without --llm, single model uses text LLM."""
        text_path, _ = tmp_model_files
        pool = _make_pool(text_path, code_path=None)

        messages = [{"role": "user", "content": "test"}]
        chunks = [_make_query_result()]

        _, llm_used = pool.route_and_generate(messages, chunks)
        assert llm_used == "text"

        pool.close()

    def test_single_model_mode_status(
        self, _mock_llama, tmp_model_files: tuple[Path, Path]
    ) -> None:
        """T061: Without code model, mode is 'single'."""
        text_path, _ = tmp_model_files
        pool = _make_pool(text_path, code_path=None)

        status = pool.get_status()
        assert status["mode"] == "single"

        pool.close()

    def test_code_heavy_logs_suggestion(
        self, _mock_llama, tmp_model_files: tuple[Path, Path], caplog
    ) -> None:
        """T061: Code-heavy query in single mode logs LLM suggestion."""
        text_path, _ = tmp_model_files
        pool = _make_pool(text_path, code_path=None)

        code_chunks = [
            _make_query_result(file_type=".py", file_path=f"/tmp/{i}.py") for i in range(5)
        ]

        with caplog.at_level(logging.INFO):
            _, llm_used = pool.route_and_generate(
                [{"role": "user", "content": "test"}], code_chunks
            )

        assert llm_used == "text"  # must use text since no code model
        # Should suggest configuring code model
        assert any("code" in r.message.lower() for r in caplog.records)

        pool.close()
