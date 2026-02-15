"""Contract tests for FileTypeHandler plugin interface.

Verifies that FileTypeHandler implementations follow the required contract
and provide all necessary methods with correct signatures and return types.
"""

import json
import re
from pathlib import Path

import pytest

from krag.plugins.exceptions import PluginExtractionError
from krag.plugins.interfaces import ChunkingStrategy, FileTypeHandler


class TestFileTypeHandlerContract:
    """Contract tests for FileTypeHandler interface."""

    def test_plugin_implements_interface(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify plugin implements all required methods."""
        assert hasattr(mock_file_handler, "name")
        assert hasattr(mock_file_handler, "version")
        assert hasattr(mock_file_handler, "required_api_version")
        assert hasattr(mock_file_handler, "supported_extensions")
        assert hasattr(mock_file_handler, "extract_text")
        assert hasattr(mock_file_handler, "extract_metadata")
        assert hasattr(mock_file_handler, "get_chunking_strategy")

    def test_plugin_properties_valid_types(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify properties return expected types."""
        # Name validation
        assert isinstance(mock_file_handler.name, str)
        assert len(mock_file_handler.name) > 0
        assert mock_file_handler.name.replace("_", "").isalnum()  # Valid identifier

        # Version validation (semver)
        assert isinstance(mock_file_handler.version, str)
        assert re.match(r"^\d+\.\d+\.\d+", mock_file_handler.version)

        # API version validation (semver)
        assert isinstance(mock_file_handler.required_api_version, str)
        assert re.match(r"^\d+\.\d+\.\d+", mock_file_handler.required_api_version)

    def test_supported_extensions_format(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify extensions follow correct format."""
        extensions = mock_file_handler.supported_extensions()
        assert isinstance(extensions, list)
        assert len(extensions) > 0

        for ext in extensions:
            assert isinstance(ext, str)
            assert ext.startswith(".")
            assert len(ext) >= 2  # At least one char after dot

    def test_extract_text_returns_string(
        self, mock_file_handler: FileTypeHandler, tmp_path: Path
    ) -> None:
        """Verify extract_text returns valid string."""
        test_file = tmp_path / "test.mock"
        test_file.write_text("test content")

        text = mock_file_handler.extract_text(test_file)
        assert isinstance(text, str)
        # Note: Empty string is allowed

    def test_extract_metadata_returns_dict(
        self, mock_file_handler: FileTypeHandler, tmp_path: Path
    ) -> None:
        """Verify extract_metadata returns valid dict."""
        test_file = tmp_path / "test.mock"
        test_file.write_text("test content")

        metadata = mock_file_handler.extract_metadata(test_file)
        assert isinstance(metadata, dict)

        # Verify all values are JSON-serializable
        json.dumps(metadata)  # Should not raise

    def test_chunking_strategy_valid_type(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify get_chunking_strategy returns valid type."""
        strategy = mock_file_handler.get_chunking_strategy()
        assert (
            strategy is None
            or isinstance(strategy, ChunkingStrategy)
            or hasattr(strategy, "chunk_text")
        )

    def test_extract_text_handles_missing_file(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify appropriate error when file missing."""
        with pytest.raises((FileNotFoundError, PluginExtractionError)):
            mock_file_handler.extract_text(Path("/nonexistent/file.mock"))

    def test_can_handle_file_default_implementation(
        self, mock_file_handler: FileTypeHandler, tmp_path: Path
    ) -> None:
        """Verify can_handle_file default implementation checks extension."""
        test_file = tmp_path / "test.mock"
        test_file.write_text("test content")

        # Should handle files with matching extension
        assert mock_file_handler.can_handle_file(test_file)

        # Should not handle files with non-matching extension
        wrong_file = tmp_path / "test.txt"
        wrong_file.write_text("test content")
        assert not mock_file_handler.can_handle_file(wrong_file)

    def test_initialize_is_optional(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify initialize method exists and is callable."""
        assert hasattr(mock_file_handler, "initialize")
        assert callable(mock_file_handler.initialize)

        # Should not raise with empty config
        mock_file_handler.initialize({})

    def test_cleanup_is_optional(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify cleanup method exists and is callable."""
        assert hasattr(mock_file_handler, "cleanup")
        assert callable(mock_file_handler.cleanup)

        # Should not raise
        mock_file_handler.cleanup()

    def test_config_schema_is_optional(self, mock_file_handler: FileTypeHandler) -> None:
        """Verify config_schema method exists and returns valid type."""
        assert hasattr(mock_file_handler, "config_schema")
        assert callable(mock_file_handler.config_schema)

        schema = mock_file_handler.config_schema()
        assert schema is None or (isinstance(schema, type) and hasattr(schema, "model_validate"))
