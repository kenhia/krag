# krag Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-03

## Active Technologies
- Extends existing Qdrant vector store and file metadata tracking to support plugin-extracted content (002-plugin-architecture)
- Python 3.13+ (maintaining 3.11/3.12 compatibility if feasible) (003-wsl-migration)
- Python >=3.11,<3.14 (pyproject.toml target: py311) + typer (CLI), llama-cpp-python (LLM inference), qdrant-client (vector store), sentence-transformers (embeddings), pydantic/pydantic-settings (config), rich (display), pyyaml + tomli-w (config I/O) (004-rag-quality-tuning)
- Qdrant (vector store, local file-based), TOML config files, GGUF model files (004-rag-quality-tuning)

- Python 3.11+ (001-text-rag-indexing)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 004-rag-quality-tuning: Added Python >=3.11,<3.14 (pyproject.toml target: py311) + typer (CLI), llama-cpp-python (LLM inference), qdrant-client (vector store), sentence-transformers (embeddings), pydantic/pydantic-settings (config), rich (display), pyyaml + tomli-w (config I/O)
- 003-wsl-migration: Added Python 3.13+ (maintaining 3.11/3.12 compatibility if feasible)
- 002-plugin-architecture: Added Python 3.11+


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
