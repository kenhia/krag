# Research: Plugin Architecture for File Type Extensions

**Feature**: 002-plugin-architecture  
**Date**: 2026-02-07  
**Status**: Phase 0 Complete

## Research Questions

### 1. Plugin Discovery Mechanism

**Question**: How should krag discover and register installed plugins?

**Decision**: Use Python setuptools entry points mechanism

**Rationale**:
- **Standard Python convention**: Entry points are the de-facto standard for plugin systems in Python (used by pytest, Flask extensions, Sphinx, etc.)
- **Automatic discovery**: Plugins register themselves via `pyproject.toml` entry points, no manual registration needed
- **Package manager integration**: Works seamlessly with pip/uv installation
- **Version management**: Package metadata includes version info automatically
- **No configuration files**: Eliminates need for plugin manifest files in user directories

**Implementation Pattern**:
```toml
# In plugin's pyproject.toml
[project.entry-points."krag.plugins"]
pdf = "krag_plugin_pdf.handler:PDFFileTypeHandler"
```

**Alternatives Considered**:
- **Manifest files** (`~/.config/krag/plugins/plugin-name.yaml`): Rejected because it requires manual file management and doesn't integrate with package installation
- **Directory scanning** (`~/.local/share/krag/plugins/`): Rejected because it doesn't leverage Python packaging ecosystem and complicates dependency management
- **Explicit registration** (code-based registration calls): Rejected because it requires users to modify krag code

---

### 2. File Type Handler Interface

**Question**: What methods must a file type handler plugin implement?

**Decision**: Define `FileTypeHandler` ABC with core extraction methods

**Rationale**:
- **Clear contract**: ABC enforces required methods at plugin load time
- **Flexibility**: Plugins control their extraction logic completely
- **Metadata support**: Handler provides both content and metadata extraction
- **Error handling**: Handler can raise specific exceptions for krag to handle gracefully

**Required Methods**:
```python
class FileTypeHandler(ABC):
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this handler supports (e.g., ['.pdf', '.PDF'])"""
        
    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """Extract plain text content from file"""
        
    @abstractmethod
    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract file-specific metadata (author, title, creation date, etc.)"""
        
    @abstractmethod
    def get_chunking_strategy(self) -> ChunkingStrategy | None:
        """Return custom chunking strategy or None to use krag's default"""
```

**Alternatives Considered**:
- **Separate content/metadata handlers**: Rejected because most file formats require parsing once to extract both
- **Only extract_text method**: Rejected because metadata is valuable for search context
- **Stream-based API**: Deferred to future version; current approach is simpler and handles most use cases

---

### 3. Chunking Strategy Selection

**Question**: How should plugins specify chunking strategies?

**Decision**: Plugins return a `ChunkingStrategy` enum or custom chunker instance

**Rationale**:
- **Flexibility**: Plugins can use krag's built-in chunkers or provide their own
- **Future-proof**: Design accommodates expansion of base chunking strategies
- **Simple default**: Returning `None` or `ChunkingStrategy.DEFAULT` uses krag's existing chunker
- **Type safety**: Enum provides clear options for base strategies

**Implementation Pattern**:
```python
class ChunkingStrategy(Enum):
    DEFAULT = "default"           # Current TextChunker behavior
    SEMANTIC = "semantic"         # Future: semantic boundary detection
    CODE_AWARE = "code_aware"     # Future: function/class boundaries
    CUSTOM = "custom"             # Plugin provides custom chunker instance

class FileTypeHandler(ABC):
    def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
        # Option 1: Use krag's default
        return None
        
        # Option 2: Request specific krag chunker
        return ChunkingStrategy.DEFAULT
        
        # Option 3: Provide custom chunker
        return MyCustomChunker(...)
```

**Alternatives Considered**:
- **Always require plugins to chunk**: Rejected because many file types (plain text conversion from DOCX) work fine with default chunking
- **Configuration-only selection**: Rejected because some file types require specialized chunking that isn't user-configurable
- **No chunking customization**: Rejected based on user requirement that plugins need chunking flexibility

---

### 4. Plugin Configuration

**Question**: How should plugin-specific configuration be structured?

**Decision**: Use nested TOML sections in main krag config

**Rationale**:
- **Centralized configuration**: Single file for all krag settings reduces user confusion
- **Hierarchical structure**: `[plugins.plugin_name]` sections keep plugin settings organized
- **Type validation**: Pydantic models validate plugin config sections
- **Override support**: Plugins can define defaults, users override in config

**Configuration Pattern**:
```toml
# ~/.config/krag/config.toml
[plugins]
enabled = ["pdf", "docx"]
disabled = ["markdown"]  # Override to disable built-in handling

[plugins.pdf]
extract_images = false
ocr_enabled = false
max_pages = 1000

[plugins.docx]
extract_comments = true
```

**Alternatives Considered**:
- **Per-plugin config files**: Rejected because it fragments configuration
- **Command-line only**: Rejected because complex plugin settings need persistence
- **Environment variables**: Rejected because it doesn't scale to multiple plugins with nested settings

---

### 5. Plugin Lifecycle Management

**Question**: When and how should plugins be loaded and initialized?

**Decision**: Lazy loading with initialization at first use

**Rationale**:
- **Performance**: Don't load plugins until actually needed
- **Error isolation**: Plugin load failures don't prevent krag startup
- **Resource efficiency**: Plugins may load large models/libraries - defer until necessary

**Lifecycle Stages**:
1. **Discovery** (at startup): Scan entry points, build registry of available plugins
2. **Validation** (at startup): Check plugin compatibility, dependencies, configuration
3. **Loading** (on-demand): Import plugin module when file type encountered
4. **Initialization** (on-demand): Call plugin setup with configuration
5. **Cleanup** (at shutdown): Call plugin teardown hooks if provided

**Implementation Pattern**:
```python
class PluginRegistry:
    def __init__(self):
        self._available: dict[str, EntryPoint] = {}  # Discovery
        self._loaded: dict[str, FileTypeHandler] = {}  # Loaded instances
        
    def discover_plugins(self):
        """Stage 1: Find all installed plugins"""
        
    def get_handler(self, extension: str) -> FileTypeHandler:
        """Stage 2-4: Load and initialize on first request"""
```

**Alternatives Considered**:
- **Eager loading**: Rejected due to startup time impact
- **No lifecycle hooks**: Rejected because plugins may need cleanup (close files, release resources)
- **Per-file initialization**: Rejected because plugin state can be reused across files

---

### 6. Error Handling and Graceful Degradation

**Question**: How should krag handle plugin failures?

**Decision**: Continue processing with remaining plugins and log errors

**Rationale**:
- **Resilience**: Plugin bugs shouldn't crash entire indexing job
- **User control**: Users can disable problematic plugins and continue working
- **Debugging support**: Clear error logs help plugin developers and users troubleshoot

**Error Handling Strategy**:
- **Plugin load failure**: Log error, mark plugin unavailable, continue with other plugins
- **File processing failure**: Log error with file path, skip file, continue with remaining files
- **Configuration error**: Show validation errors at startup, refuse to run until fixed
- **Dependency missing**: Detect at validation stage, provide clear installation instructions

**Error Examples**:
```
ERROR: Plugin 'pdf' failed to load: ModuleNotFoundError: No module named 'PyPDF2'
       To resolve: uv pip install krag-plugin-pdf[dependencies]
       
WARNING: Failed to process file.pdf with plugin 'pdf': Corrupted PDF structure
         Continuing with remaining files...
```

**Alternatives Considered**:
- **Fail entire job on plugin error**: Rejected because it makes system too fragile
- **Silent failure**: Rejected because users need to know about failures
- **Retry logic**: Deferred to future version; adds complexity without clear benefit for MVP

---

### 7. Plugin Compatibility and Versioning

**Question**: How should krag ensure plugin compatibility across versions?

**Decision**: Define plugin API version and check at load time

**Rationale**:
- **Future safety**: Allows API evolution while detecting incompatible plugins
- **Clear errors**: Plugin load failure shows exact incompatibility issue
- **Graceful degradation**: Old plugins can continue working until API breaks

**Implementation Pattern**:
```python
class FileTypeHandler(ABC):
    PLUGIN_API_VERSION = "1.0.0"  # Set by krag
    
    @property
    @abstractmethod
    def required_api_version(self) -> str:
        """Plugin declares minimum API version it needs"""
        return "1.0.0"
```

**Version Compatibility Rules**:
- **Major version change** (1.x → 2.x): Breaking changes, plugins must update
- **Minor version change** (1.0 → 1.1): New features added, old plugins still work
- **Patch version change** (1.0.0 → 1.0.1): Bug fixes only, full compatibility

**Alternatives Considered**:
- **No versioning**: Rejected because API will evolve and plugins will break
- **Strict version pinning**: Rejected because it prevents any API evolution
- **Runtime feature detection**: Deferred to future version; semantic versioning sufficient for MVP

---

### 8. Example Plugin Scope

**Question**: Which example plugins should be provided with initial release?

**Decision**: Two minimal but complete examples

**Rationale**:
- **Demonstrate patterns**: Show both chunking approaches (using krag's vs. custom)
- **Developer guidance**: Examples serve as plugin development templates
- **Test complexity**: Validate plugin system handles both simple and complex cases

**Example 1: Markdown Plugin** (uses krag's default chunking)
- **Purpose**: Show simplest plugin pattern
- **File type**: `.md` files
- **Implementation**: Strip markdown syntax, use krag's TextChunker
- **Code complexity**: ~50 lines

**Example 2: Log File Plugin** (provides custom chunking)
- **Purpose**: Show custom chunking strategy
- **File type**: `.log` files
- **Implementation**: Extract log entries, chunk by log level boundaries
- **Code complexity**: ~150 lines

**Alternatives Considered**:
- **PDF plugin as example**: Rejected because PDF parsing is complex and requires external dependencies
- **Multiple complete plugins**: Deferred to community; focus on patterns over coverage
- **No examples**: Rejected because developer guidance is critical for adoption

---

## Technology Stack Summary

### Core Plugin Infrastructure
- **Plugin discovery**: Python setuptools entry points
- **Interface definition**: Abstract Base Classes (ABC)
- **Configuration**: TOML with Pydantic validation
- **Lifecycle**: Lazy loading with on-demand initialization

### Plugin Development Dependencies
- **Minimal requirements**: Only `krag` package itself (provides interfaces)
- **Example dependencies**: Plugin-specific (PyPDF2 for PDF, python-docx for DOCX, etc.)

### Testing Strategy
- **Mock plugins**: Fixtures for testing plugin system without external dependencies
- **Contract tests**: Verify plugins implement required interfaces
- **Integration tests**: End-to-end tests with example plugins
- **Failure simulation**: Tests for error handling and graceful degradation

---

## Open Questions for Implementation Phase

None. All research questions resolved with clear decisions and rationales.

---

## References

- **Python Entry Points**: [Python Packaging Guide - Entry Points](https://packaging.python.org/specifications/entry-points/)
- **Plugin Architectures**: [Martin Fowler - Plugin Pattern](https://martinfowler.com/articles/injection.html)
- **Existing Python Plugin Systems**: pytest plugin system, Sphinx extensions, Flask extensions
- **Chunking Strategies**: [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/), [LlamaIndex Node Parsers](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/)
