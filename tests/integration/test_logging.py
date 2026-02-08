"""Integration tests for logging configuration."""

import logging
from pathlib import Path

import pytest

from krag.config.logging import setup_logging


class TestLoggingConfiguration:
    """Test logging setup with file rotation and console control."""

    def test_default_logging_creates_file(self, tmp_path: Path) -> None:
        """Test that default logging creates log file."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir, show_logs=False, verbose=False)

        # Log some messages
        logger = logging.getLogger("krag.test")
        logger.info("Test info message")
        logger.error("Test error message")

        # Verify log file was created
        log_file = log_dir / "krag.log"
        assert log_file.exists()

        # Verify contents
        log_content = log_file.read_text()
        assert "Test info message" in log_content
        assert "Test error message" in log_content

    def test_verbose_mode_includes_debug(self, tmp_path: Path) -> None:
        """Test that verbose mode logs DEBUG level messages."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir, show_logs=False, verbose=True)

        logger = logging.getLogger("krag.test")
        logger.debug("Debug message")
        logger.info("Info message")

        log_file = log_dir / "krag.log"
        log_content = log_file.read_text()
        assert "Debug message" in log_content
        assert "Info message" in log_content

    def test_third_party_logs_suppressed(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that third-party library logs are suppressed at INFO level."""
        log_dir = tmp_path / "logs"

        with caplog.at_level(logging.INFO):
            setup_logging(log_dir=log_dir, show_logs=True, verbose=False)

            # Try to log from third-party libraries
            httpx_logger = logging.getLogger("httpx")
            sentence_logger = logging.getLogger("sentence_transformers")

            httpx_logger.info("Should be suppressed")
            sentence_logger.info("Should be suppressed")
            httpx_logger.warning("Should appear")
            sentence_logger.error("Should appear")

        # INFO messages should not appear in console (suppressed)
        assert "Should be suppressed" not in caplog.text

        # WARNING and ERROR should still appear in file
        log_file = log_dir / "krag.log"
        log_content = log_file.read_text()
        assert "Should appear" in log_content

    def test_log_rotation_configuration(self, tmp_path: Path) -> None:
        """Test that log rotation is properly configured."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir, show_logs=False, verbose=False)

        # Get the file handler
        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if hasattr(h, "maxBytes")]

        assert len(file_handlers) == 1, "Should have exactly one rotating file handler"

        handler = file_handlers[0]
        assert handler.maxBytes == 10 * 1024 * 1024, "Max size should be 10MB"
        assert handler.backupCount == 5, "Should keep 5 backup files"

    def test_console_handler_respects_show_logs_flag(self, tmp_path: Path) -> None:
        """Test that console output respects show_logs flag."""
        log_dir = tmp_path / "logs"

        # Test with show_logs=False (only ERROR+)
        setup_logging(log_dir=log_dir, show_logs=False, verbose=False)

        root_logger = logging.getLogger()
        stream_handlers = [
            h
            for h in root_logger.handlers
            if type(h).__name__ in ("StreamHandler", "SafeStreamHandler")
        ]

        assert len(stream_handlers) == 1, "Should have one console handler"
        assert stream_handlers[0].level == logging.ERROR, "Console should only show ERROR+"

        # Test with show_logs=True (INFO+)
        setup_logging(log_dir=log_dir, show_logs=True, verbose=False)

        stream_handlers = [
            h
            for h in root_logger.handlers
            if type(h).__name__ in ("StreamHandler", "SafeStreamHandler")
        ]
        assert len(stream_handlers) == 1, "Should have one console handler"
        assert stream_handlers[0].level == logging.INFO, "Console should show INFO+"

    def test_multiple_setup_calls_clear_handlers(self, tmp_path: Path) -> None:
        """Test that calling setup_logging multiple times doesn't duplicate handlers."""
        log_dir = tmp_path / "logs"

        setup_logging(log_dir=log_dir, show_logs=False, verbose=False)
        root_logger = logging.getLogger()
        initial_handler_count = len(root_logger.handlers)

        setup_logging(log_dir=log_dir, show_logs=True, verbose=True)
        final_handler_count = len(root_logger.handlers)

        assert initial_handler_count == final_handler_count, "Handler count should remain the same"
        assert final_handler_count == 2, "Should have exactly 2 handlers (file + console)"
