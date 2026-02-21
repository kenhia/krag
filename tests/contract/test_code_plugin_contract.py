"""Contract tests: CodeFileHandler implements FileTypeHandler correctly."""

from pathlib import Path


class TestCodeFileHandlerContract:
    """Verify CodeFileHandler satisfies the FileTypeHandler ABC contract."""

    def test_is_subclass_of_file_type_handler(self) -> None:
        """CodeFileHandler must be a subclass of FileTypeHandler."""
        from krag_plugin_code.handler import CodeFileHandler

        from krag.plugins.interfaces import FileTypeHandler

        assert issubclass(CodeFileHandler, FileTypeHandler)

    def test_has_required_properties(self) -> None:
        """CodeFileHandler must have name, version, required_api_version properties."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        assert isinstance(handler.name, str)
        assert len(handler.name) > 0
        assert isinstance(handler.version, str)
        assert isinstance(handler.required_api_version, str)

    def test_name_is_code(self) -> None:
        """Plugin name must be 'code'."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        assert handler.name == "code"

    def test_supported_extensions_returns_list(self) -> None:
        """supported_extensions() must return a non-empty list of strings."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        extensions = handler.supported_extensions()
        assert isinstance(extensions, list)
        assert len(extensions) > 0
        assert all(isinstance(ext, str) for ext in extensions)
        assert all(ext.startswith(".") for ext in extensions)

    def test_supported_extensions_includes_python(self) -> None:
        """Must support .py files (tree-sitter-python is installed)."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        assert ".py" in handler.supported_extensions()

    def test_extract_text_returns_string(self, tmp_path: Path) -> None:
        """extract_text() must return a string."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")
        result = handler.extract_text(test_file)
        assert isinstance(result, str)
        assert "def hello" in result

    def test_extract_metadata_returns_dict(self, tmp_path: Path) -> None:
        """extract_metadata() must return a dict."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")
        result = handler.extract_metadata(test_file)
        assert isinstance(result, dict)
        assert "language" in result

    def test_get_chunking_strategy_returns_code_aware(self) -> None:
        """get_chunking_strategy() must return CODE_AWARE."""
        from krag_plugin_code.handler import CodeFileHandler

        from krag.plugins.interfaces import ChunkingStrategy

        handler = CodeFileHandler()
        strategy = handler.get_chunking_strategy()
        assert strategy is not None
        assert isinstance(strategy, ChunkingStrategy)
        assert strategy == ChunkingStrategy.CODE_AWARE

    def test_get_embedding_model_returns_optional_string(self) -> None:
        """get_embedding_model() must return a string or None."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        model = handler.get_embedding_model()
        # Without config, returns the default code embedding model
        assert model == "jinaai/jina-embeddings-v2-base-code"
        # With config, returns configured model
        handler.initialize({"embedding_model": "code-bert"})
        model = handler.get_embedding_model()
        assert model == "code-bert"

    def test_initialize_accepts_config(self) -> None:
        """initialize() must accept config dict without error."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize(config={})  # Should not raise

    def test_cleanup_callable(self) -> None:
        """cleanup() must be callable without error."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.cleanup()  # Should not raise
