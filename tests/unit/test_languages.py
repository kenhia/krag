"""Unit tests for language discovery and routing — T018."""

from pathlib import Path


class TestLanguageRouting:
    """T018: Python and Rust get AST chunking, unsupported falls back."""

    def test_python_file_gets_ast_chunking(self, tmp_path: Path) -> None:
        """Python files should be handled by the code plugin."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        extensions = handler.supported_extensions()
        assert ".py" in extensions

    def test_rust_file_gets_ast_chunking(self, tmp_path: Path) -> None:
        """Rust files should be handled by the code plugin."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        extensions = handler.supported_extensions()
        assert ".rs" in extensions

    def test_unsupported_extension_not_claimed(self) -> None:
        """Extensions without grammars should not be claimed."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        extensions = handler.supported_extensions()
        # PowerShell (.ps1) has no tree-sitter grammar installed
        assert ".ps1" not in extensions

    def test_language_grammar_discovery(self) -> None:
        """Grammar discovery should find installed grammars."""
        from krag_plugin_code.languages import discover_grammars

        grammars = discover_grammars()
        assert "python" in grammars
        assert "rust" in grammars

    def test_extension_to_language_mapping(self) -> None:
        """File extensions should map to correct language names."""
        from krag_plugin_code.languages import get_language_for_extension

        assert get_language_for_extension(".py") == "python"
        assert get_language_for_extension(".rs") == "rust"
        assert get_language_for_extension(".ps1") is None
