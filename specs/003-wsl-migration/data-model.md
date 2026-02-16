# Data Model: WSL to Native Linux Migration

**Feature**: 003-wsl-migration  
**Date**: 2026-02-15  
**Purpose**: Define configuration model changes for storage paths and GPU settings

---

## Overview

This feature extends the existing `Configuration` model with new optional fields for storage path customization and LLM GPU offloading. All changes are **backward compatible** — existing configs work without modification.

---

## Configuration Model Extensions

### Storage Path Fields

Add three new optional path fields to the `Configuration` model, all with XDG-based default factories:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_cache_path` | `Path` | `~/.cache/krag/models` | Directory for cached LLM model files (GGUF) |
| `corpus_cache_path` | `Path` | `~/.cache/krag/corpus` | Directory for cached corpus artifacts (optional) |
| `logs_path` | `Path` | `~/.local/state/krag/logs` | Directory for log files |

**Existing field (no changes)**:
- `vector_store_path` — Already exists with XDG default `~/.cache/krag/storage`

### GPU Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `llm_n_gpu_layers` | `int` | `0` | Number of LLM layers to offload to GPU. 0 = CPU only, -1 = full offload, 1-N = partial |

**Existing field (no changes)**:
- `embedding_device` — Already exists, supports `"cpu"`, `"cuda"`, `"cuda:0"`, `"mps"`

---

## Field Specifications

### `model_cache_path`

```python
def _get_default_model_cache_path() -> Path:
    """Get default model cache path (lazy import)."""
    from krag.config.xdg import get_krag_cache_dir
    return get_krag_cache_dir() / "models"

model_cache_path: Path = Field(
    default_factory=_get_default_model_cache_path,
    description="Path to cached models (XDG_CACHE_HOME/krag/models)",
)
```

**Validation**:
- Must be absolute path (field validator)
- Tilde (`~`) expanded before validation
- Parent directory must be writable (runtime validation in `ConfigManager.validate()`)
- Created automatically if missing (in `ConfigManager.validate()`)

**TOML config**:

```toml
[storage]
model_cache_path = "/krag/models"
```

**Used by**: `LLMClient` when resolving model paths

### `corpus_cache_path`

```python
def _get_default_corpus_cache_path() -> Path:
    """Get default corpus cache path (lazy import)."""
    from krag.config.xdg import get_krag_cache_dir
    return get_krag_cache_dir() / "corpus"

corpus_cache_path: Path = Field(
    default_factory=_get_default_corpus_cache_path,
    description="Path to corpus cache (XDG_CACHE_HOME/krag/corpus)",
)
```

**Validation**: Same as `model_cache_path`

**TOML config**:

```toml
[storage]
corpus_cache_path = "/krag/corpus"
```

**Used by**: Reserved for future corpus caching features (not currently used; included for completeness)

### `logs_path`

```python
def _get_default_logs_path() -> Path:
    """Get default logs path (lazy import)."""
    from krag.config.xdg import get_krag_state_dir
    return get_krag_state_dir() / "logs"

logs_path: Path = Field(
    default_factory=_get_default_logs_path,
    description="Path to log files (XDG_STATE_HOME/krag/logs)",
)
```

**Validation**: Same as `model_cache_path`

**TOML config**:

```toml
[storage]
logs_path = "/krag/logs"
```

**Used by**: `src/krag/config/logging.py` when setting up rotating file handler

### `llm_n_gpu_layers`

```python
llm_n_gpu_layers: int = Field(
    default=0,
    ge=-1,  # Minimum value: -1 (full offload)
    description=(
        "Number of model layers to offload to GPU for llama-cpp-python. "
        "0 = CPU only (default), "
        "-1 = full offload (recommended if CUDA available), "
        "1-N = hybrid offload (N layers on GPU, rest on CPU). "
        "Requires llama-cpp-python built with CUDA support."
    ),
)
```

**Validation**:
- Must be >= -1 (Pydantic constraint)
- If non-zero, GPU availability checked at runtime (warning if unavailable, no error)

**TOML config**:

```toml
[llm]
n_gpu_layers = -1  # Full GPU offload
```

**Used by**: `LLMClient._load_model()` when constructing `Llama()` instance

---

## Configuration File Structure

### Complete TOML Example

```toml
# config.toml - Example with custom storage paths and GPU settings

[directories]
paths = [
    "/krag/corpus/docs",
    "/krag/corpus/code",
]

[storage]
vector_store_path = "/krag/index"
model_cache_path = "/krag/models"
corpus_cache_path = "/krag/corpus"
logs_path = "/krag/logs"

[embedding]
model = "sentence-transformers/all-MiniLM-L6-v2"
device = "cuda"  # Use GPU for embeddings

[llm]
model = "microsoft/Phi-3-mini-4k-instruct-gguf"
n_gpu_layers = -1  # Full GPU offload for LLM
temperature = 0.7
max_tokens = 512

[chunking]
size = 512
overlap = 50

[vector_store]
collection_name = "krag_embeddings"
distance_metric = "cosine"

[retrieval]
top_k = 5
min_score = 0.7
```

### Backward Compatibility

**Existing configs work unchanged**:

```toml
# Old config.toml - still valid
[directories]
paths = ["/home/user/documents"]

[embedding]
model = "all-MiniLM-L6-v2"
device = "cpu"

# All new fields use XDG defaults automatically
```

---

## State Transitions

### Config Loading Flow

```
1. ConfigManager.load(config_path)
   ↓
2. Parse TOML file → dict
   ↓
3. Configuration(**dict)
   ↓
4. Pydantic validation:
   - Expand ~ in paths
   - Validate absolute paths
   - Validate int constraints
   ↓
5. Set defaults for omitted fields:
   - model_cache_path → default_factory()
   - logs_path → default_factory()
   - llm_n_gpu_layers → 0
   ↓
6. Return Configuration instance
```

### Runtime Validation Flow

```
1. ConfigManager.validate(config)
   ↓
2. Check directory_paths exist
   ↓
3. Check storage paths:
   - vector_store_path parent writable
   - model_cache_path parent writable
   - logs_path parent writable
   ↓
4. Create missing directories
   ↓
5. Check GPU config:
   - Warn if embedding_device="cuda" but CUDA unavailable
   - Warn if llm_n_gpu_layers>0 but CUDA unavailable
   ↓
6. Return validation result
```

---

## Relationships

### Path Hierarchy

```
XDG_CONFIG_HOME/krag/
  └─ config.toml         # Configuration file

XDG_CACHE_HOME/krag/     # Ephemeral data
  ├─ storage/            # vector_store_path (existing)
  ├─ models/             # model_cache_path (new)
  └─ corpus/             # corpus_cache_path (new)

XDG_STATE_HOME/krag/     # Persistent state
  ├─ logs/               # logs_path (new, explicit)
  └─ metadata.json       # Document metadata (existing)

Custom mount (e.g., /krag/):  # When configured
  ├─ index/              # vector_store_path override
  ├─ models/             # model_cache_path override
  ├─ corpus/             # corpus_cache_path override
  └─ logs/               # logs_path override (optional)
```

### Component Dependencies

```
Configuration Model
  ├─ Used by: ConfigManager (loading, validation)
  ├─ Used by: LLMClient (reads llm_n_gpu_layers, model_cache_path)
  ├─ Used by: EmbeddingGenerator (reads embedding_device)
  ├─ Used by: QdrantVectorStore (reads vector_store_path)
  └─ Used by: logging setup (reads logs_path)
```

---

## Validation Rules

### Field-Level Validation (Pydantic)

```python
@field_validator("model_cache_path", "corpus_cache_path", "logs_path", mode="before")
@classmethod
def expand_user_paths(cls, v: Any) -> Any:
    """Expand ~ in paths before validation."""
    if isinstance(v, str):
        return Path(v).expanduser()
    if isinstance(v, Path):
        return v.expanduser()
    return v

@field_validator("model_cache_path", "corpus_cache_path", "logs_path", mode="after")
@classmethod
def validate_absolute_paths(cls, v: Path) -> Path:
    """Ensure paths are absolute."""
    if not v.is_absolute():
        raise ValueError(f"Path must be absolute: {v}")
    return v
```

### Runtime Validation (ConfigManager)

```python
def validate(config: Configuration) -> list[str]:
    """Validate configuration at runtime.
    
    Returns list of validation errors (empty if valid).
    """
    errors = []
    
    # Check storage paths are writable (or parent is writable)
    for path_name, path in [
        ("vector_store_path", config.vector_store_path),
        ("model_cache_path", config.model_cache_path),
        ("corpus_cache_path", config.corpus_cache_path),
        ("logs_path", config.logs_path),
    ]:
        if path.exists():
            if not os.access(path, os.W_OK):
                errors.append(f"{path_name} not writable: {path}")
        else:
            # Check parent is writable
            parent = path.parent
            if not parent.exists():
                errors.append(f"Parent of {path_name} does not exist: {parent}")
            elif not os.access(parent, os.W_OK):
                errors.append(f"Cannot create {path_name}, parent not writable: {parent}")
            else:
                # Create directory
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Failed to create {path_name}: {e}")
    
    return errors
```

---

## Migration Notes

### From Existing krag Installations

**No migration needed** — existing configs and data continue to work with XDG defaults.

**Optional migration** to custom paths:

1. Copy existing data to new location:
   ```bash
   # Copy vector store
   rsync -av ~/.cache/krag/storage/ /krag/index/
   
   # Copy models
   rsync -av ~/.cache/krag/models/ /krag/models/
   ```

2. Update `config.toml`:
   ```toml
   [storage]
   vector_store_path = "/krag/index"
   model_cache_path = "/krag/models"
   ```

3. Verify with `krag config show`

4. Re-index or continue using existing data

### From WSL to Native Linux

1. Set up native Linux environment (Python, uv, CUDA)
2. Clone repository
3. Create `config.toml` with custom paths
4. **Do not copy vector store** — re-index on new machine for optimal performance
5. **Copy models if desired** — GGUF files are portable across architectures

---

## Size Estimates

### Storage Requirements

| Path | Typical Size | Growth |
|------|--------------|--------|
| `vector_store_path` | 100MB - 10GB | Grows with corpus size |
| `model_cache_path` | 2GB - 50GB | Grows with model downloads |
| `corpus_cache_path` | 0MB (unused) | Reserved for future use |
| `logs_path` | 10MB - 100MB | Capped by rotation (50MB default) |

**For RTX 4080 Super with 2TB NVME**:
- Allocate 500GB - 1TB for `vector_store_path`
- Allocate 100GB - 500GB for `model_cache_path`
- Remainder for `directory_paths` (corpus source files)

---

## Open Questions

None — data model is fully specified.

---

## Next Steps

See contracts/ directory for:
- CLI interface additions (`krag config show` enhancements)
- Configuration schema validation
- GPU diagnostic commands
