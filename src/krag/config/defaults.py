"""Default configuration values."""

from pathlib import Path

from krag.config.xdg import get_krag_cache_dir, get_krag_config_dir, get_krag_state_dir

# Default directory paths (user should customize)
DEFAULT_DIRECTORIES = [
    Path.home() / "Documents",
]

# Default exclusion patterns
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

# Default supported file types
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

# Default embedding model
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Default chunking parameters
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50

# Default retrieval parameters
DEFAULT_TOP_K = 5

# Default LLM parameters
DEFAULT_LLM_CONTEXT_SIZE = 2048
DEFAULT_LLM_NUM_THREADS = 4
DEFAULT_LLM_TEMPERATURE = 0.7

# XDG Base Directory paths
DEFAULT_CONFIG_DIR = get_krag_config_dir()
DEFAULT_CACHE_DIR = get_krag_cache_dir()
DEFAULT_STATE_DIR = get_krag_state_dir()
DEFAULT_VECTOR_STORE_PATH = DEFAULT_CACHE_DIR / "storage"
DEFAULT_LLM_MODEL_PATH = DEFAULT_CACHE_DIR / "models" / "model.gguf"
DEFAULT_LOG_DIR = DEFAULT_STATE_DIR / "logs"
