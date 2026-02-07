# Quickstart Guide: Text-Based RAG System

**Feature**: 001-text-rag-indexing  
**Version**: 1.0.0  
**Audience**: Developers implementing the system

## Purpose

This guide provides step-by-step instructions for building and using the Text-Based RAG Indexing & Retrieval System from the ground up.

---

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows with WSL
- **Python**: 3.11 or higher
- **Memory**: 8GB RAM minimum (16GB recommended)
- **Storage**: 10GB free space (for models and vector storage)
- **CPU**: Modern multi-core processor (GPU optional but beneficial)

### Required Tools
```bash
# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

---

## Setup Steps

### 1. Initialize Project

```bash
# Create project directory
mkdir krag
cd krag

# Initialize Python project with uv
uv init --lib

# Create directory structure
mkdir -p src/krag/{cli,config,discovery,extraction,embeddings,storage,retrieval,synthesis,orchestration,models}
mkdir -p tests/{unit,integration,contract,fixtures/sample_files}
touch src/krag/__init__.py
```

### 2. Configure Dependencies

Create `pyproject.toml`:

```toml
[project]
name = "krag"
version = "0.1.0"
description = "Personal Multimodal RAG System - Text Indexing"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "sentence-transformers>=2.2.0",
    "qdrant-client>=1.7.0",
    "llama-cpp-python>=0.2.0",
    "llama-index-core>=0.10.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "rich>=13.0.0",
    "tomli>=2.0.0; python_version < '3.11'",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[project.scripts]
krag = "krag.cli.main:app"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"

[tool.mypy]
python_version = "3.11"
strict = true
```

Install dependencies:

```bash
uv sync
uv sync --extra dev
```

### 3. Implement Data Models

Create `src/krag/models/file_metadata.py`:

```python
from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field


class IndexingStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DELETED = "deleted"


class FileMetadata(BaseModel):
    file_path: Path
    file_size: int
    modification_time: datetime
    file_type: str
    content_hash: str
    indexing_status: IndexingStatus = IndexingStatus.PENDING
    last_indexed_at: datetime | None = None
    error_message: str | None = None
    chunk_count: int = 0
    
    class Config:
        use_enum_values = True
```

Implement remaining models in similar files:
- `text_chunk.py` - TextChunk model
- `embedding.py` - EmbeddingRecord model
- `query_result.py` - QueryResult model
- `indexing_job.py` - IndexingJob model
- `configuration.py` - Configuration model

### 4. Implement Configuration

Create `src/krag/config/settings.py`:

```python
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class KragConfig(BaseSettings):
    # Directories
    directory_paths: List[Path] = []
    exclusion_patterns: List[str] = [
        "node_modules", ".git", "__pycache__", 
        "build", "dist", ".venv", "venv"
    ]
    
    # File processing
    supported_file_types: List[str] = [
        ".py", ".md", ".txt", ".json", ".yaml", 
        ".yml", ".toml", ".ini", ".cfg", ".xml"
    ]
    max_file_size_mb: int = 100
    
    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    embedding_device: str = "cpu"
    
    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50
    
    # Vector store
    vector_store_path: Path = Path.home() / ".krag" / "storage"
    collection_name: str = "krag_embeddings"
    distance_metric: str = "cosine"
    
    # Retrieval
    top_k: int = 5
    
    # LLM
    llm_model: str = "microsoft/Phi-3-mini-4k-instruct-gguf"
    llm_context_size: int = 2048
    llm_num_threads: int = 4
    llm_temperature: float = 0.7
    
    # Path Reductions
    path_aliases: List[str] = []  # e.g., ["/home/ken:~", "/home/ken/src:src"]
    
    model_config = SettingsConfigDict(
        env_prefix="KRAG_",
        toml_file=Path.home() / ".config" / "krag" / "config.toml"  # XDG_CONFIG_HOME
    )
```

**Note**: The system follows XDG Base Directory specification:
- Config: `~/.config/krag/` (or `$XDG_CONFIG_HOME/krag/`)
- Cache: `~/.cache/krag/` (or `$XDG_CACHE_HOME/krag/`)
- State: `~/.local/state/krag/` (or `$XDG_STATE_HOME/krag/`)

### 5. Implement Core Modules (TDD)

Follow Test-Driven Development for each module:

**Example: File Scanner**

1. Write test first (`tests/unit/test_discovery.py`):

```python
import pytest
from pathlib import Path
from krag.discovery.scanner import FileScanner

def test_scanner_discovers_files(tmp_path):
    # Setup: Create test files
    (tmp_path / "test1.txt").write_text("content")
    (tmp_path / "test2.md").write_text("content")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("content")
    
    # Execute
    scanner = FileScanner(
        directory_paths=[tmp_path],
        exclusion_patterns=["node_modules"],
        supported_extensions=[".txt", ".md"]
    )
    files = scanner.scan()
    
    # Verify
    assert len(files) == 2
    file_paths = [f.file_path.name for f in files]
    assert "test1.txt" in file_paths
    assert "test2.md" in file_paths
    assert "lib.js" not in file_paths
```

2. Run test (should fail):
```bash
uv run pytest tests/unit/test_discovery.py -v
```

3. Implement `src/krag/discovery/scanner.py` until test passes

4. Refactor and repeat for next feature

### 6. Build CLI Interface

Create `src/krag/cli/main.py`:

```python
import typer
from rich.console import Console

app = typer.Typer(name="krag", help="Personal RAG System")
console = Console()


@app.command()
def init(
    config_dir: Path = typer.Option(Path.home() / ".krag"),
    force: bool = typer.Option(False, help="Overwrite existing config")
):
    """Initialize krag configuration."""
    if config_dir.exists() and not force:
        console.print("[red]Configuration already exists. Use --force to overwrite.[/red]")
        raise typer.Exit(1)
    
    config_dir.mkdir(parents=True, exist_ok=True)
    # ... implementation
    console.print(f"[green]✓[/green] Configuration initialized at {config_dir}")


@app.command()
def index(
    full: bool = typer.Option(False, help="Force full re-index"),
    dry_run: bool = typer.Option(False, help="Show what would be indexed")
):
    """Index files from configured directories."""
    # ... implementation


@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, help="Number of results to retrieve"),
    no_synthesis: bool = typer.Option(False, help="Skip LLM synthesis")
):
    """Query the indexed knowledge base."""
    # ... implementation


if __name__ == "__main__":
    app()
```

Test CLI locally:
```bash
uv run krag --help
uv run krag init
```

### 7. Integration Testing

Create `tests/integration/test_indexing_pipeline.py`:

```python
def test_end_to_end_indexing(tmp_path, test_config):
    # Setup: Create test corpus
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc1.md").write_text("# RAG System\nInformation retrieval...")
    (corpus / "doc2.py").write_text("def query():\n    pass")
    
    # Execute: Run full indexing pipeline
    orchestrator = IndexingOrchestrator(...)
    job = orchestrator.index_full()
    
    # Verify: Check results
    assert job.status == JobStatus.COMPLETED
    assert job.files_processed == 2
    assert job.chunks_generated > 0
    
    # Verify: Can query indexed content
    query_engine = QueryEngine(...)
    response = query_engine.query("What is a RAG system?")
    assert response.answer is not None
    assert len(response.results) > 0
```

Run integration tests:
```bash
uv run pytest tests/integration/ -v
```

---

## Running the System

### First-Time Setup

```bash
# 1. Initialize configuration (creates XDG directories)
uv run krag init

# 2. Edit configuration file
vim ~/.config/krag/config.toml  # Or $XDG_CONFIG_HOME/krag/config.toml

# Add your directories:
[directories]
paths = [
    "/home/user/documents",
    "/home/user/projects"
]

# 3. Configure LLM model (uses HuggingFace, auto-downloads)
# Default: microsoft/Phi-3-mini-4k-instruct-gguf
# Or use a larger model:
[llm]
model = "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"

# Alternatively, use a local GGUF file:
# model = "/home/user/.models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"

# 4. Optional: Configure path display reductions for cleaner output
[path_reductions]
aliases = [
    "/home/user:~",
    "/home/user/projects:projects",
]
# This will display /home/user/projects/krag/README.md as projects/krag/README.md
```

### Index Your Files

```bash
# Initial full indexing
uv run krag index

# This will:
# - Scan configured directories
# - Extract and chunk text
# - Generate embeddings
# - Store in vector database
# - Typically takes 5-10 minutes for 10k files
```

### Query Your Knowledge Base

```bash
# Basic query
uv run krag query "How do I configure authentication?"

# Retrieve without synthesis
uv run krag query "authentication setup" --no-synthesis

# Get more results
uv run krag query "error handling patterns" --top-k 10

# Show source files
uv run krag query "database connection" --show-sources
```

### Maintenance

```bash
# Incremental update (after modifying files)
uv run krag index --incremental

# Check system status
uv run krag status

# Validate configuration
uv run krag config validate

# Reset everything (destructive!)
uv run krag reset --keep-config
```

---

## Development Workflow

### Pre-Commit Checks

Before every commit:

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check --fix .

# Run tests
uv run pytest

# Type checking (optional but recommended)
uv run mypy src/
```

### Adding New Features

1. Write specification in `/specs/`
2. Write tests first (TDD)
3. Implement feature
4. Update documentation
5. Run pre-commit checks
6. Commit with conventional commit message

Example commit:
```bash
git commit -m "feat(retrieval): add result filtering by file type"
```

---

## Troubleshooting

### Model Download Issues

```bash
# Embedding model fails to download
export HF_HOME=~/.cache/huggingface
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Performance Issues

```bash
# Enable GPU acceleration (if available)
export KRAG_EMBEDDING_DEVICE=cuda

# Increase batch size for faster indexing
# Edit config.toml:
[embedding]
batch_size = 64
```

### Memory Issues

```bash
# Reduce batch size
[embedding]
batch_size = 16

# Use smaller embedding model
model = "all-MiniLM-L6-v2"  # 384 dim instead of 768
```

---

## Next Steps

After completing Phase 1:

1. **Optimize**: Profile and optimize hot paths
2. **Test at Scale**: Index your full corpus (100k+ files)
3. **Tune Models**: Experiment with different embedding models
4. **Add Features**: Implement query filters, citation tracking
5. **Phase 2**: Design multimodal support (images, 3D models)

---

## Resources

- **Documentation**: `/specs/001-text-rag-indexing/`
- **Contracts**: `/specs/001-text-rag-indexing/contracts/`
- **Data Model**: `/specs/001-text-rag-indexing/data-model.md`
- **Research**: `/specs/001-text-rag-indexing/research.md`

## Support

For issues or questions during implementation:
- Review specification documents
- Check contract definitions
- Consult research document for best practices
- Run tests to verify component behavior
