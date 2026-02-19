"""Integration tests for code prompt preset.

T077: End-to-end query with code preset produces structured code answer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from krag.models.query_result import QueryResult


def _code_result(
    content: str = "def process(data: list[int]) -> int:\n    return sum(data)",
    file_path: str = "/src/core/processor.py",
    file_type: str = ".py",
    rank: int = 1,
    score: float = 0.92,
) -> QueryResult:
    return QueryResult(
        chunk_id=str(uuid4()),
        score=score,
        rank=rank,
        chunk_content=content,
        file_path=Path(file_path),
        chunk_index=0,
        file_type=file_type,
    )


class TestCodePresetIntegration:
    """T077: End-to-end code preset integration tests."""

    def test_code_preset_produces_structured_prompt(self) -> None:
        """T077a: Code preset builds a full prompt with code-aware system instructions."""
        from krag.synthesis.prompt_builder import PromptBuilder

        builder = PromptBuilder(preset_name="code")

        results = [
            _code_result(
                content="def validate_email(email: str) -> bool:\n    import re\n    return bool(re.match(r'^[\\w.-]+@[\\w.-]+\\.\\w+$', email))",
                file_path="/src/utils/validation.py",
                rank=1,
            ),
            _code_result(
                content="class EmailService:\n    def send(self, to: str, body: str) -> None:\n        self.validate(to)\n        self._client.send(to, body)",
                file_path="/src/services/email.py",
                rank=2,
                score=0.85,
            ),
            _code_result(
                content="# Email Configuration\nSMTP_HOST = 'smtp.example.com'\nSMTP_PORT = 587",
                file_path="/src/config/settings.py",
                file_type=".py",
                rank=3,
                score=0.78,
            ),
        ]

        messages = builder.build("How does email validation work?", results)

        assert len(messages) == 2
        system = messages[0]["content"]
        user = messages[1]["content"]

        # System prompt must mention code-related instructions
        system_lower = system.lower()
        assert any(term in system_lower for term in ("code", "function", "symbol", "snippet")), (
            f"Code preset system prompt should mention code concepts: {system}"
        )

        # User content must include context with file references
        assert "validation.py" in user
        assert "email.py" in user
        assert "validate_email" in user

    def test_code_preset_with_llm_pool_routing(self) -> None:
        """T077b: LLMPool routes code-heavy results, code preset auto-coupled."""
        # Create temp model files
        import tempfile

        from krag.synthesis.llm_pool import LLMPool
        from krag.synthesis.prompt_builder import PromptBuilder

        with tempfile.TemporaryDirectory() as tmp:
            text_model = Path(tmp) / "text.gguf"
            text_model.write_bytes(b"\x00" * 1024)
            code_model = Path(tmp) / "code.gguf"
            code_model.write_bytes(b"\x00" * 1024)

            mock_llama = MagicMock()
            mock_instance = MagicMock()
            mock_instance.create_chat_completion.return_value = {
                "choices": [
                    {"message": {"content": "The `process` function takes a list of integers..."}}
                ]
            }
            mock_llama.return_value = mock_instance

            with patch("llama_cpp.Llama", mock_llama):
                with patch(
                    "krag.cli.gpu.get_free_vram",
                    return_value=32_000_000_000,
                ):
                    pool = LLMPool(
                        text_model_path=text_model,
                        code_model_path=code_model,
                        load_multi_llm=True,
                    )

                code_chunks = [
                    _code_result(file_path=f"/src/mod{i}.py", rank=i + 1) for i in range(4)
                ]

                # Determine route
                route = pool.determine_route(code_chunks)
                assert route == "code"

                # Auto-couple preset
                active_preset = "code" if route == "code" else "balanced"
                assert active_preset == "code"

                # Build prompt with code preset
                builder = PromptBuilder(preset_name=active_preset)
                messages = builder.build("How does process work?", code_chunks)

                # Generate
                response, llm_used = pool.route_and_generate(messages, code_chunks)

                assert llm_used == "code"
                assert isinstance(response, str)
                assert len(response) > 0

                pool.close()

    def test_code_preset_different_from_balanced(self) -> None:
        """T077c: Code preset output differs meaningfully from balanced."""
        from krag.synthesis.prompt_builder import PromptBuilder

        code_builder = PromptBuilder(preset_name="code")
        balanced_builder = PromptBuilder(preset_name="balanced")

        results = [_code_result()]

        code_messages = code_builder.build("explain process()", results)
        balanced_messages = balanced_builder.build("explain process()", results)

        # System prompts must differ
        assert code_messages[0]["content"] != balanced_messages[0]["content"]

        # Code preset system should have code-specific language
        code_system = code_messages[0]["content"].lower()
        assert any(t in code_system for t in ("code", "function", "symbol", "snippet"))
