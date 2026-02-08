"""Text chunk model."""

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


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
    def end_after_start(cls, v: int, info: dict) -> int:  # type: ignore[type-arg]
        """Ensure end_char is greater than start_char."""
        if "start_char" in info.data and v <= info.data["start_char"]:
            raise ValueError("end_char must be greater than start_char")
        return v

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        """Serialize model with proper Path and datetime handling."""
        return {
            "chunk_id": self.chunk_id,
            "file_path": str(self.file_path),
            "chunk_index": self.chunk_index,
            "content": self.content,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat(),
        }

    model_config = ConfigDict()
