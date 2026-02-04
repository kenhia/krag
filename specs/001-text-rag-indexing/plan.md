# Implementation Plan: Text-Based RAG Indexing & Retrieval System

**Branch**: `001-text-rag-indexing` | **Date**: 2026-02-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-text-rag-indexing/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement Phase 1 of a personal multimodal RAG system that indexes text-based content (source code, markdown, documents, configuration files) from local PC and NAS storage. The system provides natural language query capabilities with answer synthesis using a local LLM. Architecture follows a modular pipeline design: file discovery → text extraction → intelligent chunking → embedding generation → vector storage → similarity retrieval → LLM synthesis. Technology choices prioritize local-first operation, extensibility for future multimodal expansion, and performance on modern hardware.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- **CLI Framework**: typer (for command-line interface)
- **Embedding**: sentence-transformers (HuggingFace models for text embeddings)
- **Vector Store**: qdrant-client (embedded mode for local vector database)
- **LLM Framework**: llama-cpp-python (efficient local LLM inference)
- **Chunking**: llama-index text splitters (semantic-aware text chunking)
- **Package Management**: uv (dependency and environment management)
- **Code Quality**: ruff (formatting and linting), pytest (testing)

**Storage**: Qdrant embedded vector database + filesystem for file metadata tracking
**Testing**: pytest with fixtures for embeddings, mock vector stores, and LLM responses
**Target Platform**: Linux/macOS/Windows desktop with local and network-mounted storage
**Project Type**: Single project (CLI application with library modules)
**Performance Goals**: 
- Index 10,000 text files in <30 minutes
- Query response (retrieval + synthesis) in <10 seconds for 95% of queries
- Incremental re-indexing of 1% changes in <5% of full indexing time

**Constraints**: 
- Fully local operation (no cloud API dependencies)
- Support NVMe and NAS storage paths
- Memory-efficient embedding generation (batch processing)
- Extensible architecture for future multimodal support

**Scale/Scope**: 
- Target corpus: 10,000-100,000 personal files
- Vector dimensions: 384-768 (sentence-transformers models)
- Concurrent operations: Single-user, sequential indexing/querying

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Core Principles Compliance

**I. Code Quality & Standards**
- ✅ Modular architecture with clear separation of concerns (discovery, extraction, embedding, storage, retrieval, synthesis)
- ✅ Type hints required for all public interfaces
- ✅ Comprehensive docstrings for modules and functions
- ✅ ruff configured for style compliance

**II. Test-Driven Development (TDD)**
- ✅ Each user story (P1-P4) independently testable
- ✅ Unit tests for each module (file discovery, chunking, embedding, retrieval)
- ✅ Integration tests for pipeline flows
- ✅ Contract tests for vector store and LLM interfaces
- ✅ Tests must pass before commit (pre-commit gate)

**III. User Experience Consistency**
- ✅ CLI interface with typer provides consistent command structure
- ✅ Progress indicators for long-running indexing operations (FR-034)
- ✅ Clear error messages for configuration errors, file access issues (FR-025, FR-033)
- ✅ Help text and documentation aligned with actual behavior

**IV. Performance & Optimization**
- ✅ Performance targets defined in Success Criteria (SC-001, SC-002, SC-003)
- ✅ Batch processing for embeddings to optimize throughput (FR-013)
- ✅ Incremental indexing to avoid redundant work (FR-027-030)
- ✅ Performance metrics tracked during indexing (FR-037)

### Python-Specific Requirements
- ✅ uv for dependency management
- ✅ ruff for formatting and linting
- ✅ pytest for testing framework
- ✅ Pre-commit workflow: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`

### Development Workflow
- ✅ Pre-commit validation mandatory for all source code changes
- ✅ Phase completion gates defined
- ✅ Version control discipline with conventional commits

**GATE STATUS**: ✅ **PASS** - All constitution requirements satisfied. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
krag/
├── pyproject.toml           # Project dependencies and configuration
├── README.md                # Project overview and setup instructions
├── .python-version          # Python version specification for uv
│
├── src/
│   ├── krag/
│   │   ├── __init__.py
│   │   ├── cli/
│   │   │   ├── __init__.py
│   │   │   ├── main.py          # Typer CLI entrypoint
│   │   │   ├── index.py         # Indexing commands
│   │   │   └── query.py         # Query commands
│   │   │
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py      # Configuration management
│   │   │   └── defaults.py      # Default configuration values
│   │   │
│   │   ├── discovery/
│   │   │   ├── __init__.py
│   │   │   ├── scanner.py       # File discovery and metadata
│   │   │   └── filters.py       # Inclusion/exclusion patterns
│   │   │
│   │   ├── extraction/
│   │   │   ├── __init__.py
│   │   │   ├── text_extractor.py   # Text extraction from files
│   │   │   └── chunker.py          # Text chunking logic
│   │   │
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   ├── generator.py     # Embedding generation
│   │   │   └── models.py        # Embedding model management
│   │   │
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── vector_store.py  # Vector store abstraction
│   │   │   ├── qdrant_impl.py   # Qdrant implementation
│   │   │   └── metadata_store.py # File metadata persistence
│   │   │
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── retriever.py     # Similarity search
│   │   │   └── ranker.py        # Result ranking/filtering
│   │   │
│   │   ├── synthesis/
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py    # LLM interface
│   │   │   └── prompt_builder.py # Prompt construction
│   │   │
│   │   ├── orchestration/
│   │   │   ├── __init__.py
│   │   │   ├── indexer.py       # Indexing orchestration
│   │   │   ├── query_engine.py  # Query orchestration
│   │   │   └── incremental.py   # Incremental update logic
│   │   │
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── file_metadata.py   # FileMetadata entity
│   │       ├── text_chunk.py      # TextChunk entity
│   │       ├── embedding.py       # EmbeddingRecord entity
│   │       └── query_result.py    # QueryResult entity
│   │
│   └── py.typed              # PEP 561 marker for type hints
│
├── tests/
│   ├── unit/
│   │   ├── test_discovery.py
│   │   ├── test_extraction.py
│   │   ├── test_embeddings.py
│   │   ├── test_storage.py
│   │   ├── test_retrieval.py
│   │   └── test_synthesis.py
│   │
│   ├── integration/
│   │   ├── test_indexing_pipeline.py
│   │   ├── test_query_pipeline.py
│   │   └── test_incremental_update.py
│   │
│   ├── contract/
│   │   ├── test_vector_store_contract.py
│   │   ├── test_llm_contract.py
│   │   └── test_embedding_contract.py
│   │
│   └── fixtures/
│       ├── sample_files/         # Test corpus
│       ├── mock_embeddings.py
│       └── mock_llm.py
│
└── .vscode/
    └── settings.json          # Pre-configured for ruff and pytest
```

**Structure Decision**: Single project structure selected. This is a CLI application with a library-style architecture. All functionality is organized into focused modules under `src/krag/`, with clear separation between layers (discovery, extraction, embeddings, storage, retrieval, synthesis, orchestration). Tests are organized by type (unit, integration, contract) to support TDD workflow. The structure is designed to be extensible for future multimodal capabilities (Phase 2+) by allowing new extraction and embedding modules to be added alongside existing text-based ones.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
