"""Tests for TOML/YAML configuration format support."""

from pathlib import Path

import pytest

from krag.config.settings import ConfigManager


class TestConfigFormatDetection:
    """Test automatic format detection for config files."""

    def test_load_toml_configuration(self, tmp_path: Path) -> None:
        """Test loading TOML configuration file."""
        config_path = tmp_path / "config.toml"
        config_manager = ConfigManager()

        # Create TOML config
        config = config_manager.create_default(config_path, format="toml")
        assert config_path.exists()

        # Load it back
        loaded_config = config_manager.load(config_path)
        assert loaded_config.embedding_model == config.embedding_model
        assert loaded_config.directory_paths == config.directory_paths

    def test_load_yaml_configuration(self, tmp_path: Path) -> None:
        """Test loading YAML configuration file."""
        config_path = tmp_path / "config.yaml"
        config_manager = ConfigManager()

        # Create YAML config
        config = config_manager.create_default(config_path, format="yaml")
        assert config_path.exists()

        # Load it back
        loaded_config = config_manager.load(config_path)
        assert loaded_config.embedding_model == config.embedding_model
        assert loaded_config.directory_paths == config.directory_paths

    def test_format_detection_by_extension(self, tmp_path: Path) -> None:
        """Test that format is correctly detected from file extension."""
        toml_path = tmp_path / "test.toml"
        yaml_path = tmp_path / "test.yaml"
        config_manager = ConfigManager()

        # Create both formats
        config_manager.create_default(toml_path, format="toml")
        config_manager.create_default(yaml_path, format="yaml")

        # Both should load successfully
        toml_config = config_manager.load(toml_path)
        yaml_config = config_manager.load(yaml_path)

        # Contents should be equivalent
        assert toml_config.embedding_model == yaml_config.embedding_model

    def test_unsupported_format_raises_error(self, tmp_path: Path) -> None:
        """Test that unsupported file format raises ValueError."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")  # Create empty JSON file
        config_manager = ConfigManager()

        with pytest.raises(ValueError, match="Unsupported configuration format"):
            config_manager.load(config_path)

    def test_missing_file_raises_error(self, tmp_path: Path) -> None:
        """Test that missing file raises FileNotFoundError."""
        config_path = tmp_path / "nonexistent.toml"
        config_manager = ConfigManager()

        with pytest.raises(FileNotFoundError):
            config_manager.load(config_path)


class TestConfigCreation:
    """Test configuration file creation."""

    def test_create_toml_by_default(self, tmp_path: Path) -> None:
        """Test that TOML is created by default."""
        config_path = tmp_path / "config.toml"
        config_manager = ConfigManager()

        config_manager.create_default(config_path)
        assert config_path.exists()
        assert config_path.suffix == ".toml"

        # Verify content
        content = config_path.read_text()
        assert "directory_paths" in content
        assert "embedding_model" in content

    def test_create_yaml_with_format_param(self, tmp_path: Path) -> None:
        """Test creating YAML config with format parameter."""
        config_path = tmp_path / "config.yaml"
        config_manager = ConfigManager()

        config_manager.create_default(config_path, format="yaml")
        assert config_path.exists()

        # Verify it's valid YAML
        content = config_path.read_text()
        assert "directory_paths:" in content or "embedding_model:" in content

    def test_create_rejects_invalid_format(self, tmp_path: Path) -> None:
        """Test that invalid format parameter raises ValueError."""
        config_path = tmp_path / "config.json"
        config_manager = ConfigManager()

        with pytest.raises(ValueError, match="Unsupported format"):
            config_manager.create_default(config_path, format="json")

    def test_create_fails_if_file_exists(self, tmp_path: Path) -> None:
        """Test that creating config fails if file already exists."""
        config_path = tmp_path / "config.toml"
        config_manager = ConfigManager()

        # Create first time
        config_manager.create_default(config_path)

        # Second attempt should fail
        with pytest.raises(FileExistsError):
            config_manager.create_default(config_path)

    def test_create_creates_parent_directory(self, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        config_path = tmp_path / "nested" / "dir" / "config.toml"
        config_manager = ConfigManager()

        config_manager.create_default(config_path)
        assert config_path.exists()
        assert config_path.parent.exists()


class TestConfigMigration:
    """Test YAML to TOML migration."""

    def test_migrate_yaml_to_toml(self, tmp_path: Path) -> None:
        """Test migrating YAML configuration to TOML."""
        yaml_path = tmp_path / "config.yaml"
        toml_path = tmp_path / "config.toml"
        config_manager = ConfigManager()

        # Create YAML config
        original_config = config_manager.create_default(yaml_path, format="yaml")

        # Migrate
        result_path = config_manager.migrate_yaml_to_toml(yaml_path, toml_path)
        assert result_path == toml_path
        assert toml_path.exists()

        # Verify contents match
        migrated_config = config_manager.load(toml_path)
        assert migrated_config.embedding_model == original_config.embedding_model
        assert migrated_config.directory_paths == original_config.directory_paths
        assert migrated_config.chunk_size == original_config.chunk_size

    def test_migrate_defaults_to_same_location(self, tmp_path: Path) -> None:
        """Test that migration defaults to same location with .toml extension."""
        yaml_path = tmp_path / "config.yaml"
        config_manager = ConfigManager()

        # Create YAML config
        config_manager.create_default(yaml_path, format="yaml")

        # Migrate without specifying output
        result_path = config_manager.migrate_yaml_to_toml(yaml_path)
        expected_path = tmp_path / "config.toml"
        assert result_path == expected_path
        assert expected_path.exists()

    def test_migrate_fails_if_yaml_missing(self, tmp_path: Path) -> None:
        """Test that migration fails if YAML file doesn't exist."""
        yaml_path = tmp_path / "missing.yaml"
        config_manager = ConfigManager()

        with pytest.raises(FileNotFoundError):
            config_manager.migrate_yaml_to_toml(yaml_path)

    def test_migrate_fails_if_toml_exists(self, tmp_path: Path) -> None:
        """Test that migration fails if TOML file already exists."""
        yaml_path = tmp_path / "config.yaml"
        toml_path = tmp_path / "config.toml"
        config_manager = ConfigManager()

        # Create both files
        config_manager.create_default(yaml_path, format="yaml")
        config_manager.create_default(toml_path, format="toml")

        # Migration should fail
        with pytest.raises(FileExistsError):
            config_manager.migrate_yaml_to_toml(yaml_path, toml_path)

    def test_migrate_preserves_custom_values(self, tmp_path: Path) -> None:
        """Test that migration preserves custom configuration values."""
        yaml_path = tmp_path / "config.yaml"
        config_manager = ConfigManager()

        # Create and modify YAML config
        config = config_manager.create_default(yaml_path, format="yaml")
        config.chunk_size = 1024
        config.chunk_overlap = 256

        # Save modified config manually
        import yaml

        with open(yaml_path, "w") as f:
            yaml.safe_dump(config.model_dump(mode="json"), f)

        # Migrate
        toml_path = config_manager.migrate_yaml_to_toml(yaml_path)

        # Verify custom values preserved
        migrated_config = config_manager.load(toml_path)
        assert migrated_config.chunk_size == 1024
        assert migrated_config.chunk_overlap == 256
