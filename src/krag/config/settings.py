"""Configuration management."""

from pathlib import Path

import toml

from krag.models.configuration import Configuration


class ConfigManager:
    """Manages loading, creating, and validating configuration."""

    @staticmethod
    def load(config_path: Path) -> Configuration:
        """Load configuration from file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        config_dict = toml.load(config_path)
        return Configuration(**config_dict)

    @staticmethod
    def create_default(config_path: Path) -> Configuration:
        """Create default configuration file.

        Args:
            config_path: Path where config file should be created

        Returns:
            Configuration object with defaults

        Raises:
            FileExistsError: If config file already exists
        """
        if config_path.exists():
            raise FileExistsError(f"Configuration file already exists: {config_path}")

        # Create parent directory if needed
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create default config with minimal required settings
        default_config = Configuration(
            directory_paths=[Path.home() / "Documents"],  # User must customize
        )

        # Write to file
        with open(config_path, "w") as f:
            toml.dump(default_config.model_dump(mode="json"), f)

        return default_config

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
