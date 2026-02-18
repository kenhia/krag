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
- 🧠 **Code-Aware Indexing**: AST-based chunking via tree-sitter, code-specialized embeddings, multi-LLM routing with hot-swap
- 🔌 **Plugin System**: Extend with custom file type handlers for PDF, DOCX, logs, and more

## Prerequisites

- Python 3.11+ (tested on 3.11, 3.12, 3.13)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- 4GB+ RAM for embedding models and LLM
- Storage space for vector embeddings (~1-2GB per 10k documents)
- **Optional**: NVIDIA GPU with CUDA for accelerated LLM inference

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

### Tool Installation (Optional)

To install krag as a globally available command-line tool:

```bash
# Install from local project directory
uv tool install --with pip --reinstall --force -e /path/to/krag

# For GPU acceleration (NVIDIA CUDA), rebuild llama-cpp-python with CUDA support:
CMAKE_ARGS="-DGGML_CUDA=on" ~/.local/share/uv/tools/krag/bin/pip install llama-cpp-python --force-reinstall --no-cache-dir
```

**Note**: The default PyPI wheel for `llama-cpp-python` is CPU-only. GPU users must rebuild from source with CUDA support as shown above.

### Initialize

```bash
# Create configuration and storage (uses XDG directories)
krag init

# Edit configuration to add your directories
# Default location: ~/.config/krag/config.toml
# Or $XDG_CONFIG_HOME/krag/config.toml
```

**Directory Structure (XDG Base Directory Compliant)**:
- Configuration: `~/.config/krag/` (or `$XDG_CONFIG_HOME/krag/`)
- Cache (models, vector store): `~/.cache/krag/` (or `$XDG_CACHE_HOME/krag/`)
- State (logs, metadata): `~/.local/state/krag/` (or `$XDG_STATE_HOME/krag/`)

**Automatic Migration**: Existing `~/.krag/` installations are automatically migrated to XDG directories on first run. Use `--legacy-paths` flag to revert to old structure if needed.

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

Configuration file location: `~/.config/krag/config.toml` (or `$XDG_CONFIG_HOME/krag/config.toml`)

**XDG Base Directory Compliance**:
- Config files: `~/.config/krag/`
- Cache data (models, vector store): `~/.cache/krag/`
- State data (logs, indexed file metadata): `~/.local/state/krag/`

Key settings:
- `directory_paths`: Directories to index
- `exclusion_patterns`: Glob patterns to exclude
- `supported_file_types`: File extensions to process
- `chunk_size` / `chunk_overlap`: Chunking parameters
- `embedding_model`: Embedding model name (default: BAAI/bge-base-en-v1.5)
- `llm_model`: HuggingFace model name or local GGUF path
- `path_aliases`: Display path reductions (e.g., `/home/ken:~`)

**Custom Storage Paths** (optional):

```toml
[storage]
vector_store_path = "/krag/index"
model_cache_path = "/krag/models"
corpus_cache_path = "/krag/corpus"
logs_path = "/krag/logs"
```

**GPU Acceleration** (optional):

```toml
[llm]
n_gpu_layers = -1  # Full GPU offload (-1), partial (24), or CPU-only (0)
```

See [docs/configuration.md](docs/configuration.md) for full details.

## GPU Acceleration

krag supports GPU-accelerated LLM inference via CUDA:

```bash
# Check GPU status
krag gpu status

# Get recommended GPU settings
krag gpu recommend

# Show GPU configuration
krag config show --gpu-only

# Show storage paths
krag config show --paths-only
```

**Verify GPU Support** (for tool installations):

After rebuilding `llama-cpp-python` with CUDA support, verify it's working:

```bash
# Check if GPU offload is supported in the tool environment
~/.local/share/uv/tools/krag/bin/python -c "from llama_cpp import llama_cpp as lib; print('GPU offload supported:', lib.llama_supports_gpu_offload())"

# Monitor GPU during a query (should show ~10-12GB VRAM and 50-90% utilization)
nvidia-smi dmon -s um -c 20 -d 1 &
krag query "test query" --top-k 3
```

See [docs/migration-guide.md](docs/migration-guide.md) for full GPU setup instructions.

## Plugin System

krag supports file type plugins for indexing specialized formats (PDF, DOCX, log files, etc.) that go beyond built-in text extraction.

### Installing Plugins

```bash
# Install a plugin package
uv pip install krag-plugin-markdown

# Install from local path (for development)
krag plugin install -e ./my-plugin
```

### Managing Plugins

```bash
# List installed plugins
krag plugin list

# Show plugin details
krag plugin info markdown

# Enable/disable plugins
krag plugin enable markdown
krag plugin disable markdown

# Validate all plugins
krag plugin validate
```

### Plugin Configuration

Plugins are configured in `config.toml`:

```toml
[plugins]
enabled = []   # Empty = all discovered plugins enabled
disabled = []  # Explicitly disabled plugins

# Per-plugin settings
[plugins.markdown]
strip_html = true

[plugins.logs]
chunking_strategy = "custom"
window_minutes = 5
```

### Developing Plugins

Create custom plugins to support new file formats. See [docs/plugin-development.md](docs/plugin-development.md) for the complete API reference and examples.

```python
from krag.plugins import FileTypeHandler

class MyHandler(FileTypeHandler):
    @property
    def name(self) -> str:
        return "my_format"

    def supported_extensions(self) -> list[str]:
        return [".myext"]

    def extract_text(self, file_path: Path) -> str:
        return file_path.read_text()

    def extract_metadata(self, file_path: Path) -> dict:
        return {"format": "my_format"}
```

See also: [docs/plugin-user-guide.md](docs/plugin-user-guide.md) for the user guide.

## Code-Aware Indexing

krag supports specialized code indexing via the `krag-plugin-code` plugin:

- **AST-based chunking**: tree-sitter parses Python and Rust into semantic units (functions, classes, methods)
- **Code embeddings**: uses `jinaai/jina-embeddings-v2-base-code` for code-optimized vectors
- **Multi-LLM routing**: routes queries to a code LLM (Qwen2.5-Coder) or text LLM (Phi-3) based on retrieved content
- **Hot-swap fallback**: single-GPU users get automatic model swapping when VRAM is limited
- **Enriched metadata**: query results include function names, class names, and line numbers
- **Code prompt preset**: `--preset code` for technically precise code Q&A

```bash
# Install the code plugin
cd examples/krag-plugin-code && uv pip install -e .

# Index and query
krag index
krag query --preset code "what does the _deduplicate method do?"
krag query --llm code "explain the Retriever class"
```

See [docs/plugin-user-guide.md](docs/plugin-user-guide.md) for detailed setup.

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
