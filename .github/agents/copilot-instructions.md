# krag Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-03

## Active Technologies
- Extends existing Qdrant vector store and file metadata tracking to support plugin-extracted content (002-plugin-architecture)
- Python 3.13+ (maintaining 3.11/3.12 compatibility if feasible) (003-wsl-migration)
- Python >=3.11,<3.14 (pyproject.toml target: py311) + typer (CLI), llama-cpp-python (LLM inference), qdrant-client (vector store), sentence-transformers (embeddings), pydantic/pydantic-settings (config), rich (display), pyyaml + tomli-w (config I/O) (004-rag-quality-tuning)
- Qdrant (vector store, local file-based), TOML config files, GGUF model files (004-rag-quality-tuning)
- Python 3.11+ (pyproject.toml: `>=3.11,<3.14`) (005-code-aware-indexing)
- Qdrant (embedded, disk-backed via `QdrantVectorStore`). Cosine distance. Currently single collection `"krag_embeddings"`. This feature adds per-model vector namespaces. (005-code-aware-indexing)
- Python >=3.11, <3.14 (tested on 3.13) + typer, sentence-transformers, qdrant-client, llama-cpp-python, pydantic, rich (006-code-quality-sprint)
- Qdrant vector store (local file-based), JSON metadata files (006-code-quality-sprint)
- Python 3.11+ (`requires-python = ">=3.11,<3.14"`) (007-service-architecture)
- Qdrant (embedded mode via filesystem path — no network Qdrant server) (007-service-architecture)
- Python 3.11–3.13 (requires-python = ">=3.11,<3.14") + FastAPI >=0.115.0, Typer >=0.9.0, qdrant-client >=1.8.0, sentence-transformers >=2.3.0, llama-cpp-python >=0.2.90, pydantic >=2.6.0, pydantic-settings >=2.2.0, httpx >=0.28.0, rich >=13.0.0, tomli-w >=1.0.0 (009-retrieval-modes)
- Qdrant (embedded file-based via qdrant-client, stored at `~/.cache/krag/storage`) (009-retrieval-modes)
- Python 3.11+ (requires-python = ">=3.11,<3.14") + FastAPI 0.115+, Qdrant-client 1.8+, sentence-transformers 2.3+, llama-cpp-python 0.2.90+, Rich 13+, Typer 0.9+, Pydantic 2.6+, uvicorn 0.34+, httpx 0.28+ (010-infrastructure-polish)
- Qdrant (vector store), filesystem (metadata.json, TOML config, mode files, logs) (010-infrastructure-polish)
- Python 3.11–3.13 + krag (core), pyyaml (frontmatter parsing), pydantic (config schema) (011-obsidian-plugin)
- Qdrant (existing `krag_docs` and `krag_code` collections via CollectionManager) (011-obsidian-plugin)
- Python >=3.11,<3.14 (ruff/mypy target: py311) + FastAPI >=0.115.0, Pydantic >=2.6.0, Uvicorn >=0.34.0, Typer >=0.9.0, Rich >=13.0.0, httpx >=0.28.0, llama-cpp-python >=0.2.90, sse-starlette >=2.0.0 (new) (012-krager-prep)
- Qdrant vector store (via qdrant-client >=1.8.0), YAML/TOML config files (012-krager-prep)
- TypeScript 5.6, Rust stable (Tauri v2 requirement), Node.js 20+ + Tauri v2, SvelteKit 2 (SPA mode, SSR off), Svelte 5 (runes), `@tauri-apps/plugin-http`, Shiki (syntax highlighting), Vitest, `@testing-library/svelte` (013-krager)
- In-memory only — Svelte 5 `$state` reactive objects in `.svelte.ts` modules; no persistence layer (013-krager)
- TypeScript 5.6 (frontend), Rust (Tauri shell, no custom commands needed) + SvelteKit 2, Svelte 5 (runes), Tauri v2, `@tauri-apps/plugin-http`, `@tauri-apps/plugin-store` (to add) (014-krager-enhancements)
- Tauri Store plugin — JSON file in OS-native app data directory (`$APPDATA/krager/settings.json`) (014-krager-enhancements)

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
- 014-krager-enhancements: Added TypeScript 5.6 (frontend), Rust (Tauri shell, no custom commands needed) + SvelteKit 2, Svelte 5 (runes), Tauri v2, `@tauri-apps/plugin-http`, `@tauri-apps/plugin-store` (to add)
- 013-krager: Added TypeScript 5.6, Rust stable (Tauri v2 requirement), Node.js 20+ + Tauri v2, SvelteKit 2 (SPA mode, SSR off), Svelte 5 (runes), `@tauri-apps/plugin-http`, Shiki (syntax highlighting), Vitest, `@testing-library/svelte`
- 012-krager-prep: Added Python >=3.11,<3.14 (ruff/mypy target: py311) + FastAPI >=0.115.0, Pydantic >=2.6.0, Uvicorn >=0.34.0, Typer >=0.9.0, Rich >=13.0.0, httpx >=0.28.0, llama-cpp-python >=0.2.90, sse-starlette >=2.0.0 (new)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
