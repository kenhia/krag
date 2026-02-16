# Migration Guide: WSL to Native Linux

This guide walks you through migrating krag from WSL (Windows Subsystem for Linux) to a native Linux installation with GPU acceleration and custom storage paths.

---

## Overview

After migration, you'll have:

- Custom storage paths on a dedicated drive (e.g., NVME at `/krag`)
- GPU-accelerated LLM inference via CUDA
- Group-based permissions for shared storage
- Python 3.13+ support

**Estimated time**: 30 minutes (excluding large model downloads)

---

## Prerequisites

### Hardware

- Linux machine with NVIDIA GPU (optional but recommended)
- Dedicated storage drive mounted (e.g., `/krag` on NVME)

### Software

- Linux (tested on Arch Linux; any distro with Python 3.11+ works)
- NVIDIA drivers installed (`nvidia-smi` works) — if using GPU
- Python 3.11+ (Python 3.13 recommended)
- `uv` package manager

**Check prerequisites**:

```bash
# Check NVIDIA driver (if using GPU)
nvidia-smi

# Check Python version
python --version  # Should be 3.11+

# Check uv
uv --version
```

---

## Step 1: System Setup

### 1.1 Install CUDA and Drivers (GPU only)

**Arch Linux**:

```bash
sudo pacman -S nvidia nvidia-utils cuda cudnn
nvidia-smi
```

**Other distros**: See [NVIDIA CUDA Installation Guide](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/)

### 1.2 Set Up Storage Group

Create a `krag` group for shared access to the storage drive:

```bash
# Create krag group
sudo groupadd krag

# Add your user to the group
sudo usermod -a -G krag $USER

# Change ownership of storage directory
sudo chown -R :krag /krag

# Set group-writable permissions
sudo chmod -R g+rw /krag

# Set setgid bit (new files inherit group)
sudo find /krag -type d -exec chmod g+s {} \;

# Apply group membership (logout/login or use newgrp)
newgrp krag
```

### 1.3 Create Storage Structure

```bash
mkdir -p /krag/{index,models,corpus,logs}
```

---

## Step 2: Install krag

### 2.1 Clone and Set Up

```bash
cd ~/src
git clone https://github.com/yourusername/krag.git
cd krag

# Create virtual environment with Python 3.13
uv venv --python 3.13

# Install krag
uv pip install -e .
```

### 2.2 Install GPU Support (optional)

```bash
# Install PyTorch with CUDA
uv pip install torch --index-url https://download.pytorch.org/whl/cu121

# Rebuild llama-cpp-python with CUDA
uv pip install llama-cpp-python --force-reinstall --no-cache-dir \
  --config-settings=cmake.args="-DGGML_CUDA=on"

# Verify
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

---

## Step 3: Configure krag

### 3.1 Create Configuration

```bash
mkdir -p ~/.config/krag
```

Create `~/.config/krag/config.toml` with your settings. See the example configuration in [examples/config-krag-paths.toml](../examples/config-krag-paths.toml) or use the template below:

```toml
# Directories to index
[directories]
paths = [
    "/krag/corpus/docs",
    "/krag/corpus/code",
]

# Custom storage paths on dedicated drive
[storage]
vector_store_path = "/krag/index"
model_cache_path = "/krag/models"
logs_path = "/krag/logs"

# Embedding configuration
[embedding]
model = "sentence-transformers/all-MiniLM-L6-v2"
device = "cuda"  # Use "cpu" if no GPU

# LLM configuration
[llm]
model = "microsoft/Phi-3-mini-4k-instruct-gguf"
n_gpu_layers = -1  # Full GPU offload; use 0 for CPU-only
temperature = 0.7
max_tokens = 512
n_ctx = 2048

# Chunking
[chunking]
size = 512
overlap = 50

# Vector store
[vector_store]
collection_name = "krag_embeddings"
distance_metric = "cosine"

# Retrieval
[retrieval]
top_k = 5
min_score = 0.7
```

**GPU layer recommendations**:

| VRAM | `n_gpu_layers` | Notes |
|------|---------------|-------|
| >= 8 GB | `-1` | Full offload |
| >= 4 GB | `32` | Partial offload |
| >= 2 GB | `16` | Minimal offload |
| No GPU | `0` | CPU only |

### 3.2 Validate Configuration

```bash
krag config validate
```

### 3.3 Check GPU Status

```bash
krag gpu status
krag gpu recommend
```

---

## Step 4: Index and Query

### 4.1 Copy Corpus

```bash
rsync -av /mnt/backup/docs/ /krag/corpus/docs/
```

### 4.2 Run Indexing

```bash
krag index
```

### 4.3 Test Query

```bash
krag query "How do I configure GPU acceleration?"
```

### 4.4 Incremental Updates

```bash
krag index --incremental
```

---

## Step 5: Verify Installation

```bash
# Show full configuration
krag config show

# Show storage paths
krag config show --paths-only

# Show GPU configuration
krag config show --gpu-only

# Run test suite (optional)
uv run pytest
```

---

## Troubleshooting

### CUDA Not Available

```bash
# Check driver
nvidia-smi

# Check PyTorch CUDA
python -c "import torch; print(torch.version.cuda)"

# Reinstall PyTorch with CUDA
uv pip install torch --force-reinstall --index-url https://download.pytorch.org/whl/cu121
```

### llama-cpp-python No GPU Support

```bash
# Rebuild with CUDA
uv pip install llama-cpp-python --force-reinstall --no-cache-dir \
  --config-settings=cmake.args="-DGGML_CUDA=on"
```

### Permission Denied on /krag

```bash
# Check group membership
groups  # Should include 'krag'

# Re-login to apply group
newgrp krag

# Fix permissions
sudo chown -R :krag /krag
sudo chmod -R g+rw /krag
sudo find /krag -type d -exec chmod g+s {} \;
```

### Config Validation Fails

Use absolute paths in `config.toml`:

```toml
[storage]
model_cache_path = "/krag/models"  # Not ./models
```

### Out of Memory (OOM)

Reduce GPU layers:

```toml
[llm]
n_gpu_layers = 24  # Instead of -1
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

## Migration Checklist

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
