"""File metadata model and enums."""

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IndexingStatus(str, Enum):
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

        now = datetime.now()
        grace_period = timedelta(hours=1)

        if v > now + grace_period:
            logging.warning(
                f"File has future timestamp: {v} (now: {now}). "
                "This may indicate clock skew or incorrect system time."
            )
        return v

    model_config = ConfigDict(json_encoders={Path: str, datetime: lambda v: v.isoformat()})
