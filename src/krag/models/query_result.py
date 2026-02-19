"""Query result model."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class QueryResult(BaseModel):
    """Retrieved chunk with relevance score from similarity search.

    Represents a single result from vector similarity search.
    """

    chunk_id: str = Field(..., description="Reference to retrieved TextChunk")
    score: float = Field(..., ge=0.0, description="Relevance score (higher is better)")
    rank: int = Field(..., gt=0, description="Rank in results (1-based, 1=most relevant)")
    chunk_content: str = Field(..., min_length=1, description="Text content of the chunk")
    file_path: Path = Field(..., description="Source file of the chunk")
    chunk_index: int = Field(..., ge=0, description="Position within source file")
    file_type: str = Field(..., description="Type of source file")

    # Enriched code metadata (optional — populated from vector payload)
    language: str | None = Field(default=None, description="Programming language")
    function_name: str | None = Field(default=None, description="Function/method name")
    class_name: str | None = Field(default=None, description="Enclosing class name")
    start_line: int | None = Field(default=None, ge=1, description="Start line (1-based)")
    end_line: int | None = Field(default=None, ge=1, description="End line (1-based)")

    @field_validator("file_path")
    @classmethod
    def file_path_must_be_absolute(cls, v: Path) -> Path:
        """Ensure file path is absolute."""
        if not v.is_absolute():
            raise ValueError("file_path must be absolute")
        return v

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        """Serialize model with proper Path handling."""
        data = {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "rank": self.rank,
            "chunk_content": self.chunk_content,
            "file_path": str(self.file_path),
            "chunk_index": self.chunk_index,
            "file_type": self.file_type,
            "language": self.language,
            "function_name": self.function_name,
            "class_name": self.class_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }
        return data

    def format_source_ref(self) -> str:
        """Format a structured source reference string.

        Builds a human-readable reference from available metadata:
        - Full:     ``Class.method() at file.py:L45-L68``
        - Function: ``function() at file.py:L10-L20``
        - Class:    ``Class at file.py:L1-L100``
        - Lines:    ``file.py:L5-L15``
        - Bare:     ``file.py``

        Returns:
            Formatted source reference string.
        """
        filename = self.file_path.name

        # Build symbol part
        if self.class_name and self.function_name:
            symbol = f"{self.class_name}.{self.function_name}()"
        elif self.function_name:
            symbol = f"{self.function_name}()"
        elif self.class_name:
            symbol = self.class_name
        else:
            symbol = None

        # Build line part
        if self.start_line is not None and self.end_line is not None:
            line_ref = f":L{self.start_line}-L{self.end_line}"
        elif self.start_line is not None:
            line_ref = f":L{self.start_line}"
        else:
            line_ref = ""

        file_ref = f"{filename}{line_ref}"

        if symbol:
            return f"{symbol} at {file_ref}"
        return file_ref

    model_config = ConfigDict()
