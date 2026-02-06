"""Configuration management."""

# Use built-in tomllib for Python 3.11+, fallback to tomli for older versions
import tomllib
from pathlib import Path

import tomli_w  # For writing TOML
import yaml

from krag.models.configuration import Configuration


class ConfigManager:
    """Manages loading, creating, and validating configuration."""

    @staticmethod
    def load(config_path: Path) -> Configuration:
        """Load configuration from file with automatic format detection.

        Supports both TOML (.toml) and YAML (.yaml, .yml) formats.
        Format is detected based on file extension.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid or format is unsupported
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Detect format from extension
        suffix = config_path.suffix.lower()

        if suffix == ".toml":
            return ConfigManager._load_toml(config_path)
        elif suffix in {".yaml", ".yml"}:
            return ConfigManager._load_yaml(config_path)
        else:
            raise ValueError(
                f"Unsupported configuration format: {suffix}. Use .toml, .yaml, or .yml"
            )

    @staticmethod
    def _load_toml(config_path: Path) -> Configuration:
        """Load TOML configuration file."""
        with open(config_path, "rb") as f:
            config_dict = tomllib.load(f)
        return Configuration(**config_dict)

    @staticmethod
    def _load_yaml(config_path: Path) -> Configuration:
        """Load YAML configuration file (legacy support)."""
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)
        return Configuration(**config_dict)

    @staticmethod
    def create_default(config_path: Path, format: str = "toml") -> Configuration:
        """Create default configuration file.

        Args:
            config_path: Path where config file should be created
            format: Configuration format - "toml" (default) or "yaml"

        Returns:
            Configuration object with defaults

        Raises:
            FileExistsError: If config file already exists
            ValueError: If format is unsupported
        """
        if config_path.exists():
            raise FileExistsError(f"Configuration file already exists: {config_path}")

        # Validate format
        if format not in {"toml", "yaml"}:
            raise ValueError(f"Unsupported format: {format}. Use 'toml' or 'yaml'")

        # Create parent directory if needed
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create default config with minimal required settings
        default_config = Configuration(
            directory_paths=[Path.home() / "Documents"],  # User must customize
        )

        # Write to file in requested format
        config_dict = default_config.model_dump(mode="json")

        if format == "toml":
            with open(config_path, "wb") as f:
                tomli_w.dump(config_dict, f)
        else:  # yaml
            with open(config_path, "w") as f:
                yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)

        return default_config

    @staticmethod
    def migrate_yaml_to_toml(yaml_path: Path, toml_path: Path | None = None) -> Path:
        """Migrate YAML configuration to TOML format.

        Args:
            yaml_path: Path to existing YAML configuration
            toml_path: Path for new TOML file (defaults to same name with .toml)

        Returns:
            Path to created TOML file

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            FileExistsError: If TOML file already exists
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"YAML configuration not found: {yaml_path}")

        # Default TOML path: same location, .toml extension
        if toml_path is None:
            toml_path = yaml_path.with_suffix(".toml")

        if toml_path.exists():
            raise FileExistsError(f"TOML configuration already exists: {toml_path}")

        # Load YAML config
        config = ConfigManager._load_yaml(yaml_path)

        # Write as TOML
        config_dict = config.model_dump(mode="json")
        with open(toml_path, "wb") as f:
            tomli_w.dump(config_dict, f)

        return toml_path

    @staticmethod
    def validate(config: Configuration) -> tuple[bool, str | None]:
        """Validate configuration.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check directory paths exist
            for path in config.directory_paths:
                if not path.exists():
                    return False, f"Directory does not exist: {path}"
                if not path.is_dir():
                    return False, f"Path is not a directory: {path}"

            # Check vector store path is writable
            if not config.vector_store_path.parent.exists():
                return (
                    False,
                    f"Vector store parent directory does not exist: {config.vector_store_path.parent}",
                )

            # Check LLM model exists if path is configured
            if config.llm_model_path and not config.llm_model_path.exists():
                return False, f"LLM model file not found: {config.llm_model_path}"

            # Validate distance metric
            valid_metrics = ["cosine", "dot", "euclidean"]
            if config.distance_metric not in valid_metrics:
                return (
                    False,
                    f"Invalid distance metric: {config.distance_metric}. Must be one of {valid_metrics}",
                )

            # Validate device
            valid_devices = ["cpu", "cuda", "mps"]
            if config.embedding_device not in valid_devices:
                return (
                    False,
                    f"Invalid embedding device: {config.embedding_device}. Must be one of {valid_devices}",
                )

            return True, None

        except Exception as e:
            return False, str(e)
