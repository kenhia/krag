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
    assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.embedding_batch_size == 32
    assert config.chunk_size == 512
    assert config.chunk_overlap == 50
    assert config.top_k == 5
    assert config.llm_temperature == 0.7


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
