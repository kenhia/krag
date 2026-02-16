"""Integration tests for custom storage paths (US1).

Tests end-to-end with custom /krag-style paths to verify correct file
creation and access.
"""

from pathlib import Path

import tomli_w

from krag.config.settings import ConfigManager
from krag.models.configuration import Configuration


def test_config_roundtrip_with_storage_paths(tmp_path: Path) -> None:
    """Test create_default → load roundtrip includes storage paths."""
    config_path = tmp_path / "config.toml"

    # Create default config
    default_config = ConfigManager.create_default(config_path)

    # Load it back
    loaded_config = ConfigManager.load(config_path)

    # Storage paths should match
    assert loaded_config.model_cache_path == default_config.model_cache_path
    assert loaded_config.corpus_cache_path == default_config.corpus_cache_path
    assert loaded_config.logs_path == default_config.logs_path


def test_custom_paths_validate_and_create(tmp_path: Path) -> None:
    """Test custom storage paths are validated and directories created."""
    test_dir = tmp_path / "docs"
    test_dir.mkdir()

    storage_base = tmp_path / "krag_storage"
    models_path = storage_base / "models"
    corpus_path = storage_base / "corpus"
    logs_path = storage_base / "logs"

    config = Configuration(
        directory_paths=[test_dir],
        vector_store_path=storage_base / "storage",
        model_cache_path=models_path,
        corpus_cache_path=corpus_path,
        logs_path=logs_path,
        llm_model="",
    )

    is_valid, error = ConfigManager.validate(config)

    assert is_valid, f"Validation failed: {error}"
    assert models_path.exists(), "model_cache_path directory not created"
    assert corpus_path.exists(), "corpus_cache_path directory not created"
    assert logs_path.exists(), "logs_path directory not created"


def test_custom_paths_from_toml_file(tmp_path: Path) -> None:
    """Test loading custom storage paths from TOML config file."""
    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()

    storage_base = tmp_path / "custom_storage"

    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
        "storage": {
            "vector_store_path": str(storage_base / "index"),
            "model_cache_path": str(storage_base / "models"),
            "corpus_cache_path": str(storage_base / "corpus"),
            "logs_path": str(storage_base / "logs"),
        },
        "llm": {
            "n_gpu_layers": 0,
        },
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)

    assert config.vector_store_path == storage_base / "index"
    assert config.model_cache_path == storage_base / "models"
    assert config.corpus_cache_path == storage_base / "corpus"
    assert config.logs_path == storage_base / "logs"
    assert config.llm_n_gpu_layers == 0

    # Validate and create directories
    is_valid, error = ConfigManager.validate(config)
    assert is_valid, f"Validation failed: {error}"
    assert (storage_base / "models").exists()
    assert (storage_base / "corpus").exists()
    assert (storage_base / "logs").exists()
