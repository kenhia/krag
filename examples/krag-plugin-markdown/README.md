# krag Markdown Plugin

A file type plugin for krag that provides indexing support for Markdown files (.md).

## Features

- **Text Extraction**: Strips Markdown syntax while preserving readable content
- **Frontmatter Support**: Parses YAML frontmatter for rich metadata
- **Default Chunking**: Uses krag's default text chunking strategy
- **Simple Integration**: No additional configuration required

## Installation

### Development Mode

```bash
# From the plugin directory
pip install -e .
```

### From Source

```bash
pip install git+https://github.com/yourusername/krag-plugin-markdown.git
```

### From PyPI (when published)

```bash
pip install krag-plugin-markdown
```

## Usage

Once installed, the plugin is automatically discovered by krag. Markdown files (.md) will be indexed automatically when you run:

```bash
krag index /path/to/docs
```

## Supported Formats

- `.md` - Markdown files with optional YAML frontmatter

## Metadata Extraction

The plugin extracts the following metadata from YAML frontmatter:

- `title`: Document title
- `author`: Document author
- `date`: Creation or publication date
- `tags`: List of tags
- Any additional frontmatter fields are stored as custom metadata

### Example Markdown File

```markdown
---
title: Getting Started Guide
author: Jane Doe
date: 2024-01-15
tags: [documentation, tutorial]
category: guides
---

# Getting Started

This is the main content of the document...
```

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .
```

## Architecture

This plugin demonstrates the simplest plugin architecture:

- **No custom chunking**: Returns `None` from `get_chunking_strategy()` to use krag's default `TextChunker`
- **Basic text extraction**: Removes Markdown syntax for clean text
- **Metadata parsing**: Extracts structured data from frontmatter

For more complex use cases (custom chunking, specialized tokenization), see the `krag-plugin-logs` example.

## License

MIT
