"""Configuration model."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid collection names for mode configuration
VALID_COLLECTIONS: frozenset[str] = frozenset({"code", "tests", "docs", "text"})

# Valid prompt presets
VALID_PRESETS: frozenset[str] = frozenset({"strict", "balanced", "verbose", "code"})

# Valid LLM slots
VALID_LLM_SLOTS: frozenset[str] = frozenset({"text", "code"})


def _get_default_vector_store_path() -> Path:
    """Get default vector store path using XDG cache directory.

    Imports lazily to avoid circular dependency.
    """
    from krag.config.xdg import get_krag_cache_dir

    return get_krag_cache_dir() / "storage"


def _get_default_model_cache_path() -> Path:
    """Get default model cache path using XDG cache directory.

    Imports lazily to avoid circular dependency.
    """
    from krag.config.xdg import get_krag_cache_dir

    return get_krag_cache_dir() / "models"


def _get_default_corpus_cache_path() -> Path:
    """Get default corpus cache path using XDG cache directory.

    Imports lazily to avoid circular dependency.
    """
    from krag.config.xdg import get_krag_cache_dir

    return get_krag_cache_dir() / "corpus"


def _get_default_logs_path() -> Path:
    """Get default logs path using XDG state directory.

    Imports lazily to avoid circular dependency.
    """
    from krag.config.xdg import get_krag_state_dir

    return get_krag_state_dir() / "logs"


def _get_default_llm_model() -> str:
    """Get default LLM model name.

    Uses Phi-3 Mini, a capable 3.8B parameter model suitable for CPU inference.
    """
    return "microsoft/Phi-3-mini-4k-instruct-gguf"


class ModeConfiguration(BaseModel):
    """A named retrieval configuration loaded from a TOML file.

    Bundles collection targeting, LLM selection, prompt preset, retrieval
    parameters, and critic settings into a single named configuration.
    """

    name: str = Field(..., description="Mode identifier (case-insensitive)")
    description: str = Field(default="", description="Human-readable description")
    collections: dict[str, float] = Field(
        default_factory=lambda: {"code": 1.0, "tests": 1.0, "docs": 1.0, "text": 1.0},
        description="Target collections with weights (0.0, 1.0]",
    )
    llm_slot: str = Field(default="text", description="LLM to use: 'text' or 'code'")
    preset: str = Field(default="balanced", description="Prompt preset name")
    top_k: int = Field(default=5, ge=1, description="Number of results to retrieve")
    similarity_threshold: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Minimum similarity score"
    )
    critic_enabled: bool = Field(default=False, description="Whether context critic is active")
    critic_threshold: int = Field(default=3, ge=0, le=5, description="Minimum critic score (0–5)")

    @field_validator("name")
    @classmethod
    def name_is_valid(cls, v: str) -> str:
        """Name must be non-empty, lowercase alphanumeric + hyphens."""
        if not v:
            raise ValueError("Mode name must be non-empty")
        lowered = v.lower()
        if not all(c.isalnum() or c == "-" for c in lowered):
            raise ValueError(f"Mode name must be lowercase alphanumeric + hyphens, got: {v!r}")
        return lowered

    @field_validator("collections")
    @classmethod
    def collections_valid(cls, v: dict[str, float]) -> dict[str, float]:
        """Collection keys must be valid names, weights in (0.0, 1.0]."""
        invalid_keys = set(v.keys()) - VALID_COLLECTIONS
        if invalid_keys:
            raise ValueError(
                f"Invalid collection names: {invalid_keys}. "
                f"Must be subset of {sorted(VALID_COLLECTIONS)}"
            )
        for key, weight in v.items():
            if weight <= 0.0 or weight > 1.0:
                raise ValueError(
                    f"Collection weight for '{key}' must be in (0.0, 1.0], got: {weight}"
                )
        return v

    @field_validator("llm_slot")
    @classmethod
    def llm_slot_valid(cls, v: str) -> str:
        """LLM slot must be 'text' or 'code'."""
        if v not in VALID_LLM_SLOTS:
            raise ValueError(f"llm_slot must be 'text' or 'code', got: {v!r}")
        return v

    @field_validator("preset")
    @classmethod
    def preset_valid(cls, v: str) -> str:
        """Preset must be a known built-in name."""
        if v not in VALID_PRESETS:
            raise ValueError(f"preset must be one of {sorted(VALID_PRESETS)}, got: {v!r}")
        return v


class LexiconConfiguration(BaseModel):
    """Configuration for the domain lexicon system.

    Controls lexicon file location and injection limits for prompt enrichment.
    """

    path: Path | None = Field(
        default=None,
        description="Path to lexicon JSON file (None = disabled)",
    )
    max_entries: int = Field(
        default=10, ge=1, description="Maximum glossary entries injected per query"
    )
    max_chars: int = Field(
        default=1500, ge=100, description="Maximum characters of glossary text per query"
    )

    @field_validator("path", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Any:
        """Expand ~ in lexicon path."""
        if isinstance(v, str):
            return Path(v).expanduser()
        if isinstance(v, Path):
            return v.expanduser()
        return v


class CriticConfiguration(BaseModel):
    """Configuration for the context relevance critic.

    Controls whether the critic is active and the minimum score threshold
    for chunk inclusion.
    """

    enabled: bool = Field(
        default=False,
        description="Whether context critic is active (disabled by default)",
    )
    threshold: int = Field(
        default=3, ge=0, le=5, description="Minimum relevance score (0–5) for inclusion"
    )


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


class ServiceConfiguration(BaseModel):
    """Configuration for the kragd service daemon.

    Controls how the HTTP service binds, which LLM slot to pre-load,
    and operational settings like idle timeout and request logging.
    """

    host: str = Field(
        default="0.0.0.0",
        description="Network interface to bind (0.0.0.0 for LAN access)",
    )
    port: int = Field(
        default=8742,
        ge=1,
        le=65535,
        description="TCP port for kragd (8742 = KRAG on phone keypad)",
    )
    primary_llm: str | None = Field(
        default="text",
        description="LLM slot to pre-load on startup: 'text', 'code', or None",
    )
    idle_timeout: int = Field(
        default=300,
        ge=0,
        description="Seconds of inactivity before unloading LLM (0 = never unload)",
    )
    log_requests: bool = Field(
        default=True,
        description="Log each HTTP request for debugging",
    )

    @field_validator("primary_llm")
    @classmethod
    def validate_primary_llm(cls, v: str | None) -> str | None:
        """Ensure primary_llm is a valid slot name or None."""
        if v is not None and v not in {"text", "code"}:
            raise ValueError(f"primary_llm must be 'text', 'code', or None, got: {v!r}")
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
        default="BAAI/bge-base-en-v1.5", description="Embedding model name"
    )
    embedding_batch_size: int = Field(
        default=64, gt=0, description="Batch size for embedding generation"
    )
    embedding_device: str = Field(default="cpu", description="Device to use (cpu, cuda, mps)")

    # Chunking
    chunk_size: int = Field(default=384, gt=0, description="Target chunk size in tokens")
    chunk_overlap: int = Field(default=64, ge=0, description="Overlap between chunks in tokens")

    # Vector Store
    vector_store_path: Path = Field(
        default_factory=_get_default_vector_store_path,
        description="Path to Qdrant storage (XDG_CACHE_HOME/krag/storage)",
    )
    collection_name: str = Field(default="krag_embeddings", description="Collection name")
    distance_metric: str = Field(default="cosine", description="Distance metric")

    # Storage Paths (configurable, XDG defaults)
    model_cache_path: Path = Field(
        default_factory=_get_default_model_cache_path,
        description="Path to cached models (XDG_CACHE_HOME/krag/models)",
    )
    corpus_cache_path: Path = Field(
        default_factory=_get_default_corpus_cache_path,
        description="Path to corpus cache (XDG_CACHE_HOME/krag/corpus)",
    )
    logs_path: Path = Field(
        default_factory=_get_default_logs_path,
        description="Path to log files (XDG_STATE_HOME/krag/logs)",
    )

    # Retrieval
    top_k: int = Field(default=5, gt=0, description="Number of results to retrieve")
    similarity_threshold: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity score for chunk inclusion (0.0-1.0)",
    )

    # LLM
    llm_model: str = Field(
        default_factory=_get_default_llm_model,
        description="HuggingFace model name (e.g., 'TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF') or local path to GGUF file",
    )
    llm_context_size: int = Field(default=8192, gt=0, description="Context window size")
    llm_num_threads: int = Field(default=8, gt=0, description="Number of threads for inference")
    llm_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="Temperature for generation"
    )
    llm_top_p: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Nucleus sampling cutoff (0.0-1.0)"
    )
    llm_repeat_penalty: float = Field(
        default=1.1, ge=1.0, description="Repetition penalty multiplier (>=1.0)"
    )
    llm_min_p: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Minimum p filter for llama.cpp (0.0-1.0)"
    )
    llm_n_gpu_layers: int = Field(
        default=0,
        ge=-1,
        description=(
            "Number of model layers to offload to GPU for llama-cpp-python. "
            "0 = CPU only (default), "
            "-1 = full offload (recommended if CUDA available), "
            "1-N = hybrid offload (N layers on GPU, rest on CPU). "
            "Requires llama-cpp-python built with CUDA support."
        ),
    )
    llm_code_model: str | None = Field(
        default=None,
        description="Path to code-specialized LLM GGUF file for multi-LLM routing",
    )
    load_multi_llm: bool = Field(
        default=False,
        description="Enable simultaneous loading of text and code LLMs when VRAM permits",
    )

    # Path Reductions
    path_aliases: list[str] = Field(
        default_factory=list,
        description="Path display aliases in 'full_path:alias' format, e.g., '/home/ken:~'",
    )

    # Prompt Configuration
    prompt_preset: str = Field(
        default="balanced",
        description="Active prompt preset name (strict, balanced, verbose)",
    )
    prompt_system_override: str | None = Field(
        default=None,
        description="Custom system prompt override (replaces preset's system prompt when set)",
    )

    # Mode System
    modes_dir: Path | None = Field(
        default=None,
        description="Directory for user-defined mode TOML files (default: ~/.config/krag/modes)",
    )
    default_mode: str = Field(
        default="default",
        description="Default retrieval mode name when --mode is not specified",
    )

    # Lexicon
    lexicon_path: Path | None = Field(
        default=None,
        description="Path to domain lexicon JSON file (None = disabled)",
    )
    lexicon_max_entries: int = Field(
        default=10, ge=1, description="Maximum glossary entries injected per query"
    )
    lexicon_max_chars: int = Field(
        default=1500, ge=100, description="Maximum characters of glossary text per query"
    )

    # Critic
    critic_enabled: bool = Field(
        default=False,
        description="Global critic enable flag (overridden by mode config)",
    )
    critic_threshold: int = Field(
        default=3, ge=0, le=5, description="Minimum relevance score (0–5) for chunk inclusion"
    )

    # Plugin System
    plugins: PluginConfiguration = Field(
        default_factory=PluginConfiguration,
        description="Plugin system configuration",
    )

    # Service Daemon
    service: ServiceConfiguration = Field(
        default_factory=ServiceConfiguration,
        description="kragd service daemon configuration",
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

    @field_validator("prompt_preset")
    @classmethod
    def prompt_preset_is_valid(cls, v: str) -> str:
        """Ensure prompt preset is a known built-in name."""
        valid_presets = {"strict", "balanced", "verbose", "code"}
        if v not in valid_presets:
            raise ValueError(f"prompt_preset must be one of {sorted(valid_presets)}, got: {v}")
        return v

    @field_validator(
        "vector_store_path",
        "model_cache_path",
        "corpus_cache_path",
        "logs_path",
        "modes_dir",
        "lexicon_path",
        mode="before",
    )
    @classmethod
    def expand_user_paths(cls, v: Any) -> Any:
        """Expand ~ in paths before validation."""
        if isinstance(v, str):
            return Path(v).expanduser()
        if isinstance(v, Path):
            return v.expanduser()
        return v

    @field_validator(
        "model_cache_path",
        "corpus_cache_path",
        "logs_path",
        mode="after",
    )
    @classmethod
    def validate_absolute_paths(cls, v: Path) -> Path:
        """Ensure storage paths are absolute."""
        if not v.is_absolute():
            raise ValueError(f"Path must be absolute: {v}")
        return v
