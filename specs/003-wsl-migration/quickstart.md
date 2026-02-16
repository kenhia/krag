# Quickstart: WSL to Native Linux Migration

**Feature**: 003-wsl-migration  
**Date**: 2026-02-15  
**Audience**: Users migrating krag from WSL to native Linux with GPU acceleration

---

## Overview

This guide walks you through migrating krag from WSL (Windows Subsystem for Linux) to a native Linux installation (Arch Linux or similar) with:

- ✅ Custom storage paths on dedicated NVME drive
- ✅ GPU acceleration for embeddings and LLM inference
- ✅ Group-based permissions for shared storage
- ✅ Python 3.13+ support

**Estimated time**: 30 minutes (excluding large model downloads)

---

## Prerequisites

### Hardware

- Linux machine with NVIDIA GPU (tested on RTX 4080 Super)
- Dedicated storage drive mounted (e.g., `/krag` on 2TB NVME)

### Software

- Arch Linux (or compatible distro)
- NVIDIA drivers installed (`nvidia-smi` works)
- Python 3.11+ (Python 3.13 recommended)
- `uv` package manager

**Check prerequisites**:

```bash
# Check NVIDIA driver
nvidia-smi

# Check Python version
python --version  # Should be 3.11+

# Check uv
uv --version
```

---

## Step 1: System Setup

### 1.1 Install CUDA and Drivers (if needed)

**Arch Linux**:

```bash
# Install NVIDIA packages
sudo pacman -S nvidia nvidia-utils cuda cudnn

# Verify installation
nvidia-smi
```

**Other distros**: See [NVIDIA CUDA Installation Guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/)

### 1.2 Set Up Storage Group

Create a `krag` group for shared access to the storage drive:

```bash
# 1. Create krag group
sudo groupadd krag

# 2. Add your user to the group
sudo usermod -a -G krag $USER

# 3. Change ownership of storage directory
sudo chown -R :krag /krag

# 4. Set group-writable permissions
sudo chmod -R g+rw /krag

# 5. Set setgid bit (new files inherit group)
sudo find /krag -type d -exec chmod g+s {} \;

# 6. Verify
ls -la /krag
# Should show: drwxrwsr-x ... <user> krag ...

# 7. Apply group membership (logout/login or use newgrp)
newgrp krag
```

**Why setgid?**: The `g+s` permission ensures new files created in `/krag` inherit the `krag` group ownership automatically.

### 1.3 Create Storage Structure

```bash
# Create subdirectories
mkdir -p /krag/{index,models,corpus,logs}

# Verify permissions
ls -la /krag
```

---

## Step 2: Install krag

### 2.1 Clone Repository

```bash
cd ~/src  # Or your preferred location
git clone https://github.com/yourusername/krag.git
cd krag
```

### 2.2 Create Virtual Environment

**With Python 3.13** (recommended):

```bash
# Let uv download and use Python 3.13
uv venv --python 3.13
```

**With system Python** (if 3.11+):

```bash
uv venv
```

**Note**: Activation is optional when using `uv` — all `uv` commands (like `uv pip install`, `uv run`) automatically use the virtual environment.

### 2.3 Install Dependencies

**Install krag in development mode**:

```bash
uv pip install -e .
```

**Install PyTorch with CUDA support**:

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cu121
```

**Rebuild llama-cpp-python with CUDA**:

```bash
uv pip install llama-cpp-python --force-reinstall --no-cache-dir \
  --config-settings=cmake.args="-DGGML_CUDA=on"
```

**Verify GPU support**:

```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
# Should print: CUDA available: True
```

---

## Step 3: Configure krag

### 3.1 Create Configuration File

Create `~/.config/krag/config.toml`:

```bash
mkdir -p ~/.config/krag
nano ~/.config/krag/config.toml
```

### 3.2 Example Configuration

```toml
# ~/.config/krag/config.toml

# Directories to index (your corpus)
[directories]
paths = [
    "/krag/corpus/docs",
    "/krag/corpus/code",
]

# Storage paths (custom paths on NVME)
[storage]
vector_store_path = "/krag/index"
model_cache_path = "/krag/models"
logs_path = "/krag/logs"

# Embedding configuration (GPU accelerated)
[embedding]
model = "sentence-transformers/all-MiniLM-L6-v2"
device = "cuda"  # Use GPU for embeddings

# LLM configuration (GPU offloading)
[llm]
model = "microsoft/Phi-3-mini-4k-instruct-gguf"
n_gpu_layers = -1  # Full GPU offload (recommended for RTX 4080)
temperature = 0.7
max_tokens = 512
n_ctx = 2048

# Chunking configuration
[chunking]
size = 512
overlap = 50

# Vector store configuration
[vector_store]
collection_name = "krag_embeddings"
distance_metric = "cosine"

# Retrieval configuration
[retrieval]
top_k = 5
min_score = 0.7
```

**For smaller GPUs** (< 12GB VRAM), use partial offload:

```toml
[llm]
n_gpu_layers = 24  # Partial offload
```

**For CPU-only** (no GPU):

```toml
[embedding]
device = "cpu"

[llm]
n_gpu_layers = 0
```

### 3.3 Validate Configuration

```bash
krag config validate
```

**Expected output**:

```
Validating configuration...

✓ Configuration file loaded: ~/.config/krag/config.toml
✓ Directory paths exist: 2 directories
✓ Storage paths accessible:
  • vector_store_path: /krag/index (created)
  • model_cache_path: /krag/models (exists)
  • logs_path: /krag/logs (exists)

GPU Configuration:
  • GPU 0: NVIDIA GeForce RTX 4080 Super (16.00 GB, compute 8.9)
  • embedding_device: cuda ✓
  • llm_n_gpu_layers: -1 ✓

Validation: PASSED
```

---

## Step 4: Populate Corpus

### 4.1 Add Documents

Copy your documents to the corpus directories:

```bash
# Example: Copy from WSL backup
rsync -av /mnt/backup/docs/ /krag/corpus/docs/

# Or copy from any source
cp -r ~/Documents/*.md /krag/corpus/docs/
```

### 4.2 Verify Permissions

```bash
ls -la /krag/corpus/docs
# Files should be readable by you
```

---

## Step 5: Index Corpus

### 5.1 Run Indexing

```bash
krag index
```

**Expected output**:

```
Discovered 523 files
Processing documents...
[████████████████████████████████████████] 523/523 • 00:02:15 • 3.9 docs/s
Generating embeddings...
[████████████████████████████████████████] 2341/2341 • 00:00:45 • 52 chunks/s
Storing vectors...
✓ Indexed 523 documents (2341 chunks) in 3m 12s
```

**GPU acceleration check**: Embedding generation should be significantly faster than CPU-only (50+ chunks/s vs. ~5 chunks/s on CPU).

### 5.2 Verify Index

```bash
# Check vector store was created
ls -lh /krag/index
# Should show qdrant storage files

# Check index size
du -sh /krag/index
```

---

## Step 6: Test Querying

### 6.1 Run Test Query

```bash
krag query "How do I configure GPU acceleration?"
```

**Expected output**:

```
Query: How do I configure GPU acceleration?

Top Results:
  1. docs/configuration.md (score: 0.89)
     GPU acceleration can be configured in config.toml...
     
  2. docs/quickstart.md (score: 0.82)
     For embedding GPU acceleration, set device = "cuda"...
  
  3. docs/llm-setup.md (score: 0.78)
     LLM GPU offloading is controlled by n_gpu_layers...

Answer:
To configure GPU acceleration in krag, set embedding device to "cuda" 
and llm_n_gpu_layers to -1 for full offload...

Query time: 1.2s (embedding: 0.1s, retrieval: 0.3s, generation: 0.8s)
```

**GPU acceleration check**: Query time should be fast (~1-2s for small queries). LLM generation may still take time depending on model and context.

---

## Step 7: Verify Installation

### 7.1 Check Configuration

```bash
krag config show
```

### 7.2 Check GPU Status

```bash
krag gpu status
```

**Expected output**:

```
GPU Status Report

CUDA Devices
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ ID ┃ Name                     ┃ Total VRAM   ┃ Free VRAM    ┃ Used VRAM    ┃ Compute  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ 0  │ NVIDIA GeForce RTX 4080  │ 16.00 GB     │ 14.23 GB     │ 1.77 GB      │ 8.9      │
└────┴──────────────────────────┴──────────────┴──────────────┴──────────────┴──────────┘

CUDA Version: 12.1
PyTorch Version: 2.5.0+cu121
```

### 7.3 Run Test Suite (Optional)

```bash
# Full test suite
uv run pytest

# Quick smoke test
uv run pytest tests/integration/test_query_pipeline.py
```

---

## Troubleshooting

### Issue: CUDA Not Available

**Symptom**:

```
Warning: CUDA requested but not available
```

**Solutions**:

1. **Check NVIDIA driver**:
   ```bash
   nvidia-smi
   ```

2. **Verify PyTorch CUDA support**:
   ```bash
   python -c "import torch; print(torch.version.cuda)"
   # Should print CUDA version (e.g., 12.1)
   ```

3. **Reinstall PyTorch with CUDA**:
   ```bash
   uv pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121
   ```

### Issue: llama-cpp-python No GPU Support

**Symptom**:

```
Warning: llm_n_gpu_layers set to -1 but model loads on CPU
```

**Solution**:

```bash
# Rebuild llama-cpp-python with CUDA
uv pip install llama-cpp-python --force-reinstall --no-cache-dir \
  --config-settings=cmake.args="-DGGML_CUDA=on"
```

**Verify**:

```bash
# Check build flags
uv pip show llama-cpp-python
# Look for CUDA in metadata
```

### Issue: Permission Denied on /krag

**Symptom**:

```
Error: vector_store_path not writable: /krag/index
```

**Solutions**:

1. **Check group membership**:
   ```bash
   groups
   # Should include 'krag'
   ```

2. **Re-login to apply group**:
   ```bash
   newgrp krag
   # Or logout and login again
   ```

3. **Fix permissions**:
   ```bash
   sudo chown -R :krag /krag
   sudo chmod -R g+rw /krag
   sudo find /krag -type d -exec chmod g+s {} \;
   ```

### Issue: Slow Embeddings on GPU

**Symptom**: Embedding generation is slow (~5 chunks/s) despite GPU

**Possible causes**:

1. **Small batch size** — Check `batch_size` in embedding config
2. **CPU fallback** — Verify `device = "cuda"` in config
3. **PyTorch CPU version** — Check `torch.cuda.is_available()`

**Solution**:

```bash
# Get GPU recommendations
krag gpu recommend

# Check current config
krag config show --gpu-only
```

### Issue: Out of Memory (OOM)

**Symptom**:

```
RuntimeError: CUDA out of memory
```

**Solutions**:

1. **Reduce LLM GPU layers**:
   ```toml
   [llm]
   n_gpu_layers = 24  # Instead of -1
   ```

2. **Reduce batch size** (if indexing):
   ```bash
   # Not configurable yet, but embeddings use adaptive batching
   ```

3. **Use smaller model quantization**:
   ```toml
   [llm]
   model = "TheBloke/Llama-2-7B-GGUF"  # Use Q4_K_M instead of Q8_0
   ```

### Issue: Config Validation Fails

**Symptom**:

```
Configuration validation error:
  model_cache_path: Path must be absolute, got: ./models
```

**Solution**: Use absolute paths in `config.toml`:

```toml
[storage]
model_cache_path = "/krag/models"  # Not ./models
```

---

## Performance Benchmarks

### Embedding Generation (RTX 4080 Super)

| Device | Speed | Speedup |
|--------|-------|---------|
| CPU (16 threads) | ~5 chunks/s | 1x |
| CUDA | ~50 chunks/s | **10x** |

### LLM Inference (Phi-3 Mini 4K Q4_K_M)

| GPU Layers | Tokens/s | VRAM Usage |
|------------|----------|------------|
| 0 (CPU) | ~8 tok/s | 0 GB |
| 24 (partial) | ~25 tok/s | 2.5 GB |
| -1 (full) | ~35 tok/s | 3.5 GB |

---

## Next Steps

### Optional Optimizations

1. **Install pynvml for detailed GPU monitoring**:
   ```bash
   uv pip install pynvml
   ```

2. **Set up log rotation** (if not using systemd):
   ```bash
   # krag already uses rotating file handler (10MB, 5 backups)
   # Verify logs are rotating
   ls -lh /krag/logs
   ```

3. **Configure umask for group writability**:
   ```bash
   # Add to ~/.bashrc or ~/.config/fish/config.fish
   umask 002
   ```

4. **Benchmark your setup**:
   ```bash
   krag gpu status
   # Check VRAM usage during indexing/querying
   ```

### Migration Checklist

- [ ] NVIDIA drivers installed (`nvidia-smi` works)
- [ ] Python 3.13 environment created
- [ ] PyTorch with CUDA support installed
- [ ] llama-cpp-python rebuilt with CUDA
- [ ] `/krag` group and permissions configured
- [ ] Configuration file created
- [ ] Configuration validated (`krag config validate`)
- [ ] Corpus copied to `/krag/corpus/`
- [ ] Index created (`krag index`)
- [ ] Test query successful (`krag query "test"`)
- [ ] GPU status verified (`krag gpu status`)

---

## Additional Resources

- **krag Documentation**: See `docs/` directory
- **NVIDIA CUDA Guide**: https://docs.nvidia.com/cuda/
- **PyTorch CUDA Installation**: https://pytorch.org/get-started/locally/
- **llama-cpp-python GPU Support**: https://github.com/abetlen/llama-cpp-python#installation-with-hardware-acceleration

---

## Support

If you encounter issues not covered in this guide:

1. Check logs: `tail -f /krag/logs/krag.log`
2. Validate config: `krag config validate`
3. Check GPU status: `krag gpu status`
4. Run tests: `uv run pytest`
5. Open an issue on GitHub with logs and system info

---

**Congratulations!** Your krag installation is now running on native Linux with GPU acceleration. 🎉
