# Plugin User Guide

A practical guide for installing, configuring, and managing krag file type plugins.

## Overview

krag plugins extend file indexing to support specialized formats like PDF, DOCX, log files, and other binary or structured file types. Plugins are Python packages that integrate seamlessly into the indexing pipeline.

## Installing Plugins

### From PyPI

```bash
# Using uv (recommended)
uv pip install krag-plugin-markdown
uv pip install krag-plugin-logs

# Using pip
pip install krag-plugin-markdown
```

### From Local Source (Development)

```bash
# Install in editable mode for development
krag plugin install -e ./path/to/plugin

# Or directly with uv
uv pip install -e ./path/to/plugin
```

### Verifying Installation

```bash
# List all discovered plugins
krag plugin list

# Check a specific plugin
krag plugin info markdown
```

## Configuring Plugins

Plugin configuration lives in your `config.toml` file (default: `~/.config/krag/config.toml`).

### Basic Configuration

```toml
[plugins]
enabled = []    # Empty list = all discovered plugins are enabled
disabled = []   # Explicitly disabled plugins
```

### Enabling Only Specific Plugins

```toml
[plugins]
enabled = ["markdown", "logs"]  # Only these plugins will be active
disabled = []
```

### Disabling Specific Plugins

```toml
[plugins]
enabled = []                # All plugins enabled by default
disabled = ["experimental"] # Except this one
```

### Per-Plugin Settings

Each plugin can have its own configuration section:

```toml
# Settings for the markdown plugin
[plugins.markdown]
strip_html = true
extract_frontmatter = true

# Settings for the logs plugin
[plugins.logs]
window_minutes = 5
chunking_strategy = "custom"

# Override chunking strategy for a plugin
[plugins.pdf]
chunking_strategy = "default"  # Force default chunking instead of custom
```

Available `chunking_strategy` overrides: `default`, `semantic`, `code_aware`.

## Managing Plugins via CLI

### List Plugins

```bash
# Basic listing
krag plugin list

# Verbose output (includes entry points)
krag plugin list --verbose
```

Output shows plugin name, version, enabled/disabled status, and supported file extensions.

### Plugin Information

```bash
krag plugin info markdown
```

Shows detailed metadata including:
- Version and API version compatibility
- Supported file extensions
- Current configuration values
- Description and author
- Any load errors

### Enable/Disable Plugins

```bash
# Disable a plugin (won't process its file types)
krag plugin disable markdown

# Re-enable a disabled plugin
krag plugin enable markdown
```

Changes are persisted to `config.toml` automatically.

### Validate Plugins

```bash
krag plugin validate
```

Checks all configured plugins for:
- API version compatibility
- Missing dependencies
- Configuration validity
- Successful import

### Install Plugins

```bash
# Install from PyPI
krag plugin install krag-plugin-pdf

# Install from local path (editable mode for development)
krag plugin install -e ./my-plugin
```

## How Plugins Work During Indexing

1. **Discovery**: When `krag index` runs, the plugin registry discovers all installed plugins via Python entry points
2. **Extension Mapping**: Each plugin's supported file extensions are registered
3. **Lazy Loading**: Plugins are only loaded when a file matching their extensions is encountered
4. **Text Extraction**: The plugin's `extract_text()` method is called instead of the default text extractor
5. **Metadata Extraction**: The plugin's `extract_metadata()` provides format-specific metadata
6. **Chunking**: The plugin can specify a custom chunking strategy or use krag's default chunker
7. **Indexing**: Extracted text is chunked, embedded, and stored as usual

### Graceful Degradation

If a plugin fails during processing:
- The error is logged and recorded in the failure-to-index report
- The plugin is automatically disabled for the remainder of the run
- Remaining files continue to be processed
- A failure summary is displayed at the end of indexing

## File Extension Conflicts

When multiple plugins claim the same file extension, the first plugin in configuration order wins. You can control priority via the `enabled` list order:

```toml
[plugins]
# markdown_pro handles .md files (listed first = higher priority)
enabled = ["markdown_pro", "markdown_basic"]
```

## Common Workflows

### Adding a New Plugin

1. Install the plugin package: `uv pip install krag-plugin-pdf`
2. Verify discovery: `krag plugin list`
3. (Optional) Configure: Edit `config.toml` to add `[plugins.pdf]` settings
4. Re-index: `krag index` (or `krag index --incremental`)

### Updating a Plugin

1. Update the package: `uv pip install --upgrade krag-plugin-pdf`
2. Validate compatibility: `krag plugin validate`
3. Re-index affected files: `krag index --incremental`

### Removing a Plugin

1. Disable the plugin: `krag plugin disable pdf`
2. Uninstall the package: `uv pip uninstall krag-plugin-pdf`
3. (Optional) Remove config section from `config.toml`

## Code Plugin

The `krag-plugin-code` plugin adds code-aware indexing using tree-sitter AST parsing.

### Installation

```bash
# From the krag repo root:
cd examples/krag-plugin-code
uv pip install -e .
```

Verify installation:
```bash
krag plugin list
# ✅ code (v0.1.0) — .py, .rs
```

### What It Does

- Parses Python and Rust files using tree-sitter grammars
- Chunks code into semantic units (functions, classes, methods) instead of character-based splitting
- Embeds code chunks with a specialized code embedding model (`jinaai/jina-embeddings-v2-base-code`)
- Enriches chunks with code metadata: language, function name, class name, line numbers
- Metadata-aware score boosting ranks code chunks matching query symbols higher

### Configuration

```toml
[plugins.code]
code_chunk_size = 2048       # Max chunk size in chars (default: 2048)
# languages = ["python"]     # Restrict to specific languages (default: all installed)
```

### Code LLM Integration

For improved code-specific answers, configure the code LLM:

```toml
[llm]
code_model = "/path/to/qwen2.5-coder-7b-instruct-q5_k_m.gguf"
load_multi_llm = false    # true = try to load both simultaneously
```

Query with the code LLM:
```bash
krag query --llm code "explain the Retriever class"
```

### Adding Language Support

Install additional tree-sitter grammars:
```bash
uv pip install tree-sitter-javascript tree-sitter-go tree-sitter-c
```

No plugin code changes needed — grammars are discovered dynamically.

## See Also

- [Plugin Development Guide](plugin-development.md) — Create your own plugins
- [Architecture](architecture.md) — Plugin system architecture details
- [Troubleshooting](troubleshooting.md) — Common issues and solutions
