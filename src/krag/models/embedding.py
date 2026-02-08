"""Embedding record model."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class EmbeddingRecord(BaseModel):
    """Vector embedding of a text chunk.

    Stored in vector database with associated metadata payload.
    """

    embedding_id: str = Field(..., description="Unique identifier (matches chunk_id)")
    chunk_id: str = Field(..., description="Reference to source TextChunk")
    vector: list[float] = Field(..., description="The embedding vector")
    vector_dim: int = Field(..., gt=0, description="Dimension of the vector")
    model_name: str = Field(..., description="Name of embedding model used")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when embedding was generated"
    )

    @field_validator("vector")
    @classmethod
    def vector_all_finite(cls, v: list[float]) -> list[float]:
        """Ensure all vector values are finite."""
        if not all(isinstance(x, (int, float)) and abs(x) != float("inf") for x in v):
            raise ValueError("All vector values must be finite floats")
        if any(x != x for x in v):  # Check for NaN
            raise ValueError("Vector cannot contain NaN values")
        return v

    @field_validator("vector_dim")
    @classmethod
    def vector_dim_matches_vector(cls, v: int, info: dict) -> int:
        """Ensure vector_dim matches actual vector length."""
        if "vector" in info.data and len(info.data["vector"]) != v:
            raise ValueError(
                f"vector_dim {v} does not match vector length {len(info.data['vector'])}"
            )
        return v

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        """Serialize model with proper datetime handling."""
        return {
            "embedding_id": self.embedding_id,
            "chunk_id": self.chunk_id,
            "vector": self.vector,
            "vector_dim": self.vector_dim,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat(),
        }

    model_config = ConfigDict()
