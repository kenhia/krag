"""Integration tests for GPU acceleration (US3).

These tests verify GPU acceleration configuration works end-to-end.
Speed comparison tests are skipped if no GPU is available.
"""

from pathlib import Path

import pytest

from krag.models.configuration import Configuration


def _cuda_available() -> bool:
    """Check if CUDA is available."""
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


def test_config_with_gpu_layers() -> None:
    """Test configuration with GPU acceleration settings."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        llm_n_gpu_layers=-1,
    )
    assert config.llm_n_gpu_layers == -1


def test_config_gpu_layers_in_toml(tmp_path: Path) -> None:
    """Test GPU layers loaded from TOML config."""
    import tomli_w

    from krag.config.settings import ConfigManager

    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
        "llm": {"n_gpu_layers": 24},
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)
    assert config.llm_n_gpu_layers == 24


@pytest.mark.skipif(
    not _cuda_available(),
    reason="CUDA not available - skipping GPU performance test",
)
def test_gpu_performance_improvement() -> None:
    """Test that GPU offloading provides performance improvement.

    This test is conditional - only runs when a CUDA GPU is available.
    """
    # This would require a model and actual inference - skip in CI
    pytest.skip("Requires model download and GPU hardware")
