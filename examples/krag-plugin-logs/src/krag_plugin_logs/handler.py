"""Log file type handler implementation."""

import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from krag.plugins.interfaces import FileTypeHandler
from krag_plugin_logs.chunker import LogFileChunker

logger = logging.getLogger(__name__)


class LogPluginConfig(BaseModel):
    """Configuration schema for log file plugin."""

    chunk_window_minutes: int = Field(
        default=5,
        description="Time window in minutes for grouping log entries into chunks",
        ge=1,
        le=60,
    )
    max_entries_per_chunk: int = Field(
        default=100,
        description="Maximum number of log entries per chunk",
        ge=10,
        le=1000,
    )
    timestamp_formats: list[str] = Field(
        default_factory=lambda: [
            r"%Y-%m-%d %H:%M:%S",
            r"%Y-%m-%dT%H:%M:%S",
            r"%Y-%m-%dT%H:%M:%S.%f",
            r"%d/%b/%Y:%H:%M:%S",
            r"%b %d %H:%M:%S",
        ],
        description="List of strptime format strings for parsing timestamps",
    )


class LogFileHandler(FileTypeHandler):
    """Handler for log files with custom timestamp-based chunking.

    This plugin demonstrates:
    - Custom chunking strategy (LogFileChunker)
    - Rich metadata extraction (log statistics, time ranges)
    - Configuration schema (Pydantic model)
    - Advanced text processing (timestamp parsing, log level detection)
    """

    def __init__(self):
        """Initialize the log file handler."""
        super().__init__()
        self._chunker: LogFileChunker | None = None
        self._config: LogPluginConfig = LogPluginConfig()

        # Regex for log level detection
        self.log_level_pattern = re.compile(
            r"\b(TRACE|DEBUG|INFO|NOTICE|WARN|WARNING|ERROR|FATAL|CRITICAL)\b",
            re.IGNORECASE,
        )

    @property
    def name(self) -> str:
        """Plugin identifier."""
        return "logs"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def required_api_version(self) -> str:
        """Required krag plugin API version."""
        return "1.0"

    def supported_extensions(self) -> list[str]:
        """Supported file extensions."""
        return [".log"]

    def extract_text(self, file_path: Path) -> str:
        """Extract text content from log file.

        Reads the entire log file as text. The custom chunker will
        parse timestamps and group entries during chunking.

        Args:
            file_path: Path to the log file

        Returns:
            Raw log file content

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be read
            UnicodeDecodeError: If file encoding is invalid
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(f"Log file not found: {file_path}")
            raise
        except PermissionError:
            logger.error(f"Permission denied reading log file: {file_path}")
            raise
        except UnicodeDecodeError:
            # Try latin-1 as fallback (common for old log files)
            try:
                content = file_path.read_text(encoding="latin-1")
                logger.warning(f"Used latin-1 encoding for log file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to decode log file {file_path}: {e}")
                raise

        return content

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract metadata from log file.

        Computes statistics from the log file:
        - Entry count
        - Time range (first and last timestamps)
        - Log level distribution
        - Source identifier

        Args:
            file_path: Path to the log file

        Returns:
            Dictionary containing log statistics and metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be read
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")

        metadata: dict[str, Any] = {
            "source": file_path.stem,  # Use filename as source identifier
        }

        # Count log levels
        log_levels = self.log_level_pattern.findall(content)
        if log_levels:
            level_counts = Counter(level.upper() for level in log_levels)
            metadata["log_levels"] = dict(level_counts)
            metadata["entry_count"] = len(log_levels)

        # Extract time range (first and last timestamps)
        timestamps = self._extract_all_timestamps(content)
        if timestamps:
            metadata["time_range_start"] = min(timestamps).isoformat()
            metadata["time_range_end"] = max(timestamps).isoformat()
            duration = max(timestamps) - min(timestamps)
            metadata["duration_seconds"] = duration.total_seconds()

        return metadata

    def get_chunking_strategy(self) -> LogFileChunker:
        """Return custom chunking strategy for log files.

        Creates and returns a LogFileChunker instance configured with
        the plugin's settings.

        Returns:
            LogFileChunker instance for timestamp-based chunking
        """
        if self._chunker is None:
            self._chunker = LogFileChunker(
                chunk_window_minutes=self._config.chunk_window_minutes,
                max_entries_per_chunk=self._config.max_entries_per_chunk,
                timestamp_formats=self._config.timestamp_formats,
            )
        return self._chunker

    def initialize(self, config: dict[str, Any] | None = None, context: Any = None) -> None:
        """Initialize the plugin.

        Creates the chunker instance with current configuration.

        Args:
            config: Plugin-specific configuration (this plugin uses internal _config)
            context: Plugin context (unused by this plugin)
        """
        self._chunker = LogFileChunker(
            chunk_window_minutes=self._config.chunk_window_minutes,
            max_entries_per_chunk=self._config.max_entries_per_chunk,
            timestamp_formats=self._config.timestamp_formats,
        )
        logger.debug(f"Log plugin initialized with {self._config.chunk_window_minutes}min windows")

    def cleanup(self) -> None:
        """Clean up plugin resources."""
        self._chunker = None
        logger.debug("Log plugin cleanup complete")

    def config_schema(self) -> dict[str, Any]:
        """Return configuration schema for the plugin.

        Returns:
            JSON schema dict generated from LogPluginConfig Pydantic model
        """
        return LogPluginConfig.model_json_schema()

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin with user settings.

        Args:
            config: Configuration dict matching LogPluginConfig schema
        """
        try:
            self._config = LogPluginConfig(**config)
            # Recreate chunker with new config
            self._chunker = None  # Will be recreated on next get_chunking_strategy()
            logger.info(f"Log plugin configured: {config}")
        except Exception as e:
            logger.error(f"Failed to configure log plugin: {e}")
            raise

    # Private helper methods

    def _extract_all_timestamps(self, content: str) -> list[datetime]:
        """Extract all timestamps from log content.

        Args:
            content: Log file content

        Returns:
            List of datetime objects found in the log
        """
        # Reuse chunker's timestamp extraction logic
        if self._chunker is None:
            self._chunker = self.get_chunking_strategy()

        timestamps = []
        for line in content.split("\n"):
            timestamp = self._chunker._extract_timestamp(line)
            if timestamp:
                timestamps.append(timestamp)

        return timestamps
