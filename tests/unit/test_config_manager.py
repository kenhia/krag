"""Unit tests for ConfigManager."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import tomli_w

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
        model_cache_path=storage_parent / "models",
        corpus_cache_path=storage_parent / "corpus",
        logs_path=storage_parent / "logs",
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


# --- T016: ConfigManager resolves custom paths from config.toml ---


def test_load_custom_storage_paths_from_toml(tmp_path: Path) -> None:
    """Test ConfigManager resolves custom paths from [storage] section."""
    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
        "storage": {
            "model_cache_path": "/krag/models",
            "corpus_cache_path": "/krag/corpus",
            "logs_path": "/krag/logs",
        },
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)

    assert config.model_cache_path == Path("/krag/models")
    assert config.corpus_cache_path == Path("/krag/corpus")
    assert config.logs_path == Path("/krag/logs")


def test_load_vector_store_from_storage_section(tmp_path: Path) -> None:
    """Test ConfigManager resolves vector_store_path from [storage] section."""
    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
        "storage": {
            "vector_store_path": "/krag/index",
        },
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)

    assert config.vector_store_path == Path("/krag/index")


def test_load_n_gpu_layers_from_toml(tmp_path: Path) -> None:
    """Test ConfigManager reads n_gpu_layers from [llm] section."""
    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
        "llm": {"n_gpu_layers": -1},
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)

    assert config.llm_n_gpu_layers == -1


# --- T017: ConfigManager uses XDG defaults when paths not in config ---


def test_load_xdg_defaults_when_no_storage_section(tmp_path: Path) -> None:
    """Test ConfigManager uses XDG defaults when [storage] section is absent."""
    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)

    # Defaults should use XDG paths
    assert config.model_cache_path.is_absolute()
    assert str(config.model_cache_path).endswith("/krag/models")
    assert config.corpus_cache_path.is_absolute()
    assert str(config.corpus_cache_path).endswith("/krag/corpus")
    assert config.logs_path.is_absolute()
    assert str(config.logs_path).endswith("/krag/logs")


# --- T018: ConfigManager validates path writability at startup ---


def test_validate_storage_path_writability(tmp_path: Path) -> None:
    """Test validation checks storage path writability."""
    test_dir = tmp_path / "test_docs"
    test_dir.mkdir()

    config = Configuration(
        directory_paths=[test_dir],
        vector_store_path=tmp_path / "storage",
        model_cache_path=tmp_path / "models",
        corpus_cache_path=tmp_path / "corpus",
        logs_path=tmp_path / "logs",
        llm_model="",
    )

    is_valid, error = ConfigManager.validate(config)

    # tmp_path parent is writable, so should pass
    assert is_valid
    assert error is None


def test_validate_unwritable_storage_path(tmp_path: Path) -> None:
    """Test validation fails when storage path parent is not writable."""
    test_dir = tmp_path / "test_docs"
    test_dir.mkdir()

    config = Configuration(
        directory_paths=[test_dir],
        vector_store_path=tmp_path / "storage",
        # Use a path that can't exist
        model_cache_path=Path("/nonexistent_root_dir/models"),
        corpus_cache_path=tmp_path / "corpus",
        logs_path=tmp_path / "logs",
        llm_model="",
    )

    is_valid, error = ConfigManager.validate(config)

    assert not is_valid
    assert "model_cache_path" in error or "not writable" in error or "does not exist" in error


# --- T019: ConfigManager creates missing directories ---


def test_validate_creates_missing_directories(tmp_path: Path) -> None:
    """Test validation creates missing storage directories."""
    test_dir = tmp_path / "test_docs"
    test_dir.mkdir()

    models_path = tmp_path / "new_models"
    corpus_path = tmp_path / "new_corpus"
    logs_path = tmp_path / "new_logs"

    config = Configuration(
        directory_paths=[test_dir],
        vector_store_path=tmp_path / "storage",
        model_cache_path=models_path,
        corpus_cache_path=corpus_path,
        logs_path=logs_path,
        llm_model="",
    )

    is_valid, error = ConfigManager.validate(config)

    assert is_valid
    assert error is None
    # Directories should have been created
    assert models_path.exists()
    assert corpus_path.exists()
    assert logs_path.exists()


# --- T020: Config.toml explicit paths take precedence over XDG env vars ---


def test_explicit_paths_override_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that explicit paths in config.toml override XDG defaults."""
    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    # Set XDG env vars
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg_cache"))

    # Set explicit paths in TOML
    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
        "storage": {
            "model_cache_path": "/krag/custom_models",
            "corpus_cache_path": "/krag/custom_corpus",
            "logs_path": "/krag/custom_logs",
        },
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)

    # Explicit paths should override XDG
    assert config.model_cache_path == Path("/krag/custom_models")
    assert config.corpus_cache_path == Path("/krag/custom_corpus")
    assert config.logs_path == Path("/krag/custom_logs")


def test_plugin_settings_nested_toml_sections(tmp_path: Path) -> None:
    """Regression: [plugins.obsidian.vaults] must be parsed into plugin_settings.

    tomllib nests [plugins.obsidian.vaults] under toml_data["plugins"]["obsidian"]
    NOT as a flat "plugins.obsidian" top-level key.  The old code iterated
    toml_data.items() and missed all per-plugin configs, leaving every plugin
    initialized with an empty config dict.
    """
    config_path = tmp_path / "config.toml"
    corpus_dir = tmp_path / "docs"
    corpus_dir.mkdir()

    toml_data = {
        "directories": {"paths": [str(corpus_dir)]},
        "plugins": {
            "enabled": ["markdown", "obsidian", "code"],
            "disabled": [],
            "code": {"code_chunk_size": 1024},
            "obsidian": {
                "vaults": {"gratch": "/home/user/obsidian/gratch", "work": "/data/vaults/work"}
            },
        },
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = ConfigManager.load(config_path)
    ps = config.plugins.plugin_settings

    # Both per-plugin sections must be present
    assert "code" in ps, "code plugin settings not found in plugin_settings"
    assert "obsidian" in ps, "obsidian plugin settings not found in plugin_settings"

    # Content must match what was written
    assert ps["code"]["code_chunk_size"] == 1024
    assert ps["obsidian"]["vaults"]["gratch"] == "/home/user/obsidian/gratch"
    assert ps["obsidian"]["vaults"]["work"] == "/data/vaults/work"

    # enabled/disabled must NOT appear as plugin settings
    assert "enabled" not in ps
    assert "disabled" not in ps
