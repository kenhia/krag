"""Unit tests for plugin interfaces.

Tests FileTypeHandler ABC enforcement, method signature validation,
and interface contract requirements.
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from krag.plugins.interfaces import ChunkingStrategy, FileTypeHandler


class TestFileTypeHandlerABC:
    """Test FileTypeHandler abstract base class enforcement."""

    def test_cannot_instantiate_abstract_class(self):
        """FileTypeHandler ABC should not be directly instantiable."""
        with pytest.raises(TypeError) as exc_info:
            FileTypeHandler()

        assert "abstract" in str(exc_info.value).lower()

    def test_must_implement_all_abstract_properties(self):
        """Subclasses must implement all abstract properties."""

        class IncompleteHandler(FileTypeHandler):
            # Missing all required properties
            pass

        with pytest.raises(TypeError):
            IncompleteHandler()

    def test_must_implement_name_property(self):
        """Subclasses must implement name property."""

        class NoNameHandler(FileTypeHandler):
            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

        with pytest.raises(TypeError):
            NoNameHandler()

    def test_must_implement_version_property(self):
        """Subclasses must implement version property."""

        class NoVersionHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

        with pytest.raises(TypeError):
            NoVersionHandler()

    def test_must_implement_required_api_version_property(self):
        """Subclasses must implement required_api_version property."""

        class NoAPIVersionHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

        with pytest.raises(TypeError):
            NoAPIVersionHandler()


class TestValidHandlerImplementation:
    """Test valid FileTypeHandler implementations."""

    def test_minimal_valid_handler(self):
        """A minimal valid handler should be instantiable."""

        class MinimalHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".min"]

            def extract_text(self, file_path: Path) -> str:
                return "text"

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        # Should be instantiable
        handler = MinimalHandler()
        assert handler.name == "minimal"
        assert handler.version == "1.0.0"

    def test_handler_with_all_methods(self):
        """A handler implementing all methods should work correctly."""

        class CompleteHandler(FileTypeHandler):
            def __init__(self):
                self._config = {}

            @property
            def name(self) -> str:
                return "complete"

            @property
            def version(self) -> str:
                return "2.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".cmp"]

            def extract_text(self, file_path: Path) -> str:
                return "extracted"

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {"key": "value"}

            def get_chunking_strategy(self) -> ChunkingStrategy | None:
                return ChunkingStrategy.DEFAULT

            def initialize(self, config: dict[str, Any], context: Any = None) -> None:
                self._config = config

            def cleanup(self) -> None:
                self._config = {}

            def config_schema(self) -> type[BaseModel] | None:
                return None

        handler = CompleteHandler()
        handler.initialize({"test": "config"})

        assert handler.name == "complete"
        assert handler._config == {"test": "config"}

        handler.cleanup()
        assert handler._config == {}


class TestMethodSignatures:
    """Test method signature requirements."""

    def test_supported_extensions_returns_list(self):
        """supported_extensions must return list[str]."""

        class TestHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".test", ".tst"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = TestHandler()
        extensions = handler.supported_extensions()

        assert isinstance(extensions, list)
        assert all(isinstance(ext, str) for ext in extensions)

    def test_extract_text_accepts_path(self):
        """extract_text must accept Path parameter."""

        class TestHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".test"]

            def extract_text(self, file_path: Path) -> str:
                assert isinstance(file_path, Path)
                return "text"

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = TestHandler()
        result = handler.extract_text(Path("/tmp/test.txt"))

        assert isinstance(result, str)

    def test_extract_metadata_returns_dict(self):
        """extract_metadata must return dict[str, Any]."""

        class TestHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".test"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {"key": "value", "number": 42}

        handler = TestHandler()
        metadata = handler.extract_metadata(Path("/tmp/test.txt"))

        assert isinstance(metadata, dict)

    def test_get_chunking_strategy_optional(self):
        """get_chunking_strategy is optional with default implementation."""

        class MinimalHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".min"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = MinimalHandler()
        strategy = handler.get_chunking_strategy()

        # Default implementation returns None
        assert strategy is None

    def test_initialize_optional(self):
        """initialize is optional with default implementation."""

        class MinimalHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".min"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = MinimalHandler()
        # Should not raise exception
        handler.initialize({})

    def test_cleanup_optional(self):
        """cleanup is optional with default implementation."""

        class MinimalHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".min"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = MinimalHandler()
        # Should not raise exception
        handler.cleanup()

    def test_config_schema_optional(self):
        """config_schema is optional with default implementation."""

        class MinimalHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".min"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = MinimalHandler()
        schema = handler.config_schema()

        # Default implementation returns None
        assert schema is None


class TestDefaultImplementations:
    """Test default implementations of optional methods."""

    def test_can_handle_file_default_checks_extension(self, tmp_path):
        """can_handle_file default implementation should check extension."""

        class TestHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".test", ".tst"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = TestHandler()

        # Should use default implementation
        test_file = tmp_path / "file.test"
        other_file = tmp_path / "file.txt"

        assert handler.can_handle_file(test_file) is True
        assert handler.can_handle_file(other_file) is False

    def test_can_handle_file_case_insensitive(self, tmp_path):
        """can_handle_file should be case-insensitive by default."""

        class TestHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".test"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

        handler = TestHandler()

        # Case variations should all work
        assert handler.can_handle_file(tmp_path / "file.test") is True
        assert handler.can_handle_file(tmp_path / "file.TEST") is True
        assert handler.can_handle_file(tmp_path / "file.Test") is True


class TestChunkingStrategyEnum:
    """Test ChunkingStrategy enum values."""

    def test_chunking_strategy_enum_values(self):
        """ChunkingStrategy should define expected enum values."""
        assert hasattr(ChunkingStrategy, "DEFAULT")
        assert hasattr(ChunkingStrategy, "SEMANTIC")
        assert hasattr(ChunkingStrategy, "CODE_AWARE")
        assert hasattr(ChunkingStrategy, "CUSTOM")

    def test_chunking_strategy_enum_usable(self):
        """ChunkingStrategy enum values should be usable."""

        class TestHandler(FileTypeHandler):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def required_api_version(self) -> str:
                return "1.0.0"

            def supported_extensions(self) -> list[str]:
                return [".test"]

            def extract_text(self, file_path: Path) -> str:
                return ""

            def extract_metadata(self, file_path: Path) -> dict[str, Any]:
                return {}

            def get_chunking_strategy(self) -> ChunkingStrategy | None:
                return ChunkingStrategy.DEFAULT

        handler = TestHandler()
        strategy = handler.get_chunking_strategy()

        assert strategy == ChunkingStrategy.DEFAULT
