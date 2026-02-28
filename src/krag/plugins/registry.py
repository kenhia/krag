"""Plugin registry for managing plugin lifecycle.

This module provides the PluginRegistry class that handles plugin discovery,
loading, validation, and lifecycle management for the plugin system.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING

from krag.models.configuration import PluginConfiguration, PluginMetadata
from krag.plugins.exceptions import PluginNotFoundError
from krag.plugins.interfaces import FileTypeHandler
from krag.plugins.loader import PluginLoader

if TYPE_CHECKING:
    from krag.plugins.context import PluginContext

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
        logger.debug(
            "Registry config: enabled=%s, disabled=%s, settings_for=%s",
            self._config.enabled_plugins or "(all)",
            self._config.disabled_plugins or "(none)",
            list(self._config.plugin_settings.keys()) or "(none)",
        )

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
                plugin_name = entry_point.name

                # Try to load plugin class to get metadata
                # This is a lightweight operation - we instantiate but don't initialize
                try:
                    handler_class = self._loader.load_plugin_class(plugin_name)
                    handler = self._loader.instantiate_plugin(handler_class)

                    # Get metadata from plugin instance
                    version = handler.version
                    required_api_version = handler.required_api_version
                    supported_extensions = handler.supported_extensions()
                    description = getattr(handler, "description", None)
                    author = getattr(handler, "author", None)
                    load_error = None

                    logger.debug(
                        f"Discovered plugin: {plugin_name} v{version} "
                        f"(extensions: {', '.join(supported_extensions)})"
                    )

                except Exception as load_err:
                    # If plugin fails to load, create placeholder metadata with error
                    version = "0.0.0"
                    required_api_version = "1.0.0"
                    supported_extensions = [".__unknown__"]
                    description = None
                    author = None
                    load_error = str(load_err)

                    logger.warning(
                        f"Plugin '{plugin_name}' discovered but failed to load: {load_err}"
                    )

                # Create metadata from entry point
                # T015: Detect if plugin overrides claims_file()
                has_claims_file = False
                if load_error is None:
                    handler_cls = type(handler)
                    if hasattr(handler_cls, "claims_file"):
                        has_claims_file = handler_cls.claims_file is not FileTypeHandler.claims_file

                metadata = PluginMetadata(
                    name=plugin_name,
                    version=version,
                    entry_point=f"{entry_point.value}",
                    supported_extensions=supported_extensions,
                    description=description,
                    author=author,
                    required_api_version=required_api_version,
                    is_enabled=self._is_plugin_enabled(plugin_name),
                    load_error=load_error,
                    has_claims_file=has_claims_file,
                )

                self._discovered[plugin_name] = metadata
                discovered_plugins.append(metadata)

            except Exception as e:
                logger.warning(f"Failed to discover plugin {entry_point.name}: {e}")
                continue

        logger.info(f"Discovered {len(discovered_plugins)} plugins")

        # Auto-build extension map so callers don't need to call _build_extension_map()
        self._build_extension_map()

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
                # Normalize to lowercase for case-insensitive matching
                ext_lower = ext.lower()
                # First in config order wins for conflicts
                if ext_lower not in self._extension_map:
                    self._extension_map[ext_lower] = plugin_name
                    logger.debug(f"Mapped extension {ext_lower} to plugin {plugin_name}")
                else:
                    if metadata.has_claims_file:
                        # Plugin uses claims_file() for path-based routing and does not
                        # depend on the extension map, so this is not a real conflict.
                        logger.debug(
                            "Extension %s: %s uses claims_file() routing "
                            "(extension map entry belongs to %s)",
                            ext_lower,
                            plugin_name,
                            self._extension_map[ext_lower],
                        )
                    else:
                        logger.warning(
                            "Extension %s conflict: %s ignored "
                            "(already mapped to %s)",
                            ext_lower,
                            plugin_name,
                            self._extension_map[ext_lower],
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

    def get_supported_extensions(self) -> list[str]:
        """Get all file extensions supported by enabled plugins.

        Returns:
            list[str]: List of file extensions (e.g., ['.pdf', '.docx'])

        Note:
            Extensions are lowercase with leading dot.
            Only extensions from enabled plugins are included.

        Example:
            >>> extensions = registry.get_supported_extensions()
            >>> print(f"Plugins support: {extensions}")
        """
        return list(self._extension_map.keys())

    def get_plugins_by_extension(self, extension: str) -> list[PluginMetadata]:
        """Get plugins that handle a specific file extension.

        Args:
            extension: File extension to look up (e.g., '.md', '.log')

        Returns:
            list[PluginMetadata]: Plugin metadata for plugins that handle this extension

        Example:
            >>> plugins = registry.get_plugins_by_extension(".md")
            >>> print(f"Markdown handled by: {[p.name for p in plugins]}")
        """
        ext_lower = extension.lower()
        results = []
        for _plugin_name, metadata in self._discovered.items():
            if not metadata.is_enabled:
                continue
            if ext_lower in [e.lower() for e in metadata.supported_extensions]:
                results.append(metadata)
        return results

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

    def load_plugin(
        self, name: str, context: PluginContext | None = None
    ) -> FileTypeHandler | None:
        """Load, instantiate, and initialize a plugin.

        All operations wrapped in try-catch. On exception, plugin is disabled and
        None is returned to enable graceful degradation.

        Args:
            name: Plugin name to load
            context: Plugin context for initialization (optional)

        Returns:
            FileTypeHandler | None: Loaded handler instance, or None if load failed

        Note:
            If plugin fails to load, it is automatically disabled and error is logged.
            Subsequent calls to load this plugin will return None immediately.

        Example:
            >>> handler = registry.load_plugin("pdf", context)
            >>> if handler:
            ...     text = handler.extract_text(Path("document.pdf"))
        """
        # Check if plugin is discovered
        if name not in self._discovered:
            logger.warning(f"Cannot load unknown plugin: {name}")
            return None

        metadata = self._discovered[name]

        # Check if already loaded
        if name in self._loaded:
            logger.debug(f"Plugin '{name}' already loaded")
            return self._loaded[name]

        # Check if plugin is enabled
        if not metadata.is_enabled:
            logger.debug(f"Plugin '{name}' is disabled, not loading")
            return None

        # Check if plugin previously failed to load
        if metadata.load_error is not None:
            logger.debug(f"Plugin '{name}' previously failed to load: {metadata.load_error}")
            return None

        try:
            # Load plugin class
            handler_class = self._loader.load_plugin_class(name)

            # Instantiate plugin
            handler = self._loader.instantiate_plugin(handler_class)

            # Check API compatibility
            self._loader.check_api_compatibility(handler.required_api_version, name)

            # Get plugin configuration
            plugin_config = self._config.plugin_settings.get(name, {})

            # Initialize plugin with config and context
            self._loader.initialize_plugin(handler, plugin_config, context)

            # Cache loaded handler
            self._loaded[name] = handler

            # Update metadata
            metadata.version = handler.version
            metadata.required_api_version = handler.required_api_version
            metadata.supported_extensions = handler.supported_extensions()
            metadata.is_loaded = True

            logger.info(f"Successfully loaded plugin: {name} v{handler.version}")
            return handler

        except Exception as e:
            # Disable plugin on load failure with structured error context
            from krag.plugins.exceptions import (
                PluginAPIVersionError,
                PluginConfigurationError,
                PluginDependencyError,
            )

            if isinstance(e, PluginDependencyError):
                error_msg = (
                    f"Plugin '{name}' has missing dependencies: {e}. "
                    f"Install with: uv pip install <package> or pip install <package>"
                )
            elif isinstance(e, PluginAPIVersionError):
                error_msg = (
                    f"Plugin '{name}' is incompatible with this version of krag: {e}. "
                    f"Check for a plugin update or downgrade krag."
                )
            elif isinstance(e, PluginConfigurationError):
                error_msg = (
                    f"Plugin '{name}' has invalid configuration: {e}. "
                    f"Check [plugins.{name}] section in config.toml."
                )
            else:
                error_msg = f"Plugin '{name}' failed to load: {e}"

            logger.error(error_msg)
            metadata.is_enabled = False
            metadata.load_error = error_msg
            return None

    def unload_plugin(self, name: str) -> None:
        """Unload plugin and clean up resources.

        Calls plugin's cleanup() hook and removes from loaded cache.
        Safe to call on plugins that are not loaded.

        Args:
            name: Plugin name to unload

        Example:
            >>> registry.unload_plugin("pdf")
        """
        if name not in self._loaded:
            logger.debug(f"Plugin '{name}' is not loaded, nothing to unload")
            return

        try:
            handler = self._loaded[name]
            self._loader.cleanup_plugin(handler)
            del self._loaded[name]

            # Update metadata
            if name in self._discovered:
                self._discovered[name].is_loaded = False

            logger.info(f"Unloaded plugin: {name}")

        except Exception as e:
            logger.error(f"Error unloading plugin '{name}': {e}")

    def get_handler_for_extension(
        self, ext: str, context: PluginContext | None = None
    ) -> FileTypeHandler | None:
        """Get handler for a file extension (lazy load).

        Performs lazy loading: if handler not yet loaded, loads it on first access.
        Returns None if no handler is registered for the extension or if loading fails.

        Args:
            ext: File extension (e.g., '.pdf')
            context: Plugin context for initialization if lazy loading (optional)

        Returns:
            FileTypeHandler | None: Handler instance or None if no handler available

        Note:
            Extensions are matched case-insensitively. If extension has conflicts
            (multiple plugins claim it), first enabled plugin in config order wins.

        Example:
            >>> handler = registry.get_handler_for_extension(".pdf", context)
            >>> if handler:
            ...     text = handler.extract_text(file_path)
        """
        # Normalize to lowercase for case-insensitive matching
        ext_lower = ext.lower()

        # Check extension map
        plugin_name = self._extension_map.get(ext_lower)
        if plugin_name is None:
            logger.debug(f"No handler registered for extension: {ext_lower}")
            return None

        # Check if already loaded
        if plugin_name in self._loaded:
            return self._loaded[plugin_name]

        # Lazy load the plugin
        logger.debug(f"Lazy loading handler for {ext} -> {plugin_name}")
        return self.load_plugin(plugin_name, context)

    def get_handler_for_file(
        self, file_path: Path, context: PluginContext | None = None
    ) -> FileTypeHandler | None:
        """Get handler for a specific file.

        Two-phase resolution:
          Phase 1: Check path-claiming plugins (via claims_file()).
          Phase 2: Fall back to extension-based lookup + can_handle_file().

        Args:
            file_path: Path to file needing handler
            context: Plugin context for initialization if lazy loading (optional)

        Returns:
            FileTypeHandler | None: Handler that can process this file, or None

        Example:
            >>> handler = registry.get_handler_for_file(Path("doc.pdf"), context)
            >>> if handler:
            ...     text = handler.extract_text(file_path)
        """
        # Phase 1: Path-claiming plugins
        claimed = self._resolve_by_path_claim(file_path, context)
        if claimed is not None:
            return claimed

        # Phase 2: Extension-based fallback
        ext = file_path.suffix.lower()
        if not ext:
            logger.debug(f"File has no extension: {file_path}")
            return None

        handler = self.get_handler_for_extension(ext, context)
        if handler is None:
            return None

        # Additional validation via plugin's can_handle_file
        try:
            if not handler.can_handle_file(file_path):
                logger.debug(f"Plugin '{handler.name}' cannot handle file: {file_path}")
                return None
        except Exception as e:
            logger.warning(f"Error in can_handle_file for '{handler.name}': {e}")
            return None

        return handler

    def _resolve_by_path_claim(
        self, file_path: Path, context: PluginContext | None = None
    ) -> FileTypeHandler | None:
        """Check path-claiming plugins for a file match.

        Only iterates plugins whose metadata has has_claims_file=True.
        Returns the first plugin that claims the file, or None.

        Args:
            file_path: Path to the file to check.
            context: Plugin context for lazy loading if needed.

        Returns:
            FileTypeHandler | None: The claiming handler, or None.
        """
        for name, meta in self._discovered.items():
            if not meta.has_claims_file or not meta.is_enabled:
                continue

            # Ensure plugin is loaded
            handler = self._loaded.get(name)
            if handler is None:
                handler = self.load_plugin(name, context)
            if handler is None:
                continue

            try:
                if handler.claims_file(file_path):
                    logger.debug(f"Plugin '{name}' claims file via path: {file_path}")
                    return handler
            except Exception as e:
                logger.warning(f"Error in claims_file for '{name}': {e}")
                continue

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

    def shutdown_all_plugins(self) -> None:
        """Shutdown and cleanup all loaded plugins.

        Calls cleanup() on all loaded plugin handlers and clears the loaded
        plugins dictionary. Handles cleanup errors gracefully by logging them
        and continuing to clean up remaining plugins.

        Example:
            >>> registry.shutdown_all_plugins()
        """
        for plugin_name, handler in list(self._loaded.items()):
            try:
                self._loader.cleanup_plugin(handler)
            except Exception as e:
                logger.warning(f"Error cleaning up plugin '{plugin_name}': {e}")

        self._loaded.clear()
        logger.info("All plugins shutdown successfully")

    def validate_dependencies(self) -> dict[str, str]:
        """Check that all discovered plugins have their dependencies installed.

        Attempts to import each enabled plugin and reports any missing
        dependencies with installation instructions.

        Returns:
            dict[str, str]: Map of plugin name to dependency error message.
                            Empty dict if all dependencies are satisfied.

        Example:
            >>> issues = registry.validate_dependencies()
            >>> for plugin, msg in issues.items():
            ...     print(f"{plugin}: {msg}")
        """
        issues: dict[str, str] = {}

        for plugin_name, metadata in self._discovered.items():
            if not metadata.is_enabled:
                continue

            try:
                self._loader.load_plugin_class(plugin_name)
            except Exception as e:
                from krag.plugins.exceptions import PluginDependencyError

                if isinstance(e, PluginDependencyError):
                    issues[plugin_name] = str(e)
                else:
                    issues[plugin_name] = (
                        f"Failed to import: {e}\n"
                        f"  Try: uv pip install --force-reinstall <plugin-package>\n"
                        f"  Or:  pip install --force-reinstall <plugin-package>"
                    )

                metadata.is_enabled = False
                metadata.load_error = str(e)
                logger.warning(f"Plugin '{plugin_name}' dependency check failed: {e}")

        return issues
