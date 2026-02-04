"""Text chunk model."""

from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TextChunk(BaseModel):
    """Segment of extracted text from a source file.

    Represents a single chunk of text with position information
    for retrieval and display.
    """

    chunk_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier")
    file_path: Path = Field(..., description="Reference to source file")
    chunk_index: int = Field(..., ge=0, description="Sequential index within file (0-based)")
    content: str = Field(..., min_length=1, description="Text content of the chunk")
    start_char: int = Field(..., ge=0, description="Character offset where chunk starts")
    end_char: int = Field(..., ge=0, description="Character offset where chunk ends")
    token_count: int = Field(..., gt=0, description="Number of tokens in chunk")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when chunk was created"
    )

    @field_validator("chunk_id")
    @classmethod
    def chunk_id_is_uuid(cls, v: str) -> str:
        """Validate chunk_id is a valid UUID string."""
        try:
            UUID(v)
        except ValueError as e:
            raise ValueError("chunk_id must be a valid UUID") from e
        return v

    @field_validator("end_char")
    @classmethod
    def end_after_start(cls, v: int, info: dict) -> int:
        """Ensure end_char is greater than start_char."""
        if "start_char" in info.data and v <= info.data["start_char"]:
            raise ValueError("end_char must be greater than start_char")
        return v

    model_config = ConfigDict(json_encoders={Path: str, datetime: lambda v: v.isoformat()})
