# PR: WSL to Native Linux Migration (003-wsl-migration)

## Summary

Migrate krag from WSL to native Arch Linux with configurable storage paths, GPU acceleration, group-based permissions documentation, and Python 3.11-3.13 compatibility validation.

This feature is organized around 5 independent user stories, each delivering standalone value:

1. **Configurable Storage Paths (US1)** — Custom paths for vector store, model cache, corpus cache, and logs via `config.toml`, with XDG defaults when not specified
2. **Group-Based Storage Permissions (US2)** — Documentation for shared group access to `/krag` storage
3. **GPU-Accelerated Inference (US3)** — `n_gpu_layers` configuration for LLM GPU offloading with automatic detection and CPU fallback
4. **Python 3.13+ Compatibility (US4)** — Validated on Python 3.11, 3.12, and 3.13
5. **Re-Index Validation (US5)** — End-to-end migration workflow validated

## Changes

### Source Code

| File | Change | Description |
|------|--------|-------------|
| `src/krag/models/configuration.py` | MODIFIED | Added `model_cache_path`, `corpus_cache_path`, `logs_path` fields with XDG default factories; added `llm_n_gpu_layers` field (ge=-1); added `expand_user_paths` and `validate_absolute_paths` field validators |
| `src/krag/config/settings.py` | MODIFIED | Added `[storage]` section parsing in `_load_toml()`; added `n_gpu_layers` parsing from `[llm]`; added storage path writability validation and directory creation in `validate()`; updated `create_default()` and `migrate_yaml_to_toml()` |
| `src/krag/config/defaults.py` | MODIFIED | Added `DEFAULT_VECTOR_STORE_PATH`, `DEFAULT_MODEL_CACHE_PATH`, `DEFAULT_CORPUS_CACHE_PATH`, `DEFAULT_LOGS_PATH`, `DEFAULT_LLM_N_GPU_LAYERS` constants |
| `src/krag/config/logging.py` | MODIFIED | Added `config` parameter to `setup_logging()` for direct `logs_path` usage |
| `src/krag/cli/config.py` | MODIFIED | Added `--paths-only`, `--gpu-only` flags to `krag config show`; added `_show_storage_paths()` and `_show_gpu_config()` helpers; enhanced validation error messages |
| `src/krag/cli/gpu.py` | **NEW** | GPU detection module: `check_cuda_available()`, `recommend_gpu_layers()`, `krag gpu status`, `krag gpu recommend` commands |
| `src/krag/cli/main.py` | MODIFIED | Registered `gpu_app` as `krag gpu` command group |
| `src/krag/synthesis/llm_client.py` | MODIFIED | Added `n_gpu_layers` parameter to constructor; passes to `Llama()` init; added `_check_gpu_availability()` warning method |

### Tests

| File | Change | Tests |
|------|--------|-------|
| `tests/unit/test_configuration.py` | MODIFIED | +15 tests: storage path defaults, custom paths, GPU layers validation, tilde expansion, absolute path rejection |
| `tests/unit/test_config_manager.py` | MODIFIED | +6 tests: custom path loading, XDG defaults, writability validation, directory creation, path precedence |
| `tests/unit/test_gpu.py` | **NEW** | 3 tests: CUDA available/unavailable/no-torch detection |
| `tests/contract/test_llm_contract.py` | MODIFIED | +4 tests: n_gpu_layers acceptance, default=0, full offload (-1), partial offload (24) |
| `tests/integration/test_custom_storage_paths.py` | **NEW** | 3 tests: roundtrip storage paths, validate & create dirs, TOML file loading |
| `tests/integration/test_gpu_acceleration.py` | **NEW** | 2 tests + 1 conditional skip: config GPU layers, TOML GPU layers, GPU performance |

### Documentation

| File | Change | Description |
|------|--------|-------------|
| `README.md` | MODIFIED | Added Python 3.13+ mention, GPU prerequisites, storage paths config example, GPU commands section |
| `docs/migration-guide.md` | **NEW** | Full migration guide: CUDA install, group setup, config, indexing, troubleshooting, benchmarks |
| `examples/config-krag-paths.toml` | **NEW** | Annotated example config with custom `/krag` storage paths and GPU settings |

### Specs

| File | Change |
|------|--------|
| `specs/003-wsl-migration/tasks.md` | All 64 tasks marked [X] |
| `specs/003-wsl-migration/research.md` | Added Python validation results and GPU detection results |
| `specs/003-wsl-migration/test-config.toml` | Test config for Phase 7 validation |

## Test Results

### Full Suite (Python 3.13)

```
572 passed, 2 skipped, 14 failed (pre-existing)
```

The 14 failures are all in `tests/integration/test_example_plugins.py` — pre-existing, unrelated to this feature, identical across all Python versions.

### Cross-Version Compatibility

| Python Version | Passed | Failed | Skipped | Status |
|---------------|--------|--------|---------|--------|
| 3.11.14 | 572 | 14 (pre-existing) | 2 | PASS |
| 3.12.12 | 572 | 14 (pre-existing) | 2 | PASS |
| 3.13.12 | 572 | 14 (pre-existing) | 2 | PASS |

### Code Quality

- `ruff format`: 114 files unchanged
- `ruff check`: 0 errors remaining
- All new code follows existing patterns and conventions

## GPU Detection

Validated on target hardware:

```
Device: NVIDIA GeForce RTX 4080 SUPER
CUDA Version: 12.8
Compute Capability: 8.9
```

## New CLI Commands

```bash
# GPU diagnostics
krag gpu status          # Show CUDA availability, device info
krag gpu recommend       # Suggest optimal n_gpu_layers

# Enhanced config display
krag config show --paths-only   # Show storage paths table
krag config show --gpu-only     # Show GPU configuration
```

## Configuration

New optional TOML sections (backward compatible — existing configs work unchanged):

```toml
[storage]
vector_store_path = "/krag/index"
model_cache_path = "/krag/models"
corpus_cache_path = "/krag/corpus"
logs_path = "/krag/logs"

[llm]
n_gpu_layers = -1  # -1=full GPU, 0=CPU, 1-N=partial
```

## Breaking Changes

None. All changes are additive:
- New config fields have XDG defaults
- New CLI flags are optional
- Existing CLI commands unchanged
- `llm_n_gpu_layers` defaults to 0 (CPU-only)
