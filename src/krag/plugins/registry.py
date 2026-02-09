"""Plugin registry for managing plugin lifecycle.

This module provides the PluginRegistry class that handles plugin discovery,
loading, validation, and lifecycle management for the plugin system.
"""

import logging
from importlib.metadata import entry_points

from krag.models.configuration import PluginConfiguration, PluginMetadata
from krag.plugins.exceptions import PluginNotFoundError
from krag.plugins.interfaces import FileTypeHandler
from krag.plugins.loader import PluginLoader

logger = logging.getLogger(__name__)

# Current plugin API version - plugins must be compatible (major version match)
PLUGIN_API_VERSION = "1.0.0"


class PluginRegistry:
    """Central registry managing plugin discovery, loading, and lifecycle.

    Handles plugin discovery via entry points, lazy loading, configuration-driven
    extension mapping, and plugin lifecycle management.

    Example:
        >>> config = PluginConfiguration(enabled_plugins=["pdf"])
        >>> registry = PluginRegistry(config)
        >>> plugins = registry.discover_plugins()
        >>> handler = registry.get_handler_for_extension(".pdf")
    """

    def __init__(self, config: PluginConfiguration):
        """Initialize plugin registry.

        Args:
            config: Plugin configuration including enabled/disabled lists
        """
        self._config = config
        self._api_version = PLUGIN_API_VERSION
        self._discovered: dict[str, PluginMetadata] = {}
        self._loaded: dict[str, FileTypeHandler] = {}
        self._extension_map: dict[str, str] = {}
        self._loader = PluginLoader(api_version=self._api_version)

        logger.info("Plugin registry initialized with API version %s", self._api_version)

    def discover_plugins(self) -> list[PluginMetadata]:
        """Discover installed plugins via entry points.

        Scans for plugins registered under 'krag.plugins' entry point group,
        loads their metadata, and applies enable/disable filters from configuration.

        Returns:
            list[PluginMetadata]: List of discovered plugin metadata

        Example:
            >>> registry = PluginRegistry(config)
            >>> plugins = registry.discover_plugins()
            >>> print(f"Found {len(plugins)} plugins")
        """
        discovered_plugins: list[PluginMetadata] = []

        # Discover plugins from entry points
        eps = entry_points()
        plugin_group = (
            eps.select(group="krag.plugins")
            if hasattr(eps, "select")
            else eps.get("krag.plugins", [])
        )  # type: ignore

        for entry_point in plugin_group:
            try:
                # Load entry point metadata without importing the module yet
                plugin_name = entry_point.name

                # Create metadata from entry point
                # Note: We'll need to actually load the plugin to get full metadata
                # For now, create minimal metadata
                metadata = PluginMetadata(
                    name=plugin_name,
                    version="0.0.0",  # Will be updated when plugin loads
                    entry_point=f"{entry_point.value}",
                    supported_extensions=[],  # Will be populated from config
                    required_api_version="1.0.0",  # Will be updated when plugin loads
                    is_enabled=self._is_plugin_enabled(plugin_name),
                )

                self._discovered[plugin_name] = metadata
                discovered_plugins.append(metadata)

                logger.debug(f"Discovered plugin: {plugin_name} from entry point")

            except Exception as e:
                logger.warning(f"Failed to discover plugin {entry_point.name}: {e}")
                continue

        logger.info(f"Discovered {len(discovered_plugins)} plugins")
        return discovered_plugins

    def _is_plugin_enabled(self, plugin_name: str) -> bool:
        """Check if plugin is enabled in configuration.

        Args:
            plugin_name: Name of plugin to check

        Returns:
            bool: True if plugin is enabled
        """
        # If plugin is explicitly disabled, return False
        if plugin_name in self._config.disabled_plugins:
            return False

        # If enabled_plugins is empty, all non-disabled plugins are enabled
        if not self._config.enabled_plugins:
            return True

        # Otherwise, plugin must be in enabled list
        return plugin_name in self._config.enabled_plugins

    def _build_extension_map(self) -> None:
        """Build extension to plugin name mapping from configuration.

        Reads the configuration to determine which file extensions should be
        handled by which plugins. This is config-driven, not runtime scan.

        The extension map is built from:
        1. Plugin configuration file entries
        2. Discovered plugins' supported_extensions after validation
        """
        self._extension_map.clear()

        for plugin_name, metadata in self._discovered.items():
            if not metadata.is_enabled:
                continue

            for ext in metadata.supported_extensions:
                # First in config order wins for conflicts
                if ext not in self._extension_map:
                    self._extension_map[ext] = plugin_name
                    logger.debug(f"Mapped extension {ext} to plugin {plugin_name}")
                else:
                    logger.warning(
                        f"Extension {ext} conflict: {plugin_name} ignored "
                        f"(already mapped to {self._extension_map[ext]})"
                    )

    def list_plugins(self, filter_status: str | None = None) -> list[PluginMetadata]:
        """List plugins with optional status filtering.

        Args:
            filter_status: Optional filter ('enabled', 'disabled', 'loaded', None for all)

        Returns:
            list[PluginMetadata]: Filtered list of plugin metadata

        Example:
            >>> enabled = registry.list_plugins(filter_status="enabled")
            >>> all_plugins = registry.list_plugins()
        """
        plugins = list(self._discovered.values())

        if filter_status == "enabled":
            plugins = [p for p in plugins if p.is_enabled]
        elif filter_status == "disabled":
            plugins = [p for p in plugins if not p.is_enabled]
        elif filter_status == "loaded":
            plugins = [p for p in plugins if p.is_loaded]

        return plugins

    def get_plugin_info(self, name: str) -> PluginMetadata:
        """Get metadata for a specific plugin.

        Args:
            name: Plugin name

        Returns:
            PluginMetadata: Plugin metadata

        Raises:
            PluginNotFoundError: If plugin is not discovered
        """
        if name not in self._discovered:
            raise PluginNotFoundError(
                f"Plugin '{name}' not found. Available plugins: {list(self._discovered.keys())}",
                plugin_name=name,
            )

        return self._discovered[name]

    def get_handler_for_extension(self, ext: str) -> FileTypeHandler | None:
        """Get handler for a file extension (lazy load).

        Args:
            ext: File extension (e.g., '.pdf')

        Returns:
            FileTypeHandler | None: Handler instance or None if no handler available

        Note:
            This method will be fully implemented in later tasks (T021-T025)
            when plugin loading is complete.
        """
        # TODO: Implement lazy loading in T021-T025
        plugin_name = self._extension_map.get(ext)
        if plugin_name is None:
            return None

        # Check if already loaded
        if plugin_name in self._loaded:
            return self._loaded[plugin_name]

        # Lazy loading will be implemented later
        logger.debug(f"Handler for {ext} -> {plugin_name} not yet loaded")
        return None

    def validate_plugins(self) -> list[str]:
        """Validate discovered plugins for API compatibility and dependencies.

        Attempts to import each discovered plugin, check API version compatibility,
        and validate plugin configuration schema. Updates plugin metadata with
        validation results.

        Returns:
            list[str]: List of plugin names that failed validation

        Example:
            >>> registry.discover_plugins()
            >>> failed = registry.validate_plugins()
            >>> if failed:
            ...     print(f"Failed to validate: {', '.join(failed)}")
        """
        failed_plugins: list[str] = []

        for plugin_name, metadata in self._discovered.items():
            if not metadata.is_enabled:
                logger.debug(f"Skipping validation for disabled plugin: {plugin_name}")
                continue

            try:
                # Attempt to load plugin class
                handler_class = self._loader.load_plugin_class(plugin_name)

                # Instantiate to get properties
                handler = self._loader.instantiate_plugin(handler_class)

                # Check API version compatibility
                self._loader.check_api_compatibility(handler.required_api_version, plugin_name)

                # Update metadata with actual plugin info
                metadata.version = handler.version
                metadata.required_api_version = handler.required_api_version
                metadata.supported_extensions = handler.supported_extensions()

                # Validate config_schema if plugin provides one
                config_schema = handler.config_schema()
                if config_schema is not None:
                    # Check if plugin has settings in config
                    if plugin_name in self._config.plugin_settings:
                        try:
                            # Validate settings against schema
                            config_schema(**self._config.plugin_settings[plugin_name])
                            logger.debug(f"Plugin '{plugin_name}' config validated successfully")
                        except Exception as e:
                            error_msg = f"Invalid configuration for plugin '{plugin_name}': {e}"
                            logger.error(error_msg)
                            metadata.is_enabled = False
                            metadata.load_error = error_msg
                            failed_plugins.append(plugin_name)
                            continue

                logger.info(f"Plugin '{plugin_name}' validated successfully")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to validate plugin '{plugin_name}': {error_msg}")
                metadata.load_error = error_msg
                metadata.is_enabled = False
                failed_plugins.append(plugin_name)

        return failed_plugins

    def check_extension_conflicts(self) -> dict[str, list[str]]:
        """Check for file extension conflicts between enabled plugins.

        Identifies cases where multiple enabled plugins claim the same file
        extension. First plugin in configuration order wins; conflicts are
        logged as warnings.

        Returns:
            dict[str, list[str]]: Mapping of extension to list of conflicting plugin names

        Example:
            >>> conflicts = registry.check_extension_conflicts()
            >>> for ext, plugins in conflicts.items():
            ...     print(f"{ext}: claimed by {', '.join(plugins)}")
        """
        extension_claims: dict[str, list[str]] = {}

        # Collect all extension claims
        for plugin_name, metadata in self._discovered.items():
            if not metadata.is_enabled:
                continue

            for ext in metadata.supported_extensions:
                if ext not in extension_claims:
                    extension_claims[ext] = []
                extension_claims[ext].append(plugin_name)

        # Find conflicts (extensions claimed by multiple plugins)
        conflicts = {ext: plugins for ext, plugins in extension_claims.items() if len(plugins) > 1}

        if conflicts:
            for ext, plugins in conflicts.items():
                winner = plugins[0]  # First in config order wins
                losers = plugins[1:]
                logger.warning(
                    f"Extension {ext} conflict: {winner} will handle (ignoring {', '.join(losers)})"
                )

        return conflicts
