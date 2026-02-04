"""Query result model."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryResult(BaseModel):
    """Retrieved chunk with relevance score from similarity search.

    Represents a single result from vector similarity search.
    """

    chunk_id: str = Field(..., description="Reference to retrieved TextChunk")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0.0-1.0)")
    rank: int = Field(..., gt=0, description="Rank in results (1-based, 1=most relevant)")
    chunk_content: str = Field(..., min_length=1, description="Text content of the chunk")
    file_path: Path = Field(..., description="Source file of the chunk")
    chunk_index: int = Field(..., ge=0, description="Position within source file")
    file_type: str = Field(..., description="Type of source file")

    @field_validator("file_path")
    @classmethod
    def file_path_must_be_absolute(cls, v: Path) -> Path:
        """Ensure file path is absolute."""
        if not v.is_absolute():
            raise ValueError("file_path must be absolute")
        return v

    model_config = ConfigDict(json_encoders={Path: str})
