# krag

**Personal Multimodal RAG System - Phase 1: Text Indexing and Retrieval**

A local-first system for indexing personal files (PC and NAS storage) and querying them using natural language with LLM-synthesized answers.

## Features

- 🗂️ **File Discovery**: Recursively scan directories with configurable inclusion/exclusion patterns
- 📝 **Text Extraction**: Support for plain text, markdown, source code, JSON, YAML, XML, CSV
- 🧩 **Smart Chunking**: Semantic-aware text chunking that preserves context boundaries
- 🔢 **Vector Embeddings**: Local embedding generation using sentence-transformers
- 💾 **Vector Storage**: Qdrant embedded mode for high-performance similarity search
- 🔍 **Natural Language Query**: Ask questions in plain language
- 🤖 **LLM Synthesis**: Local LLM generates coherent answers from retrieved content
- ⚡ **Incremental Updates**: Re-index only new or modified files
- ⚙️ **Flexible Configuration**: Customize directories, file types, chunking, models

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- 4GB+ RAM for embedding models and LLM
- Storage space for vector embeddings (~1-2GB per 10k documents)

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd krag

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e ".[dev]"
```

### Initialize

```bash
# Create configuration and storage
krag init

# Edit configuration to add your directories
# Default location: ~/.config/krag/config.toml
```

### Index Your Files

```bash
# Run initial indexing
krag index

# Subsequent incremental updates
krag index --incremental
```

### Query Your Knowledge Base

```bash
# Ask a question
krag query "What are the main features of my project?"

# Show source information
krag query "How do I configure logging?" --show-sources

# Return JSON output
krag query "List all Python dependencies" --format json
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
uv sync --all-extras

# Run pre-commit validation
uv run ruff format .
uv run ruff check --fix .
uv run pytest
```

### Run Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# With coverage report
uv run pytest --cov=src/krag --cov-report=html
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check --fix .

# Type check
uv run mypy src/
```

## Configuration

Configuration file location: `~/.config/krag/config.toml`

Key settings:
- `directory_paths`: Directories to index
- `exclusion_patterns`: Glob patterns to exclude
- `supported_file_types`: File extensions to process
- `chunk_size` / `chunk_overlap`: Chunking parameters
- `embedding_model`: sentence-transformers model name
- `llm_model_path`: Path to local GGUF model

See [docs/configuration.md](docs/configuration.md) for full details.

## Architecture

```
Discovery → Extraction → Chunking → Embedding → Storage
                                                    ↓
Query → Embedding → Retrieval ← ← ← ← ← ← ← ← ← ← ┘
  ↓
LLM Synthesis → Answer
```

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

## Performance Targets

- Index 10,000 files in <30 minutes
- Query response in <10 seconds (95th percentile)
- Incremental re-indexing of 1% changes in <5% of full indexing time

## License

MIT

## Roadmap

**Phase 1** (Current): Text indexing and retrieval
**Phase 2**: Image indexing and multimodal retrieval
**Phase 3**: 3D model indexing
**Phase 4**: Audio/video content processing
