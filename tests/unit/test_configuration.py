"""Unit tests for Configuration model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from krag.models.configuration import Configuration


def test_configuration_default_values() -> None:
    """Test configuration with default values."""
    config = Configuration(directory_paths=[Path("/test/path").absolute()])

    assert config.max_file_size_mb == 10
    assert config.skip_binary_files is True
    assert config.embedding_model == "BAAI/bge-base-en-v1.5"
    assert config.embedding_batch_size == 64
    assert config.chunk_size == 384
    assert config.chunk_overlap == 64
    assert config.top_k == 5
    assert config.llm_temperature == 0.2
    assert config.similarity_threshold == 0.2
    assert config.llm_top_p == 0.9
    assert config.llm_repeat_penalty == 1.1
    assert config.llm_min_p == 0.05
    assert config.prompt_preset == "balanced"
    assert config.prompt_system_override is None


def test_configuration_requires_directory_paths() -> None:
    """Test that directory_paths is required."""
    with pytest.raises(ValidationError):
        Configuration(directory_paths=[])


def test_configuration_paths_must_be_absolute() -> None:
    """Test that paths must be absolute."""
    with pytest.raises(ValidationError, match="All paths must be absolute"):
        Configuration(directory_paths=[Path("relative/path")])


def test_configuration_chunk_size_must_gt_overlap() -> None:
    """Test that chunk_overlap must be less than chunk_size."""
    with pytest.raises(ValidationError, match="chunk_overlap must be less than chunk_size"):
        Configuration(
            directory_paths=[Path("/test/path").absolute()],
            chunk_size=100,
            chunk_overlap=150,
        )


def test_configuration_temperature_range() -> None:
    """Test that temperature must be in valid range."""
    with pytest.raises(ValidationError):
        Configuration(
            directory_paths=[Path("/test/path").absolute()],
            llm_temperature=3.0,  # Invalid
        )


def test_configuration_custom_exclusions() -> None:
    """Test custom exclusion patterns."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        exclusion_patterns=["**/*.log", "**/temp/**"],
    )

    assert "**/*.log" in config.exclusion_patterns
    assert "**/temp/**" in config.exclusion_patterns


# --- T012: Test new storage path fields with defaults ---


def test_configuration_model_cache_path_default() -> None:
    """Test model_cache_path has XDG-based default."""
    config = Configuration(directory_paths=[Path("/test/path").absolute()])
    assert config.model_cache_path.is_absolute()
    assert str(config.model_cache_path).endswith("/krag/models")


def test_configuration_corpus_cache_path_default() -> None:
    """Test corpus_cache_path has XDG-based default."""
    config = Configuration(directory_paths=[Path("/test/path").absolute()])
    assert config.corpus_cache_path.is_absolute()
    assert str(config.corpus_cache_path).endswith("/krag/corpus")


def test_configuration_logs_path_default() -> None:
    """Test logs_path has XDG-based default."""
    config = Configuration(directory_paths=[Path("/test/path").absolute()])
    assert config.logs_path.is_absolute()
    assert str(config.logs_path).endswith("/krag/logs")


def test_configuration_custom_storage_paths() -> None:
    """Test setting custom storage paths."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        model_cache_path=Path("/krag/models"),
        corpus_cache_path=Path("/krag/corpus"),
        logs_path=Path("/krag/logs"),
    )
    assert config.model_cache_path == Path("/krag/models")
    assert config.corpus_cache_path == Path("/krag/corpus")
    assert config.logs_path == Path("/krag/logs")


# --- T013: Test llm_n_gpu_layers field validation ---


def test_configuration_llm_n_gpu_layers_default() -> None:
    """Test llm_n_gpu_layers defaults to 0 (CPU only)."""
    config = Configuration(directory_paths=[Path("/test/path").absolute()])
    assert config.llm_n_gpu_layers == 0


def test_configuration_llm_n_gpu_layers_full_offload() -> None:
    """Test llm_n_gpu_layers accepts -1 (full offload)."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        llm_n_gpu_layers=-1,
    )
    assert config.llm_n_gpu_layers == -1


def test_configuration_llm_n_gpu_layers_partial() -> None:
    """Test llm_n_gpu_layers accepts positive values for partial offload."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        llm_n_gpu_layers=24,
    )
    assert config.llm_n_gpu_layers == 24


def test_configuration_llm_n_gpu_layers_rejects_below_minus_one() -> None:
    """Test llm_n_gpu_layers rejects values < -1."""
    with pytest.raises(ValidationError):
        Configuration(
            directory_paths=[Path("/test/path").absolute()],
            llm_n_gpu_layers=-2,
        )


# --- T014: Test tilde expansion validator ---


def test_configuration_tilde_expansion_model_cache() -> None:
    """Test ~ is expanded in model_cache_path."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        model_cache_path=Path("~/my-models"),
    )
    assert config.model_cache_path.is_absolute()
    assert "~" not in str(config.model_cache_path)


def test_configuration_tilde_expansion_corpus_cache() -> None:
    """Test ~ is expanded in corpus_cache_path."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        corpus_cache_path=Path("~/my-corpus"),
    )
    assert config.corpus_cache_path.is_absolute()
    assert "~" not in str(config.corpus_cache_path)


def test_configuration_tilde_expansion_logs() -> None:
    """Test ~ is expanded in logs_path."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        logs_path=Path("~/my-logs"),
    )
    assert config.logs_path.is_absolute()
    assert "~" not in str(config.logs_path)


def test_configuration_tilde_expansion_string_input() -> None:
    """Test ~ is expanded when path is provided as string."""
    config = Configuration(
        directory_paths=[Path("/test/path").absolute()],
        model_cache_path="~/string-models",
    )
    assert config.model_cache_path.is_absolute()
    assert "~" not in str(config.model_cache_path)


# --- T015: Test absolute path validator ---


def test_configuration_rejects_relative_model_cache_path() -> None:
    """Test that relative model_cache_path is rejected."""
    with pytest.raises(ValidationError, match="Path must be absolute"):
        Configuration(
            directory_paths=[Path("/test/path").absolute()],
            model_cache_path=Path("relative/models"),
        )


def test_configuration_rejects_relative_corpus_cache_path() -> None:
    """Test that relative corpus_cache_path is rejected."""
    with pytest.raises(ValidationError, match="Path must be absolute"):
        Configuration(
            directory_paths=[Path("/test/path").absolute()],
            corpus_cache_path=Path("relative/corpus"),
        )


def test_configuration_rejects_relative_logs_path() -> None:
    """Test that relative logs_path is rejected."""
    with pytest.raises(ValidationError, match="Path must be absolute"):
        Configuration(
            directory_paths=[Path("/test/path").absolute()],
            logs_path=Path("relative/logs"),
        )
