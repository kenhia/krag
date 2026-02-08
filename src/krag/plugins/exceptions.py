"""Exception classes for the plugin system.

This module defines the exception hierarchy for plugin-related errors,
inheriting from krag's base KragError exception.
"""

from pathlib import Path

from krag.models.exceptions import KragError


class PluginError(KragError):
    """Base exception for all plugin-related errors.

    All plugin exceptions inherit from this class, which in turn inherits
    from KragError for consistent error handling across krag.
    """

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        file_path: Path | None = None,
        original_exception: Exception | None = None,
    ):
        """Initialize plugin error.

        Args:
            message: Error message
            plugin_name: Name of plugin that raised error
            file_path: File being processed (if applicable)
            original_exception: Underlying exception that caused this error
        """
        super().__init__(message)
        self.plugin_name = plugin_name
        self.file_path = file_path
        self.original_exception = original_exception


class PluginNotFoundError(PluginError):
    """Requested plugin is not installed or not discoverable.

    Raised when attempting to load a plugin that doesn't exist in the
    entry points or is not properly registered.
    """


class PluginLoadError(PluginError):
    """Failed to import or instantiate plugin.

    Raised when a plugin cannot be loaded due to import errors,
    missing dependencies, or instantiation failures.
    """


class PluginConfigurationError(PluginError):
    """Invalid plugin configuration.

    Raised when plugin configuration is invalid, missing required settings,
    or fails validation against the plugin's config_schema().
    """


class PluginExtractionError(PluginError):
    """Plugin failed to extract content from file.

    Raised when a plugin encounters an error while processing a file
    (e.g., corrupted file, unsupported format variant).
    """


class PluginAPIVersionError(PluginError):
    """Plugin requires unsupported API version.

    Raised when a plugin's required_api_version is not compatible with
    the current krag plugin API version using semver major-version rules.
    """


class PluginDependencyError(PluginError):
    """Plugin missing required dependencies.

    Raised when a plugin cannot be loaded because required third-party
    packages are not installed.
    """


class PluginDisabledError(PluginError):
    """Plugin was disabled during runtime due to failure.

    Raised when attempting to use a plugin that has been automatically
    disabled due to repeated failures or critical errors (see FR-008).
    """
