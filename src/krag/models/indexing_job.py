"""Indexing job model and enums."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobType(str, Enum):
    """Type of indexing job."""

    FULL = "full"
    INCREMENTAL = "incremental"


class JobStatus(str, Enum):
    """Status of indexing job."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FileError(BaseModel):
    """Error encountered during file processing."""

    file_path: Path
    error_type: str
    error_message: str


class IndexingJob(BaseModel):
    """Single indexing operation (full or incremental).

    Tracks progress and statistics for an indexing run.
    """

    job_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier")
    job_type: JobType = Field(..., description="Type of job (full/incremental)")
    status: JobStatus = Field(default=JobStatus.RUNNING, description="Current status")
    start_time: datetime = Field(default_factory=datetime.now, description="When job started")
    end_time: datetime | None = Field(default=None, description="When job completed")
    files_discovered: int = Field(default=0, ge=0, description="Total files found")
    files_processed: int = Field(default=0, ge=0, description="Files successfully indexed")
    files_skipped: int = Field(default=0, ge=0, description="Files skipped")
    files_errored: int = Field(default=0, ge=0, description="Files with errors")
    chunks_generated: int = Field(default=0, ge=0, description="Total chunks created")
    embeddings_created: int = Field(default=0, ge=0, description="Total embeddings generated")
    error_summary: list[FileError] = Field(
        default_factory=list, description="List of errors encountered"
    )

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: datetime | None, info: dict) -> datetime | None:
        """Ensure end_time is after start_time."""
        if v is not None and "start_time" in info.data and v < info.data["start_time"]:
            raise ValueError("end_time must be >= start_time")
        return v

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat(), Path: str})
