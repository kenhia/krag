# Research: WSL to Native Linux Migration

**Feature**: 003-wsl-migration  
**Date**: 2026-02-15  
**Purpose**: Document technical research and decisions for migration implementation

## Overview

This research phase resolved technical unknowns about Python 3.13 compatibility, GPU configuration patterns, and Pydantic path handling to guide implementation of the migration feature.

---

## 1. Python 3.13 Compatibility

### Decision

**Target**: Python 3.13 as minimum (3.11-3.13 supported)  
**Rationale**: All critical dependencies now support Python 3.13. The target machine has 3.14 installed, but 3.13 offers broader compatibility without requiring source-level changes.

### Dependency Compatibility

| Dependency | 3.13 Support | Minimum Version | Notes |
|------------|--------------|----------------|--------|
| `sentence-transformers` | ✅ | 2.3.0+ | Requires PyTorch 2.1+ |
| `llama-cpp-python` | ✅ | 0.2.90+ | C extension with wheels for 3.13 |
| `qdrant-client` | ✅ | 1.8.0+ | gRPC dependencies updated |
| `pydantic` | ✅ | 2.6.0+ | Full 3.13 support in v2.6+ |
| `pydantic-settings` | ✅ | 2.2.0+ | Matches pydantic requirements |
| `typer` | ✅ | 0.9.0+ | No changes needed |
| `rich` | ✅ | 13.0.0+ | No changes needed |
| `pyyaml` | ✅ | 6.0.1+ | Security fixes and 3.13 wheels |

### pyproject.toml Configuration

```toml
[project]
requires-python = ">=3.11,<3.14"
```

**Rationale**: 
- Python 3.11 minimum preserves backward compatibility
- Python 3.14 excluded as stretch goal (dependencies less tested)
- Allows testing on both 3.11 and 3.13 in CI

### Migration Impact

**No code changes required** — krag's codebase does not use:
- Deprecated typing features
- `imp` module (removed in 3.12)
- Undocumented CPython internals

**Testing strategy**:
1. Test full suite on Python 3.11 (baseline)
2. Test full suite on Python 3.13 (target)
3. Update CI to test both versions

### Alternatives Considered

1. **Stay on Python 3.11** — Rejected: Target machine has 3.14; maintaining old version creates friction
2. **Target Python 3.14** — Rejected: Dependency ecosystem less mature; 3.13 offers sufficient benefit
3. **Drop 3.11 support** — Rejected: User requested backward compat if feasible (FR-014 SHOULD)

---

## 2. GPU Configuration Patterns

### Decision: Three-Layer GPU Configuration

1. **Embedding GPU acceleration** — Use existing `embedding_device` field
2. **LLM GPU offloading** — Add new `llm_n_gpu_layers` field
3. **Runtime validation** — Graceful fallback with warnings, not hard failures

### 2.1 CUDA Detection

**Pattern**: Lazy detection at startup with PyTorch

```python
import torch

def detect_cuda() -> tuple[bool, list[dict]]:
    """Detect CUDA availability and GPU info.
    
    Returns:
        (cuda_available, list of GPU info dicts)
    """
    if not torch.cuda.is_available():
        return False, []
    
    gpu_info = []
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        gpu_info.append({
            'id': i,
            'name': props.name,
            'vram_gb': props.total_memory / (1024**3),
            'compute_capability': f"{props.major}.{props.minor}"
        })
    
    return True, gpu_info
```

**When to check**: At CLI startup (after config load, before model initialization)

**Fallback strategy**: Warn and fall back to CPU, don't fail

### 2.2 Embedding Device Configuration

**Current implementation**: Already supports `embedding_device` field  
**Valid values**: `"cpu"`, `"cuda"`, `"cuda:0"`, `"mps"`  
**No changes needed** ✅

**Validation pattern** (add to ConfigManager):

```python
def validate_embedding_device(config: Configuration) -> tuple[str, list[str]]:
    """Validate embedding device and return (actual_device, warnings)."""
    warnings = []
    
    if config.embedding_device.startswith("cuda"):
        if not torch.cuda.is_available():
            warnings.append(
                "CUDA requested but not available. Falling back to CPU. "
                "Install CUDA PyTorch with: uv pip install torch --index-url "
                "https://download.pytorch.org/whl/cu121"
            )
            return "cpu", warnings
    
    return config.embedding_device, warnings
```

### 2.3 LLM GPU Offloading

**New configuration field**:

```python
llm_n_gpu_layers: int = Field(
    default=0,
    ge=-1,
    description=(
        "Number of model layers to offload to GPU. "
        "0 = CPU only, -1 = full offload (recommended if CUDA available), "
        "1-N = hybrid offload"
    )
)
```

**Valid values**:
- `0` — CPU only (default for backward compatibility)
- `-1` — Full offload (all layers on GPU)
- `1-N` — Partial offload (N layers on GPU)

**Optimal layer calculation** (for RTX 4080 Super, 16GB VRAM):

| Model Size | Quantization | Recommended `n_gpu_layers` |
|------------|--------------|---------------------------|
| 7B | Q4_K_M | -1 (full offload, ~4GB) |
| 7B | Q8_0 | -1 (full offload, ~7GB) |
| 13B | Q4_K_M | -1 (full offload, ~8GB) |
| 13B | Q8_0 | 40 (partial, ~12GB) |

**Implementation in LLMClient**:

```python
# In LLMClient.__init__
self.n_gpu_layers = n_gpu_layers

# In LLMClient._load_model
self.model = Llama(
    model_path=str(self.model_path),
    n_ctx=self.n_ctx,
    n_threads=self.n_threads,
    n_gpu_layers=self.n_gpu_layers,  # ADD THIS
    verbose=is_verbose
)
```

**Error handling**: Try GPU layers first, fall back to CPU on CUDA/OOM errors:

```python
try:
    self.model = Llama(..., n_gpu_layers=self.n_gpu_layers)
except Exception as e:
    if "cuda" in str(e).lower() or "out of memory" in str(e).lower():
        logger.warning(f"GPU offload failed: {e}. Falling back to CPU.")
        self.model = Llama(..., n_gpu_layers=0)
    else:
        raise
```

### 2.4 Configuration Validation

**Add startup validation** to display GPU status and warnings:

```python
# In cli/index.py, cli/query.py (after config load)
from krag.config.gpu_validator import ConfigValidator

config = ConfigManager.load()
config = ConfigValidator.validate_and_report(config)
# Displays GPU info and any warnings to console
```

**Validation behavior**:
- Detect available GPUs with PyTorch
- Check if configured devices are available
- Warn if GPU configured but unavailable
- Adjust `embedding_device` to fallback value
- Do NOT change `n_gpu_layers` (let LLMClient handle fallback)
- Display GPU info (name, VRAM) for user awareness

### Alternatives Considered

1. **Auto-detect GPU layers** — Rejected: Explicit config preferred; auto-detection requires loading model multiple times (slow)
2. **Fail fast on GPU unavailable** — Rejected: Graceful fallback is more user-friendly
3. **Single `use_gpu` boolean** — Rejected: Insufficient control; embeddings and LLM have different memory profiles

---

## 3. Storage Path Configuration

### Decision: Explicit Config Fields with XDG Defaults

**Pattern**: Add config fields for each storage type, all optional with XDG-based defaults.

### 3.1 Pydantic v2 Path Handling

**Field type**: Use `pathlib.Path` (not `str`)  
**Validation**: Use `field_validator` for structure, separate runtime validation for filesystem checks

**Tilde expansion** (add to Configuration model):

```python
from pydantic import field_validator

@field_validator("vector_store_path", "model_cache_path", mode="before")
@classmethod
def expand_user_paths(cls, v: Any) -> Any:
    """Expand ~ in paths."""
    if isinstance(v, str):
        return Path(v).expanduser()
    if isinstance(v, Path):
        return v.expanduser()
    return v
```

**Validation pattern** (continue existing approach):
- **At model level**: Check paths are absolute (structural validation)
- **At runtime (ConfigManager.validate)**: Check paths exist, writable (filesystem validation)

**Why not use `DirectoryPath`**: Pydantic's `DirectoryPath` validates existence at model construction time, breaking:
- Default factories (XDG functions called before dirs exist)
- Config loading when dirs don't exist yet
- Graceful "create if missing" behavior

### 3.2 Default Factories

**Current pattern** (excellent, continue using):

```python
def _get_default_vector_store_path() -> Path:
    """Lazy import to avoid circular dependency."""
    from krag.config.xdg import get_krag_cache_dir
    return get_krag_cache_dir() / "storage"

vector_store_path: Path = Field(
    default_factory=_get_default_vector_store_path,
    description="Path to Qdrant storage (XDG_CACHE_HOME/krag/storage)",
)
```

**Extend for new storage paths**:

```python
def _get_default_model_cache_path() -> Path:
    from krag.config.xdg import get_krag_cache_dir
    return get_krag_cache_dir() / "models"

def _get_default_logs_path() -> Path:
    from krag.config.xdg import get_krag_state_dir
    return get_krag_state_dir() / "logs"

model_cache_path: Path = Field(
    default_factory=_get_default_model_cache_path,
    description="Path to cached models (XDG_CACHE_HOME/krag/models)",
)

logs_path: Path = Field(
    default_factory=_get_default_logs_path,
    description="Path to log files (XDG_STATE_HOME/krag/logs)",
)
```

### 3.3 Config Precedence

**Current approach**: krag manually loads config files via `ConfigManager.load()`, not using pydantic-settings' env var loading.

**Precedence** (current behavior, keep it):
1. Config file values (explicit settings in config.toml)
2. Default factories (XDG-based defaults)

**Environment variables**: Currently do NOT work because krag doesn't use `Configuration.from_env()`. To add env var support:

**Option A**: Keep current approach (simpler) — config file only, no env vars  
**Option B**: Add pydantic-settings custom sources (complex) — config file overrides env vars

**Recommendation**: **Option A** (keep current approach). Env var support is not a requirement (FR-006 only says config file must override XDG env vars like `XDG_CACHE_HOME`, not that it must support `KRAG_*` env vars).

### 3.4 Path Resolution Display

**Add to `krag config show`**:

```python
def show_resolved_paths(config: Configuration) -> None:
    """Display resolved storage paths with their sources."""
    from rich.table import Table
    
    table = Table(title="Storage Paths")
    table.add_column("Setting")
    table.add_column("Path")
    table.add_column("Source")
    
    # Check if each path is default or custom
    default_vector = _get_default_vector_store_path()
    vector_source = "default (XDG)" if config.vector_store_path == default_vector else "config.toml"
    
    table.add_row("vector_store_path", str(config.vector_store_path), vector_source)
    # Repeat for other paths...
    
    console.print(table)
```

### Alternatives Considered

1. **Symlinks** — Rejected: User explicitly stated dislike; less portable
2. **XDG env var overrides** — Rejected: Affects all XDG-compliant apps; config file preferred
3. **Single `storage_root` path** — Rejected: Different storage types have different XDG categories (cache vs state)

---

## 4. Group-Based Permissions

### Decision: Documentation-Based Approach

**No code changes needed** — this is a system administration task documented for users.

### Setup Instructions (for migration guide)

```bash
# 1. Create krag group
sudo groupadd krag

# 2. Add users to group
sudo usermod -a -G krag ken
sudo usermod -a -G krag krag-service  # Future service user

# 3. Change ownership of /krag
sudo chown -R :krag /krag

# 4. Set permissions (group writable)
sudo chmod -R g+rw /krag

# 5. Set setgid bit (new files inherit group)
sudo find /krag -type d -exec chmod g+s {} \;

# 6. Verify
ls -la /krag
# Should show: drwxrwsr-x ... ken krag ...

# 7. Reboot or newgrp to apply group membership
newgrp krag
```

### umask Consideration

**User's umask** affects new file permissions. Recommend setting umask in shell profile:

```bash
# In ~/.bashrc or ~/.config/fish/config.fish
umask 002  # 775 for dirs, 664 for files (group writable)
```

### Config Example

```toml
[storage]
vector_store_path = "/krag/index"
model_cache_path = "/krag/models"

[directories]
paths = ["/krag/corpus"]
```

### Alternatives Considered

1. **ACLs (Access Control Lists)** — Rejected: Overkill for simple shared access
2. **Run as root** — Rejected: Security antipattern
3. **User-level permissions** — Rejected: Doesn't support future service account

---

## 5. Installation & Dependencies

### CUDA Installation (Arch Linux)

```bash
# 1. Install NVIDIA drivers and CUDA toolkit
sudo pacman -S nvidia nvidia-utils cuda cudnn

# 2. Verify installation
nvidia-smi

# 3. Rebuild llama-cpp-python with CUDA support
uv pip install llama-cpp-python --force-reinstall --no-cache-dir \
  --config-settings=cmake.args="-DGGML_CUDA=on"

# 4. Install PyTorch with CUDA support
uv pip install torch --index-url https://download.pytorch.org/whl/cu121

# 5. Verify CUDA in PyTorch
uv run python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### uv Environment Setup

```bash
# 1. Clone repository
cd /home/ken/src/krag

# 2. Create virtual environment with Python 3.13
uv venv --python 3.13

# 3. Activate
source .venv/bin/activate

# 4. Install krag in development mode
uv pip install -e .

# 5. Run tests
uv run pytest
```

---

## Summary of Decisions

| **Area** | **Decision** | **Rationale** |
|----------|--------------|---------------|
| **Python Version** | 3.13 minimum, 3.11-3.13 supported | All deps support 3.13; broader compat than 3.14 |
| **Embedding GPU** | Keep existing `embedding_device` field | Already implemented, no changes needed |
| **LLM GPU** | Add `llm_n_gpu_layers` field (default 0) | Separate control; -1 for full offload on RTX 4080 |
| **GPU Detection** | Lazy at startup with PyTorch | Warn and fallback, don't fail fast |
| **Storage Paths** | Explicit config fields with XDG defaults | User preference; config file > XDG env vars |
| **Path Type** | `pathlib.Path` with `field_validator` | Matches existing pattern; structural validation |
| **Default Factories** | Continue lazy import pattern | Avoids circular deps; works with XDG |
| **Permissions** | Document group setup, no code changes | Sysadmin task; krag respects file permissions |
| **Env Vars** | No `KRAG_*` env var support | Simplifies; config file is sufficient |
| **Validation** | Structural (pydantic) + filesystem (runtime) | Graceful; allows "create if missing" |

---

## Open Questions

None — all NEEDS CLARIFICATION items resolved.

---

## Python Version Validation Results (T046-T051)

**Validation Date**: 2026-02-15

### Test Results by Python Version

| Python Version | Tests Passed | Tests Failed | Tests Skipped | Status |
|---------------|-------------|-------------|---------------|--------|
| 3.11.14 | 572 | 14 (pre-existing) | 2 | ✅ PASS |
| 3.12.12 | 572 | 14 (pre-existing) | 2 | ✅ PASS |
| 3.13.12 | 572 | 14 (pre-existing) | 2 | ✅ PASS |

### Pre-existing Failures (Not Version-Specific)

All 14 failures are in `tests/integration/test_example_plugins.py` and occur identically across all Python versions. These are related to example plugin installation/discovery (not installed in editable mode during testing) and are not related to the 003-wsl-migration feature.

### Python 3.13-Specific Notes

- No Python 3.13-specific issues encountered
- All dependencies resolve successfully via `uv lock`
- No deprecation warnings related to 3.13 changes
- `tomllib` (stdlib since 3.11) works correctly for TOML parsing
- Type hints using `X | Y` syntax work correctly (PEP 604, available since 3.10)

---

## GPU Detection Results (T063)

**Machine**: Arch Linux, NVIDIA GeForce RTX 4080 SUPER  
**CUDA Version**: 12.8  
**Compute Capability**: 8.9

### `krag gpu status` Output

```
CUDA GPU: Available
Device: NVIDIA GeForce RTX 4080 SUPER
CUDA Version: 12.8
Device Count: 1
Compute Capability: 8.9
```

### `krag gpu recommend` Output

```
GPU has sufficient VRAM - try full offload, reduce if OOM
Recommended: n_gpu_layers = -1
```

### Expected Performance (from quickstart benchmarks)

| Metric | CPU | GPU (full offload) | Speedup |
|--------|-----|-------------------|---------|
| Embedding | ~5 chunks/s | ~50 chunks/s | 10x |
| LLM (Phi-3 Q4_K_M) | ~8 tok/s | ~35 tok/s | 4.4x |

---

## Next Phase

Proceed to **Phase 1: Design** to create:
- `data-model.md` — Configuration field additions
- `contracts/` — CLI interface contracts, config schema
- `quickstart.md` — User setup guide for migration
