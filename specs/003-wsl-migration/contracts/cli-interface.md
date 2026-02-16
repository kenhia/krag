# CLI Interface Contract: Configuration Commands

**Feature**: 003-wsl-migration  
**Date**: 2026-02-15  
**Purpose**: Define CLI interface extensions for configuration display and validation

---

## Overview

Extend existing `krag config` commands to display resolved storage paths and validate GPU configuration.

---

## Command: `krag config show`

### Synopsis

```bash
krag config show [--format=<format>] [--paths-only] [--gpu-only]
```

### Description

Display current configuration with resolved storage paths and GPU status.

###Options

- `--format TEXT` — Output format: `table` (default), `json`, `yaml`
- `--paths-only` — Show only storage paths (no other config)
- `--gpu-only` — Show only GPU configuration and status
- `--help` — Show help message

### Behavior

**Default (table format)**:

1. Load and validate configuration
2. Display GPU status (if CUDA available)
3. Display storage paths with source indicators
4. Display other config sections (embedding, llm, chunking, etc.)

**With `--paths-only`**:
- Display only storage paths table
- Show whether each path is from config.toml or XDG default

**With `--gpu-only`**:
- Display GPU hardware info (name, VRAM, compute capability)
- Display configured GPU settings (embedding_device, llm_n_gpu_layers)
- Display warnings if GPU configured but unavailable

### Output Format

#### Table (default)

```
GPU Configuration
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Device ┃ Name                    ┃ VRAM         ┃ Compute  ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ cuda:0 │ NVIDIA GeForce RTX 4080 │ 16.00 GB     │ 8.9      │
└────────┴─────────────────────────┴──────────────┴──────────┘

Storage Paths
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Setting            ┃ Path                          ┃ Source           ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ vector_store_path  │ /krag/index                   │ config.toml      │
│ model_cache_path   │ /krag/models                  │ config.toml      │
│ corpus_cache_path  │ ~/.cache/krag/corpus          │ default (XDG)    │
│ logs_path          │ /krag/logs                    │ config.toml      │
└────────────────────┴───────────────────────────────┴──────────────────┘

Embedding Configuration
  model: sentence-transformers/all-MiniLM-L6-v2
  device: cuda
  
LLM Configuration
  model: microsoft/Phi-3-mini-4k-instruct-gguf
  n_gpu_layers: -1
  temperature: 0.7
  max_tokens: 512
  
[... other sections ...]
```

#### JSON

```json
{
  "gpu": {
    "cuda_available": true,
    "devices": [
      {
        "id": 0,
        "name": "NVIDIA GeForce RTX 4080 Super",
        "vram_gb": 16.0,
        "compute_capability": "8.9"
      }
    ]
  },
  "storage_paths": {
    "vector_store_path": {
      "path": "/krag/index",
      "source": "config.toml"
    },
    "model_cache_path": {
      "path": "/krag/models",
      "source": "config.toml"
    },
    "corpus_cache_path": {
      "path": "/home/ken/.cache/krag/corpus",
      "source": "default"
    },
    "logs_path": {
      "path": "/krag/logs",
      "source": "config.toml"
    }
  },
  "embedding": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "device": "cuda"
  },
  "llm": {
    "model": "microsoft/Phi-3-mini-4k-instruct-gguf",
    "n_gpu_layers": -1,
    "temperature": 0.7,
    "max_tokens": 512
  }
}
```

### Exit Codes

- `0` — Success
- `1` — Configuration file not found
- `2` — Configuration file invalid (parse error)

### Examples

```bash
# Show full configuration
krag config show

# Show only storage paths
krag config show --paths-only

# Show only GPU status
krag config show --gpu-only

# Export as JSON
krag config show --format=json > config-snapshot.json
```

---

## Command: `krag config validate`

### Synopsis

```bash
krag config validate [--strict] [--fix]
```

### Description

Validate configuration, check storage paths, and verify GPU availability.

### Options

- `--strict` — Fail if GPU is configured but unavailable
- `--fix` — Create missing directories automatically (default behavior, included for explicitness)
- `--help` — Show help message

### Behavior

**Validation steps**:

1. **Load configuration** — Parse and validate config file
2. **Check directory_paths** — Verify all corpus directories exist
3. **Check storage paths** — Verify paths are accessible and writable
4. **Create missing directories** — Attempt to create storage dirs if missing
5. **Check GPU configuration** — Warn if GPU configured but unavailable
6. **Report results** — Display validation summary

**Default behavior (without `--strict`)**:
- Warnings for GPU unavailable, but validation passes
- Exit code 0 if only GPU warnings

**With `--strict`**:
- GPU unavailable is an error
- Exit code 1 if GPU configured but unavailable

### Output Format

```
Validating configuration...

✓ Configuration file loaded: ~/.config/krag/config.toml
✓ Directory paths exist: 2 directories
✓ Storage paths accessible:
  • vector_store_path: /krag/index (exists, writable)
  • model_cache_path: /krag/models (created)
  • corpus_cache_path: ~/.cache/krag/corpus (exists)
  • logs_path: /krag/logs (exists, writable)

⚠ GPU Warnings:
  • embedding_device set to "cuda" but CUDA not available
    → Install CUDA PyTorch: uv pip install torch --index-url https://download.pytorch.org/whl/cu121
  • llm_n_gpu_layers set to -1 but CUDA not available
    → LLM will fall back to CPU

Validation: PASSED (with warnings)
```

### Exit Codes

- `0` — Validation passed (with or without warnings)
- `1` — Validation failed (errors found)
- `2` — Configuration file not found or invalid

### Examples

```bash
# Validate configuration
krag config validate

# Strict validation (fail on GPU unavailable)
krag config validate --strict

# Just check, don't create missing directories (hypothetical, not implemented)
# krag config validate --no-fix
```

---

## Command: `krag config edit`

### Synopsis

```bash
krag config edit
```

### Description

Open configuration file in `$EDITOR` (unchanged from existing behavior).

### Behavior

**Existing behavior (no changes)**.

---

## Command: `krag gpu` (NEW)

### Synopsis

```bash
krag gpu <command>
```

### Description

GPU diagnostics and configuration utilities.

### Subcommands

#### `krag gpu status`

Display detailed GPU status including VRAM usage.

**Example output**:

```
GPU Status Report

CUDA Devices
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ ID ┃ Name                     ┃ Total VRAM   ┃ Free VRAM    ┃ Used VRAM    ┃ Compute  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ 0  │ NVIDIA GeForce RTX 4080  │ 16.00 GB     │ 14.23 GB     │ 1.77 GB      │ 8.9      │
└────┴──────────────────────────┴──────────────┴──────────────┴──────────────┴──────────┘

CUDA Version: 12.1
PyTorch Version: 2.5.0
```

#### `krag gpu recommend`

Recommend optimal GPU configuration for current hardware.

**Example output**:

```
GPU Configuration Recommendations

Detected: NVIDIA GeForce RTX 4080 Super with 16.0 GB VRAM

Embeddings:
  ✓ Current setting 'cuda' is optimal

LLM GPU Offloading:
  → Recommend: n_gpu_layers = -1  (full offload)
    Your 16GB VRAM can handle full offload for 7B Q4 models

Add to config.toml:

[embedding]
device = "cuda"

[llm]
n_gpu_layers = -1
```

### Options

- `--help` — Show help for gpu commands

### Exit Codes

- `0` — Success
- `1` — No GPU available

---

## Backward Compatibility

### Existing Commands (unchanged)

- `krag index` — No changes
- `krag query` — No changes
- `krag config edit` — No changes

### Existing `krag config show` Output

**Old behavior** (pre-migration):
- Displays config as loaded from file
- No GPU status
- No path source indicators

**New behavior**:
- Adds GPU status section (if CUDA available)
- Adds path source indicators
- Otherwise same output format

**Impact**: Enhanced output, no breaking changes. Scripts parsing JSON output may see new fields but existing fields unchanged.

---

## Error Messages

### Missing Configuration

```
Error: Configuration file not found
Expected location: ~/.config/krag/config.toml
Create a default config with: krag config init
```

### Invalid Configuration

```
Error: Configuration file is invalid
Path: ~/.config/krag/config.toml
Reason: vector_store_path must be an absolute path, got: ./storage

Fix the configuration file or regenerate with: krag config init
```

### Storage Path Not Writable

```
Error: Configuration validation failed

Storage path errors:
  • vector_store_path not writable: /krag/index
    → Check permissions: ls -la /krag/index
    → Fix with: sudo chown -R :krag /krag && sudo chmod -R g+rw /krag

Run with --fix to attempt automatic creation of missing directories.
```

### GPU Configured but Unavailable

```
Warning: GPU configuration issues detected

  • embedding_device set to "cuda" but CUDA not available
    → Embeddings will fall back to CPU
    → Install CUDA PyTorch: uv pip install torch --index-url https://download.pytorch.org/whl/cu121

  • llm_n_gpu_layers set to -1 but CUDA not available
    → LLM will fall back to CPU
    → Verify NVIDIA drivers: nvidia-smi
    → Rebuild llama-cpp-python with CUDA: uv pip install llama-cpp-python --force-reinstall --config-settings=cmake.args="-DGGML_CUDA=on"

Configuration is valid, but GPU acceleration will not be available.
```

---

## Testing Contract

### Unit Tests

```python
def test_config_show_displays_gpu_status(capsys):
    """GPU status appears in config show output."""
    # Given: Config with GPU settings
    # When: run config show
    # Then: Output includes GPU section
    
def test_config_show_displays_path_sources(capsys):
    """Path sources (config vs default) are indicated."""
    # Given: Config with some custom paths
    # When: run config show --paths-only
    # Then: Output shows source for each path

def test_config_validate_checks_storage_paths():
    """Storage path validation checks existence and permissions."""
    # Given: Config with non-writable path
    # When: run config validate
    # Then: Validation fails with clear error

def test_config_validate_creates_missing_directories(tmp_path):
    """Missing directories are created automatically."""
    # Given: Config with non-existent path in writable parent
    # When: run config validate
    # Then: Directory is created

def test_config_validate_warns_on_gpu_unavailable(capsys, monkeypatch):
    """GPU unavailable produces warning, not error."""
    # Given: Config with GPU settings, CUDA unavailable
    # When: run config validate
    # Then: Warning displayed, exit code 0

def test_config_validate_strict_fails_on_gpu_unavailable(monkeypatch):
    """Strict mode fails when GPU configured but unavailable."""
    # Given: Config with GPU settings, CUDA unavailable
    # When: run config validate --strict
    # Then: Validation fails with exit code 1
```

### Integration Tests

```python
def test_config_show_json_format():
    """JSON output is valid and contains expected fields."""
    # Given: Valid configuration
    # When: run config show --format=json
    # Then: Parseable JSON with gpu, storage_paths, embedding, llm keys

def test_gpu_recommend_suggests_optimal_settings(monkeypatch):
    """GPU recommend command suggests config based on hardware."""
    # Given: Mock GPU with 16GB VRAM
    # When: run gpu recommend
    # Then: Output includes n_gpu_layers=-1 recommendation

def test_gpu_status_displays_vram_usage():
    """GPU status shows current VRAM usage."""
    # Given: CUDA available
    # When: run gpu status
    # Then: Output includes VRAM total/free/used

def test_config_commands_work_without_gpu():
    """All config commands work when GPU unavailable."""
    # Given: No CUDA
    # When: run config show, validate
    # Then: Commands complete successfully with CPU settings
```

---

## Implementation Notes

### GPU Status Display

**Implementation location**: `src/krag/cli/config.py`

**Dependencies**:
```python
import torch
from rich.table import Table
from rich.console import Console
```

**GPU detection helper**:
```python
def get_gpu_status() -> dict:
    """Get GPU status for display."""
    try:
        import torch
        if torch.cuda.is_available():
            devices = []
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                devices.append({
                    'id': i,
                    'name': props.name,
                    'vram_gb': props.total_memory / (1024**3),
                    'compute_capability': f"{props.major}.{props.minor}",
                })
            return {'cuda_available': True, 'devices': devices}
        else:
            return {'cuda_available': False, 'devices': []}
    except ImportError:
        return {'cuda_available': False, 'devices': []}
```

### Path Source Determination

```python
def get_path_source(config: Configuration, field_name: str) -> str:
    """Determine if path is from config file or default."""
    default_factories = {
        'vector_store_path': _get_default_vector_store_path,
        'model_cache_path': _get_default_model_cache_path,
        'corpus_cache_path': _get_default_corpus_cache_path,
        'logs_path': _get_default_logs_path,
    }
    
    actual_path = getattr(config, field_name)
    default_path = default_factories[field_name]()
    
    return "default (XDG)" if actual_path == default_path else "config.toml"
```

---

## Security Considerations

### Path Traversal

**Risk**: User-provided paths could contain `..` or symlinks to escape intended directories.

**Mitigation**: 
- Paths resolved to absolute with `Path.resolve()`
- Validation checks resolved path is within expected root (if configured)
- File operations use `Path` objects (no shell escapes)

### Permission Escalation

**Risk**: Creating directories with elevated permissions.

**Mitigation**:
- krag runs as user, respects umask
- No `sudo` or privilege escalation
- Documentation guides group setup, not code

### Information Disclosure

**Risk**: `krag config show` displays paths that might be sensitive.

**Mitigation**:
- Paths are configuration, not secrets
- User controls config file permissions
- No credentials displayed

---

## Dependencies

### New Dependencies

None — uses existing dependencies (typer, rich, pydantic).

### Optional Dependencies

- `pynvml` — For detailed GPU info in `krag gpu status` (optional, graceful fallback if missing)

---

## Future Enhancements (Out of Scope)

- `krag config init` — Interactive config file creation wizard
- `krag config migrate` — Migrate data from XDG to custom paths
- `krag gpu benchmark` — Benchmark GPU vs CPU performance
- `krag gpu monitor` — Real-time VRAM usage monitoring during indexing/query

---

## Change Summary

### New Commands

- `krag gpu status` — GPU diagnostics
- `krag gpu recommend` — Configuration recommendations

### Enhanced Commands

- `krag config show` — Adds GPU status, path sources, `--paths-only`, `--gpu-only` flags
- `krag config validate` — Checks storage paths, GPU config, adds `--strict` flag

### Unchanged Commands

- `krag config edit`
- All indexing/query commands ( `krag index`, `krag query`)
