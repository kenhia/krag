"""XDG Base Directory utilities."""

import os
from pathlib import Path


def get_xdg_config_home() -> Path:
    """Get XDG config directory.

    Returns:
        Path to config directory (~/.config or $XDG_CONFIG_HOME)
    """
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def get_xdg_cache_home() -> Path:
    """Get XDG cache directory.

    Returns:
        Path to cache directory (~/.cache or $XDG_CACHE_HOME)
    """
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def get_xdg_state_home() -> Path:
    """Get XDG state directory.

    Returns:
        Path to state directory (~/.local/state or $XDG_STATE_HOME)
    """
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))


def get_xdg_runtime_dir() -> Path:
    """Get XDG runtime directory for ephemeral files (PID, sockets).

    Falls back to /tmp per XDG Base Directory Specification when
    XDG_RUNTIME_DIR is not set.

    Returns:
        Path to runtime directory ($XDG_RUNTIME_DIR or /tmp)
    """
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))


def get_krag_runtime_dir() -> Path:
    """Get krag runtime directory for PID files and Unix sockets.

    Returns:
        Path to krag runtime directory ($XDG_RUNTIME_DIR/krag or /tmp/krag)
    """
    return get_xdg_runtime_dir() / "krag"


def get_krag_config_dir(legacy: bool = False) -> Path:
    """Get krag configuration directory.

    Args:
        legacy: If True, use legacy ~/.krag path

    Returns:
        Path to krag config directory
    """
    if legacy:
        return Path.home() / ".krag"
    return get_xdg_config_home() / "krag"


def get_krag_cache_dir(legacy: bool = False) -> Path:
    """Get krag cache directory.

    Args:
        legacy: If True, use legacy ~/.krag path

    Returns:
        Path to krag cache directory
    """
    if legacy:
        return Path.home() / ".krag"
    return get_xdg_cache_home() / "krag"


def get_krag_state_dir(legacy: bool = False) -> Path:
    """Get krag state directory.

    Args:
        legacy: If True, use legacy ~/.krag path

    Returns:
        Path to krag state directory
    """
    if legacy:
        return Path.home() / ".krag"
    return get_xdg_state_home() / "krag"


def should_migrate_from_legacy() -> bool:
    """Check if legacy ~/.krag directory exists and should be migrated.

    Returns:
        True if legacy directory exists and XDG directories don't
    """
    legacy_path = Path.home() / ".krag"
    xdg_config = get_krag_config_dir()

    # Only migrate if legacy exists and XDG config doesn't
    return legacy_path.exists() and not xdg_config.exists()


def migrate_from_legacy() -> dict[str, Path]:
    """Migrate from legacy ~/.krag to XDG directories.

    Moves files from ~/.krag to appropriate XDG locations:
    - config.{toml,yaml} → XDG_CONFIG_HOME/krag/
    - storage/ (vector store) → XDG_CACHE_HOME/krag/storage/
    - models/ → XDG_CACHE_HOME/krag/models/
    - logs/ → XDG_STATE_HOME/krag/logs/
    - metadata.json → XDG_STATE_HOME/krag/metadata.json

    Returns:
        Dictionary mapping old paths to new paths for moved items
    """
    import shutil

    legacy_path = Path.home() / ".krag"
    if not legacy_path.exists():
        return {}

    xdg_config = get_krag_config_dir()
    xdg_cache = get_krag_cache_dir()
    xdg_state = get_krag_state_dir()

    # Ensure XDG directories exist
    xdg_config.mkdir(parents=True, exist_ok=True)
    xdg_cache.mkdir(parents=True, exist_ok=True)
    xdg_state.mkdir(parents=True, exist_ok=True)

    migrations: dict[str, Path] = {}

    # Migrate config files
    for config_file in ["config.toml", "config.yaml"]:
        old_config = legacy_path / config_file
        if old_config.exists():
            new_config = xdg_config / config_file
            shutil.move(str(old_config), str(new_config))
            migrations[str(old_config)] = new_config

    # Migrate vector store
    old_storage = legacy_path / "storage"
    if old_storage.exists():
        new_storage = xdg_cache / "storage"
        shutil.move(str(old_storage), str(new_storage))
        migrations[str(old_storage)] = new_storage

    # Migrate models
    old_models = legacy_path / "models"
    if old_models.exists():
        new_models = xdg_cache / "models"
        shutil.move(str(old_models), str(new_models))
        migrations[str(old_models)] = new_models

    # Migrate logs
    old_logs = legacy_path / "logs"
    if old_logs.exists():
        new_logs = xdg_state / "logs"
        shutil.move(str(old_logs), str(new_logs))
        migrations[str(old_logs)] = new_logs

    # Migrate metadata
    old_metadata = legacy_path / "metadata.json"
    if old_metadata.exists():
        new_metadata = xdg_state / "metadata.json"
        shutil.move(str(old_metadata), str(new_metadata))
        migrations[str(old_metadata)] = new_metadata

    # Remove legacy directory if empty
    try:
        legacy_path.rmdir()
    except OSError:
        # Directory not empty, leave it
        pass

    return migrations
