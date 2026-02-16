# Configuration Schema Contract

**Feature**: 003-wsl-migration  
**Date**: 2026-02-15  
**Purpose**: Define configuration schema extensions for storage paths and GPU settings

---

## Overview

This contract defines the structure, types, and validation rules for new configuration fields. All changes maintain backward compatibility with existing TOML configs.

---

## Schema Extensions

### TOML Structure

```toml
# config.toml - New fields (all optional)

[storage]
vector_store_path = "/krag/index"               # Existing field
model_cache_path = "/krag/models"               # NEW
corpus_cache_path = "/krag/corpus"              # NEW
logs_path = "/krag/logs"                        # NEW

[embedding]
model = "sentence-transformers/all-MiniLM-L6-v2"
device = "cuda"                                 # Existing field

[llm]
model = "microsoft/Phi-3-mini-4k-instruct-gguf"
n_gpu_layers = -1                               # NEW
temperature = 0.7
max_tokens = 512
```

### Pydantic Model

```python
from pathlib import Path
from pydantic import BaseSettings, Field, field_validator
from typing import Any

class Configuration(BaseSettings):
    """krag configuration with storage and GPU extensions."""
    
    # Storage paths (new fields)
    model_cache_path: Path = Field(
        default_factory=_get_default_model_cache_path,
        description="Path to cached models",
    )
    
    corpus_cache_path: Path = Field(
        default_factory=_get_default_corpus_cache_path,
        description="Path to corpus cache",
    )
    
    logs_path: Path = Field(
        default_factory=_get_default_logs_path,
        description="Path to log files",
    )
    
    # GPU configuration (new field)
    llm_n_gpu_layers: int = Field(
        default=0,
        ge=-1,
        description="GPU layers for LLM offloading",
    )
    
    # Validators
    @field_validator(
        "model_cache_path", 
        "corpus_cache_path", 
        "logs_path", 
        mode="before"
    )
    @classmethod
    def expand_user_paths(cls, v: Any) -> Any:
        """Expand ~ in paths."""
        if isinstance(v, str):
            return Path(v).expanduser()
        if isinstance(v, Path):
            return v.expanduser()
        return v
    
    @field_validator(
        "model_cache_path",
        "corpus_cache_path",
        "logs_path",
        mode="after"
    )
    @classmethod
    def validate_absolute_paths(cls, v: Path) -> Path:
        """Ensure paths are absolute."""
        if not v.is_absolute():
            raise ValueError(f"Path must be absolute: {v}")
        return v
    
    model_config = SettingsConfigDict(
        env_prefix="KRAG_",
        # Note: env vars not used with manual config loading
    )
```

---

## Field Specifications

### `model_cache_path`

| Property | Value |
|----------|-------|
| **Type** | `Path` |
| **Default** | `~/.cache/krag/models` (via XDG) |
| **Required** | No |
| **Validation** | Must be absolute, `~` expanded |
| **Runtime** | Parent must be writable, created if missing |
| **TOML section** | `[storage]` |
| **Env var** | N/A (manual config loading) |

**Examples**:

```toml
# Absolute path
[storage]
model_cache_path = "/krag/models"

# Tilde expansion supported
[storage]
model_cache_path = "~/my-models"

# Omit for XDG default
# (no model_cache_path key)
```

**Invalid**:

```toml
# Relative path - rejected at load time
[storage]
model_cache_path = "./models"  # ERROR: must be absolute
```

### `corpus_cache_path`

| Property | Value |
|----------|-------|
| **Type** | `Path` |
| **Default** | `~/.cache/krag/corpus` (via XDG) |
| **Required** | No |
| **Validation** | Must be absolute, `~` expanded |
| **Runtime** | Parent must be writable, created if missing |
| **TOML section** | `[storage]` |
| **Usage** | Reserved for future corpus caching |

**Examples**:

```toml
[storage]
corpus_cache_path = "/krag/corpus"
```

### `logs_path`

| Property | Value |
|----------|-------|
| **Type** | `Path` |
| **Default** | `~/.local/state/krag/logs` (via XDG) |
| **Required** | No |
| **Validation** | Must be absolute, `~` expanded |
| **Runtime** | Parent must be writable, created if missing |
| **TOML section** | `[storage]` |
| **Usage** | Rotating log file handler |

**Examples**:

```toml
[storage]
logs_path = "/krag/logs"
```

### `llm_n_gpu_layers`

| Property | Value |
|----------|-------|
| **Type** | `int` |
| **Default** | `0` |
| **Required** | No |
| **Validation** | Must be >= -1 |
| **Runtime** | GPU availability checked, warning if unavailable |
| **TOML section** | `[llm]` |
| **Values** | `-1` = full offload, `0` = CPU only, `1-N` = partial offload |

**Examples**:

```toml
# Full GPU offload (recommended for RTX 4080)
[llm]
n_gpu_layers = -1

# Partial offload (hybrid)
[llm]
n_gpu_layers = 24

# CPU only (default)
[llm]
n_gpu_layers = 0

# Omit for default (CPU only)
# (no n_gpu_layers key)
```

**Invalid**:

```toml
# Negative value < -1 rejected
[llm]
n_gpu_layers = -2  # ERROR: must be >= -1

# String value rejected
[llm]
n_gpu_layers = "auto"  # ERROR: must be int
```

---

## Validation Rules

### Load-Time Validation (Pydantic)

**Executed when**: `Configuration(**toml_dict)` called

**Rules**:

1. **Type checking** — All fields match declared types
2. **Path expansion** — `~` expanded in paths (`mode="before"` validator)
3. **Absolute paths** — All paths are absolute (`mode="after"` validator)
4. **Integer constraints** — `llm_n_gpu_layers >= -1`

**Failure behavior**: Raise `ValidationError` with descriptive message

**Example error**:

```python
ValidationError: 1 validation error for Configuration
model_cache_path
  Path must be absolute: ./models (type=value_error)
```

### Runtime Validation (ConfigManager)

**Executed when**: `ConfigManager.validate(config)` called

**Rules**:

1. **Directory existence** — All `directory_paths` exist
2. **Storage path writability** — Storage paths exist and writable, OR parent writable
3. **Directory creation** — Attempt to create missing storage directories
4. **GPU availability** — Check GPU config against available hardware

**Failure behavior**: Return list of error messages (empty list if valid)

**Example**:

```python
errors = ConfigManager.validate(config)
if errors:
    for error in errors:
        print(f"Error: {error}")
    sys.exit(1)
```

### Validation Phases

```
1. TOML Parsing
   ConfigManager.load()
   ↓
   tomllib.loads(file_content)
   ↓
   dict with parsed values
   
2. Pydantic Validation
   Configuration(**dict)
   ↓
   • Type checking
   • Path expansion
   • Absolute path validation
   • Integer constraints
   ↓
   Configuration instance
   
3. Runtime Validation
   ConfigManager.validate(config)
   ↓
   • Directory existence
   • Path writability
   • GPU availability
   ↓
   List of errors (empty if valid)
```

---

## Backward Compatibility

### Existing Configs (Unchanged)

**Old config.toml** (pre-migration):

```toml
[directories]
paths = ["/home/user/documents"]

[embedding]
model = "all-MiniLM-L6-v2"
device = "cpu"

[llm]
model = "phi-3-mini"
temperature = 0.7
```

**Behavior**: Loads successfully, new fields use XDG defaults.

```python
# After loading:
config.model_cache_path  # => Path('~/.cache/krag/models')
config.llm_n_gpu_layers  # => 0
```

### New Fields (Optional)

All new fields have defaults. Omitting them does not break configuration.

### Field Additions vs Changes

| Field | Status | Impact |
|-------|--------|--------|
| `model_cache_path` | NEW | No impact on existing configs |
| `corpus_cache_path` | NEW | No impact on existing configs |
| `logs_path` | NEW | No impact on existing configs |
| `llm_n_gpu_layers` | NEW | No impact on existing configs |
| `vector_store_path` | EXISTING | No changes made |
| `embedding_device` | EXISTING | No changes made |

---

## TOML Section Mapping

### Current Structure (Existing)

```toml
[directories]           # Source directories to index
paths = [...]

[embedding]             # Embedding model configuration
model = "..."
device = "cpu"

[chunking]              # Chunking configuration
size = 512
overlap = 50

[vector_store]          # Qdrant configuration
collection_name = "..."
distance_metric = "cosine"

[retrieval]             # Retrieval configuration
top_k = 5
min_score = 0.7

[llm]                   # LLM configuration
model = "..."
temperature = 0.7
max_tokens = 512

[path_reductions]       # Path aliasing
aliases = [...]

[plugins]               # Plugin configuration
chunking = [...]
extraction = [...]
```

### New Structure (With Extensions)

```toml
[directories]           # UNCHANGED
paths = [...]

[storage]               # NEW SECTION (or extend vector_store)
vector_store_path = "/krag/index"      # can also be in [vector_store]
model_cache_path = "/krag/models"      # NEW
corpus_cache_path = "/krag/corpus"     # NEW
logs_path = "/krag/logs"               # NEW

[embedding]             # UNCHANGED
model = "..."
device = "cpu"

[llm]                   # EXTENDED
model = "..."
n_gpu_layers = 0        # NEW FIELD
temperature = 0.7
max_tokens = 512

# ... other sections unchanged ...
```

### Alternative: Keep `vector_store_path` in `[vector_store]`

```toml
[vector_store]
collection_name = "krag_embeddings"
distance_metric = "cosine"
storage_path = "/krag/index"  # Renamed from vector_store_path

[storage]
model_cache_path = "/krag/models"
corpus_cache_path = "/krag/corpus"
logs_path = "/krag/logs"
```

**Decision**: Use `[storage]` section for all path configs to group related settings. Keep `vector_store_path` field name for backward compatibility.

---

## Type Definitions

### Python Types

```python
from pathlib import Path
from typing import Literal

# Storage paths
model_cache_path: Path
corpus_cache_path: Path
logs_path: Path
vector_store_path: Path  # existing

# GPU configuration
llm_n_gpu_layers: int  # -1 or >= 0
embedding_device: Literal["cpu", "cuda", "mps"] | str  # existing, allow cuda:0, cuda:1, etc.
```

### JSON Schema (for tooling)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "storage": {
      "type": "object",
      "properties": {
        "vector_store_path": {
          "type": "string",
          "description": "Path to Qdrant vector store"
        },
        "model_cache_path": {
          "type": "string",
          "description": "Path to cached models",
          "default": "~/.cache/krag/models"
        },
        "corpus_cache_path": {
          "type": "string",
          "description": "Path to corpus cache",
          "default": "~/.cache/krag/corpus"
        },
        "logs_path": {
          "type": "string",
          "description": "Path to log files",
          "default": "~/.local/state/krag/logs"
        }
      }
    },
    "llm": {
      "type": "object",
      "properties": {
        "n_gpu_layers": {
          "type": "integer",
          "minimum": -1,
          "default": 0,
          "description": "GPU layers for offloading. -1=full, 0=CPU, 1-N=partial"
        }
      }
    }
  }
}
```

---

## Error Messages

### Invalid Path (Relative)

```
Configuration validation error:
  model_cache_path: Path must be absolute, got: ./models
  
Fix: Use absolute path or tilde:
  model_cache_path = "/krag/models"
  model_cache_path = "~/my-models"
```

### Invalid Integer

```
Configuration validation error:
  llm_n_gpu_layers: Value must be >= -1, got: -5
  
Fix: Use 0 for CPU, -1 for full offload, or positive integer:
  n_gpu_layers = 0   # CPU only
  n_gpu_layers = -1  # Full offload
  n_gpu_layers = 24  # Partial offload (24 layers)
```

### Path Not Writable (Runtime)

```
Configuration validation failed:
  model_cache_path not writable: /krag/models
  
Check permissions:
  ls -la /krag/models
  
Fix with:
  sudo chown -R :krag /krag
  sudo chmod -R g+rw /krag
```

### GPU Unavailable (Runtime Warning)

```
Warning: GPU configuration issues
  llm_n_gpu_layers set to -1 but CUDA not available
  → LLM will fall back to CPU
  
Verify GPU availability:
  nvidia-smi
  python -c "import torch; print(torch.cuda.is_available())"
  
Rebuild llama-cpp-python with CUDA:
  uv pip install llama-cpp-python --force-reinstall \
    --config-settings=cmake.args="-DGGML_CUDA=on"
```

---

## Testing Contract

### Unit Tests

```python
def test_config_loads_with_custom_paths(tmp_path):
    """Custom storage paths load correctly."""
    config_content = """
    [storage]
    model_cache_path = "/krag/models"
    logs_path = "/krag/logs"
    """
    # Assert: config.model_cache_path == Path("/krag/models")

def test_config_expands_tilde_in_paths():
    """Tilde expansion works for all path fields."""
    config_content = """
    [storage]
    model_cache_path = "~/my-models"
    """
    # Assert: config.model_cache_path == Path.home() / "my-models"

def test_config_rejects_relative_paths():
    """Relative paths are rejected."""
    config_content = """
    [storage]
    model_cache_path = "./models"
    """
    # Assert: ValidationError raised

def test_config_defaults_to_xdg_paths():
    """Omitted paths use XDG defaults."""
    config_content = """
    [directories]
    paths = ["/docs"]
    """
    # Assert: config.model_cache_path == XDG_CACHE/krag/models

def test_config_validates_gpu_layers_constraint():
    """GPU layers must be >= -1."""
    config_content = """
    [llm]
    n_gpu_layers = -2
    """
    # Assert: ValidationError raised

def test_config_allows_zero_gpu_layers():
    """Zero GPU layers is valid (CPU only)."""
    config_content = """
    [llm]
    n_gpu_layers = 0
    """
    # Assert: config.llm_n_gpu_layers == 0

def test_config_allows_full_gpu_offload():
    """Full GPU offload (-1) is valid."""
    config_content = """
    [llm]
    n_gpu_layers = -1
    """
    # Assert: config.llm_n_gpu_layers == -1
```

### Integration Tests

```python
def test_config_validation_checks_path_writability(tmp_path):
    """Runtime validation checks storage path permissions."""
    # Given: Config with path in read-only directory
    # When: ConfigManager.validate() called
    # Then: Validation error returned

def test_config_validation_creates_missing_directories(tmp_path):
    """Runtime validation creates missing storage directories."""
    # Given: Config with non-existent path in writable parent
    # When: ConfigManager.validate() called
    # Then: Directory created successfully

def test_config_validation_warns_on_gpu_unavailable(monkeypatch):
    """Runtime validation warns if GPU configured but unavailable."""
    # Given: Config with GPU settings, mock CUDA unavailable
    # When: ConfigManager.validate() called
    # Then: Warning in errors list, not fatal error
```

---

## Migration Scenarios

### Scenario 1: Fresh Installation

**Config**: Default (no custom paths)

```toml
[directories]
paths = ["/home/user/docs"]
```

**Behavior**:
- `model_cache_path` → `~/.cache/krag/models`
- `logs_path` → `~/.local/state/krag/logs`
- `llm_n_gpu_layers` → `0`

### Scenario 2: Migrate to Custom Storage

**Old config**:

```toml
[directories]
paths = ["/home/user/docs"]
```

**New config**:

```toml
[directories]
paths = ["/krag/corpus"]

[storage]
vector_store_path = "/krag/index"
model_cache_path = "/krag/models"
logs_path = "/krag/logs"

[embedding]
device = "cuda"

[llm]
n_gpu_layers = -1
```

**Migration steps**:
1. Set up `/krag` permissions (see migration guide)
2. Update config.toml
3. Copy or re-index data

### Scenario 3: Partial Customization

**Config**:

```toml
[storage]
vector_store_path = "/krag/index"
# model_cache_path uses default
# logs_path uses default
```

**Behavior**:
- `vector_store_path` → `/krag/index` (custom)
- `model_cache_path` → `~/.cache/krag/models` (default)
- `logs_path` → `~/.local/state/krag/logs` (default)

---

## Security Considerations

### Path Injection

**Risk**: User-provided paths could contain malicious patterns.

**Mitigation**:
- Paths resolved to absolute with `Path.resolve()`
- No shell command execution with user paths
- Path operations use `pathlib.Path` (safe)

### Permission Boundaries

**Risk**: krag could be tricked into writing outside intended directories.

**Mitigation**:
- All paths must be absolute (enforced)
- No automatic privilege escalation
- User controls config file, responsible for path safety

### Config File Tampering

**Risk**: Attacker modifies config.toml to redirect data.

**Mitigation**:
- Config file inherits user permissions (not world-writable)
- krag runs as user, not root
- No setuid/setgid binaries

---

## Dependencies

### Required

- `pydantic>=2.6.0` — Model validation
- `pydantic-settings>=2.2.0` — BaseSettings (currently used)
- `tomllib` (Python 3.11+) — TOML parsing

### Optional

None for config schema.

---

## Open Questions

None — schema is fully specified.

---

## Next Steps

- Implement `Configuration` model extensions in `src/krag/models/configuration.py`
- Update `ConfigManager.validate()` in `src/krag/config/settings.py`
- Add tests for new fields and validators
- Update CLI commands per `cli-interface.md` contract
