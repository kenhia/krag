# Quickstart: Code-Aware Indexing

## Prerequisites

- krag v0.1.0+ installed
- Python 3.11+
- NVIDIA GPU recommended (CPU fallback available)
- ~2 GB disk for embedding model download
- ~5.4 GB disk for code LLM download (optional)

## 1. Install the Code Plugin

```bash
# From the krag repo root:
cd examples/krag-plugin-code
uv pip install -e .

# This also installs tree-sitter + tree-sitter-python + tree-sitter-rust
```

Verify installation:
```bash
krag plugin list
```

Expected output:
```
Plugins:
  ✅ code (v0.1.0) — .py, .rs
  ...
```

## 2. Download the Code Embedding Model

The code plugin declares `jinaai/jina-embeddings-v2-base-code` as its preferred embedding model. It will be automatically downloaded on first `krag index`.

To pre-download:
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('jinaai/jina-embeddings-v2-base-code')"
```

## 3. Index a Code Project

```bash
# Configure krag to index your project
krag config set directories.paths '["~/my-project/src"]'

# Run indexing
krag index
```

The code plugin will:
- Parse `.py` and `.rs` files with tree-sitter
- Chunk code into semantic units (functions, classes, methods)
- Embed code chunks with the code embedding model
- Embed text files with the default text embedding model
- Store both in Qdrant with named vectors

## 4. Query

```bash
# Basic code query
krag query "how does the retriever handle deduplication?"

# With code prompt preset
krag query --preset code "what does the _deduplicate method do?"
```

## 5. Optional: Code LLM Setup

For improved code-specific answers, download and configure the code LLM:

```bash
# Download Qwen2.5-Coder-7B (requires huggingface-cli or manual download)
# Place the GGUF file at a known path

# Configure in config.toml:
krag config set llm.code_model "/path/to/qwen2.5-coder-7b-instruct-q5_k_m.gguf"
```

### Using the Code LLM

```bash
# Explicit switch
krag query --llm code "explain the Retriever class"

# Or enable auto-routing (requires sufficient VRAM for both LLMs)
krag config set llm.load_multi_llm true
krag query "explain the Retriever class"  # auto-routes to code LLM
```

## Configuration Reference

### Plugin Settings (config.toml)

```toml
[plugins.code]
code_chunk_size = 2048       # Max chunk size in chars (default: 2048)
# languages = ["python"]     # Restrict to specific languages (default: all installed)
```

### LLM Settings (config.toml)

```toml
[llm]
model = "/path/to/phi3-medium-q5_k_m.gguf"           # Text LLM (existing)
code_model = "/path/to/qwen2.5-coder-7b-q5_k_m.gguf" # Code LLM (new)
load_multi_llm = false    # true = try to load both simultaneously
```

### Prompt Settings (config.toml)

```toml
[prompt]
preset = "balanced"   # Default preset for text queries
# The "code" preset is auto-applied when routing to code LLM
# Set preset = "code" to force code preset for all queries
```

## Adding Language Support

Install additional tree-sitter grammars to support more languages:

```bash
uv pip install tree-sitter-javascript tree-sitter-go tree-sitter-c

# Verify
krag plugin list
# code (v0.1.0) — .py, .rs, .js, .go, .c
```

No plugin code changes needed — grammars are discovered dynamically.

## Troubleshooting

### "VRAM insufficient for simultaneous models"

This warning means your GPU can't hold both embedding models at once. Indexing falls back to sequential two-pass mode (slower but works). No action needed.

### "VRAM insufficient for multi-LLM mode, falling back to hot-swap"

This means `load_multi_llm = true` but both LLMs don't fit. Use `--llm code` or `--llm text` to select the LLM per query.

### Code chunks are character-split, not function-level

Check that:
1. The code plugin is installed: `krag plugin list`
2. The file type is supported: `.py` and `.rs` initially
3. Tree-sitter grammar is installed: `python -c "import tree_sitter_python"`

### Query results don't show line numbers

Code metadata is only present for chunks created by the code plugin. Re-index after installing the plugin:
```bash
krag index --force
```
