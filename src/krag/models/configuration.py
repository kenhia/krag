"""Configuration model."""

from pathlib import Path

from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings


def _get_default_vector_store_path() -> Path:
    """Get default vector store path using XDG cache directory.

    Imports lazily to avoid circular dependency.
    """
    from krag.config.xdg import get_krag_cache_dir

    return get_krag_cache_dir() / "storage"


def _get_default_llm_model_path() -> Path:
    """Get default LLM model path using XDG cache directory.

    Imports lazily to avoid circular dependency.
    """
    from krag.config.xdg import get_krag_cache_dir

    return get_krag_cache_dir() / "models" / "model.gguf"


class Configuration(BaseSettings):
    model_config = ConfigDict(env_prefix="KRAG_", env_file=".env", env_file_encoding="utf-8")
    """System configuration settings.

    Loads from environment variables and config file.
    """

    # Directories
    directory_paths: list[Path] = Field(..., description="Directories to index")
    exclusion_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/.git/**",
            "**/build/**",
            "**/__pycache__/**",
            "**/.venv/**",
            "**/venv/**",
            "**/dist/**",
            "**/target/**",
            "**/.pytest_cache/**",
            "**/.mypy_cache/**",
        ],
        description="Glob patterns to exclude",
    )

    # File Processing
    follow_symlinks: bool = Field(
        default=True,
        description="Follow symbolic links (with cycle detection for safety)",
    )
    supported_file_types: list[str] = Field(
        default_factory=lambda: [
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".rs",
            ".go",
            ".rb",
            ".php",
            ".lua",
            ".ps1",
            ".psm1",
            ".psd1",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".csv",
            ".toml",
            ".ini",
            ".cfg",
        ],
        description="File extensions to process",
    )
    max_file_size_mb: int = Field(default=10, gt=0, description="Maximum file size to process")
    skip_binary_files: bool = Field(default=True, description="Whether to skip binary files")

    # Embedding
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model name"
    )
    embedding_batch_size: int = Field(
        default=32, gt=0, description="Batch size for embedding generation"
    )
    embedding_device: str = Field(default="cpu", description="Device to use (cpu, cuda, mps)")

    # Chunking
    chunk_size: int = Field(default=512, gt=0, description="Target chunk size in tokens")
    chunk_overlap: int = Field(default=50, ge=0, description="Overlap between chunks in tokens")

    # Vector Store
    vector_store_path: Path = Field(
        default_factory=_get_default_vector_store_path,
        description="Path to Qdrant storage (XDG_CACHE_HOME/krag/storage)",
    )
    collection_name: str = Field(default="krag_embeddings", description="Collection name")
    distance_metric: str = Field(default="cosine", description="Distance metric")

    # Retrieval
    top_k: int = Field(default=5, gt=0, description="Number of results to retrieve")

    # LLM
    llm_model_path: Path | None = Field(
        default_factory=_get_default_llm_model_path,
        description="Path to GGUF model file (XDG_CACHE_HOME/krag/models/model.gguf)",
    )
    llm_context_size: int = Field(default=2048, gt=0, description="Context window size")
    llm_num_threads: int = Field(default=4, gt=0, description="Number of threads for inference")
    llm_temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature for generation"
    )

    @field_validator("directory_paths")
    @classmethod
    def directory_paths_not_empty(cls, v: list[Path]) -> list[Path]:
        """Ensure at least one directory is configured."""
        if not v:
            raise ValueError("directory_paths must not be empty")
        return v

    @field_validator("directory_paths", mode="after")
    @classmethod
    def all_paths_absolute(cls, v: list[Path]) -> list[Path]:
        """Ensure all paths are absolute."""
        for path in v:
            if not path.is_absolute():
                raise ValueError(f"All paths must be absolute, got: {path}")
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def chunk_overlap_lt_chunk_size(cls, v: int, info: dict) -> int:
        """Ensure chunk_overlap < chunk_size."""
        if "chunk_size" in info.data and v >= info.data["chunk_size"]:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v
