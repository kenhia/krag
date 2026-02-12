"""Unit tests for LogFileHandler."""

from pathlib import Path

import pytest

from krag_plugin_logs.chunker import LogFileChunker
from krag_plugin_logs.handler import LogFileHandler, LogPluginConfig


@pytest.fixture
def handler():
    """Create a LogFileHandler instance."""
    return LogFileHandler()


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestLogFileHandler:
    """Test suite for LogFileHandler."""

    def test_plugin_properties(self, handler):
        """Test plugin metadata properties."""
        assert handler.name == "logs"
        assert handler.version == "1.0.0"
        assert handler.required_api_version == "1.0"

    def test_supported_extensions(self, handler):
        """Test supported file extensions."""
        extensions = handler.supported_extensions()
        assert ".log" in extensions
        assert len(extensions) == 1

    def test_extract_text_simple(self, handler, fixtures_dir):
        """Test text extraction from simple log file."""
        file_path = fixtures_dir / "simple.log"
        text = handler.extract_text(file_path)

        assert "Application started" in text
        assert "Database connected" in text
        assert "Cache initialized" in text

    def test_extract_text_with_stack_trace(self, handler, fixtures_dir):
        """Test text extraction preserves multi-line entries."""
        file_path = fixtures_dir / "with_errors.log"
        text = handler.extract_text(file_path)

        assert "NullPointerException" in text
        assert "at com.example" in text

    def test_extract_text_file_not_found(self, handler, tmp_path):
        """Test handling of missing file."""
        file_path = tmp_path / "nonexistent.log"
        with pytest.raises(FileNotFoundError):
            handler.extract_text(file_path)

    def test_extract_metadata_counts_log_levels(self, handler, fixtures_dir):
        """Test metadata extraction counts log levels."""
        file_path = fixtures_dir / "simple.log"
        metadata = handler.extract_metadata(file_path)

        assert "log_levels" in metadata
        assert metadata["log_levels"]["INFO"] >= 2
        assert "entry_count" in metadata

    def test_extract_metadata_extracts_time_range(self, handler, fixtures_dir):
        """Test metadata includes time range."""
        file_path = fixtures_dir / "simple.log"
        metadata = handler.extract_metadata(file_path)

        assert "time_range_start" in metadata
        assert "time_range_end" in metadata
        assert "duration_seconds" in metadata
        assert metadata["duration_seconds"] >= 0

    def test_extract_metadata_source_from_filename(self, handler, fixtures_dir):
        """Test metadata includes source from filename."""
        file_path = fixtures_dir / "application.log"
        metadata = handler.extract_metadata(file_path)

        assert metadata["source"] == "application"

    def test_extract_metadata_with_error_levels(self, handler, fixtures_dir):
        """Test metadata captures ERROR and WARN levels."""
        file_path = fixtures_dir / "with_errors.log"
        metadata = handler.extract_metadata(file_path)

        assert "log_levels" in metadata
        log_levels = metadata["log_levels"]
        assert "ERROR" in log_levels
        assert log_levels["ERROR"] >= 1

    def test_get_chunking_strategy_returns_custom_chunker(self, handler):
        """Test that handler returns custom LogFileChunker."""
        strategy = handler.get_chunking_strategy()

        assert strategy is not None
        assert isinstance(strategy, LogFileChunker)

    def test_get_chunking_strategy_reuses_instance(self, handler):
        """Test that chunker instance is reused."""
        strategy1 = handler.get_chunking_strategy()
        strategy2 = handler.get_chunking_strategy()

        assert strategy1 is strategy2

    def test_initialize(self, handler):
        """Test plugin initialization."""
        handler.initialize()
        # Should create chunker
        assert handler._chunker is not None
        assert isinstance(handler._chunker, LogFileChunker)

    def test_cleanup(self, handler):
        """Test plugin cleanup."""
        handler.initialize()
        handler.cleanup()
        # Should clear chunker
        assert handler._chunker is None

    def test_config_schema_returns_dict(self, handler):
        """Test configuration schema."""
        schema = handler.config_schema()

        assert schema is not None
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "chunk_window_minutes" in schema["properties"]
        assert "max_entries_per_chunk" in schema["properties"]

    def test_configure_with_valid_config(self, handler):
        """Test configuration with valid settings."""
        config = {
            "chunk_window_minutes": 10,
            "max_entries_per_chunk": 50,
        }

        handler.configure(config)

        assert handler._config.chunk_window_minutes == 10
        assert handler._config.max_entries_per_chunk == 50

    def test_configure_with_invalid_config(self, handler):
        """Test configuration with invalid settings."""
        config = {"chunk_window_minutes": -5}  # Invalid: negative

        with pytest.raises(Exception):
            handler.configure(config)

    def test_configure_resets_chunker(self, handler):
        """Test that configuration resets chunker instance."""
        handler.initialize()
        old_chunker = handler._chunker

        handler.configure({"chunk_window_minutes": 10})

        # Chunker should be reset
        assert handler._chunker is None or handler._chunker is not old_chunker

    def test_default_config_values(self, handler):
        """Test default configuration values."""
        assert handler._config.chunk_window_minutes == 5
        assert handler._config.max_entries_per_chunk == 100
        assert len(handler._config.timestamp_formats) > 0

    def test_extract_all_timestamps(self, handler):
        """Test private helper extracts all timestamps."""
        content = """2024-02-11 10:00:00 INFO First
2024-02-11 10:05:00 INFO Second
2024-02-11 10:10:00 INFO Third"""

        timestamps = handler._extract_all_timestamps(content)

        assert len(timestamps) == 3
        assert all(ts.year == 2024 for ts in timestamps)
        assert all(ts.month == 2 for ts in timestamps)

    def test_log_level_pattern(self, handler):
        """Test log level regex pattern."""
        text = "INFO DEBUG WARN ERROR FATAL CRITICAL"
        matches = handler.log_level_pattern.findall(text)

        assert len(matches) == 6
        assert "INFO" in matches
        assert "ERROR" in matches

    def test_log_level_case_insensitive(self, handler):
        """Test log level detection is case-insensitive."""
        text = "info debug Error FATAL"
        matches = handler.log_level_pattern.findall(text)

        assert len(matches) == 4


class TestLogPluginConfig:
    """Test suite for LogPluginConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LogPluginConfig()

        assert config.chunk_window_minutes == 5
        assert config.max_entries_per_chunk == 100
        assert len(config.timestamp_formats) > 0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = LogPluginConfig(chunk_window_minutes=10, max_entries_per_chunk=50)

        assert config.chunk_window_minutes == 10
        assert config.max_entries_per_chunk == 50

    def test_validation_min_chunk_window(self):
        """Test validation of chunk window minimum."""
        with pytest.raises(Exception):
            LogPluginConfig(chunk_window_minutes=0)

    def test_validation_max_chunk_window(self):
        """Test validation of chunk window maximum."""
        with pytest.raises(Exception):
            LogPluginConfig(chunk_window_minutes=61)

    def test_validation_min_entries(self):
        """Test validation of min entries per chunk."""
        with pytest.raises(Exception):
            LogPluginConfig(max_entries_per_chunk=5)

    def test_validation_max_entries(self):
        """Test validation of max entries per chunk."""
        with pytest.raises(Exception):
            LogPluginConfig(max_entries_per_chunk=2000)

    def test_json_schema_generation(self):
        """Test JSON schema generation."""
        schema = LogPluginConfig.model_json_schema()

        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "chunk_window_minutes" in schema["properties"]
