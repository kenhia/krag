"""Logging configuration for krag CLI."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from krag.config.xdg import get_krag_state_dir

if TYPE_CHECKING:
    from krag.models.configuration import Configuration


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that ignores I/O errors during shutdown.

    This prevents logging errors when third-party libraries try to log
    after the stream has been closed during Python interpreter shutdown.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record, ignoring I/O errors during shutdown."""
        try:
            super().emit(record)
        except (ValueError, OSError):
            # Stream is closed or unavailable (likely during shutdown)
            # Silently ignore rather than showing confusing error messages
            pass


def setup_logging(
    log_dir: Path | None = None,
    show_logs: bool = False,
    verbose: bool = False,
    config: "Configuration | None" = None,
) -> None:
    """Configure logging for krag application.

    Sets up file-based logging with rotation and optional console output.
    Third-party library logs are suppressed at INFO level to reduce noise.
    ERROR and CRITICAL messages always appear on console regardless of settings.

    Args:
        log_dir: Directory for log files (defaults to XDG_STATE_HOME/krag/logs)
        show_logs: Enable console logging for INFO+ application messages
        verbose: Enable DEBUG level logging (applies to both file and console)
        config: Configuration object; if provided, logs_path overrides log_dir
    """
    # Determine log directory: config.logs_path > explicit log_dir > XDG default
    if config is not None and log_dir is None:
        log_dir = config.logs_path
    if log_dir is None:
        log_dir = get_krag_state_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "krag.log"

    # Set base level
    base_level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(base_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # File handler with rotation (max 10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(base_level)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler with safe I/O handling
    console_handler = SafeStreamHandler(sys.stderr)
    console_formatter = logging.Formatter(
        "%(levelname)s: %(message)s",
    )
    console_handler.setFormatter(console_formatter)

    if show_logs:
        # Show all application logs at INFO+ level
        console_handler.setLevel(base_level)
    else:
        # Only show ERROR and CRITICAL
        console_handler.setLevel(logging.ERROR)

    root_logger.addHandler(console_handler)

    # Suppress third-party library logs at INFO level
    # These libraries can be very noisy during normal operation
    # Use NullHandler to prevent any output during shutdown
    third_party_loggers = [
        "httpx",
        "httpcore",
        "sentence_transformers",
        "transformers",  # HuggingFace transformers
        "transformers.modeling_utils",
        "transformers.configuration_utils",
        "transformers.modeling_tf_utils",
        "qdrant_client",
        "llama_cpp",
        "urllib3",
        "filelock",
        "huggingface_hub",
    ]

    for logger_name in third_party_loggers:
        third_party_logger = logging.getLogger(logger_name)
        if verbose:
            # In verbose mode, allow INFO+ from third-party libraries
            third_party_logger.setLevel(logging.INFO)
        else:
            # Allow WARNING+ but suppress INFO and DEBUG
            third_party_logger.setLevel(logging.WARNING)
        # Ensure no duplicate handlers
        third_party_logger.propagate = True

    # Set environment variables for transformers library
    if not verbose:
        os.environ["TRANSFORMERS_VERBOSITY"] = "error"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
    else:
        os.environ["TRANSFORMERS_VERBOSITY"] = "info"

    # Log the initialization
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging configured: file={log_file}, show_logs={show_logs}, verbose={verbose}")
