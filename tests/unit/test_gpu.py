"""Unit tests for GPU availability detection (US3)."""

from unittest.mock import patch


def test_check_cuda_available_true() -> None:
    """Test GPU detection when CUDA is available."""
    from krag.cli.gpu import check_cuda_available

    with patch("krag.cli.gpu.torch") as mock_torch:
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4080 Super"
        mock_torch.cuda.device_count.return_value = 1

        result = check_cuda_available()

        assert result["available"] is True
        assert result["device_name"] == "NVIDIA RTX 4080 Super"
        assert result["device_count"] == 1


def test_check_cuda_available_false() -> None:
    """Test GPU detection when CUDA is not available."""
    from krag.cli.gpu import check_cuda_available

    with patch("krag.cli.gpu.torch") as mock_torch:
        mock_torch.cuda.is_available.return_value = False

        result = check_cuda_available()

        assert result["available"] is False


def test_check_cuda_no_torch() -> None:
    """Test GPU detection when torch is not installed."""

    with patch.dict("sys.modules", {"torch": None}):
        # Force reimport to pick up missing torch
        import importlib

        import krag.cli.gpu

        importlib.reload(krag.cli.gpu)

        result = krag.cli.gpu.check_cuda_available()
        assert result["available"] is False
        assert "not installed" in result.get("error", "")
