"""File metadata model and enums."""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class IndexingStatus(StrEnum):
    """Status of file indexing."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"  # Generic failure
    ACCESS_DENIED = "access_denied"  # Permission error
    SKIPPED = "skipped"  # Excluded by pattern or size limit
    DELETED = "deleted"  # File removed from filesystem
    UNSUPPORTED = "unsupported"  # File type not supported


class FileMetadata(BaseModel):
    """Metadata for a discovered file.

    Tracks file information and indexing status for change detection
    and incremental updates.
    """

    file_path: Path = Field(..., description="Absolute path to the file")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    modification_time: datetime = Field(..., description="Last modification timestamp")
    file_type: str = Field(..., description="File type (e.g., 'python', 'markdown')")
    content_hash: str = Field(..., description="SHA-256 hash of file content")
    indexing_status: IndexingStatus = Field(
        default=IndexingStatus.PENDING, description="Current indexing status"
    )
    last_indexed_at: datetime | None = Field(
        default=None, description="Timestamp of last successful indexing"
    )
    error_message: str | None = Field(default=None, description="Error details if failed")
    chunk_count: int = Field(default=0, ge=0, description="Number of chunks generated")

    # Plugin system fields (T030, T031)
    handler_plugin: str | None = Field(
        default=None,
        description="Name of plugin that processed this file (None for built-in text extractor)",
    )
    plugin_metadata: dict[str, Any] | None = Field(
        default=None, description="Plugin-specific metadata extracted from file"
    )

    @field_validator("file_path")
    @classmethod
    def file_path_must_be_absolute(cls, v: Path) -> Path:
        """Ensure file path is absolute."""
        if not v.is_absolute():
            raise ValueError("file_path must be absolute")
        return v

    @field_validator("modification_time")
    @classmethod
    def modification_time_not_future(cls, v: datetime) -> datetime:
        """Warn if modification time is suspiciously far in future.

        Allows 1 hour grace period for clock skew between systems.
        """
        import logging
        from datetime import timedelta

        now = datetime.now(UTC)
        grace_period = timedelta(hours=1)

        # Make comparison timezone-aware
        v_aware = v if v.tzinfo else v.replace(tzinfo=UTC)

        if v_aware > now + grace_period:
            logging.warning(
                f"File has future timestamp: {v_aware} (now: {now}). "
                "This may indicate clock skew or incorrect system time."
            )
        return v

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        """Serialize model with proper Path and datetime handling."""
        return {
            "file_path": str(self.file_path),
            "file_size": self.file_size,
            "modification_time": self.modification_time.isoformat(),
            "file_type": self.file_type,
            "content_hash": self.content_hash,
            "indexing_status": self.indexing_status.value,
            "last_indexed_at": self.last_indexed_at.isoformat() if self.last_indexed_at else None,
            "error_message": self.error_message,
            "chunk_count": self.chunk_count,
            "handler_plugin": self.handler_plugin,
            "plugin_metadata": self.plugin_metadata,
        }

    model_config = ConfigDict()
