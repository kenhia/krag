# Implementation Plan: Plugin Architecture for File Type Extensions

**Branch**: `002-plugin-architecture` | **Date**: 2026-02-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-plugin-architecture/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Extend krag with a plugin system that enables file type handlers to be added without modifying core code. Plugins can extract text from specialized file formats (PDF, DOCX, code files, etc.) and integrate seamlessly into the existing indexing pipeline. The system provides plugin discovery via Python entry points, lifecycle management (load, initialize, configure, cleanup), and flexible chunking where plugins can either provide custom chunking strategies or select from krag's available base chunkers. CLI commands enable plugin management (install, list, enable, disable, configure). Architecture maintains backward compatibility with core text-only system while providing extensibility for third-party plugin development.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: 
- Existing krag infrastructure (typer, sentence-transformers, qdrant-client, llama-cpp-python, llama-index)
- Python setuptools entry points mechanism for plugin discovery
- Plugin-specific dependencies installed per plugin (e.g., PyPDF2, python-docx will be plugin dependencies)

**Storage**: Extends existing Qdrant vector store and file metadata tracking to support plugin-extracted content
**Testing**: pytest with fixtures for mock plugins, plugin registry, and file type handler interfaces
**Target Platform**: Same as core krag (Linux/macOS/Windows desktop)
**Project Type**: Single project (extension to existing CLI application)
**Performance Goals**: 
- Plugin discovery and registration adds <1 second to startup time
- Plugin system overhead <5% when no plugins installed
- Plugin-extracted content indexed at rates comparable to native text files (within 20%)

**Constraints**: 
- Backward compatibility with existing krag installations (core system must work without plugins)
- Plugin failures cannot crash indexing pipeline (graceful degradation required)
- Plugin API surface minimized to reduce maintenance burden
- Must work within XDG Base Directory conventions

**Scale/Scope**: 
- Support 10-20 simultaneously installed plugins
- Plugin configuration sections in main TOML config
- Plugin development time target: <4 hours for basic file type handler

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Core Principles Compliance

**I. Code Quality & Standards**
- ✅ Plugin interface abstraction maintains modularity
- ✅ Clear plugin contract definitions with type hints
- ✅ Comprehensive docstrings for plugin API
- ✅ ruff configured for plugin module style compliance

**II. Test-Driven Development (TDD)**
- ✅ Each user story (P1-P4) independently testable
- ✅ Unit tests for plugin registry, discovery, lifecycle management
- ✅ Integration tests for plugin pipeline integration
- ✅ Contract tests for plugin interfaces
- ✅ Mock plugin fixtures for testing without external dependencies

**III. User Experience Consistency**
- ✅ CLI plugin commands follow existing typer patterns
- ✅ Plugin error messages guide users toward resolution
- ✅ Plugin configuration follows TOML structure consistency
- ✅ Plugin status feedback clear and actionable

**IV. Performance & Optimization**
- ✅ Performance targets defined in Success Criteria (SC-003: <5% overhead)
- ✅ Lazy plugin loading (load only when needed)
- ✅ Plugin failures isolated to prevent cascade
- ✅ Plugin processing performance monitored and reported

### Python-Specific Requirements
- ✅ uv for dependency management (plugins as separate packages)
- ✅ ruff for formatting and linting plugin code
- ✅ pytest for plugin testing framework
- ✅ Pre-commit workflow applies to plugin system code

### Development Workflow
- ✅ Pre-commit validation mandatory for plugin system code changes
- ✅ Phase completion gates defined
- ✅ Version control discipline with conventional commits

**GATE STATUS**: ✅ **PASS** - All constitution requirements satisfied. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/002-plugin-architecture/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── plugin-interface.md         # FileTypeHandler interface contract
│   ├── plugin-registry.md          # PluginRegistry API contract
│   └── plugin-chunking.md          # Chunking strategy selection contract
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/krag/
├── plugins/                    # NEW: Plugin system module
│   ├── __init__.py
│   ├── registry.py            # PluginRegistry: discovery, registration, lifecycle
│   ├── interfaces.py          # FileTypeHandler ABC and plugin contracts
│   ├── loader.py              # Plugin loading and validation
│   ├── chunking.py            # Chunking strategy selection and plugin chunker wrapper
│   └── exceptions.py          # Plugin-specific exceptions
│
├── cli/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py
│   ├── index.py
│   ├── query.py
│   ├── config.py
│   ├── plugin.py              # NEW: Plugin management CLI commands
│   └── utils.py
│
├── config/
│   ├── __init__.py
│   ├── settings.py            # MODIFIED: Add plugin configuration support
│   ├── defaults.py            # MODIFIED: Add plugin defaults
│   ├── logging.py
│   ├── path_reducer.py
│   └── xdg.py
│
├── models/
│   ├── __init__.py
│   ├── configuration.py       # MODIFIED: Add plugin config models
│   ├── file_metadata.py
│   ├── text_chunk.py
│   ├── embedding.py
│   ├── query_result.py
│   ├── indexing_job.py
│   └── exceptions.py
│
├── orchestration/
│   ├── __init__.py
│   ├── indexer.py             # MODIFIED: Integrate plugin file handlers
│   ├── query_engine.py
│   └── incremental.py
│
├── extraction/                 # Existing (used by plugins)
│   ├── __init__.py
│   ├── text_extractor.py
│   └── chunker.py
│
├── discovery/                  # Existing (modified for plugin extensions)
│   ├── __init__.py
│   └── scanner.py             # MODIFIED: Query plugin registry for file type support
│
└── [other existing modules unchanged]

tests/
├── contract/
│   ├── test_plugin_interface_contract.py      # NEW: Plugin interface contract tests
│   └── test_plugin_registry_contract.py       # NEW: Registry contract tests
│
├── integration/
│   ├── test_plugin_indexing_pipeline.py       # NEW: End-to-end plugin integration
│   └── test_plugin_chunking_selection.py      # NEW: Chunking strategy selection tests
│
└── unit/
    └── plugins/                                # NEW: Plugin system unit tests
        ├── test_registry.py
        ├── test_loader.py
        ├── test_interfaces.py
        └── test_chunking.py

# Example plugin structure (separate repository/package)
krag-plugin-pdf/                                # Example: PDF plugin
├── pyproject.toml              # Entry point: [project.entry-points."krag.plugins"]
├── src/
│   └── krag_plugin_pdf/
│       ├── __init__.py
│       └── handler.py          # PDFFileTypeHandler implementation
└── tests/
    └── test_pdf_handler.py
```

**Structure Decision**: Extends existing single-project structure by adding `src/krag/plugins/` module for plugin system infrastructure. Modified CLI, config, orchestration, and discovery modules to integrate plugin capabilities. Plugins themselves are separate Python packages that register via entry points and are installed independently.

## Phase 0: Outline & Research
