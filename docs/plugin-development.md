# Plugin Development Guide

**Version**: 1.0.0  
**Last Updated**: February 11, 2026  
**Audience**: Plugin Developers

---

## Table of Contents

1. [Overview](#overview)
2. [Plugin System Architecture](#plugin-system-architecture)
3. [FileTypeHandler Interface](#filetypehandler-interface)
4. [Plugin Lifecycle](#plugin-lifecycle)
5. [Chunking Strategy Selection](#chunking-strategy-selection)
6. [Failure Reporting API](#failure-reporting-api)
7. [Plugin Package Structure](#plugin-package-structure)
8. [Installation and Registration](#installation-and-registration)
9. [Configuration Schema](#configuration-schema)
10. [Testing Your Plugin](#testing-your-plugin)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The krag plugin system enables developers to extend file type support without modifying the core application. Plugins are standard Python packages that implement the `FileTypeHandler` interface and register themselves via entry points.

### Key Features

- **Automatic Discovery**: Plugins self-register via setuptools entry points
- **Lazy Loading**: Plugins load only when a matching file type is encountered
- **Graceful Degradation**: Plugin failures don't crash indexing pipeline
- **Flexible Chunking**: Choose from built-in chunkers or provide custom chunking
- **Rich Context**: Access embedding generator, vector store, logging, and failure reporting
- **Configuration Validation**: Define Pydantic schemas for type-safe plugin config

### Requirements

- Python 3.11+
- krag >= 1.0.0
- Implement `FileTypeHandler` abstract base class
- Register via `krag.plugins` entry point group

### Development Time

A basic file type handler plugin typically requires **2-4 hours** to implement and test.

---

## Plugin System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    krag Indexing Pipeline                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           PluginRegistry                             │   │
│  │  - Discovers plugins via entry points                │   │
│  │  - Builds extension → handler mapping                │   │
│  │  - Manages plugin lifecycle                          │   │
│  └──────┬──────────────────────────────────────────────┘   │
│         │                                                    │
│         ↓                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           PluginLoader                               │   │
│  │  - Imports plugin packages                           │   │
│  │  - Validates API compatibility                       │   │
│  │  - Instantiates handlers                             │   │
│  └──────┬──────────────────────────────────────────────┘   │
│         │                                                    │
│         ↓                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │        YourPlugin (FileTypeHandler)                  │   │
│  │  - extract_text(file_path)                           │   │
│  │  - extract_metadata(file_path)                       │   │
│  │  - get_chunking_strategy()                           │   │
│  │  - initialize(config, context)                       │   │
│  └──────┬──────────────────────────────────────────────┘   │
│         │                                                    │
│         ↓                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           PluginContext                              │   │
│  │  - embedding_generator                               │   │
│  │  - vector_store                                      │   │
│  │  - chunker                                           │   │
│  │  - logger                                            │   │
│  │  - report_indexing_failure()                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Execution Flow

1. **Discovery**: Registry scans for `krag.plugins` entry points on startup
2. **Registration**: Extension → plugin mapping built from configuration
3. **Lazy Loading**: Plugin loaded when file with matching extension is encountered
4. **Initialization**: Plugin receives configuration and `PluginContext`
5. **Extraction**: Plugin extracts text and metadata from file
6. **Chunking**: Plugin returns chunking strategy (or uses default)
7. **Cleanup**: Plugin receives cleanup call when unloaded

---

## FileTypeHandler Interface

### Interface Contract

All plugins must implement the `FileTypeHandler` abstract base class:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from krag.plugins.interfaces import FileTypeHandler, ChunkingStrategy
from krag.plugins.context import PluginContext


class MyFileTypeHandler(FileTypeHandler):
    """Handler for .myformat files."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (used for configuration and logging).
        
        Returns:
            str: Unique plugin identifier (e.g., 'pdf', 'docx', 'markdown')
        """
        return "myformat"
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version string (semver format).
        
        Returns:
            str: Version in format 'major.minor.patch' (e.g., '1.0.0')
        """
        return "1.0.0"
    
    @property
    @abstractmethod
    def required_api_version(self) -> str:
        """Minimum krag plugin API version required.
        
        The plugin API uses semver. krag checks major version compatibility:
        - API 1.x.x plugins work with krag 1.x.x
        - API 2.x.x plugins require krag 2.x.x
        
        Returns:
            str: Required API version (e.g., '1.0.0')
        """
        return "1.0.0"
    
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return file extensions this handler supports.
        
        Extensions should:
        - Include the leading dot (e.g., '.pdf', '.docx')
        - Be lowercase (matching is case-insensitive)
        - Include all variations (e.g., ['.jpg', '.jpeg'])
        
        Returns:
            list[str]: List of supported file extensions
            
        Example:
            >>> handler.supported_extensions()
            ['.md', '.markdown', '.mdown']
        """
        pass
    
    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """Extract plain text content from file.
        
        This is the core extraction method. Extract all readable text
        content, stripping formatting but preserving structure where
        appropriate (paragraphs, lists, etc.).
        
        Args:
            file_path: Absolute path to file to extract
            
        Returns:
            str: Extracted plain text content
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read
            ValueError: If file is corrupt or unsupported variant
            Exception: Other extraction errors (will be logged and continue)
            
        Example:
            >>> handler.extract_text(Path('/docs/report.md'))
            'Title\\n\\nThis is the report content...'
        """
        pass
    
    @abstractmethod
    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract file-specific metadata.
        
        Extract metadata that helps with search and organization:
        - Document properties (title, author, creation date)
        - Statistics (word count, page count)
        - Custom attributes (tags, categories)
        
        Metadata is stored alongside file content and can be queried.
        
        Args:
            file_path: Absolute path to file to extract metadata from
            
        Returns:
            dict[str, Any]: Metadata dictionary with string keys
            
        Example:
            >>> handler.extract_metadata(Path('/docs/report.md'))
            {
                'title': 'Monthly Report',
                'author': 'John Doe',
                'created': '2026-02-01T10:30:00',
                'word_count': 1234,
                'tags': ['report', 'monthly']
            }
        """
        pass
    
    def get_chunking_strategy(self) -> ChunkingStrategy | Any | None:
        """Return chunking strategy for this file type.
        
        Plugins can:
        1. Return None → Use krag's default chunker (TextChunker)
        2. Return ChunkingStrategy enum → Use named base chunker
        3. Return custom chunker instance → Use plugin's chunker
        
        Default implementation returns None (use default chunking).
        
        Returns:
            ChunkingStrategy | TextChunker | None: Chunking strategy
            
        Example - Use default:
            >>> def get_chunking_strategy(self):
            ...     return None
            
        Example - Use base strategy:
            >>> def get_chunking_strategy(self):
            ...     return ChunkingStrategy.CODE_AWARE
            
        Example - Custom chunker:
            >>> def get_chunking_strategy(self):
            ...     return MyCustomChunker(chunk_size=500)
        """
        return None
    
    def initialize(
        self, config: dict[str, Any] | None, context: PluginContext | None
    ) -> None:
        """Initialize plugin with configuration and context.
        
        Called after plugin is loaded, before any extraction occurs.
        Use this to:
        - Validate configuration
        - Initialize internal state
        - Store context reference for later use
        - Perform one-time setup
        
        Args:
            config: Plugin configuration from config.toml
            context: PluginContext providing access to services
            
        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If initialization fails
            
        Example:
            >>> def initialize(self, config, context):
            ...     self.context = context
            ...     self.max_size = config.get('max_size_mb', 10)
            ...     self.logger = context.logger if context else logging.getLogger(__name__)
        """
        pass
    
    def cleanup(self) -> None:
        """Clean up plugin resources before unload.
        
        Called when plugin is disabled or krag shuts down.
        Use this to:
        - Close file handles
        - Release external resources
        - Flush caches
        - Clean up temporary files
        
        Example:
            >>> def cleanup(self):
            ...     if hasattr(self, '_temp_dir'):
            ...         shutil.rmtree(self._temp_dir)
        """
        pass
    
    @classmethod
    def config_schema(cls) -> type[BaseModel] | None:
        """Return Pydantic model for configuration validation.
        
        Define a Pydantic BaseModel that describes valid configuration
        for this plugin. krag validates user config against this schema.
        
        Returns:
            type[BaseModel] | None: Pydantic model class or None
            
        Example:
            >>> from pydantic import BaseModel, Field
            >>> class PDFPluginConfig(BaseModel):
            ...     extract_images: bool = Field(default=False)
            ...     ocr_enabled: bool = Field(default=False)
            ...     max_pages: int = Field(default=1000, gt=0)
            ...
            >>> @classmethod
            >>> def config_schema(cls):
            ...     return PDFPluginConfig
        """
        return None
```

### Method Signatures and Contracts

#### Required Methods

**`name`** (required property)
- Returns unique plugin identifier
- Used in configuration (`[plugins.{name}]`)
- Used in logging and error messages
- Should be lowercase, alphanumeric with underscores

**`version`** (required property)
- Returns plugin version string (semver)
- Format: `major.minor.patch`
- Used for compatibility checking

**`required_api_version`** (required property)
- Minimum krag plugin API version
- Major version must match krag's API version
- Minor/patch versions are backward compatible

**`supported_extensions()`** (required)
- Returns list of file extensions (with leading dot)
- Extensions are lowercase
- Matching is case-insensitive
- Must return non-empty list

**`extract_text(file_path)`** (required)
- Extracts plain text from file
- Returns string (can be empty for non-text files)
- Should preserve meaningful structure
- Raises exceptions for errors (handled gracefully)

**`extract_metadata(file_path)`** (required)
- Extracts file-specific metadata
- Returns dictionary with string keys
- Can return empty dict if no metadata
- Common keys: `title`, `author`, `created`, `modified`, `word_count`

#### Optional Methods

**`get_chunking_strategy()`** (optional)
- Returns chunking strategy or None
- Default implementation returns None
- See [Chunking Strategy Selection](#chunking-strategy-selection)

**`initialize(config, context)`** (optional)
- Called once after plugin loads
- Receives user configuration and PluginContext
- Store context for later use
- Validate configuration here

**`cleanup()`** (optional)
- Called when plugin unloads
- Release resources, close handles
- Clean up temporary files

**`config_schema()`** (optional class method)
- Returns Pydantic model for config validation
- Enables type-safe configuration
- krag validates config against schema

---

## Plugin Lifecycle

### Initialization Sequence

```
1. Discovery Phase (on krag startup)
   ├─ Scan for krag.plugins entry points
   ├─ Create PluginMetadata for each discovered plugin
   └─ Build extension → plugin mapping from config

2. Load Phase (when file with matching extension encountered)
   ├─ Import plugin module
   ├─ Check API version compatibility
   ├─ Instantiate handler class
   ├─ Call initialize(config, context)
   └─ Cache handler instance

3. Extraction Phase (for each file)
   ├─ Call extract_text(file_path)
   ├─ Call extract_metadata(file_path)
   ├─ Get chunking strategy
   └─ Process chunks through pipeline

4. Cleanup Phase (on unload or shutdown)
   └─ Call cleanup()
```

### `initialize(config, context)` Method

Called once after plugin is loaded, before first file extraction.

**Purpose**:
- Validate and store configuration
- Store PluginContext reference
- Initialize internal state
- Perform one-time setup

**Parameters**:

```python
def initialize(
    self, 
    config: dict[str, Any] | None,
    context: PluginContext | None
) -> None:
    """Initialize plugin with configuration and context.
    
    Args:
        config: User configuration from [plugins.{name}] section
        context: PluginContext providing access to services
    """
```

**Example Implementation**:

```python
class PDFHandler(FileTypeHandler):
    def initialize(self, config: dict[str, Any] | None, context: PluginContext | None) -> None:
        # Store context for later use
        self.context = context
        self.logger = context.logger if context else logging.getLogger(__name__)
        
        # Extract and validate configuration
        config = config or {}
        self.extract_images = config.get('extract_images', False)
        self.ocr_enabled = config.get('ocr_enabled', False)
        self.max_pages = config.get('max_pages', 1000)
        
        # Validate configuration
        if self.max_pages <= 0:
            raise ValueError("max_pages must be positive")
        
        # Initialize internal state
        self._page_cache = {}
        self._temp_dir = Path(tempfile.mkdtemp(prefix='krag-pdf-'))
        
        self.logger.info(
            f"PDF plugin initialized: ocr={self.ocr_enabled}, max_pages={self.max_pages}"
        )
```

### `cleanup()` Method

Called when plugin is unloaded (disabled, or krag shuts down).

**Purpose**:
- Release external resources
- Close file handles
- Clean up temporary files
- Flush caches

**Example Implementation**:

```python
class PDFHandler(FileTypeHandler):
    def cleanup(self) -> None:
        # Close any open handles
        if hasattr(self, '_pdf_handle') and self._pdf_handle:
            self._pdf_handle.close()
        
        # Remove temporary directory
        if hasattr(self, '_temp_dir') and self._temp_dir.exists():
            import shutil
            shutil.rmtree(self._temp_dir)
            
        # Clear caches
        if hasattr(self, '_page_cache'):
            self._page_cache.clear()
        
        if hasattr(self, 'logger'):
            self.logger.info("PDF plugin cleaned up")
```

### Lifecycle Best Practices

1. **Store context**: Save `PluginContext` reference in `initialize()`
2. **Lazy initialization**: Defer expensive setup until first use
3. **Stateless extraction**: Don't rely on instance state between file extractions
4. **Clean shutdown**: Always release resources in `cleanup()`
5. **Log lifecycle events**: Use `context.logger` for initialization/cleanup messages

---

## Chunking Strategy Selection

### Overview

Plugins control how extracted text is chunked for embedding and indexing. Three options:

1. **Default Chunking** (return `None`): Use krag's standard `TextChunker`
2. **Base Strategy** (return `ChunkingStrategy` enum): Select from krag's built-in chunkers
3. **Custom Chunking** (return chunker instance): Provide plugin-specific chunker

### ChunkingStrategy Enum

```python
from krag.plugins.interfaces import ChunkingStrategy

class ChunkingStrategy(Enum):
    """Built-in chunking strategies provided by krag."""
    
    DEFAULT = "default"           # Standard TextChunker (sentence-aware)
    SEMANTIC = "semantic"         # Future: semantic boundary detection
    CODE_AWARE = "code_aware"     # Future: respect function/class boundaries
```

### Option 1: Default Chunking (Recommended)

Return `None` to use krag's standard text chunker:

```python
class MarkdownHandler(FileTypeHandler):
    def get_chunking_strategy(self) -> None:
        # Use default chunking
        return None
```

**When to use**:
- Standard document formats (markdown, text, HTML)
- Content with paragraph structure
- No special chunking requirements

**Default chunker behavior**:
- 1000 character chunks with 200 character overlap
- Respects sentence boundaries
- Preserves paragraph structure
- Configurable via krag config

### Option 2: Base Strategy Selection

Return a `ChunkingStrategy` enum value:

```python
class PythonCodeHandler(FileTypeHandler):
    def get_chunking_strategy(self) -> ChunkingStrategy:
        # Request code-aware chunking
        return ChunkingStrategy.CODE_AWARE
```

**When to use**:
- File types that align with base strategies
- Want krag's implementation
- No custom logic needed

**Note**: Currently only `DEFAULT` is implemented. `SEMANTIC` and `CODE_AWARE` are reserved for future versions.

### Option 3: Custom Chunking

Return a chunker instance implementing the chunking interface:

```python
from pathlib import Path
from krag.extraction.chunker import TextChunker
from krag.models.text_chunk import TextChunk

class LogFileChunker:
    """Custom chunker for log files - chunks by time windows."""
    
    def __init__(self, time_window_minutes: int = 60):
        self.time_window_minutes = time_window_minutes
    
    def chunk(
        self, 
        text: str, 
        file_path: Path | None = None,
        file_type: str | None = None
    ) -> list[TextChunk]:
        """Chunk log file by time windows."""
        chunks = []
        lines = text.split('\n')
        
        current_chunk = []
        current_start = 0
        chunk_index = 0
        
        for i, line in enumerate(lines):
            # Parse timestamp from log line
            timestamp = self._extract_timestamp(line)
            
            if timestamp and self._is_new_window(timestamp, current_chunk):
                # Create chunk from accumulated lines
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    chunks.append(TextChunk(
                        file_path=file_path or Path("unknown"),
                        chunk_index=chunk_index,
                        content=chunk_text,
                        start_char=current_start,
                        end_char=current_start + len(chunk_text),
                        token_count=len(chunk_text.split())
                    ))
                    chunk_index += 1
                
                current_chunk = [line]
                current_start = sum(len(l) + 1 for l in lines[:i])
            else:
                current_chunk.append(line)
        
        # Handle last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(TextChunk(
                file_path=file_path or Path("unknown"),
                chunk_index=chunk_index,
                content=chunk_text,
                start_char=current_start,
                end_char=current_start + len(chunk_text),
                token_count=len(chunk_text.split())
            ))
        
        return chunks
    
    def _extract_timestamp(self, line: str) -> datetime | None:
        # Parse timestamp from log line
        # Implementation depends on log format
        pass
    
    def _is_new_window(self, timestamp: datetime, current_chunk: list[str]) -> bool:
        # Check if timestamp is in new time window
        pass


class LogFileHandler(FileTypeHandler):
    def get_chunking_strategy(self) -> LogFileChunker:
        # Return custom chunker instance
        return LogFileChunker(time_window_minutes=30)
```

**Custom chunker requirements**:
- Implement `chunk(text, file_path, file_type)` method
- Return `list[TextChunk]`
- Each chunk must have valid `file_path`, `chunk_index`, `content`, `start_char`, `end_char`, `token_count`

**When to use**:
- File format has specific structure (logs, CSVs, JSON)
- Need semantic chunking based on content
- Want chunks to respect format boundaries
- Base chunkers don't meet requirements

### Chunking API Summary

| Return Value | Behavior | Use Case |
|-------------|----------|----------|
| `None` | Default TextChunker | Standard documents |
| `ChunkingStrategy.DEFAULT` | Default TextChunker | Explicit default |
| `ChunkingStrategy.CODE_AWARE` | Code-aware chunker (future) | Source code files |
| `ChunkingStrategy.SEMANTIC` | Semantic chunker (future) | Advanced text |
| Custom chunker instance | Plugin's chunker | Special formats |

---

## Failure Reporting API

### PluginContext Overview

The `PluginContext` provides plugins with access to krag services and the failure reporting API. Context is passed to `initialize()` and should be stored for later use.

**Available Services**:

```python
from krag.plugins.context import PluginContext

class PluginContext:
    """Context object providing plugins access to krag services.
    
    Attributes:
        embedding_generator: Generate embeddings for text
        vector_store: Access to vector storage (read-only for plugins)
        chunker: Default text chunker instance
        logger: Configured logger for plugin messages
    """
    
    embedding_generator: EmbeddingGenerator
    vector_store: VectorStore
    chunker: TextChunker
    logger: logging.Logger
    
    def report_indexing_failure(
        self,
        file_path: Path,
        error_message: str,
        error_type: str = "extraction_error"
    ) -> None:
        """Report a file that failed to index.
        
        Use this to track files that couldn't be processed. Failures are
        collected and shown in indexing summary.
        
        Args:
            file_path: Path to file that failed
            error_message: Human-readable error description
            error_type: Error category (e.g., 'extraction_error', 'parse_error')
        """
```

### Using PluginContext

Store context reference in `initialize()`:

```python
class PDFHandler(FileTypeHandler):
    def initialize(self, config: dict[str, Any] | None, context: PluginContext | None) -> None:
        self.context = context
        self.logger = context.logger if context else logging.getLogger(__name__)
```

Use stored context in extraction methods:

```python
def extract_text(self, file_path: Path) -> str:
    try:
        # Attempt extraction
        text = self._extract_pdf_text(file_path)
        return text
    except CorruptPDFError as e:
        # Report failure for summary
        if self.context:
            self.context.report_indexing_failure(
                file_path=file_path,
                error_message=f"Corrupt PDF: {e}",
                error_type="corrupt_file"
            )
        # Re-raise for pipeline to handle
        raise
```

### Failure Reporting Best Practices

1. **Report before raising**: Call `report_indexing_failure()` before raising exception
2. **Categorize errors**: Use descriptive `error_type` values
3. **Include context**: Error messages should help user understand what went wrong
4. **Don't catch silently**: Always re-raise exceptions after reporting
5. **Check context**: Guard against `None` context in test environments

### Common Error Types

| Error Type | When to Use |
|-----------|-------------|
| `extraction_error` | General extraction failure |
| `parse_error` | File content couldn't be parsed |
| `corrupt_file` | File is damaged or invalid format |
| `permission_denied` | Can't read file (permissions) |
| `file_too_large` | File exceeds size limits |
| `unsupported_version` | File format version not supported |
| `missing_dependency` | Required library not installed |
| `timeout` | Extraction exceeded time limit |

### Example: Robust Error Handling

```python
class PDFHandler(FileTypeHandler):
    def extract_text(self, file_path: Path) -> str:
        """Extract text with comprehensive error handling."""
        
        # Check file exists and is readable
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            if self.context:
                self.context.report_indexing_failure(
                    file_path, error_msg, "file_not_found"
                )
            raise FileNotFoundError(error_msg)
        
        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_size_mb:
            error_msg = f"PDF too large: {file_size_mb:.1f}MB (max: {self.max_size_mb}MB)"
            if self.context:
                self.context.report_indexing_failure(
                    file_path, error_msg, "file_too_large"
                )
            raise ValueError(error_msg)
        
        try:
            # Attempt extraction
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                # Check page count
                if len(pdf_reader.pages) > self.max_pages:
                    error_msg = f"PDF has {len(pdf_reader.pages)} pages (max: {self.max_pages})"
                    if self.context:
                        self.context.report_indexing_failure(
                            file_path, error_msg, "too_many_pages"
                        )
                    raise ValueError(error_msg)
                
                # Extract text from all pages
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                
                return '\n\n'.join(text_parts)
        
        except PyPDF2.errors.PdfReadError as e:
            error_msg = f"Corrupt or invalid PDF: {e}"
            if self.context:
                self.context.report_indexing_failure(
                    file_path, error_msg, "corrupt_file"
                )
            raise ValueError(error_msg) from e
        
        except Exception as e:
            error_msg = f"PDF extraction failed: {e}"
            if self.context:
                self.context.report_indexing_failure(
                    file_path, error_msg, "extraction_error"
                )
            raise
```

---

## Plugin Package Structure

### Recommended Project Layout

```
krag-plugin-myformat/
├── pyproject.toml              # Package metadata and entry point
├── README.md                   # Plugin documentation
├── LICENSE                     # Open source license
├── src/
│   └── krag_plugin_myformat/
│       ├── __init__.py
│       ├── handler.py          # FileTypeHandler implementation
│       ├── chunker.py          # Custom chunker (if needed)
│       └── extractor.py        # Format-specific extraction logic
├── tests/
│   ├── __init__.py
│   ├── test_handler.py
│   ├── test_chunker.py
│   └── fixtures/
│       ├── sample.myformat
│       └── corrupt.myformat
└── examples/
    ├── basic_usage.py
    └── advanced_config.py
```

### pyproject.toml Configuration

Entry point registration is the key to plugin discovery:

```toml
[project]
name = "krag-plugin-myformat"
version = "1.0.0"
description = "krag plugin for MyFormat files"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["krag", "plugin", "myformat"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "krag>=1.0.0",
    "myformat-parser>=2.0.0",  # Format-specific dependencies
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.12.0",
]

# CRITICAL: Entry point registration
[project.entry-points."krag.plugins"]
myformat = "krag_plugin_myformat.handler:MyFormatHandler"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
```

### Entry Point Format

The entry point has three parts:

```toml
[project.entry-points."krag.plugins"]
plugin_name = "package.module:ClassName"
```

1. **Group**: `krag.plugins` (fixed - this is how krag discovers plugins)
2. **Plugin name**: Unique identifier (lowercase, underscores only)
3. **Import path**: `module.path:HandlerClassName`

**Example**:
```toml
[project.entry-points."krag.plugins"]
pdf = "krag_plugin_pdf.handler:PDFFileTypeHandler"
markdown = "krag_plugin_markdown.handler:MarkdownHandler"
logs = "krag_plugin_logs.handler:LogFileHandler"
```

---

## Installation and Registration

### Development Workflow

#### 1. Install Plugin in Development Mode

```bash
# From plugin directory
cd krag-plugin-myformat
uv pip install -e .

# Or from any directory
uv pip install -e /path/to/krag-plugin-myformat
```

Development mode (`-e` / `--editable`) allows you to edit plugin code without reinstalling.

#### 2. Verify Plugin Discovery

```bash
# List discovered plugins
krag plugin list

# Expected output:
# Name       Version  Status      Extensions
# myformat   1.0.0    discovered  .myformat, .myfmt
```

#### 3. Configure Plugin

Edit `~/.config/krag/config.toml`:

```toml
[plugins]
enabled = ["myformat"]  # Enable your plugin

[plugins.myformat]
# Plugin-specific configuration
max_file_size_mb = 50
extract_metadata = true
custom_option = "value"
```

#### 4. Test Plugin

```bash
# Create test file
echo "test content" > test.myformat

# Index with plugin
krag index . --verbose

# Expected output:
# ✓ test.myformat (myformat plugin)
```

### Distribution Workflow

Once plugin is ready for release:

#### 1. Build Distribution Package

```bash
# Install build tools (if not already installed)
uv pip install build

# Build package
cd krag-plugin-myformat
python -m build

# Creates:
# dist/krag-plugin-myformat-1.0.0.tar.gz
# dist/krag-plugin-myformat-1.0.0-py3-none-any.whl
```

#### 2. Publish to PyPI (Optional)

```bash
# Install twine
uv pip install twine

# Upload to PyPI
twine upload dist/*
```

#### 3. User Installation

```bash
# From PyPI
uv pip install krag-plugin-myformat

# From local wheel
uv pip install /path/to/krag-plugin-myformat-1.0.0-py3-none-any.whl

# From git repository
uv pip install git+https://github.com/you/krag-plugin-myformat.git
```

### Installation Commands Summary

| Command | Purpose |
|---------|---------|
| `uv pip install -e .` | Install in development mode |
| `uv pip install krag-plugin-myformat` | Install from PyPI |
| `uv pip install /path/to/wheel.whl` | Install from local wheel |
| `uv pip install git+https://...` | Install from git |
| `uv pip uninstall krag-plugin-myformat` | Remove plugin |
| `python -m build` | Build distribution package |

---

## Configuration Schema

### Defining Configuration Schema

Define a Pydantic model for type-safe configuration validation:

```python
from pydantic import BaseModel, Field, field_validator

class MyFormatConfig(BaseModel):
    """Configuration schema for MyFormat plugin."""
    
    # Basic options with defaults
    max_file_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum file size to process in MB"
    )
    
    extract_images: bool = Field(
        default=False,
        description="Extract embedded images as separate files"
    )
    
    # Advanced options
    parser_mode: str = Field(
        default="strict",
        description="Parser mode: 'strict', 'lenient', or 'aggressive'"
    )
    
    custom_tags: list[str] = Field(
        default_factory=list,
        description="Custom tags to apply to all extracted content"
    )
    
    # Custom validation
    @field_validator('parser_mode')
    @classmethod
    def validate_parser_mode(cls, v: str) -> str:
        valid_modes = {'strict', 'lenient', 'aggressive'}
        if v not in valid_modes:
            raise ValueError(f"parser_mode must be one of {valid_modes}")
        return v


class MyFormatHandler(FileTypeHandler):
    @classmethod
    def config_schema(cls) -> type[BaseModel]:
        return MyFormatConfig
    
    def initialize(self, config: dict[str, Any] | None, context: PluginContext | None) -> None:
        self.context = context
        
        # Parse and validate config
        if config:
            validated_config = MyFormatConfig(**config)
        else:
            validated_config = MyFormatConfig()
        
        # Store validated config
        self.max_file_size = validated_config.max_file_size_mb * 1024 * 1024
        self.extract_images = validated_config.extract_images
        self.parser_mode = validated_config.parser_mode
        self.custom_tags = validated_config.custom_tags
```

### User Configuration

Users configure plugins in `~/.config/krag/config.toml`:

```toml
[plugins.myformat]
max_file_size_mb = 100
extract_images = true
parser_mode = "lenient"
custom_tags = ["imported", "myformat"]
```

### Configuration Best Practices

1. **Provide sensible defaults**: Plugin should work without configuration
2. **Validate early**: Check config in `initialize()`, not during extraction
3. **Use Pydantic**: Type-safe validation prevents runtime errors
4. **Document options**: Use `description` fields in Pydantic model
5. **Environment-aware**: Support environment variables via Pydantic SettingsConfigDict

---

## Testing Your Plugin

### Test Structure

```
tests/
├── __init__.py
├── test_handler.py          # Handler interface tests
├── test_extraction.py       # Extraction logic tests
├── test_chunking.py         # Chunking strategy tests
├── test_config.py           # Configuration validation tests
└── fixtures/
    ├── valid.myformat
    ├── empty.myformat
    ├── corrupt.myformat
    └── large.myformat
```

### Unit Test Example

```python
# tests/test_handler.py
import pytest
from pathlib import Path
from krag_plugin_myformat.handler import MyFormatHandler


@pytest.fixture
def handler():
    """Create handler instance for testing."""
    handler = MyFormatHandler()
    handler.initialize(config=None, context=None)
    return handler


@pytest.fixture
def sample_file(tmp_path):
    """Create sample MyFormat file."""
    file_path = tmp_path / "test.myformat"
    file_path.write_text("Sample content\nLine 2\nLine 3")
    return file_path


class TestMyFormatHandler:
    """Test MyFormat plugin handler."""
    
    def test_supported_extensions(self, handler):
        """Handler reports correct extensions."""
        extensions = handler.supported_extensions()
        assert '.myformat' in extensions
        assert '.myfmt' in extensions
    
    def test_extract_text_basic(self, handler, sample_file):
        """Basic text extraction works."""
        text = handler.extract_text(sample_file)
        assert "Sample content" in text
        assert "Line 2" in text
    
    def test_extract_text_empty_file(self, handler, tmp_path):
        """Empty files handled gracefully."""
        empty_file = tmp_path / "empty.myformat"
        empty_file.write_text("")
        
        text = handler.extract_text(empty_file)
        assert text == ""
    
    def test_extract_metadata(self, handler, sample_file):
        """Metadata extraction returns expected fields."""
        metadata = handler.extract_metadata(sample_file)
        
        assert 'line_count' in metadata
        assert metadata['line_count'] == 3
    
    def test_missing_file_raises(self, handler):
        """Missing files raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            handler.extract_text(Path("/nonexistent.myformat"))
    
    def test_initialize_with_config(self):
        """Plugin accepts configuration."""
        handler = MyFormatHandler()
        config = {
            'max_file_size_mb': 100,
            'extract_images': True
        }
        handler.initialize(config=config, context=None)
        
        assert handler.max_file_size == 100 * 1024 * 1024
        assert handler.extract_images is True
```

### Integration Test Example

```python
# tests/test_integration.py
import pytest
from pathlib import Path
from krag.plugins.registry import PluginRegistry
from krag.models.configuration import PluginConfiguration


@pytest.fixture
def plugin_registry():
    """Create plugin registry for integration tests."""
    config = PluginConfiguration(
        enabled_plugins=["myformat"],
        disabled_plugins=[]
    )
    return PluginRegistry(config)


def test_plugin_discovery(plugin_registry):
    """Plugin is discovered via entry points."""
    discovered = plugin_registry.discover_plugins()
    plugin_names = [p.name for p in discovered]
    assert "myformat" in plugin_names


def test_plugin_loading(plugin_registry):
    """Plugin loads successfully."""
    plugin_registry.discover_plugins()
    handler = plugin_registry.load_plugin("myformat")
    
    assert handler is not None
    assert handler.name == "myformat"


def test_file_indexing(plugin_registry, sample_file):
    """Plugin integrates with indexing pipeline."""
    plugin_registry.discover_plugins()
    handler = plugin_registry.get_handler_for_extension(".myformat", None)
    
    assert handler is not None
    
    # Test extraction
    text = handler.extract_text(sample_file)
    assert text
    
    metadata = handler.extract_metadata(sample_file)
    assert isinstance(metadata, dict)
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=krag_plugin_myformat --cov-report=html

# Run specific test file
pytest tests/test_handler.py

# Run specific test
pytest tests/test_handler.py::TestMyFormatHandler::test_extract_text_basic

# Run with verbose output
pytest -v

# Run with print statements visible
pytest -s
```

### Test Coverage Goals

Aim for **>80% code coverage**:

```bash
# Generate coverage report
pytest --cov=krag_plugin_myformat --cov-report=term-missing

# View detailed HTML report
pytest --cov=krag_plugin_myformat --cov-report=html
open htmlcov/index.html
```

---

## Best Practices

### Code Quality

1. **Type hints**: Use type annotations for all public methods
2. **Docstrings**: Document all public classes and methods
3. **Error handling**: Catch specific exceptions, not bare `except:`
4. **Logging**: Use `context.logger` for informative messages
5. **Testing**: Write tests before implementation (TDD)

### Performance

1. **Lazy initialization**: Defer expensive setup until needed
2. **Stream large files**: Don't load entire file into memory
3. **Cache metadata**: Parse once, cache results if called multiple times
4. **Respect limits**: Check file size before processing
5. **Timeout operations**: Add timeouts to external calls

### Security

1. **Validate inputs**: Check file paths, sizes, formats
2. **Sanitize output**: Strip dangerous content from extracted text
3. **Limit resources**: Implement max file size, max processing time
4. **Handle malformed files**: Don't crash on corrupt input
5. **Permission checks**: Respect file permissions

### User Experience

1. **Informative errors**: Error messages should guide users to solutions
2. **Configuration discovery**: Support common config patterns
3. **Sensible defaults**: Work out-of-the-box without configuration
4. **Progress feedback**: Log progress for long-running operations
5. **Documentation**: Provide README with examples

---

## Troubleshooting

### Plugin Not Discovered

**Symptom**: `krag plugin list` doesn't show your plugin

**Solutions**:

1. **Check entry point registration**:
   ```bash
   # Verify entry point is registered
   python -c "from importlib.metadata import entry_points; print([ep for ep in entry_points()['krag.plugins']])"
   ```

2. **Reinstall plugin**:
   ```bash
   uv pip uninstall krag-plugin-myformat
   uv pip install -e .
   ```

3. **Check plugin name**: Entry point name must match `handler.name` property

4. **Verify krag version**: Plugin API might not match krag version

### Plugin Fails to Load

**Symptom**: Plugin appears in `krag plugin list` but status shows "error"

**Solutions**:

1. **Check logs**:
   ```bash
   krag index --verbose
   # Look for plugin load errors
   ```

2. **Test import manually**:
   ```python
   from krag_plugin_myformat.handler import MyFormatHandler
   handler = MyFormatHandler()
   ```

3. **Check API version**: Verify `required_api_version` matches krag API

4. **Validate dependencies**: Ensure all plugin dependencies are installed

### Extraction Fails

**Symptom**: Files not indexed, errors in logs

**Solutions**:

1. **Test extraction directly**:
   ```python
   from pathlib import Path
   from krag_plugin_myformat.handler import MyFormatHandler
   
   handler = MyFormatHandler()
   handler.initialize(None, None)
   
   text = handler.extract_text(Path("test.myformat"))
   print(text)
   ```

2. **Check file format**: Verify file is valid MyFormat

3. **Review error logs**: Look for specific exception messages

4. **Test with minimal file**: Create simplest possible valid file

### Configuration Not Applied

**Symptom**: Plugin ignores configuration from config.toml

**Solutions**:

1. **Verify config location**:
   ```bash
   # Check config file location
   ls ~/.config/krag/config.toml
   ```

2. **Check config syntax**:
   ```bash
   # Validate TOML syntax
   python -c "import tomli; tomli.load(open('~/.config/krag/config.toml', 'rb'))"
   ```

3. **Verify section name**: Section must be `[plugins.{plugin_name}]`

4. **Check initialization**: Print config in `initialize()` to debug

### Performance Issues

**Symptom**: Plugin extraction is very slow

**Solutions**:

1. **Profile extraction**:
   ```python
   import cProfile
   import pstats
   
   cProfile.run('handler.extract_text(file_path)', 'profile_stats')
   stats = pstats.Stats('profile_stats')
   stats.sort_stats('cumulative').print_stats(20)
   ```

2. **Check file size**: Large files take longer

3. **Optimize parsing**: Use faster libraries or binary formats

4. **Add timeout**: Prevent hang on problematic files

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `No module named 'krag_plugin_...'` | Plugin not installed | Run `uv pip install -e .` |
| `Entry point not found` | Entry point misconfigured | Check `pyproject.toml` |
| `API version mismatch` | Plugin incompatible with krag | Update plugin or krag |
| `FileTypeHandler must implement...` | Missing required method | Implement all abstract methods |
| `Config validation failed` | Invalid configuration | Check config against schema |
| `Plugin disabled due to error` | Initialization failed | Check logs for initialization error |

### Getting Help

1. **Check logs**: Run with `--verbose` flag
2. **Review contract tests**: Run `pytest tests/contract/`
3. **Search documentation**: Check this guide and krag docs
4. **Community support**: Ask in krag discussions/issues
5. **Debug mode**: Enable debug logging in krag

---

## Additional Resources

- **Plugin Examples**: See `examples/krag-plugin-markdown/` and `examples/krag-plugin-logs/`
- **krag Documentation**: https://github.com/kennethreitz/krag
- **Entry Points Guide**: https://packaging.python.org/en/latest/specifications/entry-points/
- **Pydantic Documentation**: https://docs.pydantic.dev/

---

## Appendix: Quick Reference

### Minimal Plugin Template

```python
from abc import abstractmethod
from pathlib import Path
from typing import Any

from krag.plugins.interfaces import FileTypeHandler
from krag.plugins.context import PluginContext

class MinimalHandler(FileTypeHandler):
    """Minimal file type handler example."""
    
    @property
    def name(self) -> str:
        return "minimal"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def required_api_version(self) -> str:
        return "1.0.0"
    
    def supported_extensions(self) -> list[str]:
        return [".min"]
    
    def extract_text(self, file_path: Path) -> str:
        return file_path.read_text()
    
    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        return {"file_name": file_path.name}
```

### Complete Interface Checklist

- [ ] `name` property implemented
- [ ] `version` property implemented
- [ ] `required_api_version` property implemented
- [ ] `supported_extensions()` returns non-empty list
- [ ] `extract_text()` implemented and tested
- [ ] `extract_metadata()` implemented and tested
- [ ] `get_chunking_strategy()` returns appropriate value
- [ ] `initialize()` stores config and context
- [ ] `cleanup()` releases resources
- [ ] `config_schema()` returns Pydantic model (if configurable)
- [ ] Entry point registered in pyproject.toml
- [ ] Tests cover >80% of code
- [ ] README documents plugin usage
- [ ] Error handling includes failure reporting

---

**Document Version**: 1.0.0  
**Last Updated**: February 11, 2026  
**Maintainer**: krag Plugin Team
