# Contract: VRAM Utility

**Module**: `src/krag/cli/gpu.py`

## Consolidated Function

```python
def get_free_vram(device: int = 0) -> int | None:
    """Get free VRAM in bytes for the specified CUDA device.

    Uses torch.cuda.mem_get_info() which accounts for fragmentation
    and CUDA context overhead (unlike total_memory - memory_allocated).

    Args:
        device: CUDA device index (default: 0).

    Returns:
        Free VRAM in bytes, or None if CUDA is unavailable.

    Handles:
        - ImportError: torch not installed
        - RuntimeError: CUDA not available or driver issue
        - ValueError: Invalid device index
    """
```

## Consumers

After consolidation, the following modules import from `krag.cli.gpu`:

| Module | Usage |
|--------|-------|
| `embeddings/orchestrator.py` | Determine batch size for embedding generation |
| `synthesis/llm_pool.py` | Check available VRAM for model loading decisions |
| `cli/gpu.py` (`check_cuda_available()`) | Existing CLI `krag gpu` command |
