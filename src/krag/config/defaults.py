"""Default configuration values for krag.

This module defines all default configuration constants used throughout krag.
These values are used when the user has not specified overrides in their
config.toml configuration file.
"""

from pathlib import Path

from krag.config.xdg import get_krag_cache_dir, get_krag_config_dir, get_krag_state_dir

# Default directory paths that krag will scan for documents to index.
# Users should customize this list in their config.toml to point at their
# own project directories, notes folders, or documentation trees.
DEFAULT_DIRECTORIES = [
    Path.home() / "Documents",
]

# Default glob patterns for excluding files and directories from indexing.
# These patterns prevent krag from indexing build artifacts, virtual
# environments, caches, and other generated content.
DEFAULT_EXCLUSION_PATTERNS = [
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
    "**/.idea/**",
    "**/.vscode/**",
]

# Default list of file extensions that krag will index. Only files with
# these extensions are processed during indexing. Includes common source
# code, documentation, and configuration file types.
DEFAULT_SUPPORTED_FILE_TYPES = [
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
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".csv",
    ".toml",
    ".ini",
    ".cfg",
]

# The default embedding model used by krag for generating vector embeddings.
# krag uses sentence-transformers/all-MiniLM-L6-v2 which produces 384-dimensional
# vectors and supports semantic similarity search over text content.
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# The default chunk size in characters used when splitting documents for indexing.
# krag splits files into chunks of 512 characters by default. Larger chunks
# preserve more context but reduce retrieval precision.
DEFAULT_CHUNK_SIZE = 512

# The default overlap in characters between consecutive chunks. An overlap of
# 50 characters ensures that content near chunk boundaries is not missed
# during retrieval.
DEFAULT_CHUNK_OVERLAP = 50

# The default number of top results returned by krag's retrieval engine.
# When querying, krag retrieves the 5 most similar chunks by default.
DEFAULT_TOP_K = 5

# The default minimum similarity threshold for filtering retrieval results.
# Chunks with a cosine similarity score below 0.3 are discarded. Lower values
# return more results; higher values return only highly relevant chunks.
DEFAULT_SIMILARITY_THRESHOLD = 0.3

# Default LLM (large language model) parameters for answer generation.
# These control the behavior of the local GGUF model used for synthesis.
DEFAULT_LLM_CONTEXT_SIZE = 2048  # Maximum context window in tokens
DEFAULT_LLM_NUM_THREADS = 4  # CPU threads for LLM inference
DEFAULT_LLM_TEMPERATURE = 0.2  # Sampling temperature (lower = more deterministic)
DEFAULT_LLM_TOP_P = 0.9  # Nucleus sampling probability cutoff
DEFAULT_LLM_REPEAT_PENALTY = 1.1  # Penalty for repeating tokens
DEFAULT_LLM_MIN_P = 0.05  # Minimum probability threshold for sampling

# Default prompt parameters
DEFAULT_PROMPT_PRESET = "balanced"

# XDG Base Directory paths
DEFAULT_CONFIG_DIR = get_krag_config_dir()
DEFAULT_CACHE_DIR = get_krag_cache_dir()
DEFAULT_STATE_DIR = get_krag_state_dir()

# Storage paths (derived from XDG directories)
DEFAULT_VECTOR_STORE_PATH = DEFAULT_CACHE_DIR / "storage"
DEFAULT_MODEL_CACHE_PATH = DEFAULT_CACHE_DIR / "models"
DEFAULT_CORPUS_CACHE_PATH = DEFAULT_CACHE_DIR / "corpus"
DEFAULT_LOGS_PATH = DEFAULT_STATE_DIR / "logs"

# GPU defaults
DEFAULT_LLM_N_GPU_LAYERS = 0  # CPU only by default
DEFAULT_VECTOR_STORE_PATH = DEFAULT_CACHE_DIR / "storage"
DEFAULT_LLM_MODEL_PATH = DEFAULT_CACHE_DIR / "models" / "model.gguf"
DEFAULT_LOG_DIR = DEFAULT_STATE_DIR / "logs"

# Plugin system defaults
DEFAULT_ENABLED_PLUGINS: list[str] = []  # Empty = all discovered plugins enabled
DEFAULT_DISABLED_PLUGINS: list[str] = []  # Explicitly disabled plugins
DEFAULT_PLUGIN_SETTINGS: dict[str, dict] = {}  # Per-plugin settings
