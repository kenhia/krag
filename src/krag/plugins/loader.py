"""Plugin loader for importing and instantiating plugins.

This module provides the PluginLoader class that handles plugin import,
instantiation, and API version compatibility checking.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from krag.plugins.exceptions import (
    PluginAPIVersionError,
    PluginDependencyError,
    PluginLoadError,
)
from krag.plugins.interfaces import FileTypeHandler

if TYPE_CHECKING:
    from krag.plugins.context import PluginContext

logger = logging.getLogger(__name__)


def _parse_semver(version: str) -> tuple[int, int, int]:
    """Parse semantic version string.

    Args:
        version: Version string (e.g., '1.2.3' or '2.0.0-beta')

    Returns:
        tuple[int, int, int]: Major, minor, patch version numbers

    Raises:
        ValueError: If version string is invalid
    """
    # Strip pre-release/build metadata
    base_version = version.split("-")[0].split("+")[0]
    parts = base_version.split(".")

    if len(parts) != 3:
        raise ValueError(f"Invalid semver format: {version}")

    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as e:
        raise ValueError(f"Invalid semver format: {version}") from e


class PluginLoader:
    """Handles plugin import, instantiation, and version checking.

    Provides utilities for loading plugins from entry points, checking API
    version compatibility using semver major-version matching, and instantiating
    plugin handler classes.

    Example:
        >>> loader = PluginLoader(api_version="1.0.0")
        >>> handler_class = loader.load_plugin_class("pdf")
        >>> handler = loader.instantiate_plugin(handler_class)
    """

    def __init__(self, api_version: str):
        """Initialize plugin loader.

        Args:
            api_version: Current krag plugin API version
        """
        self._api_version = api_version
        self._api_major, _, _ = _parse_semver(api_version)
        logger.debug(f"PluginLoader initialized with API version {api_version}")

    def check_api_compatibility(self, required_version: str, plugin_name: str) -> None:
        """Check if plugin's required API version is compatible.

        Uses semver major-version matching: plugins are compatible with the same
        major version (e.g., plugin requiring 1.2.0 works with API 1.5.0, but not 2.0.0).

        Args:
            required_version: Plugin's required API version
            plugin_name: Plugin name (for error messages)

        Raises:
            PluginAPIVersionError: If versions are incompatible
        """
        try:
            required_major, _, _ = _parse_semver(required_version)
        except ValueError as e:
            raise PluginAPIVersionError(
                f"Plugin '{plugin_name}' has invalid required_api_version: {required_version}",
                plugin_name=plugin_name,
            ) from e

        if required_major != self._api_major:
            raise PluginAPIVersionError(
                f"Plugin '{plugin_name}' requires API v{required_version} "
                f"(major version {required_major}), but krag has v{self._api_version} "
                f"(major version {self._api_major}). Plugin is incompatible.",
                plugin_name=plugin_name,
            )

        logger.debug(
            f"Plugin '{plugin_name}' API version {required_version} is compatible "
            f"with {self._api_version}"
        )

    def load_plugin_class(self, plugin_name: str) -> type[FileTypeHandler]:
        """Load plugin handler class from entry point.

        Args:
            plugin_name: Name of plugin to load

        Returns:
            Type[FileTypeHandler]: Plugin handler class (not instantiated)

        Raises:
            PluginLoadError: If plugin cannot be imported
            PluginDependencyError: If plugin dependencies are missing
        """
        try:
            # Find entry point for this plugin
            eps = entry_points()
            plugin_group = (
                eps.select(group="krag.plugins")
                if hasattr(eps, "select")
                else eps.get("krag.plugins", [])
            )  # type: ignore

            entry_point = None
            for ep in plugin_group:
                if ep.name == plugin_name:
                    entry_point = ep
                    break

            if entry_point is None:
                raise PluginLoadError(
                    f"No entry point found for plugin '{plugin_name}'",
                    plugin_name=plugin_name,
                )

            # Load the entry point (this imports the module)
            logger.debug(f"Loading plugin '{plugin_name}' from {entry_point.value}")
            handler_class = entry_point.load()

            # Verify it's a FileTypeHandler subclass
            if not issubclass(handler_class, FileTypeHandler):
                raise PluginLoadError(
                    f"Plugin '{plugin_name}' entry point does not point to a FileTypeHandler subclass",
                    plugin_name=plugin_name,
                )

            logger.info(f"Successfully loaded plugin class: {plugin_name}")
            return handler_class

        except ImportError as e:
            # Check if it's a missing dependency
            if "No module named" in str(e):
                raise PluginDependencyError(
                    f"Plugin '{plugin_name}' has missing dependencies: {e}",
                    plugin_name=plugin_name,
                    original_exception=e,
                ) from e
            raise PluginLoadError(
                f"Failed to import plugin '{plugin_name}': {e}",
                plugin_name=plugin_name,
                original_exception=e,
            ) from e

        except Exception as e:
            raise PluginLoadError(
                f"Unexpected error loading plugin '{plugin_name}': {e}",
                plugin_name=plugin_name,
                original_exception=e,
            ) from e

    def instantiate_plugin(self, handler_class: type[FileTypeHandler]) -> FileTypeHandler:
        """Instantiate plugin handler.

        Args:
            handler_class: Plugin handler class to instantiate

        Returns:
            FileTypeHandler: Plugin handler instance

        Raises:
            PluginLoadError: If instantiation fails
        """
        try:
            handler = handler_class()
            logger.debug(f"Instantiated plugin: {handler.name}")
            return handler

        except Exception as e:
            plugin_name = getattr(handler_class, "__name__", "unknown")
            raise PluginLoadError(
                f"Failed to instantiate plugin '{plugin_name}': {e}",
                plugin_name=plugin_name,
                original_exception=e,
            ) from e

    def initialize_plugin(
        self,
        handler: FileTypeHandler,
        config: dict[str, Any],
        context: PluginContext | None = None,
    ) -> None:
        """Initialize plugin with configuration and context.

        Args:
            handler: Plugin handler instance
            config: Plugin-specific configuration
            context: Plugin context providing access to krag services (optional)

        Raises:
            PluginLoadError: If initialization fails

        Note:
            The context parameter is optional to support plugins that don't need
            access to krag services. Plugins can ignore the context parameter.
        """
        try:
            # Call initialize with context if plugin supports it
            import inspect

            sig = inspect.signature(handler.initialize)
            if "context" in sig.parameters:
                handler.initialize(config, context=context)
            else:
                handler.initialize(config)

            logger.info(f"Initialized plugin: {handler.name} v{handler.version}")

        except Exception as e:
            raise PluginLoadError(
                f"Failed to initialize plugin '{handler.name}': {e}",
                plugin_name=handler.name,
                original_exception=e,
            ) from e

    def cleanup_plugin(self, handler: FileTypeHandler) -> None:
        """Clean up plugin resources.

        Args:
            handler: Plugin handler instance to clean up

        Note:
            Exceptions during cleanup are logged but not raised to ensure
            graceful shutdown even if plugins misbehave.
        """
        try:
            handler.cleanup()
            logger.info(f"Cleaned up plugin: {handler.name}")

        except Exception as e:
            logger.warning(f"Error during cleanup of plugin '{handler.name}': {e}")
