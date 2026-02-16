"""Configuration management."""

# Use built-in tomllib for Python 3.11+, fallback to tomli for older versions
import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w  # For writing TOML
import yaml

from krag.models.configuration import Configuration, PluginConfiguration


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
        """Load TOML configuration file with section-based format.

        Expects TOML sections like:
        [directories]
        paths = ["/home/user"]

        [embedding]
        model = "model-name"
        """
        with open(config_path, "rb") as f:
            toml_data = tomllib.load(f)

        # Flatten section-based TOML to flat dict for Configuration model
        config_dict = {}

        # [directories] section
        if "directories" in toml_data:
            dirs_section = toml_data["directories"]
            if "paths" in dirs_section:
                config_dict["directory_paths"] = [Path(p) for p in dirs_section["paths"]]
            if "exclusion_patterns" in dirs_section:
                config_dict["exclusion_patterns"] = dirs_section["exclusion_patterns"]
            if "follow_symlinks" in dirs_section:
                config_dict["follow_symlinks"] = dirs_section["follow_symlinks"]
            if "supported_file_types" in dirs_section:
                config_dict["supported_file_types"] = dirs_section["supported_file_types"]
            if "max_file_size_mb" in dirs_section:
                config_dict["max_file_size_mb"] = dirs_section["max_file_size_mb"]
            if "skip_binary_files" in dirs_section:
                config_dict["skip_binary_files"] = dirs_section["skip_binary_files"]

        # [embedding] section
        if "embedding" in toml_data:
            emb_section = toml_data["embedding"]
            if "model" in emb_section:
                config_dict["embedding_model"] = emb_section["model"]
            if "batch_size" in emb_section:
                config_dict["embedding_batch_size"] = emb_section["batch_size"]
            if "device" in emb_section:
                config_dict["embedding_device"] = emb_section["device"]

        # [chunking] section
        if "chunking" in toml_data:
            chunk_section = toml_data["chunking"]
            if "size" in chunk_section:
                config_dict["chunk_size"] = chunk_section["size"]
            if "overlap" in chunk_section:
                config_dict["chunk_overlap"] = chunk_section["overlap"]

        # [vector_store] section
        if "vector_store" in toml_data:
            vs_section = toml_data["vector_store"]
            if "path" in vs_section:
                config_dict["vector_store_path"] = Path(vs_section["path"])
            if "collection_name" in vs_section:
                config_dict["collection_name"] = vs_section["collection_name"]
            if "distance_metric" in vs_section:
                config_dict["distance_metric"] = vs_section["distance_metric"]

        # [retrieval] section
        if "retrieval" in toml_data:
            retr_section = toml_data["retrieval"]
            if "top_k" in retr_section:
                config_dict["top_k"] = retr_section["top_k"]

        # [llm] section
        if "llm" in toml_data:
            llm_section = toml_data["llm"]
            # Support both 'model' (new) and 'model_path' (legacy) keys
            if "model" in llm_section:
                config_dict["llm_model"] = llm_section["model"]
            elif "model_path" in llm_section and llm_section["model_path"]:
                config_dict["llm_model"] = llm_section["model_path"]
            if "context_size" in llm_section:
                config_dict["llm_context_size"] = llm_section["context_size"]
            if "num_threads" in llm_section:
                config_dict["llm_num_threads"] = llm_section["num_threads"]
            if "temperature" in llm_section:
                config_dict["llm_temperature"] = llm_section["temperature"]
            if "n_gpu_layers" in llm_section:
                config_dict["llm_n_gpu_layers"] = llm_section["n_gpu_layers"]

        # [storage] section (new: configurable storage paths)
        if "storage" in toml_data:
            storage_section = toml_data["storage"]
            if "vector_store_path" in storage_section:
                config_dict["vector_store_path"] = Path(storage_section["vector_store_path"])
            if "model_cache_path" in storage_section:
                config_dict["model_cache_path"] = Path(storage_section["model_cache_path"])
            if "corpus_cache_path" in storage_section:
                config_dict["corpus_cache_path"] = Path(storage_section["corpus_cache_path"])
            if "logs_path" in storage_section:
                config_dict["logs_path"] = Path(storage_section["logs_path"])

        # [path_reductions] section
        if "path_reductions" in toml_data:
            pr_section = toml_data["path_reductions"]
            if "aliases" in pr_section:
                config_dict["path_aliases"] = pr_section["aliases"]

        # [plugins] section (T028: plugin configuration parsing)
        if "plugins" in toml_data:
            plugin_section = toml_data["plugins"]
            plugin_config_dict: dict[str, Any] = {}

            if "enabled" in plugin_section:
                plugin_config_dict["enabled_plugins"] = plugin_section["enabled"]
            if "disabled" in plugin_section:
                plugin_config_dict["disabled_plugins"] = plugin_section["disabled"]

            # Collect per-plugin settings from [plugins.<plugin_name>] sections
            plugin_settings: dict[str, dict[str, Any]] = {}
            for key, value in toml_data.items():
                if key.startswith("plugins.") and isinstance(value, dict):
                    plugin_name = key.split(".", 1)[1]
                    plugin_settings[plugin_name] = value

            if plugin_settings:
                plugin_config_dict["plugin_settings"] = plugin_settings

            # Create PluginConfiguration and validate (T029: validation happens here)
            config_dict["plugins"] = PluginConfiguration(**plugin_config_dict)

        return Configuration(**config_dict)

    @staticmethod
    def _load_yaml(config_path: Path) -> Configuration:
        """Load YAML configuration file (legacy support)."""
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)

        # Convert string paths to Path objects
        if "directory_paths" in config_dict:
            config_dict["directory_paths"] = [Path(p) for p in config_dict["directory_paths"]]
        if "vector_store_path" in config_dict:
            config_dict["vector_store_path"] = Path(config_dict["vector_store_path"])
        # Handle legacy llm_model_path field
        if "llm_model_path" in config_dict and config_dict["llm_model_path"]:
            config_dict["llm_model"] = str(config_dict["llm_model_path"])
            del config_dict["llm_model_path"]

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
        if format == "toml":
            # Create section-based TOML structure
            toml_dict = {
                "directories": {
                    "paths": [str(p) for p in default_config.directory_paths],
                    "exclusion_patterns": default_config.exclusion_patterns,
                    "follow_symlinks": default_config.follow_symlinks,
                    "supported_file_types": default_config.supported_file_types,
                    "max_file_size_mb": default_config.max_file_size_mb,
                    "skip_binary_files": default_config.skip_binary_files,
                },
                "storage": {
                    "vector_store_path": str(default_config.vector_store_path),
                    "model_cache_path": str(default_config.model_cache_path),
                    "corpus_cache_path": str(default_config.corpus_cache_path),
                    "logs_path": str(default_config.logs_path),
                },
                "embedding": {
                    "model": default_config.embedding_model,
                    "batch_size": default_config.embedding_batch_size,
                    "device": default_config.embedding_device,
                },
                "chunking": {
                    "size": default_config.chunk_size,
                    "overlap": default_config.chunk_overlap,
                },
                "vector_store": {
                    "collection_name": default_config.collection_name,
                    "distance_metric": default_config.distance_metric,
                },
                "retrieval": {
                    "top_k": default_config.top_k,
                },
                "llm": {
                    "model": default_config.llm_model,
                    "context_size": default_config.llm_context_size,
                    "num_threads": default_config.llm_num_threads,
                    "temperature": default_config.llm_temperature,
                    "n_gpu_layers": default_config.llm_n_gpu_layers,
                },
                "path_reductions": {
                    "aliases": default_config.path_aliases,
                },
                "plugins": {
                    "enabled": default_config.plugins.enabled_plugins,
                    "disabled": default_config.plugins.disabled_plugins,
                },
            }
            with open(config_path, "wb") as f:
                tomli_w.dump(toml_dict, f)
        else:  # yaml
            config_dict = default_config.model_dump(mode="json")
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

        # Write as section-based TOML
        toml_dict = {
            "directories": {
                "paths": [str(p) for p in config.directory_paths],
                "exclusion_patterns": config.exclusion_patterns,
                "follow_symlinks": config.follow_symlinks,
                "supported_file_types": config.supported_file_types,
                "max_file_size_mb": config.max_file_size_mb,
                "skip_binary_files": config.skip_binary_files,
            },
            "storage": {
                "vector_store_path": str(config.vector_store_path),
                "model_cache_path": str(config.model_cache_path),
                "corpus_cache_path": str(config.corpus_cache_path),
                "logs_path": str(config.logs_path),
            },
            "embedding": {
                "model": config.embedding_model,
                "batch_size": config.embedding_batch_size,
                "device": config.embedding_device,
            },
            "chunking": {
                "size": config.chunk_size,
                "overlap": config.chunk_overlap,
            },
            "vector_store": {
                "collection_name": config.collection_name,
                "distance_metric": config.distance_metric,
            },
            "retrieval": {
                "top_k": config.top_k,
            },
            "llm": {
                "model": config.llm_model,
                "context_size": config.llm_context_size,
                "num_threads": config.llm_num_threads,
                "temperature": config.llm_temperature,
                "n_gpu_layers": config.llm_n_gpu_layers,
            },
            "path_reductions": {
                "aliases": config.path_aliases,
            },
            "plugins": {
                "enabled": config.plugins.enabled_plugins,
                "disabled": config.plugins.disabled_plugins,
            },
        }

        # Add per-plugin settings sections from migration
        for plugin_name, settings in config.plugins.plugin_settings.items():
            toml_dict[f"plugins.{plugin_name}"] = settings

        with open(toml_path, "wb") as f:
            tomli_w.dump(toml_dict, f)

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

            # Validate and create storage directories
            storage_paths = {
                "vector_store_path": config.vector_store_path,
                "model_cache_path": config.model_cache_path,
                "corpus_cache_path": config.corpus_cache_path,
                "logs_path": config.logs_path,
            }

            for name, path in storage_paths.items():
                # Find the nearest existing ancestor to check writability
                check_path = path
                while not check_path.exists():
                    check_path = check_path.parent
                    if check_path == check_path.parent:
                        # Reached filesystem root
                        return (
                            False,
                            f"Storage path {name} parent does not exist: {path.parent}",
                        )

                if not os.access(check_path, os.W_OK):
                    return (
                        False,
                        f"Storage path {name} is not writable: {check_path}",
                    )

                # Create directory if it doesn't exist
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    return (
                        False,
                        f"Cannot create storage directory {name}: {path} (permission denied)",
                    )
                except OSError as e:
                    return (
                        False,
                        f"Cannot create storage directory {name}: {path} ({e})",
                    )

            # Check LLM model exists if it's a local path (not a HuggingFace model name)
            if (
                config.llm_model
                and "/" in config.llm_model
                and not config.llm_model.startswith("http")
            ):
                # Looks like a filesystem path
                model_path = Path(config.llm_model)
                if model_path.exists() and not model_path.is_file():
                    return False, f"LLM model path is not a file: {config.llm_model}"
                # Don't fail validation if model doesn't exist yet - it might be downloaded later
            # If it contains no slash, assume it's a HuggingFace model name (will be downloaded on first use)

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

            # Validate plugin configuration
            if config.plugins:
                # Check for overlapping enabled/disabled lists
                overlap = set(config.plugins.enabled_plugins) & set(config.plugins.disabled_plugins)
                if overlap:
                    return (
                        False,
                        f"Plugin(s) listed in both enabled and disabled: {', '.join(overlap)}.\n"
                        f"  Fix: Remove from one list in [plugins] section of config.toml.\n"
                        f"  Example:\n"
                        f"    [plugins]\n"
                        f'    enabled = ["markdown", "logs"]\n'
                        f"    disabled = []",
                    )

            return True, None

        except Exception as e:
            return False, str(e)
