"""Unit tests for ConfigManager."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from krag.config import ConfigManager
from krag.models.configuration import Configuration


def test_create_default_config() -> None:
    """Test creating default configuration file."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"

        config = ConfigManager.create_default(config_path)

        assert config_path.exists()
        assert isinstance(config, Configuration)
        assert len(config.directory_paths) > 0


def test_create_default_fails_if_exists() -> None:
    """Test that creating default config fails if file exists."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.touch()

        with pytest.raises(FileExistsError):
            ConfigManager.create_default(config_path)


def test_load_config() -> None:
    """Test loading configuration from file."""
    with TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"

        # Create default config
        ConfigManager.create_default(config_path)

        # Load it back
        loaded_config = ConfigManager.load(config_path)

        assert isinstance(loaded_config, Configuration)


def test_load_missing_config() -> None:
    """Test loading non-existent configuration file."""
    with pytest.raises(FileNotFoundError):
        ConfigManager.load(Path("/nonexistent/config.toml"))


def test_validate_config_success(tmp_path: Path) -> None:
    """Test validating a valid configuration."""
    # Create test directory
    test_dir = tmp_path / "test_docs"
    test_dir.mkdir()

    # Create storage parent directory
    storage_parent = tmp_path / ".krag"
    storage_parent.mkdir()

    config = Configuration(
        directory_paths=[test_dir],
        vector_store_path=storage_parent / "storage",
        llm_model="",  # Skip LLM validation for this test
    )

    is_valid, error = ConfigManager.validate(config)

    assert is_valid
    assert error is None


def test_validate_config_missing_directory() -> None:
    """Test validation fails for missing directory."""
    config = Configuration(
        directory_paths=[Path("/nonexistent/directory").absolute()],
    )

    is_valid, error = ConfigManager.validate(config)

    assert not is_valid
    assert "does not exist" in error


def test_validate_config_invalid_metric() -> None:
    """Test validation fails for invalid distance metric."""
    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create storage parent directory
        storage_parent = tmpdir_path / ".krag"
        storage_parent.mkdir()

        config = Configuration(
            directory_paths=[tmpdir_path],
            vector_store_path=storage_parent / "storage",
            distance_metric="invalid_metric",
            llm_model="",  # Skip LLM check
        )

        is_valid, error = ConfigManager.validate(config)

        assert not is_valid
        assert "Invalid distance metric" in error
