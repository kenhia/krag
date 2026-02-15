# Quickstart: Plugin Architecture

**Feature**: 002-plugin-architecture  
**Date**: 2026-02-07  
**Audience**: Plugin Users & Plugin Developers

---

## For Plugin Users

### Installing a Plugin

Plugins are standard Python packages installed via pip/uv:

```bash
# Install a plugin
uv pip install krag-plugin-pdf

# Or with optional dependencies
uv pip install krag-plugin-pdf[ocr]

# Install multiple plugins
uv pip install krag-plugin-pdf krag-plugin-docx krag-plugin-code
```

### Verifying Installation

```bash
# List all discovered plugins
krag plugin list

# Output:
# Name      Version  Status   Extensions
# --------  -------  -------  -----------
# pdf       1.0.0    enabled  .pdf, .PDF
# docx      1.2.0    enabled  .docx, .DOCX
# markdown  1.0.0    enabled  .md, .markdown
```

### Installing from Local Source

For development or testing plugins locally:

```bash
# Install a plugin in editable mode via krag CLI
krag plugin install -e ./my-plugin

# Or directly with uv pip
uv pip install -e ./my-plugin
```

### Using Plugins

Plugins work automatically once installed:

```bash
# Index directory with PDF and DOCX files
krag index ~/documents

# krag automatically detects file types and uses appropriate plugins
# Output:
# Indexing ~/documents...
# ✓ text_file.txt (builtin handler)
# ✓ manual.pdf (pdf plugin)
# ✓ report.docx (docx plugin)
# ✓ notes.md (markdown plugin)
# Indexed 4 files in 12.5s
```

### Configuring Plugins

Edit `~/.config/krag/config.toml`:

```toml
[plugins]
# Explicitly enable only certain plugins (optional)
enabled = ["pdf", "docx"]

# Disable specific plugins
disabled = ["markdown"]  # Use builtin text handler instead

[plugins.pdf]
# Plugin-specific settings
extract_images = false
ocr_enabled = false
max_pages = 1000
timeout_seconds = 30

[plugins.docx]
extract_comments = true
include_headers_footers = true
```

### Managing Plugins

```bash
# List enabled plugins
krag plugin list --enabled

# Show plugin details
krag plugin info pdf

# Disable a plugin
krag plugin disable markdown

# Enable a plugin
krag plugin enable pdf

# Validate plugin configuration
krag plugin validate
```

---

## For Plugin Developers

### Minimal Plugin Example

**File: `krag_plugin_markdown/handler.py`**

```python
from pathlib import Path
from typing import Any
from krag.plugins.interfaces import FileTypeHandler, ChunkingStrategy

class MarkdownFileTypeHandler(FileTypeHandler):
    """Simple markdown plugin using krag's default chunking"""
    
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
        return [".md", ".markdown", ".MD", ".MARKDOWN"]
    
    def extract_text(self, file_path: Path) -> str:
        """Extract text with basic markdown syntax stripping"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic markdown cleanup
        import re
        content = re.sub(r'#+\s*', '', content)  # Remove headers
        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)  # Bold
        content = re.sub(r'\*([^*]+)\*', r'\1', content)  # Italic
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)  # Links
        
        return content
    
    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract YAML frontmatter if present"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                import yaml
                try:
                    return yaml.safe_load(parts[1]) or {}
                except:
                    pass
        
        return {}
    
    def get_chunking_strategy(self) -> ChunkingStrategy | None:
        """Use krag's default chunker"""
        return None
```

**File: `pyproject.toml`**

```toml
[project]
name = "krag-plugin-markdown"
version = "1.0.0"
description = "Markdown file support for krag"
requires-python = ">=3.11"
dependencies = [
    "krag>=0.1.0",
    "pyyaml>=6.0.0",
]

[project.entry-points."krag.plugins"]
markdown = "krag_plugin_markdown.handler:MarkdownFileTypeHandler"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Testing Your Plugin

```python
# tests/test_markdown_handler.py
import pytest
from pathlib import Path
from krag_plugin_markdown.handler import MarkdownFileTypeHandler

def test_markdown_extraction(tmp_path):
    # Create test file
    test_file = tmp_path / "test.md"
    test_file.write_text("# Title\n\nThis is **bold** text.")
    
    # Test plugin
    handler = MarkdownFileTypeHandler()
    text = handler.extract_text(test_file)
    
    assert "Title" in text
    assert "bold" in text
    assert "**" not in text  # Markdown syntax stripped

def test_metadata_extraction(tmp_path):
    # Create test file with frontmatter
    test_file = tmp_path / "test.md"
    test_file.write_text("""---
title: Test Document
author: Jane Doe
---

# Content
""")
    
    handler = MarkdownFileTypeHandler()
    metadata = handler.extract_metadata(test_file)
    
    assert metadata["title"] == "Test Document"
    assert metadata["author"] == "Jane Doe"
```

### Custom Chunking Example

**File: `krag_plugin_logs/handler.py`**

```python
import re
from pathlib import Path
from typing import Any
from krag.plugins.interfaces import FileTypeHandler
from krag.extraction.chunker import TextChunker

class LogFileChunker(TextChunker):
    """Chunk log files by timestamp boundaries"""
    
    def __init__(self, timestamp_pattern: str = r'^\[\d{4}-\d{2}-\d{2}'):
        self.pattern = re.compile(timestamp_pattern, re.MULTILINE)
    
    def chunk_text(self, text: str) -> list[str]:
        matches = list(self.pattern.finditer(text))
        
        if not matches:
            return [text] if text else []
        
        chunks = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunks.append(text[start:end].strip())
        
        return chunks

class LogFileHandler(FileTypeHandler):
    """Log file plugin with custom chunking"""
    
    @property
    def name(self) -> str:
        return "logs"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def required_api_version(self) -> str:
        return "1.0.0"
    
    def supported_extensions(self) -> list[str]:
        return [".log", ".LOG"]
    
    def extract_text(self, file_path: Path) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        # Extract log statistics
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return {
            "line_count": content.count('\n'),
            "error_count": content.lower().count('error'),
            "warning_count": content.lower().count('warning'),
        }
    
    def get_chunking_strategy(self) -> TextChunker:
        """Provide custom log file chunker"""
        return LogFileChunker()
```

### Plugin with Configuration

```python
class PDFFileHandler(FileTypeHandler):
    def __init__(self):
        self.max_pages = 1000
        self.ocr_enabled = False
    
    def initialize(self, config: dict[str, Any]) -> None:
        """Called once after plugin loads"""
        self.max_pages = config.get("max_pages", 1000)
        self.ocr_enabled = config.get("ocr_enabled", False)
        
        if self.max_pages < 1:
            from krag.plugins.exceptions import PluginConfigurationError
            raise PluginConfigurationError(
                "max_pages must be positive",
                plugin_name=self.name
            )
    
    def extract_text(self, file_path: Path) -> str:
        # Use self.max_pages and self.ocr_enabled
        pass
```

### Plugin with Resource Cleanup

```python
class DatabasePluginHandler(FileTypeHandler):
    def initialize(self, config: dict[str, Any]) -> None:
        """Open database connection"""
        self.db_connection = open_database(config["db_path"])
    
    def cleanup(self) -> None:
        """Called at krag shutdown"""
        if hasattr(self, 'db_connection'):
            self.db_connection.close()
```

---

## Development Workflow

### 1. Create Plugin Package

```bash
# Create package structure
mkdir -p krag-plugin-myformat/src/krag_plugin_myformat
cd krag-plugin-myformat

# Create files
touch src/krag_plugin_myformat/__init__.py
touch src/krag_plugin_myformat/handler.py
touch pyproject.toml
touch README.md
```

### 2. Implement Handler

See examples above. Key requirements:
- Inherit from `FileTypeHandler`
- Implement all abstract methods
- Return valid types
- Handle errors gracefully

### 3. Add Entry Point

In `pyproject.toml`:
```toml
[project.entry-points."krag.plugins"]
myformat = "krag_plugin_myformat.handler:MyFormatHandler"
```

### 4. Write Tests

```bash
# Create test directory
mkdir tests
touch tests/test_handler.py

# Run tests
uv run pytest tests/
```

### 5. Install in Development Mode

```bash
# Install plugin for local testing
uv pip install -e .

# Verify krag sees your plugin
krag plugin list
```

### 6. Test with krag

```bash
# Create test corpus
mkdir test_files
echo "test content" > test_files/test.myformat

# Index with your plugin
krag index test_files/

# Query to verify
krag query "test content"
```

### 7. Publish Plugin

```bash
# Build package
uv build

# Publish to PyPI
uv publish
```

---

## Common Patterns

### Pattern 1: Binary File Handling

```python
def extract_text(self, file_path: Path) -> str:
    try:
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        # Parse binary format
        text = parse_binary_format(binary_content)
        
        return text
    except Exception as e:
        from krag.plugins.exceptions import PluginExtractionError
        raise PluginExtractionError(
            f"Failed to parse {file_path}",
            plugin_name=self.name,
            file_path=file_path,
            original_exception=e
        )
```

### Pattern 2: Optional Dependencies

```toml
# pyproject.toml
[project.optional-dependencies]
ocr = ["pytesseract>=0.3.0"]
advanced = ["pillow>=10.0.0", "numpy>=1.24.0"]
```

```python
def initialize(self, config: dict[str, Any]) -> None:
    if config.get("ocr_enabled"):
        try:
            import pytesseract
            self.ocr = pytesseract
        except ImportError:
            from krag.plugins.exceptions import PluginDependencyError
            raise PluginDependencyError(
                "OCR requires pytesseract: pip install krag-plugin-pdf[ocr]",
                plugin_name=self.name
            )
```

### Pattern 3: File Type Validation

```python
def can_handle_file(self, file_path: Path) -> bool:
    """Verify file is actually a PDF by checking magic bytes"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
        return header == b'%PDF'
    except:
        return False
```

### Pattern 4: Progress Reporting

```python
def extract_text(self, file_path: Path) -> str:
    import logging
    logger = logging.getLogger(__name__)
    
    with open(file_path, 'rb') as f:
        pages = extract_pages(f)
    
    text_parts = []
    for i, page in enumerate(pages):
        if i % 10 == 0:
            logger.info(f"Processing page {i+1}/{len(pages)}")
        text_parts.append(extract_text_from_page(page))
    
    return '\n'.join(text_parts)
```

---

## Debugging Tips

### Enable Debug Logging

```bash
# Set log level in config.toml
[logging]
level = "DEBUG"

# Or via environment variable
KRAG_LOG_LEVEL=DEBUG krag index ~/documents
```

### Test Plugin Isolation

```python
# Test plugin without krag
from krag_plugin_myformat.handler import MyFormatHandler

handler = MyFormatHandler()
handler.initialize({})

text = handler.extract_text("test.myformat")
print(text)
```

### Check Plugin Discovery

```bash
# See what krag discovers
krag plugin list --all

# Validate plugin compatibility
krag plugin validate

# Show detailed plugin info
krag plugin info myformat
```

---

## Best Practices

### DO:
- ✅ Handle encoding errors gracefully
- ✅ Return empty dict for metadata when none available
- ✅ Log informative messages during processing
- ✅ Validate configuration in `initialize()`
- ✅ Document plugin configuration options
- ✅ Write comprehensive tests
- ✅ Use semantic versioning

### DON'T:
- ❌ Raise exceptions for empty files (return "" instead)
- ❌ Modify files during extraction
- ❌ Cache large objects in plugin instance
- ❌ Assume specific krag version beyond API version
- ❌ Use blocking I/O without timeouts
- ❌ Print to stdout/stderr (use logging)

---

## API Versioning

### Plugin API Compatibility

Current API version: **1.0.0**

Your plugin declares compatibility:
```python
@property
def required_api_version(self) -> str:
    return "1.0.0"  # Requires at least 1.0.0
```

Version compatibility rules:
- **Major version** (1.x → 2.x): Breaking changes
- **Minor version** (1.0 → 1.1): New features, backward compatible
- **Patch version** (1.0.0 → 1.0.1): Bug fixes

### Future-Proofing

```python
def get_chunking_strategy(self):
    # Request future feature that falls back gracefully
    return ChunkingStrategy.SEMANTIC  # Falls back to DEFAULT if not available
```

---

## Resources

- **Plugin API Documentation**: See `contracts/` directory
- **Data Models**: See `data-model.md`
- **Example Plugins**: 
  - `krag-plugin-markdown` (simple, default chunking)
  - `krag-plugin-logs` (custom chunking)
- **Community Plugins**: [krag-plugins GitHub topic](https://github.com/topics/krag-plugin)

---

## Getting Help

- **Plugin Development**: Open issue with "[plugin]" label
- **Plugin Bugs**: Report in plugin's repository
- **API Questions**: Check contracts documentation
- **Feature Requests**: Open discussion in krag repository
