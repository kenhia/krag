"""GPU detection and management CLI commands."""

import logging
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)

# Try to import torch for GPU detection
try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

# Create GPU subcommand app
gpu_app = typer.Typer(
    name="gpu",
    help="GPU detection and management",
    add_completion=False,
)

console = Console()


def get_free_vram(device: int = 0) -> int | None:
    """Get free VRAM in bytes for the specified CUDA device.

    Uses torch.cuda.mem_get_info() which accounts for fragmentation
    and CUDA context overhead (unlike total_memory - memory_allocated).

    Args:
        device: CUDA device index (default: 0).

    Returns:
        Free VRAM in bytes, or None if CUDA is unavailable.
    """
    try:
        import torch  # noqa: F811

        free, _total = torch.cuda.mem_get_info(device)
        return int(free)
    except (ImportError, RuntimeError, ValueError):
        return None


def check_cuda_available() -> dict[str, Any]:
    """Check CUDA GPU availability and return device info.

    Returns:
        Dictionary with GPU information:
        - available: bool - whether CUDA is available
        - device_name: str - GPU device name (if available)
        - device_count: int - number of CUDA devices
        - cuda_version: str - CUDA version string
        - vram_total: int - total VRAM in bytes (if available)
        - vram_free: int - free VRAM in bytes (if available)
        - compute_capability: tuple - compute capability (if available)
        - error: str - error message (if not available)
    """
    if torch is None:
        return {
            "available": False,
            "error": "torch not installed - install with: uv add torch",
        }

    if not torch.cuda.is_available():
        return {
            "available": False,
            "error": "CUDA not available - check NVIDIA drivers and PyTorch CUDA build",
        }

    try:
        device_count = torch.cuda.device_count()
        device_name = torch.cuda.get_device_name(0)

        result: dict[str, Any] = {
            "available": True,
            "device_name": device_name,
            "device_count": device_count,
            "cuda_version": torch.version.cuda or "unknown",
        }

        # Try to get VRAM info — use mem_get_info which queries the CUDA
        # driver and reflects memory used by *all* processes, not just this one.
        # (memory_allocated() only tracks the current PyTorch process.)
        try:
            vram_free, vram_total = torch.cuda.mem_get_info(0)
            result["vram_total"] = vram_total
            result["vram_free"] = vram_free
        except Exception:
            pass

        # Try to get compute capability
        try:
            cc = torch.cuda.get_device_capability(0)
            result["compute_capability"] = cc
        except Exception:
            pass

        return result

    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }


def recommend_gpu_layers(gpu_info: dict[str, Any]) -> dict[str, Any]:
    """Recommend optimal n_gpu_layers based on GPU capabilities.

    Args:
        gpu_info: GPU info from check_cuda_available()

    Returns:
        Dictionary with recommendations:
        - recommended_layers: int - recommended n_gpu_layers value
        - reason: str - explanation
        - config_snippet: str - TOML config to use
    """
    if not gpu_info.get("available"):
        return {
            "recommended_layers": 0,
            "reason": "No GPU available - using CPU only",
            "config_snippet": "[llm]\nn_gpu_layers = 0  # CPU only",
        }

    vram_total = gpu_info.get("vram_total", 0)
    vram_gb = vram_total / (1024**3) if vram_total else 0

    if vram_gb >= 8:
        return {
            "recommended_layers": -1,
            "reason": f"GPU has {vram_gb:.1f} GB VRAM - full offload recommended",
            "config_snippet": "[llm]\nn_gpu_layers = -1  # Full GPU offload",
        }
    elif vram_gb >= 4:
        return {
            "recommended_layers": 32,
            "reason": f"GPU has {vram_gb:.1f} GB VRAM - partial offload (32 layers) recommended",
            "config_snippet": "[llm]\nn_gpu_layers = 32  # Partial GPU offload",
        }
    elif vram_gb >= 2:
        return {
            "recommended_layers": 16,
            "reason": f"GPU has {vram_gb:.1f} GB VRAM - partial offload (16 layers) recommended",
            "config_snippet": "[llm]\nn_gpu_layers = 16  # Partial GPU offload",
        }
    else:
        return {
            "recommended_layers": -1,
            "reason": f"GPU has {vram_gb:.1f} GB VRAM - try full offload, reduce if OOM",
            "config_snippet": "[llm]\nn_gpu_layers = -1  # Full GPU offload (reduce if OOM)",
        }


@gpu_app.command(name="status")
def gpu_status() -> None:
    """Show GPU status and CUDA availability.

    Displays detailed GPU information including device name, VRAM,
    compute capability, and CUDA version.

    Examples:

        krag gpu status
    """
    gpu_info = check_cuda_available()

    if not gpu_info["available"]:
        console.print("[yellow]CUDA GPU: Not Available[/yellow]")
        console.print(f"  Reason: {gpu_info.get('error', 'Unknown')}")
        console.print()
        console.print("[dim]To enable GPU acceleration:[/dim]")
        console.print("  1. Install NVIDIA drivers")
        console.print(
            "  2. Install PyTorch with CUDA: uv add torch --index-url https://download.pytorch.org/whl/cu121"
        )
        console.print("  3. Rebuild llama-cpp-python with CUDA support")
        return

    console.print("[green]CUDA GPU: Available[/green]\n")

    table = Table(title="GPU Information", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Device", gpu_info["device_name"])
    table.add_row("CUDA Version", gpu_info.get("cuda_version", "unknown"))
    table.add_row("Device Count", str(gpu_info.get("device_count", 1)))

    if "vram_total" in gpu_info:
        vram_total_gb = gpu_info["vram_total"] / (1024**3)
        vram_free_gb = gpu_info.get("vram_free", 0) / (1024**3)
        table.add_row("VRAM Total", f"{vram_total_gb:.1f} GB")
        table.add_row("VRAM Free", f"{vram_free_gb:.1f} GB")

    if "compute_capability" in gpu_info:
        cc = gpu_info["compute_capability"]
        table.add_row("Compute Capability", f"{cc[0]}.{cc[1]}")

    console.print(table)


@gpu_app.command(name="recommend")
def gpu_recommend() -> None:
    """Recommend optimal GPU settings for your hardware.

    Analyzes available GPU and suggests n_gpu_layers setting
    for optimal performance.

    Examples:

        krag gpu recommend
    """
    gpu_info = check_cuda_available()
    recommendation = recommend_gpu_layers(gpu_info)

    console.print("[cyan]GPU Recommendation[/cyan]\n")
    console.print(f"  {recommendation['reason']}\n")
    console.print("[cyan]Add to your config.toml:[/cyan]\n")
    console.print(f"  {recommendation['config_snippet']}")
    console.print()

    if gpu_info.get("available"):
        console.print("[dim]Tip: Monitor VRAM usage with 'nvidia-smi' during inference[/dim]")
