"""Configuration model."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_default_vector_store_path() -> Path:
    """Get default vector store path using XDG cache directory.

    Imports lazily to avoid circular dependency.
    """
    from krag.config.xdg import get_krag_cache_dir

    return get_krag_cache_dir() / "storage"


def _get_default_llm_model() -> str:
    """Get default LLM model name.

    Uses Phi-3 Mini, a capable 3.8B parameter model suitable for CPU inference.
    """
    return "microsoft/Phi-3-mini-4k-instruct-gguf"


class PluginMetadata(BaseModel):
    """Metadata about an installed plugin discovered via entry points.

    Represents a plugin's identity, capabilities, and current state in the
    plugin system.
    """

    name: str = Field(..., description="Plugin identifier (e.g., 'pdf', 'docx')")
    version: str = Field(..., description="Plugin version from package metadata")
    entry_point: str = Field(
        ..., description="Full entry point reference (e.g., 'krag_plugin_pdf.handler:PDFHandler')"
    )
    supported_extensions: list[str] = Field(
        ..., description="File extensions this plugin handles (e.g., ['.pdf', '.PDF'])"
    )
    description: str | None = Field(None, description="Human-readable plugin description")
    author: str | None = Field(None, description="Plugin author from package metadata")
    required_api_version: str = Field(
        ..., description="Minimum plugin API version required (semver)"
    )
    is_enabled: bool = Field(default=True, description="Whether plugin is currently enabled")
    is_loaded: bool = Field(
        default=False, description="Whether plugin has been imported and instantiated"
    )
    load_error: str | None = Field(None, description="Error message if plugin failed to load")

    @field_validator("name")
    @classmethod
    def name_is_valid_identifier(cls, v: str) -> str:
        """Ensure plugin name is a valid Python identifier."""
        if not v.replace("_", "").isalnum():
            raise ValueError(f"Plugin name must be alphanumeric + underscore, got: {v}")
        return v

    @field_validator("supported_extensions")
    @classmethod
    def extensions_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure plugin supports at least one extension."""
        if not v:
            raise ValueError("supported_extensions must not be empty")
        return v


class PluginConfiguration(BaseModel):
    """Configuration for the plugin system.

    Defines which plugins are enabled/disabled and provides per-plugin settings
    that are validated against each plugin's config_schema().
    """

    enabled_plugins: list[str] = Field(
        default_factory=list,
        description="List of plugin names to enable (empty = all discovered)",
    )
    disabled_plugins: list[str] = Field(
        default_factory=list, description="List of plugin names to explicitly disable"
    )
    plugin_settings: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-plugin configuration (validated against plugin's config_schema)",
    )

    @field_validator("enabled_plugins", "disabled_plugins")
    @classmethod
    def no_overlap(cls, v: list[str], info: dict) -> list[str]:
        """Ensure enabled and disabled plugin lists do not overlap."""
        if info.field_name == "disabled_plugins" and "enabled_plugins" in info.data:
            enabled = set(info.data["enabled_plugins"])
            disabled = set(v)
            overlap = enabled & disabled
            if overlap:
                raise ValueError(
                    f"Plugin(s) cannot be both enabled and disabled: {', '.join(overlap)}"
                )
        return v


class Configuration(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KRAG_", env_file=".env", env_file_encoding="utf-8"
    )
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
    llm_model: str = Field(
        default_factory=_get_default_llm_model,
        description="HuggingFace model name (e.g., 'TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF') or local path to GGUF file",
    )
    llm_context_size: int = Field(default=2048, gt=0, description="Context window size")
    llm_num_threads: int = Field(default=4, gt=0, description="Number of threads for inference")
    llm_temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Temperature for generation"
    )

    # Path Reductions
    path_aliases: list[str] = Field(
        default_factory=list,
        description="Path display aliases in 'full_path:alias' format, e.g., '/home/ken:~'",
    )

    # Plugin System
    plugins: PluginConfiguration = Field(
        default_factory=PluginConfiguration,
        description="Plugin system configuration",
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
