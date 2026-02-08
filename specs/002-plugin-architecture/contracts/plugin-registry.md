# Contract: PluginRegistry API

**Version**: 1.0.0  
**Status**: Draft  
**Purpose**: Defines the contract for the PluginRegistry that manages plugin lifecycle

---

## API Definition

### PluginRegistry

Central registry for managing plugin discovery, loading, validation, and lifecycle.

#### Initialization

```python
class PluginRegistry:
    def __init__(self, config: PluginConfiguration):
        """
        Initialize plugin registry with configuration.
        
        Args:
            config (PluginConfiguration): Plugin system configuration
            
        Effects:
            - Discovers all available plugins via entry points
            - Builds extension → plugin mapping
            - Does NOT load plugins (lazy loading)
        """
```

#### Discovery Methods

```python
def discover_plugins(self) -> list[PluginMetadata]:
    """
    Scan Python entry points for installed plugins.
    
    Returns:
        list[PluginMetadata]: Metadata for all discovered plugins
        
    Effects:
        - Scans 'krag.plugins' entry point group
        - Creates PluginMetadata for each found entry point
        - Updates internal _discovered registry
        - Builds _extension_map from supported extensions
        
    Constraints:
        - Should complete in <1 second for typical installations
        - Should not import plugin modules (deferred to loading)
        - Should handle malformed entry points gracefully
    
    Example:
        >>> registry = PluginRegistry(config)
        >>> plugins = registry.discover_plugins()
        >>> [p.name for p in plugins]
        ['pdf', 'docx', 'markdown']
    """

def list_plugins(
    self, 
    status: Literal["all", "enabled", "disabled", "loaded"] = "all"
) -> list[PluginMetadata]:
    """
    List plugins filtered by status.
    
    Args:
        status: Filter by plugin status
            - "all": All discovered plugins
            - "enabled": Only enabled plugins
            - "disabled": Only disabled plugins  
            - "loaded": Only currently loaded plugins
            
    Returns:
        list[PluginMetadata]: Filtered plugin metadata list
        
    Example:
        >>> registry.list_plugins(status="enabled")
        [PluginMetadata(name='pdf', is_enabled=True, ...)]
    """

def get_plugin_info(self, name: str) -> PluginMetadata | None:
    """
    Get metadata for specific plugin.
    
    Args:
        name (str): Plugin name
        
    Returns:
        PluginMetadata | None: Plugin metadata or None if not found
        
    Example:
        >>> registry.get_plugin_info("pdf")
        PluginMetadata(name='pdf', version='1.0.0', ...)
    """
```

#### Validation Methods

```python
def validate_plugins(self) -> dict[str, list[str]]:
    """
    Validate all discovered plugins.
    
    Returns:
        dict[str, list[str]]: Validation results
            Key: Plugin name
            Value: List of validation errors (empty if valid)
            
    Checks:
        - API version compatibility
        - No extension conflicts between enabled plugins
        - Configuration validity
        - Dependency availability (if checkable)
        
    Effects:
        - Updates PluginMetadata.load_error for invalid plugins
        
    Example:
        >>> registry.validate_plugins()
        {
            'pdf': [],  # Valid
            'docx': ['Requires krag API 2.0.0, but current is 1.0.0'],
            'old_plugin': ['Conflicting extension .txt with builtin handler']
        }
    """

def check_extension_conflict(self, extension: str) -> list[str]:
    """
    Check if file extension has conflicting handlers.
    
    Args:
        extension (str): File extension with leading dot
        
    Returns:
        list[str]: Plugin names claiming this extension
        
    Example:
        >>> registry.check_extension_conflict(".pdf")
        ['pdf']  # No conflict
        
        >>> registry.check_extension_conflict(".txt")
        ['builtin', 'enhanced_text']  # Conflict!
    """
```

#### Loading Methods

```python
def load_plugin(self, name: str) -> FileTypeHandler:
    """
    Load and initialize a plugin.
    
    Args:
        name (str): Plugin name to load
        
    Returns:
        FileTypeHandler: Initialized plugin handler
        
    Raises:
        PluginNotFoundError: Plugin not discovered
        PluginLoadError: Failed to import or instantiate
        PluginAPIVersionError: Incompatible API version
        PluginConfigurationError: Invalid configuration
        
    Effects:
        - Imports plugin module
        - Instantiates FileTypeHandler class
        - Calls handler.initialize() with plugin config
        - Updates PluginMetadata.is_loaded = True
        - Caches handler in _loaded registry
        
    Side Effects:
        - Plugin's __init__ may load models, open files, etc.
        - Plugin's initialize() may validate config, allocate resources
        
    Constraints:
        - Must check API version compatibility before loading
        - Must pass plugin-specific config from config.toml
        - Should complete in <5 seconds for typical plugins
        - Subsequent calls return cached instance
        
    Example:
        >>> handler = registry.load_plugin("pdf")
        >>> handler.name
        'pdf'
        >>> handler.supported_extensions()
        ['.pdf', '.PDF']
    """

def unload_plugin(self, name: str) -> None:
    """
    Unload and cleanup a plugin.
    
    Args:
        name (str): Plugin name to unload
        
    Effects:
        - Calls handler.cleanup() if plugin loaded
        - Removes handler from _loaded cache
        - Updates PluginMetadata.is_loaded = False
        - Does not remove from _discovered registry
        
    Raises:
        PluginNotFoundError: Plugin not discovered
        
    Example:
        >>> registry.unload_plugin("pdf")
        >>> registry.get_plugin_info("pdf").is_loaded
        False
    """

def reload_plugin(self, name: str) -> FileTypeHandler:
    """
    Reload a plugin (for development/debugging).
    
    Args:
        name (str): Plugin name to reload
        
    Returns:
        FileTypeHandler: New plugin instance
        
    Effects:
        - Calls unload_plugin(name)
        - Reloads Python module
        - Calls load_plugin(name)
        
    Raises:
        PluginNotFoundError: Plugin not discovered
        PluginLoadError: Failed to reload
        
    Warning:
        Module reloading has limitations and may not work correctly
        for all plugins. Recommend restarting krag instead.
        
    Example:
        >>> handler = registry.reload_plugin("pdf")
    """
```

#### Handler Retrieval Methods

```python
def get_handler_for_extension(self, extension: str) -> FileTypeHandler | None:
    """
    Get plugin handler for specific file extension.
    
    Args:
        extension (str): File extension with leading dot (e.g., ".pdf")
        
    Returns:
        FileTypeHandler | None: Handler if available, None otherwise
        
    Effects:
        - Looks up extension in _extension_map
        - Loads plugin if not already loaded (lazy loading)
        - Returns cached handler if already loaded
        
    Raises:
        PluginLoadError: If plugin fails to load
        
    Constraints:
        - Case-insensitive extension matching
        - Disabled plugins not returned
        - First call may trigger plugin load (slow)
        - Subsequent calls return cached instance (fast)
        
    Example:
        >>> handler = registry.get_handler_for_extension(".pdf")
        >>> handler.name
        'pdf'
        
        >>> handler = registry.get_handler_for_extension(".xyz")
        >>> handler is None
        True
    """

def get_handler_for_file(self, file_path: Path) -> FileTypeHandler | None:
    """
    Get plugin handler for specific file.
    
    Args:
        file_path (Path): Path to file
        
    Returns:
        FileTypeHandler | None: Handler if available, None otherwise
        
    Effects:
        - Extracts file extension from path
        - Calls get_handler_for_extension()
        - Optionally calls handler.can_handle_file() for extra validation
        
    Example:
        >>> handler = registry.get_handler_for_file(Path("doc.pdf"))
        >>> handler.name
        'pdf'
    """
```

#### Configuration Management

```python
def update_plugin_config(self, name: str, config: dict[str, Any]) -> None:
    """
    Update configuration for a plugin.
    
    Args:
        name (str): Plugin name
        config (dict): New configuration values
        
    Effects:
        - Updates plugin configuration in registry
        - If plugin loaded, calls handler.initialize() with new config
        - Validates configuration
        
    Raises:
        PluginNotFoundError: Plugin not discovered
        PluginConfigurationError: Invalid configuration
        
    Example:
        >>> registry.update_plugin_config("pdf", {"max_pages": 500})
    """

def enable_plugin(self, name: str) -> None:
    """
    Enable a disabled plugin.
    
    Args:
        name (str): Plugin name
        
    Effects:
        - Updates PluginMetadata.is_enabled = True
        - Updates configuration
        - Rebuilds extension map
        
    Raises:
        PluginNotFoundError: Plugin not discovered
        
    Example:
        >>> registry.enable_plugin("pdf")
    """

def disable_plugin(self, name: str) -> None:
    """
    Disable a plugin.
    
    Args:
        name (str): Plugin name
        
    Effects:
        - Unloads plugin if loaded
        - Updates PluginMetadata.is_enabled = False
        - Updates configuration
        - Rebuilds extension map
        
    Raises:
        PluginNotFoundError: Plugin not discovered
        
    Example:
        >>> registry.disable_plugin("pdf")
    """
```

#### Lifecycle Management

```python
def shutdown(self) -> None:
    """
    Shutdown plugin system and cleanup all plugins.
    
    Effects:
        - Calls cleanup() on all loaded plugins
        - Clears _loaded cache
        - Logs any cleanup errors
        
    Constraints:
        - Should not raise exceptions
        - Should handle plugin cleanup failures gracefully
        - Should complete in <10 seconds
        
    Example:
        >>> registry.shutdown()
    """
```

---

## Contract Tests

### Test 1: Discovery

```python
def test_discover_plugins():
    """Verify plugin discovery works"""
    registry = PluginRegistry(config)
    plugins = registry.discover_plugins()
    
    assert isinstance(plugins, list)
    for plugin in plugins:
        assert isinstance(plugin, PluginMetadata)
        assert len(plugin.name) > 0
        assert len(plugin.supported_extensions) > 0
```

### Test 2: Validation

```python
def test_validate_plugins():
    """Verify plugin validation detects issues"""
    registry = PluginRegistry(config)
    registry.discover_plugins()
    
    results = registry.validate_plugins()
    assert isinstance(results, dict)
    
    for plugin_name, errors in results.items():
        assert isinstance(plugin_name, str)
        assert isinstance(errors, list)
```

### Test 3: Loading

```python
def test_load_plugin():
    """Verify plugin loading"""
    registry = PluginRegistry(config)
    registry.discover_plugins()
    
    # Mock plugin for testing
    handler = registry.load_plugin("mock_plugin")
    assert isinstance(handler, FileTypeHandler)
    
    # Verify cached
    handler2 = registry.load_plugin("mock_plugin")
    assert handler is handler2
```

### Test 4: Handler Retrieval

```python
def test_get_handler_for_extension():
    """Verify extension-based handler lookup"""
    registry = PluginRegistry(config)
    registry.discover_plugins()
    
    handler = registry.get_handler_for_extension(".mock")
    assert handler is not None
    assert ".mock" in handler.supported_extensions()
    
    handler = registry.get_handler_for_extension(".nonexistent")
    assert handler is None
```

### Test 5: Error Handling

```python
def test_load_nonexistent_plugin_raises():
    """Verify error when loading nonexistent plugin"""
    registry = PluginRegistry(config)
    
    with pytest.raises(PluginNotFoundError):
        registry.load_plugin("nonexistent")

def test_load_incompatible_plugin_raises():
    """Verify error when API version incompatible"""
    registry = PluginRegistry(config)
    
    with pytest.raises(PluginAPIVersionError):
        registry.load_plugin("incompatible_plugin")
```

### Test 6: Configuration

```python
def test_enable_disable_plugin():
    """Verify enable/disable functionality"""
    registry = PluginRegistry(config)
    registry.discover_plugins()
    
    registry.disable_plugin("mock_plugin")
    assert not registry.get_plugin_info("mock_plugin").is_enabled
    
    registry.enable_plugin("mock_plugin")
    assert registry.get_plugin_info("mock_plugin").is_enabled
```

### Test 7: Lifecycle

```python
def test_plugin_lifecycle():
    """Verify complete plugin lifecycle"""
    registry = PluginRegistry(config)
    
    # Discovery
    plugins = registry.discover_plugins()
    assert len(plugins) > 0
    
    # Validation
    results = registry.validate_plugins()
    assert "mock_plugin" in results
    
    # Loading
    handler = registry.load_plugin("mock_plugin")
    assert registry.get_plugin_info("mock_plugin").is_loaded
    
    # Unloading
    registry.unload_plugin("mock_plugin")
    assert not registry.get_plugin_info("mock_plugin").is_loaded
    
    # Shutdown
    registry.shutdown()
```

---

## Performance Requirements

The PluginRegistry MUST meet these performance requirements:

- **discover_plugins()**: <1 second for 50 installed plugins
- **validate_plugins()**: <2 seconds for 50 installed plugins
- **load_plugin()**: <5 seconds per plugin (first load)
- **get_handler_for_extension()**: <1ms (cached), <5s (uncached)
- **shutdown()**: <10 seconds total for all plugins

---

## Thread Safety

The PluginRegistry SHOULD be thread-safe for concurrent handler retrieval:

- Multiple threads can call `get_handler_for_extension()` simultaneously
- Plugin loading must be thread-safe (use locks if necessary)
- Configuration updates should block handler retrieval during update

---

## Error Handling

The PluginRegistry MUST:

- Catch and log plugin load errors, don't crash
- Provide detailed error messages for troubleshooting
- Continue operation when individual plugins fail
- Mark failed plugins as unavailable

---

## Example Usage

```python
# Initialization
config = PluginConfiguration(
    enabled_plugins=["pdf", "docx"],
    plugin_settings={
        "pdf": {"max_pages": 1000}
    }
)
registry = PluginRegistry(config)

# Discovery and validation
plugins = registry.discover_plugins()
validation_errors = registry.validate_plugins()

# Get handler for file
handler = registry.get_handler_for_extension(".pdf")
if handler:
    text = handler.extract_text(Path("document.pdf"))

# List plugins
enabled = registry.list_plugins(status="enabled")
for plugin in enabled:
    print(f"{plugin.name} v{plugin.version}")

# Shutdown
registry.shutdown()
```
