"""Tests for configuration validation."""

from pathlib import Path

import pytest

from krag.models.configuration import Configuration


class TestConfigurationValidation:
    """Test configuration validation rules."""

    def test_directory_paths_not_empty(self) -> None:
        """Test that directory_paths cannot be empty."""
        with pytest.raises(ValueError, match="directory_paths must not be empty"):
            Configuration(directory_paths=[])

    def test_all_paths_must_be_absolute(self) -> None:
        """Test that all directory paths must be absolute."""
        with pytest.raises(ValueError, match="All paths must be absolute"):
            Configuration(directory_paths=[Path("relative/path")])

    def test_chunk_overlap_must_be_less_than_chunk_size(self) -> None:
        """Test that chunk_overlap < chunk_size."""
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            Configuration(
                directory_paths=[Path("/tmp")],
                chunk_size=100,
                chunk_overlap=100,  # Equal to chunk_size, should fail
            )

    def test_chunk_overlap_cannot_exceed_chunk_size(self) -> None:
        """Test that chunk_overlap cannot exceed chunk_size."""
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            Configuration(
                directory_paths=[Path("/tmp")],
                chunk_size=100,
                chunk_overlap=150,  # Greater than chunk_size
            )

    def test_valid_configuration_passes(self) -> None:
        """Test that valid configuration passes validation."""
        config = Configuration(
            directory_paths=[Path("/tmp")],
            chunk_size=512,
            chunk_overlap=50,
        )
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50

    def test_temperature_range_validation(self) -> None:
        """Test that temperature must be in valid range."""
        # Test lower bound
        with pytest.raises(ValueError):
            Configuration(
                directory_paths=[Path("/tmp")],
                llm_temperature=-0.1,  # Below 0.0
            )

        # Test upper bound
        with pytest.raises(ValueError):
            Configuration(
                directory_paths=[Path("/tmp")],
                llm_temperature=2.1,  # Above 2.0
            )

        # Valid temperature
        config = Configuration(
            directory_paths=[Path("/tmp")],
            llm_temperature=0.7,
        )
        assert config.llm_temperature == 0.7

    def test_positive_values_validation(self) -> None:
        """Test that numeric values must be positive."""
        # Test chunk_size must be > 0
        with pytest.raises(ValueError):
            Configuration(
                directory_paths=[Path("/tmp")],
                chunk_size=0,
            )

        # Test chunk_overlap must be >= 0
        with pytest.raises(ValueError):
            Configuration(
                directory_paths=[Path("/tmp")],
                chunk_overlap=-1,
            )

        # Test embedding_batch_size must be > 0
        with pytest.raises(ValueError):
            Configuration(
                directory_paths=[Path("/tmp")],
                embedding_batch_size=0,
            )

        # Test max_file_size_mb must be > 0
        with pytest.raises(ValueError):
            Configuration(
                directory_paths=[Path("/tmp")],
                max_file_size_mb=0,
            )

        # Test top_k must be > 0
        with pytest.raises(ValueError):
            Configuration(
                directory_paths=[Path("/tmp")],
                top_k=0,
            )

    def test_distance_metric_options(self) -> None:
        """Test that distance_metric accepts valid options."""
        # Valid metrics
        for metric in ["cosine", "dot", "euclidean"]:
            config = Configuration(
                directory_paths=[Path("/tmp")],
                distance_metric=metric,
            )
            assert config.distance_metric == metric

    def test_custom_exclusion_patterns(self) -> None:
        """Test custom exclusion patterns."""
        custom_patterns = ["*.pyc", "__pycache__/**", "*.tmp"]
        config = Configuration(
            directory_paths=[Path("/tmp")],
            exclusion_patterns=custom_patterns,
        )
        assert config.exclusion_patterns == custom_patterns

    def test_custom_supported_file_types(self) -> None:
        """Test custom supported file types."""
        custom_types = [".txt", ".md", ".py"]
        config = Configuration(
            directory_paths=[Path("/tmp")],
            supported_file_types=custom_types,
        )
        assert config.supported_file_types == custom_types
