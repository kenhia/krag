# krag-plugin-code

Code-aware indexing plugin for [krag](https://github.com/your-org/krag). Uses tree-sitter AST parsing to chunk source code into complete semantic units — functions, methods, classes — instead of arbitrary character-based splits.

## Features

- **AST-based chunking**: Preserves complete function/method boundaries
- **Class context**: Method chunks include `# Class: ClassName` prefix for retrieval clarity
- **Import grouping**: Import statements grouped into a single chunk
- **Oversized splitting**: Functions exceeding `max_chunk_size` split at line boundaries
- **Graceful fallback**: Falls back to text-based chunking on parse errors
- **Multi-language**: Ships with Python and Rust support; auto-discovers installed tree-sitter grammars

## Supported Languages

| Language | Grammar Package | Extension |
|----------|----------------|-----------|
| Python   | `tree-sitter-python` | `.py` |
| Rust     | `tree-sitter-rust` | `.rs` |

Additional languages are auto-discovered if their `tree-sitter-<lang>` package is installed and provides a `.language()` function.

## Installation

```bash
# From the krag repository root:
uv pip install -e examples/krag-plugin-code

# Or with pip:
pip install -e examples/krag-plugin-code
```

The plugin registers as `code` via the `krag.plugins` entry point and will be automatically discovered by krag's plugin registry.

## Configuration

In your `krag.toml`:

```toml
[plugins.code]
max_chunk_size = 2048        # Max characters per chunk (default: 2048)
embedding_model = "default"  # Override embedding model (optional)
```

## Usage

Once installed, krag automatically uses the code plugin for supported file extensions:

```bash
# Index a Python project
krag index /path/to/python/project

# Query for specific functions
krag query "How does the parse_config function work?"
```

## How It Works

1. **File discovery**: krag's plugin registry routes supported extensions (`.py`, `.rs`) to the code handler
2. **AST parsing**: tree-sitter parses the source into a syntax tree
3. **Semantic extraction**: Functions, methods, classes, and imports are extracted as `SemanticUnit` objects
4. **Chunk conversion**: Each unit becomes a `TextChunk` with code-specific metadata (function name, class name, line numbers)
5. **Metadata injection**: The indexer stores code metadata in the vector payload for retrieval-time boosting

## Development

```bash
# Run code plugin tests
uv run pytest tests/unit/test_ast_chunker.py tests/unit/test_languages.py -v
uv run pytest tests/contract/test_code_plugin_contract.py tests/contract/test_ast_chunker_contract.py -v
uv run pytest tests/integration/test_code_indexing_pipeline.py -v
```
