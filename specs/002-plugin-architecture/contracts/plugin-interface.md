# Contract: FileTypeHandler Plugin Interface

**Version**: 1.0.0  
**Status**: Draft  
**Purpose**: Defines the contract that all file type handler plugins must implement

---

## Interface Definition

### FileTypeHandler (Abstract Base Class)

All plugins must inherit from `FileTypeHandler` and implement the following methods:

#### Required Properties

```python
@property
@abstractmethod
def name(self) -> str:
    """
    Returns the plugin identifier (e.g., "pdf", "docx").
    
    Constraints:
    - Must be unique across all plugins
    - Must be valid Python identifier (alphanumeric + underscore)
    - Should be lowercase for consistency
    
    Returns:
        str: Plugin name
    """

@property
@abstractmethod
def version(self) -> str:
    """
    Returns the plugin version string.
    
    Constraints:
    - Must be valid semantic version (e.g., "1.0.0", "2.1.3-beta")
    
    Returns:
        str: Plugin version
    """

@property
@abstractmethod
def required_api_version(self) -> str:
    """
    Returns minimum plugin API version required by this plugin.
    
    Constraints:
    - Must be valid semantic version
    - Must be compatible with current krag plugin API version
    
    Returns:
        str: Required API version (e.g., "1.0.0")
    """
```

#### Required Methods

```python
@abstractmethod
def supported_extensions(self) -> list[str]:
    """
    Returns list of file extensions this plugin handles.
    
    Constraints:
    - Must include leading dot (e.g., ".pdf" not "pdf")
    - Should include case variations if filesystem is case-sensitive
    - Must not be empty
    - Extensions should not conflict with other enabled plugins
    
    Returns:
        list[str]: File extensions (e.g., [".pdf", ".PDF"])
    
    Example:
        >>> handler.supported_extensions()
        [".pdf", ".PDF"]
    """

@abstractmethod
def extract_text(self, file_path: Path) -> str:
    """
    Extracts plain text content from the file.
    
    Args:
        file_path (Path): Absolute path to file to process
        
    Returns:
        str: Extracted text content (may be empty string if file has no text)
        
    Raises:
        PluginExtractionError: If file cannot be processed
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
        
    Constraints:
    - Must return valid UTF-8 string
    - Should strip control characters except newlines/tabs
    - Should handle empty or corrupted files gracefully
    - Should not raise on empty content (return "" instead)
    
    Example:
        >>> handler.extract_text(Path("/docs/paper.pdf"))
        "This is the document text..."
    """

@abstractmethod
def extract_metadata(self, file_path: Path) -> dict[str, Any]:
    """
    Extracts file-specific metadata.
    
    Args:
        file_path (Path): Absolute path to file to process
        
    Returns:
        dict[str, Any]: Metadata dictionary (may be empty)
        
    Raises:
        PluginExtractionError: If metadata extraction fails critically
        
    Constraints:
    - Must return dictionary (may be empty {})
    - Keys should be descriptive strings (e.g., "author", "page_count")
    - Values must be JSON-serializable (str, int, float, bool, list, dict)
    - Should not raise on missing metadata (return {} instead)
    - Recommended keys: title, author, creation_date, page_count, language
    
    Example:
        >>> handler.extract_metadata(Path("/docs/paper.pdf"))
        {
            "page_count": 42,
            "author": "Jane Doe",
            "title": "Research Paper",
            "creation_date": "2026-01-15",
            "pdf_version": "1.7"
        }
    """

@abstractmethod
def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
    """
    Returns preferred chunking strategy for this file type.
    
    Returns:
        ChunkingStrategy | TextChunker | None: 
            - ChunkingStrategy enum for built-in strategies
            - TextChunker instance for custom chunking
            - None to use krag's default chunker
            
    Constraints:
    - If returning TextChunker, must have chunk_text(text: str) method
    - ChunkingStrategy.CUSTOM requires returning custom TextChunker
    
    Example:
        >>> handler.get_chunking_strategy()
        ChunkingStrategy.DEFAULT
        
        >>> handler.get_chunking_strategy()
        MyCustomChunker(delimiter="\\n\\n")
        
        >>> handler.get_chunking_strategy()
        None  # Same as ChunkingStrategy.DEFAULT
    """
```

#### Optional Lifecycle Hooks

```python
def initialize(self, config: dict[str, Any]) -> None:
    """
    Called once after plugin is loaded, before first use.
    
    Args:
        config (dict): Plugin-specific configuration from config.toml
        
    Raises:
        PluginConfigurationError: If configuration is invalid
        
    Constraints:
    - Should validate configuration
    - Should initialize any stateful resources
    - Should not perform expensive operations (defer to first extract call)
    - Default implementation does nothing
    """

def cleanup(self) -> None:
    """
    Called at krag shutdown for resource cleanup.
    
    Constraints:
    - Should release file handles, network connections, etc.
    - Should not raise exceptions
    - Default implementation does nothing
    """

def can_handle_file(self, file_path: Path) -> bool:
    """
    Additional validation beyond file extension matching.
    
    Args:
        file_path (Path): File to check
        
    Returns:
        bool: True if plugin can handle this file
        
    Constraints:
    - Should be lightweight (check magic bytes, not full parse)
    - Default implementation checks extension only
    - Should not raise exceptions (return False instead)
    
    Example:
        >>> handler.can_handle_file(Path("file.pdf"))
        True  # Valid PDF magic bytes
        
        >>> handler.can_handle_file(Path("corrupted.pdf"))
        False  # Invalid PDF structure
    """
```

---

## Contract Tests

Plugin implementations MUST pass these contract tests:

### Test 1: Interface Implementation

```python
def test_plugin_implements_interface(handler: FileTypeHandler):
    """Verify plugin implements all required methods"""
    assert hasattr(handler, 'name')
    assert hasattr(handler, 'version')
    assert hasattr(handler, 'required_api_version')
    assert hasattr(handler, 'supported_extensions')
    assert hasattr(handler, 'extract_text')
    assert hasattr(handler, 'extract_metadata')
    assert hasattr(handler, 'get_chunking_strategy')
```

### Test 2: Properties Return Valid Types

```python
def test_plugin_properties_valid_types(handler: FileTypeHandler):
    """Verify properties return expected types"""
    assert isinstance(handler.name, str)
    assert len(handler.name) > 0
    assert handler.name.replace('_', '').isalnum()  # Valid identifier
    
    assert isinstance(handler.version, str)
    assert re.match(r'^\d+\.\d+\.\d+', handler.version)  # Semver
    
    assert isinstance(handler.required_api_version, str)
    assert re.match(r'^\d+\.\d+\.\d+', handler.required_api_version)
```

### Test 3: Supported Extensions Format

```python
def test_supported_extensions_format(handler: FileTypeHandler):
    """Verify extensions follow correct format"""
    extensions = handler.supported_extensions()
    assert isinstance(extensions, list)
    assert len(extensions) > 0
    
    for ext in extensions:
        assert isinstance(ext, str)
        assert ext.startswith('.')
        assert len(ext) >= 2  # At least one char after dot
```

### Test 4: Text Extraction Returns String

```python
def test_extract_text_returns_string(handler: FileTypeHandler, test_file: Path):
    """Verify extract_text returns valid string"""
    text = handler.extract_text(test_file)
    assert isinstance(text, str)
    # Note: Empty string is allowed
```

### Test 5: Metadata Returns Dict

```python
def test_extract_metadata_returns_dict(handler: FileTypeHandler, test_file: Path):
    """Verify extract_metadata returns valid dict"""
    metadata = handler.extract_metadata(test_file)
    assert isinstance(metadata, dict)
    
    # Verify all values are JSON-serializable
    import json
    json.dumps(metadata)  # Should not raise
```

### Test 6: Chunking Strategy Returns Valid Type

```python
def test_chunking_strategy_valid_type(handler: FileTypeHandler):
    """Verify get_chunking_strategy returns valid type"""
    strategy = handler.get_chunking_strategy()
    assert strategy is None or \
           isinstance(strategy, ChunkingStrategy) or \
           hasattr(strategy, 'chunk_text')
```

### Test 7: Error Handling

```python
def test_extract_text_handles_missing_file(handler: FileTypeHandler):
    """Verify appropriate error when file missing"""
    with pytest.raises((FileNotFoundError, PluginExtractionError)):
        handler.extract_text(Path("/nonexistent/file.pdf"))

def test_extract_text_handles_corrupted_file(handler: FileTypeHandler, corrupted_file: Path):
    """Verify appropriate error on corrupted file"""
    with pytest.raises(PluginExtractionError):
        handler.extract_text(corrupted_file)
```

---

## Example Implementation

```python
from pathlib import Path
from typing import Any
from krag.plugins.interfaces import FileTypeHandler, ChunkingStrategy
from krag.plugins.exceptions import PluginExtractionError

class MarkdownFileTypeHandler(FileTypeHandler):
    """Example: Simple markdown plugin using default chunking"""
    
    @property
    def name(self) -> str:
        return "markdown"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def required_api_version(self) -> str:
        return "1.0.0"
    
    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown", ".MD"]
    
    def extract_text(self, file_path: Path) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Strip markdown syntax (simple approach)
            import re
            content = re.sub(r'#+\s*', '', content)  # Headers
            content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)  # Bold
            content = re.sub(r'\*([^*]+)\*', r'\1', content)  # Italic
            
            return content
        except Exception as e:
            raise PluginExtractionError(
                f"Failed to extract text from {file_path}",
                plugin_name=self.name,
                file_path=file_path,
                original_exception=e
            )
    
    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        # Extract YAML frontmatter if present
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if content.startswith('---'):
                import yaml
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    return yaml.safe_load(parts[1]) or {}
        except:
            pass
        
        return {}
    
    def get_chunking_strategy(self) -> ChunkingStrategy | None:
        return None  # Use krag's default chunker
```

---

## Version Compatibility

### API Version 1.0.0 (Current)

This is the initial plugin API version. All plugins MUST implement the interface defined above.

### Future Compatibility

- **Minor version changes** (1.x): New optional methods may be added
- **Major version changes** (2.0): Breaking changes to required methods

Plugins should check `required_api_version` to ensure compatibility.

---

## Error Handling Requirements

Plugins MUST:
- Raise `PluginExtractionError` for file processing failures
- Include original exception in `original_exception` attribute
- Provide helpful error messages
- Not leak sensitive information in error messages

Plugins SHOULD:
- Log errors using krag's logging system
- Provide debugging information in error messages
- Handle common error cases gracefully

---

## Performance Requirements

Plugins SHOULD:
- Extract text in <5 seconds for typical files (<10MB)
- Stream large file processing when possible
- Release resources promptly after processing
- Not cache files in memory unnecessarily

Plugins MAY:
- Warn if file is unusually large before processing
- Skip certain file sections if extraction would be too slow
