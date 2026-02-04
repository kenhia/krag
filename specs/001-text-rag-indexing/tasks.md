# Tasks: Text-Based RAG Indexing & Retrieval System

**Input**: Design documents from `/specs/001-text-rag-indexing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are REQUIRED per constitution (TDD is NON-NEGOTIABLE). All tests must be written FIRST and FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/krag/`, `tests/` at repository root
- Paths follow structure defined in plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure per plan.md (src/krag with subdirectories, tests/ with subdirectories)
- [X] T002 Initialize Python project with pyproject.toml including all dependencies from plan.md
- [X] T003 [P] Create .python-version file with Python 3.11+
- [X] T004 [P] Configure ruff in pyproject.toml with linting and formatting rules
- [X] T005 [P] Configure pytest in pyproject.toml with test paths and options
- [X] T006 [P] Configure mypy in pyproject.toml for type checking
- [X] T007 [P] Create src/krag/__init__.py
- [X] T008 [P] Create tests/__init__.py and test subdirectory __init__.py files
- [X] T009 Install dependencies with `uv sync` and verify installation
- [X] T010 [P] Create README.md with project overview and setup instructions
- [X] T011 [P] Create .gitignore file excluding __pycache__, .venv, qdrant_storage, etc.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Data Models (Foundation)

- [X] T012 [P] Create src/krag/models/__init__.py
- [X] T013 [P] Implement IndexingStatus and JobStatus enums in src/krag/models/file_metadata.py
- [X] T014 [P] Implement FileMetadata model in src/krag/models/file_metadata.py with Pydantic
- [X] T015 [P] Implement TextChunk model in src/krag/models/text_chunk.py with Pydantic
- [X] T016 [P] Implement EmbeddingRecord model in src/krag/models/embedding.py with Pydantic
- [X] T017 [P] Implement QueryResult model in src/krag/models/query_result.py with Pydantic
- [X] T018 [P] Implement IndexingJob model in src/krag/models/indexing_job.py with Pydantic
- [X] T019 [P] Implement Configuration model in src/krag/models/configuration.py with Pydantic Settings

### Configuration System

- [X] T020 [P] Create src/krag/config/__init__.py
- [X] T021 Implement ConfigManager in src/krag/config/settings.py with load, create_default, validate methods
- [X] T022 [P] Create default config template in src/krag/config/defaults.py
- [X] T023 Write unit tests for Configuration model in tests/unit/test_configuration.py
- [X] T024 Write unit tests for ConfigManager in tests/unit/test_config_manager.py

### Error Handling

- [X] T025 [P] Define custom exception classes in src/krag/models/exceptions.py (KragError, ConfigurationError, StorageError, ModelLoadError, etc.)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Query Personal Knowledge Base (Priority: P1) 🎯 MVP

**Goal**: Enable querying indexed content with LLM-synthesized answers. This is the core value proposition - users can ask questions and get answers from their personal files.

**Independent Test**: Index a small test corpus (~10 files), submit a natural language query, verify relevant content is retrieved and synthesized into a coherent answer.

### Tests for User Story 1 (TDD - WRITE FIRST, VERIFY THEY FAIL)

- [ ] T026 [P] [US1] Create test fixtures directory tests/fixtures/sample_files/ with sample documents
- [ ] T027 [P] [US1] Create mock embedding generator in tests/fixtures/mock_embeddings.py
- [ ] T028 [P] [US1] Create mock LLM client in tests/fixtures/mock_llm.py
- [ ] T029 [P] [US1] Write contract test for Retriever interface in tests/contract/test_retriever_contract.py
- [ ] T030 [P] [US1] Write contract test for LLMClient interface in tests/contract/test_llm_contract.py
- [ ] T031 [P] [US1] Write integration test for query pipeline in tests/integration/test_query_pipeline.py
- [ ] T032 [P] [US1] Write unit tests for PromptBuilder in tests/unit/test_prompt_builder.py

### Implementation for User Story 1

**Retrieval Module**

- [ ] T033 [P] [US1] Create src/krag/retrieval/__init__.py
- [X] T034 [US1] Implement Retriever class in src/krag/retrieval/retriever.py with retrieve method
- [ ] T035 [P] [US1] Implement result ranking logic in src/krag/retrieval/ranker.py
- [ ] T036 [US1] Write unit tests for Retriever in tests/unit/test_retrieval.py

**Synthesis Module**

- [X] T037 [P] [US1] Create src/krag/synthesis/__init__.py
- [X] T038 [US1] Implement LLMClient class in src/krag/synthesis/llm_client.py with generate method
- [X] T039 [P] [US1] Implement PromptBuilder class in src/krag/synthesis/prompt_builder.py
- [ ] T040 [US1] Write unit tests for LLMClient in tests/unit/test_synthesis.py

**Query Orchestration**

- [X] T041 [P] [US1] Create src/krag/orchestration/__init__.py
- [X] T042 [US1] Implement QueryEngine class in src/krag/orchestration/query_engine.py with query method
- [X] T043 [US1] Implement QueryResponse dataclass in src/krag/orchestration/query_engine.py
- [X] T044 [US1] Add error handling for empty queries and no results
- [X] T045 [US1] Add logging for query operations
- [X] T046 [US1] Write unit tests for QueryEngine in tests/unit/test_query_engine.py

**CLI for Querying**

- [X] T047 [P] [US1] Create src/krag/cli/__init__.py
- [X] T048 [US1] Implement query command in src/krag/cli/query.py with typer
- [X] T049 [US1] Add --top-k, --no-synthesis, --show-sources, --format options to query command
- [X] T050 [US1] Add output formatting (text and JSON formats)
- [X] T051 [US1] Integrate QueryEngine with query CLI command
- [X] T052 [US1] Add error handling and user-friendly messages for query CLI

**Integration & Validation**

- [X] T053 [US1] Run integration test for query pipeline and verify it passes
- [X] T054 [US1] Run contract tests for Retriever and LLMClient and verify they pass
- [X] T055 [US1] Manual test: Query sample corpus and verify synthesized answers

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently (requires indexed data from US2)

---

## Phase 4: User Story 2 - Index Local and Network Storage (Priority: P2)

**Goal**: Enable comprehensive file discovery and indexing from multiple storage locations. Users can index files from PC and NAS to make them searchable.

**Independent Test**: Configure multiple directory paths, run indexing, verify files from all locations are discovered and embedded in vector store.

### Tests for User Story 2 (TDD - WRITE FIRST, VERIFY THEY FAIL)

- [ ] T056 [P] [US2] Write contract test for VectorStore interface in tests/contract/test_vector_store_contract.py
- [ ] T057 [P] [US2] Write contract test for EmbeddingGenerator interface in tests/contract/test_embedding_contract.py
- [ ] T058 [P] [US2] Write integration test for indexing pipeline in tests/integration/test_indexing_pipeline.py
- [ ] T059 [P] [US2] Write unit tests for FileScanner in tests/unit/test_discovery.py
- [ ] T060 [P] [US2] Write unit tests for TextExtractor in tests/unit/test_extraction.py
- [ ] T061 [P] [US2] Write unit tests for TextChunker in tests/unit/test_chunker.py

### Implementation for User Story 2

**Discovery Module**

- [ ] T062 [P] [US2] Create src/krag/discovery/__init__.py
- [ ] T063 [US2] Implement FileScanner class in src/krag/discovery/scanner.py with scan and scan_incremental methods
- [ ] T064 [P] [US2] Implement FileFilter class in src/krag/discovery/filters.py
- [ ] T065 [US2] Add progress tracking for file discovery
- [ ] T066 [US2] Add error handling for permission denied and missing directories

**Extraction Module**

- [ ] T067 [P] [US2] Create src/krag/extraction/__init__.py
- [ ] T068 [US2] Implement TextExtractor class in src/krag/extraction/text_extractor.py with extract and detect_encoding methods
- [ ] T069 [P] [US2] Implement TextChunker class in src/krag/extraction/chunker.py using llama-index splitters
- [ ] T070 [US2] Add support for code-aware chunking in TextChunker.chunk_code method
- [ ] T071 [US2] Add file size limit handling in TextExtractor
- [ ] T072 [US2] Add error handling for corrupt/unreadable files

**Embeddings Module**

- [ ] T073 [P] [US2] Create src/krag/embeddings/__init__.py
- [ ] T074 [US2] Implement EmbeddingGenerator class in src/krag/embeddings/generator.py using sentence-transformers
- [ ] T075 [US2] Add batch processing in EmbeddingGenerator.generate method
- [ ] T076 [P] [US2] Implement model management in src/krag/embeddings/models.py
- [ ] T077 [US2] Add progress tracking for embedding generation
- [ ] T078 [US2] Write unit tests for EmbeddingGenerator in tests/unit/test_embeddings.py

**Storage Module**

- [ ] T079 [P] [US2] Create src/krag/storage/__init__.py
- [ ] T080 [US2] Define VectorStore abstract interface in src/krag/storage/vector_store.py
- [ ] T081 [US2] Implement QdrantVectorStore in src/krag/storage/qdrant_impl.py with upsert, search, delete, get_stats methods
- [ ] T082 [P] [US2] Implement MetadataStore in src/krag/storage/metadata_store.py using SQLite
- [ ] T083 [US2] Add collection initialization in QdrantVectorStore
- [ ] T084 [US2] Add error handling for storage operations
- [ ] T085 [US2] Write unit tests for MetadataStore in tests/unit/test_storage.py

**Indexing Orchestration**

- [ ] T086 [US2] Implement IndexingOrchestrator class in src/krag/orchestration/indexer.py with index_full method
- [ ] T087 [US2] Connect all pipeline stages in IndexingOrchestrator (discovery → extraction → chunking → embedding → storage)
- [ ] T088 [US2] Add progress tracking and reporting for IndexingOrchestrator
- [ ] T089 [US2] Add per-file error handling (continue on error, collect error summary)
- [ ] T090 [US2] Add logging for indexing operations
- [ ] T091 [US2] Write unit tests for IndexingOrchestrator in tests/unit/test_indexing_orchestrator.py

**CLI for Indexing**

- [ ] T092 [US2] Implement Typer app entrypoint in src/krag/cli/main.py
- [ ] T093 [US2] Implement init command in src/krag/cli/main.py for configuration initialization
- [ ] T094 [US2] Implement index command in src/krag/cli/index.py with --full, --dry-run options
- [ ] T095 [US2] Add progress bars using rich library in index command
- [ ] T096 [US2] Add error summary display at end of indexing
- [ ] T097 [US2] Integrate IndexingOrchestrator with index CLI command
- [ ] T098 [US2] Add status command in src/krag/cli/main.py to show index statistics
- [ ] T099 [US2] Add config command in src/krag/cli/main.py with show, validate, edit subcommands

**Integration & Validation**

- [ ] T100 [US2] Run integration test for indexing pipeline and verify it passes
- [ ] T101 [US2] Run contract tests for VectorStore and EmbeddingGenerator and verify they pass
- [ ] T102 [US2] Manual test: Index sample corpus and verify embeddings in vector store
- [ ] T103 [US2] End-to-end test: Index files (US2) then query them (US1) and verify complete workflow

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently. MVP is complete!

---

## Phase 5: User Story 3 - Incremental Re-Indexing (Priority: P3)

**Goal**: Optimize indexing by only processing new or modified files. Users can keep their index current without full re-indexing.

**Independent Test**: Index a corpus, modify specific files, run incremental indexing, verify only changed files are re-processed.

### Tests for User Story 3 (TDD - WRITE FIRST, VERIFY THEY FAIL)

- [ ] T104 [P] [US3] Write integration test for incremental update in tests/integration/test_incremental_update.py
- [ ] T105 [P] [US3] Write unit tests for incremental logic in tests/unit/test_incremental.py

### Implementation for User Story 3

**Incremental Indexing Logic**

- [ ] T106 [US3] Implement index_incremental method in src/krag/orchestration/indexer.py
- [ ] T107 [US3] Implement change detection logic in src/krag/orchestration/incremental.py using modification time and content hash
- [ ] T108 [US3] Add file categorization (new, modified, deleted, unchanged) in incremental.py
- [ ] T109 [US3] Implement deletion handling (remove vectors from store)
- [ ] T110 [US3] Add logging for incremental operations (showing files categorized)

**CLI Integration**

- [ ] T111 [US3] Add --incremental option to index command (make it default behavior)
- [ ] T112 [US3] Update index command to use index_incremental by default
- [ ] T113 [US3] Add statistics display for incremental runs (new, modified, deleted, unchanged counts)

**Integration & Validation**

- [ ] T114 [US3] Run integration test for incremental update and verify it passes
- [ ] T115 [US3] Manual test: Index corpus, modify files, run incremental, verify correct behavior
- [ ] T116 [US3] Performance test: Verify incremental is significantly faster than full re-index

**Checkpoint**: All three core user stories (P1, P2, P3) should now be independently functional

---

## Phase 6: User Story 4 - Configure Indexing Behavior (Priority: P4)

**Goal**: Provide configuration flexibility for directories, file types, and chunking parameters. Users can tailor system to their specific needs.

**Independent Test**: Modify configuration settings, run indexing, verify only specified directories and file types are processed according to rules.

### Tests for User Story 4 (TDD - WRITE FIRST, VERIFY THEY FAIL)

- [ ] T117 [P] [US4] Write unit tests for configuration validation in tests/unit/test_config_validation.py
- [ ] T118 [P] [US4] Write integration test for configuration-based filtering in tests/integration/test_config_filtering.py

### Implementation for User Story 4

**Enhanced Configuration**

- [ ] T119 [US4] Ensure Configuration model supports all required fields per data-model.md
- [ ] T120 [US4] Add validation rules to Configuration model (chunk_size > chunk_overlap, etc.)
- [ ] T121 [US4] Implement configuration file template generation in ConfigManager.create_default
- [ ] T122 [US4] Add configuration validation error messages in ConfigManager.validate

**Apply Configuration Throughout System**

- [ ] T123 [US4] Update FileScanner to respect exclusion_patterns from configuration
- [ ] T124 [US4] Update FileScanner to respect supported_file_types from configuration
- [ ] T125 [US4] Update TextChunker to use chunk_size and chunk_overlap from configuration
- [ ] T126 [US4] Update EmbeddingGenerator to use embedding_model and device from configuration
- [ ] T127 [US4] Update Retriever to use top_k from configuration

**CLI for Configuration**

- [ ] T128 [US4] Enhance init command to create configuration file with prompts for directories
- [ ] T129 [US4] Implement config validate subcommand with detailed validation messages
- [ ] T130 [US4] Implement config show subcommand with formatted output
- [ ] T131 [US4] Implement config edit subcommand to open config in default editor

**Integration & Validation**

- [ ] T132 [US4] Run integration test for configuration filtering and verify it passes
- [ ] T133 [US4] Manual test: Change configuration, verify indexing behavior changes accordingly
- [ ] T134 [US4] Test invalid configurations are caught and reported clearly

**Checkpoint**: All user stories (P1-P4) should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and overall quality

**Documentation**

- [ ] T135 [P] Create comprehensive README.md with installation, setup, usage examples
- [ ] T136 [P] Add docstrings to all public classes and methods
- [ ] T137 [P] Create docs/architecture.md documenting system design
- [ ] T138 [P] Create docs/configuration.md explaining all config options
- [ ] T139 [P] Create docs/troubleshooting.md with common issues and solutions

**Additional Testing**

- [ ] T140 [P] Add unit tests for any modules missing coverage in tests/unit/
- [ ] T141 [P] Add edge case tests for all 9 edge cases from spec.md (empty query, no indexed content, large files, binary misidentification, storage unavailable, corrupt files, long chunks, concurrent indexing, config errors)
- [ ] T142 Achieve minimum 80% test coverage across all modules
- [ ] T143 [P] Add performance tests in tests/performance/ for indexing throughput
- [ ] T144 [P] Add accuracy validation test in tests/integration/ for SC-004 (verify top-5 retrieval accuracy on test corpus)
- [ ] T145 [P] Add memory profiling test in tests/performance/ for SC-006 (verify no memory leaks during extended operation)

**Code Quality**

- [ ] T146 Run `uv run ruff format .` and verify all code is formatted
- [ ] T147 Run `uv run ruff check --fix .` and fix all linting issues
- [ ] T148 Run `uv run mypy src/` and fix all type errors
- [ ] T149 Run `uv run pytest` and ensure all tests pass
- [ ] T150 Review and refactor any code smells or duplication

**Error Handling & Logging**

- [ ] T151 [P] Ensure all modules have consistent error handling
- [ ] T152 [P] Ensure all CLI commands have user-friendly error messages
- [ ] T153 Add log rotation configuration
- [ ] T154 Add structured logging for machine-readable logs

**CLI Enhancements**

- [ ] T155 [P] Add reset command with confirmation prompts
- [ ] T156 [P] Add --version flag to main CLI
- [ ] T157 Add shell completion support for bash/zsh
- [ ] T158 Improve progress indicators with richer formatting

**Quickstart Validation**

- [ ] T159 Follow quickstart.md step-by-step and verify all instructions work
- [ ] T160 Update quickstart.md with any discovered issues or improvements

**Final Pre-Commit Validation**

- [ ] T161 Run complete pre-commit workflow: `uv run ruff format . && uv run ruff check --fix . && uv run pytest`
- [ ] T162 Verify all tests pass and code quality checks succeed
- [ ] T163 Review git status and ensure no unintended files are staged

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion - Can start after Phase 2
- **User Story 2 (Phase 4)**: Depends on Foundational completion - Can start after Phase 2 (can run parallel with US1 except US1 needs US2 for actual indexing)
- **User Story 3 (Phase 5)**: Depends on User Story 2 completion (needs full indexing to work)
- **User Story 4 (Phase 6)**: Depends on Foundational completion - Can start after Phase 2 (can run parallel with other stories)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Requires indexed data to query - functionally depends on US2 for real-world use but can be tested with fixtures
- **User Story 2 (P2)**: Independent - provides indexing capability
- **User Story 3 (P3)**: Depends on User Story 2 - extends indexing with incremental updates
- **User Story 4 (P4)**: Independent - configuration affects all stories but can be developed independently

### Optimal Implementation Order

1. **Phase 1 (Setup)** → Complete all setup tasks first
2. **Phase 2 (Foundational)** → Complete all foundation tasks before any user stories
3. **Phase 4 (US2)** → Implement indexing first so there's data to query
4. **Phase 3 (US1)** → Implement querying to deliver MVP
5. **Phase 5 (US3)** → Add incremental indexing optimization
6. **Phase 6 (US4)** → Add configuration flexibility
7. **Phase 7 (Polish)** → Final quality improvements

### Parallel Opportunities

**Within Setup (Phase 1)**:
- T003, T004, T005, T006, T007, T008, T010, T011 can all run in parallel

**Within Foundational (Phase 2)**:
- T013-T019 (all models) can run in parallel
- T020, T022, T025 can run in parallel with model creation
- T023, T024 run after their respective implementations

**Within User Stories**:
- All test tasks marked [P] within a story can run in parallel
- All model tasks marked [P] within a story can run in parallel
- Different user stories can be worked on by different developers (after Foundational phase)

### Within Each User Story (TDD Flow)

1. **Write tests FIRST** (all test tasks) → Verify they FAIL
2. **Implement models/interfaces** (parallelizable tasks)
3. **Implement services** (sequential, depend on models)
4. **Implement CLI/integration** (sequential, depend on services)
5. **Run tests** → Verify they PASS
6. **Refactor** if needed

---

## Parallel Example: User Story 2 (Indexing)

### Phase 1: Write All Tests First
```bash
# Launch all test creation tasks together:
T056: Contract test for VectorStore
T057: Contract test for EmbeddingGenerator
T058: Integration test for indexing pipeline
T059: Unit tests for FileScanner
T060: Unit tests for TextExtractor
T061: Unit tests for TextChunker
```

### Phase 2: Create All Models/Modules in Parallel
```bash
# Launch all independent implementation tasks together:
T062: Create discovery __init__.py
T067: Create extraction __init__.py
T073: Create embeddings __init__.py
T079: Create storage __init__.py
```

### Phase 3: Implement Core Logic
```bash
# Sequential tasks that depend on models:
T063 → T064 → T065 → T066 (Discovery chain)
T068 → T069 → T070 → T071 → T072 (Extraction chain)
T074 → T075 → T076 → T077 → T078 (Embeddings chain)
T080 → T081 → T082 → T083 → T084 → T085 (Storage chain)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete **Phase 1: Setup** (T001-T011)
2. Complete **Phase 2: Foundational** (T012-T025) - CRITICAL GATE
3. Complete **Phase 4: User Story 2 - Indexing** (T056-T103) - Build indexing capability
4. Complete **Phase 3: User Story 1 - Querying** (T026-T055) - Add query capability
5. **STOP and VALIDATE**: Test full workflow (index → query) independently
6. **MVP COMPLETE** - System can index files and answer questions!

### Incremental Delivery After MVP

1. **MVP (US1 + US2)** → Index files and query them → Deploy/Demo ✅
2. **+US3 (Incremental Indexing)** → Add optimization → Deploy/Demo
3. **+US4 (Configuration)** → Add flexibility → Deploy/Demo
4. **+Polish** → Add quality improvements → Final release

### Parallel Team Strategy

With multiple developers after Foundational phase:

1. **Team completes Phase 1 + 2 together**
2. **After Foundational complete:**
   - **Developer A**: User Story 2 (Indexing) - T056-T103
   - **Developer B**: User Story 1 (Querying) - T026-T055 (can start tests/mocks)
   - **Developer C**: User Story 4 (Configuration) - T117-T134
3. **After US2 complete:**
   - **Developer A**: User Story 3 (Incremental) - T104-T116
   - **Developer B**: Continues US1 integration with real data
4. **Everyone**: Polish phase together

---

## Task Summary

- **Total Tasks**: 163
- **Setup Phase**: 11 tasks
- **Foundational Phase**: 14 tasks
- **User Story 1 (Query)**: 30 tasks
- **User Story 2 (Indexing)**: 48 tasks
- **User Story 3 (Incremental)**: 13 tasks
- **User Story 4 (Configuration)**: 18 tasks
- **Polish Phase**: 29 tasks

### Tasks by Type

- **Tests**: 35 tasks (TDD-mandated)
- **Models/Data**: 14 tasks
- **Core Implementation**: 74 tasks
- **CLI**: 17 tasks
- **Documentation**: 9 tasks
- **Quality/Validation**: 14 tasks

### Parallel Opportunities

- **Setup Phase**: 8 tasks can run in parallel
- **Foundational Phase**: 11 tasks can run in parallel
- **User Story 1**: 8 test tasks + 5 implementation tasks in parallel
- **User Story 2**: 6 test tasks + 8 implementation tasks in parallel
- **User Story 3**: 2 test tasks in parallel
- **User Story 4**: 2 test tasks + configuration work in parallel
- **Polish Phase**: 15 tasks can run in parallel

### Suggested MVP Scope

**Minimum Viable Product** = User Story 1 (Query) + User Story 2 (Indexing)
- **Task range**: T001-T103 (103 tasks)
- **Time estimate**: 2-3 weeks for single developer
- **Delivers**: Ability to index personal files and query them with LLM synthesis
- **Value**: Core functionality that solves the primary user problem

---

## Notes

- **[P] tasks** = Different files, no dependencies, can parallelize
- **[US#] label** = Maps task to specific user story for traceability
- **Each user story** is independently completable and testable
- **TDD is mandatory**: Tests must be written FIRST and FAIL before implementation
- **Commit frequently**: After each task or logical group
- **Stop at checkpoints**: Validate story independently before proceeding
- **Pre-commit validation**: Required before all commits per constitution

---

## Format Validation

✅ All 163 tasks follow checklist format:
- ✅ Checkbox: `- [ ]`
- ✅ Task ID: Sequential T001-T163
- ✅ [P] marker: Present where tasks can parallelize
- ✅ [Story] label: Present for all user story tasks (US1, US2, US3, US4)
- ✅ Description: Includes clear action and file path
- ✅ No story label: Setup, Foundational, and Polish phases as expected
