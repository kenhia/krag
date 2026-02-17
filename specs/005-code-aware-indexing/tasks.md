# Tasks: Code-Aware Indexing

**Input**: Design documents from `/specs/005-code-aware-indexing/`
**Branch**: `005-code-aware-indexing`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included - TDD approach per constitution requirement. Write tests first, watch them fail, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Core krag**: `src/krag/` at repository root
- **Plugin package**: `examples/krag-plugin-code/`
- **Tests**: `tests/{unit,contract,integration}/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and extension points

- [ ] T001 Add tree-sitter dependencies to pyproject.toml (tree-sitter>=0.23.0, tree-sitter-python>=0.23.0, tree-sitter-rust>=0.23.0)
- [ ] T002 Create plugin package structure at examples/krag-plugin-code/ with pyproject.toml, entry point configuration
- [ ] T003 [P] Extend FileTypeHandler ABC with get_embedding_model() method in src/krag/plugins/interfaces.py (default returns None)
- [ ] T004 [P] Add close() method to LLMClient in src/krag/synthesis/llm_client.py (delegates to self._llm.close())
- [ ] T005 [P] Extend Configuration model with llm_code_model and load_multi_llm fields in src/krag/models/configuration.py
- [ ] T006 [P] Add --llm CLI parameter to query command in src/krag/cli/main.py (accepts "text" or "code")
- [ ] T007 [P] Add code-related defaults in src/krag/config/defaults.py (DEFAULT_CODE_CHUNK_SIZE=2048)
- [ ] T008 [P] Update ConfigManager to parse [llm] section for code_model and load_multi_llm in src/krag/config/settings.py
- [ ] T009 [P] Create test fixtures directory tests/fixtures/code/ with sample Python/Rust files
- [ ] T010 [P] Create test fixtures directory tests/fixtures/code/malformed/ with intentionally broken code files

**Checkpoint**: Extension points ready, dependencies installed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No blocking foundational work — krag's plugin system already exists

✅ **Foundational work complete** - user stories can proceed

---

## Phase 3: User Story 1 - Code-Aware Chunking via Plugin (Priority: P1) 🎯 MVP

**Goal**: Retrieve complete, self-contained functions/methods instead of mid-definition fragments. Chunks include scope context (class name, file path).

**Independent Test**: Install code plugin, index a Python project, query for specific functions/classes. Verify returned chunks are complete semantic units (whole functions, whole methods) not character-split fragments.

### Tests for User Story 1

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T011 [P] [US1] Contract test: CodeFileHandler implements FileTypeHandler in tests/contract/test_code_plugin_contract.py
- [ ] T012 [P] [US1] Contract test: ASTChunker produces valid TextChunk objects in tests/contract/test_ast_chunker_contract.py
- [ ] T013 [P] [US1] Unit test: 30-line function chunked as single unit with decorators/docstring in tests/unit/test_ast_chunker.py
- [ ] T014 [P] [US1] Unit test: Class with 5 methods produces 5 separate chunks with parent class context in tests/unit/test_ast_chunker.py
- [ ] T015 [P] [US1] Unit test: Import blocks handled (as own chunk or prepended to function chunks) in tests/unit/test_ast_chunker.py
- [ ] T016 [P] [US1] Unit test: Parse errors trigger graceful fallback to TextChunker with warning in tests/unit/test_ast_chunker.py
- [ ] T017 [P] [US1] Unit test: Oversized function (>2048 chars) splits at statement boundaries in tests/unit/test_ast_chunker.py
- [ ] T018 [P] [US1] Unit test: Python and Rust files get AST chunking, PowerShell falls back in tests/unit/test_languages.py
- [ ] T019 [US1] Integration test: End-to-end Python project indexing with code plugin in tests/integration/test_code_indexing_pipeline.py

### Implementation for User Story 1

- [ ] T020 [P] [US1] Implement LanguageGrammar discovery system in examples/krag-plugin-code/src/krag_plugin_code/languages.py
- [ ] T021 [P] [US1] Implement SemanticUnit dataclass in examples/krag-plugin-code/src/krag_plugin_code/ast_chunker.py
- [ ] T022 [US1] Implement ASTChunker._extract_semantic_units() using tree-sitter queries in examples/krag-plugin-code/src/krag_plugin_code/ast_chunker.py
- [ ] T023 [US1] Implement ASTChunker._units_to_chunks() with scope context prepending in examples/krag-plugin-code/src/krag_plugin_code/ast_chunker.py
- [ ] T024 [US1] Implement ASTChunker._split_oversized_unit() at statement boundaries in examples/krag-plugin-code/src/krag_plugin_code/ast_chunker.py
- [ ] T025 [US1] Implement ASTChunker.chunk() with parse error fallback in examples/krag-plugin-code/src/krag_plugin_code/ast_chunker.py
- [ ] T026 [US1] Implement ASTChunker.get_chunk_metadata() returning CodeMetadata dict in examples/krag-plugin-code/src/krag_plugin_code/ast_chunker.py
- [ ] T027 [P] [US1] Implement CodeFileHandler.supported_extensions() via language discovery in examples/krag-plugin-code/src/krag_plugin_code/handler.py
- [ ] T028 [P] [US1] Implement CodeFileHandler.extract_text() and extract_metadata() in examples/krag-plugin-code/src/krag_plugin_code/handler.py
- [ ] T029 [US1] Implement CodeFileHandler.get_chunking_strategy() returning CUSTOM with ASTChunker in examples/krag-plugin-code/src/krag_plugin_code/handler.py
- [ ] T030 [US1] Implement CodeFileHandler.initialize() loading tree-sitter parsers in examples/krag-plugin-code/src/krag_plugin_code/handler.py
- [ ] T031 [US1] Update IndexingOrchestrator to call get_chunk_metadata() and inject into vector payload in src/krag/orchestration/indexer.py
- [ ] T032 [US1] Add code plugin README with installation and usage instructions in examples/krag-plugin-code/README.md

**Checkpoint**: Code plugin functional - complete functions/methods indexed as semantic units

---

## Phase 4: User Story 2 - Multi-Model Embedding Orchestration (Priority: P2)

**Goal**: Plugin-declared embedding models loaded and routed automatically. Files embedded by appropriate model (code vs text). Query searches both spaces, results merged via RRF.

**Independent Test**: Install code plugin, index mixed project (.py + .md). Verify code files use code embedder, text files use text embedder (check vector metadata). Run queries, verify results from both spaces are merged.

### Tests for User Story 2

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T033 [P] [US2] Contract test: EmbeddingOrchestrator.embed_chunks() returns list[list[float]] in tests/contract/test_embedding_orchestrator_contract.py
- [ ] T034 [P] [US2] Contract test: EmbeddingOrchestrator.embed_query() returns dict[str, list[float]] in tests/contract/test_embedding_orchestrator_contract.py
- [ ] T035 [P] [US2] Unit test: Code files embedded with code model, text files with text model (payload records model) in tests/unit/test_embedding_orchestrator.py
- [ ] T036 [P] [US2] Unit test: Query embedded by all active models (both text and code) in tests/unit/test_embedding_orchestrator.py
- [ ] T037 [P] [US2] Unit test: RRF merge produces unified ranked list from multiple result sets in tests/unit/test_rrf_merge.py
- [ ] T038 [P] [US2] Unit test: Combined embedding model footprint <1.2 GB (mock VRAM check) in tests/unit/test_embedding_orchestrator.py
- [ ] T039 [P] [US2] Unit test: Sequential two-pass fallback when VRAM insufficient in tests/unit/test_embedding_orchestrator.py
- [ ] T040 [US2] Integration test: Multi-model query pipeline + RRF merge in tests/integration/test_multi_model_query.py

### Implementation for User Story 2

- [ ] T041 [US2] Implement EmbeddingOrchestrator.__init__() with model loading and VRAM checks in src/krag/embeddings/orchestrator.py
- [ ] T042 [US2] Implement EmbeddingOrchestrator.embed_chunks() routing to specific model in src/krag/embeddings/orchestrator.py
- [ ] T043 [US2] Implement EmbeddingOrchestrator.embed_query() embedding with all active models in src/krag/embeddings/orchestrator.py
- [ ] T044 [P] [US2] Implement EmbeddingOrchestrator.get_vector_config() for Qdrant named vectors in src/krag/embeddings/orchestrator.py
- [ ] T045 [P] [US2] Implement EmbeddingOrchestrator._check_vram_budget() using torch.cuda.mem_get_info() in src/krag/embeddings/orchestrator.py
- [ ] T046 [US2] Implement reciprocal_rank_fusion() function in src/krag/retrieval/retriever.py
- [ ] T047 [US2] Update QdrantVectorStore to support named vectors in collection creation in src/krag/storage/qdrant_impl.py
- [ ] T048 [US2] Update QdrantVectorStore.upsert() to handle dict vectors (named vectors) in src/krag/storage/qdrant_impl.py
- [ ] T049 [US2] Update IndexingOrchestrator to use EmbeddingOrchestrator instead of EmbeddingGenerator in src/krag/orchestration/indexer.py
- [ ] T050 [US2] Update IndexingOrchestrator to determine vector_name per file based on plugin.get_embedding_model() in src/krag/orchestration/indexer.py
- [ ] T051 [US2] Update Retriever to use EmbeddingOrchestrator.embed_query() and query_batch_points in src/krag/retrieval/retriever.py
- [ ] T052 [US2] Update Retriever.retrieve() to merge results via RRF instead of single vector space search in src/krag/retrieval/retriever.py
- [ ] T053 [US2] Implement CodeFileHandler.get_embedding_model() returning jinaai/jina-embeddings-v2-base-code in examples/krag-plugin-code/src/krag_plugin_code/handler.py

**Checkpoint**: Multi-model embedding working - code and text files use appropriate embedders, queries search both spaces

---

## Phase 5: User Story 3 - Multi-LLM Routing with Hot-Swap Fallback (Priority: P3)

**Goal**: Code-specialized LLM for code-heavy queries, text LLM for text-heavy queries. Simultaneous loading when VRAM permits, hot-swap fallback otherwise. CLI `--llm` switch for manual selection.

**Independent Test**: Download both LLMs. Test simultaneous loading (verify both respond). Test hot-swap (`krag query --llm code`, then `--llm text`, verify swaps and answers). Compare code query answer quality between LLMs.

### Tests for User Story 3

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T054 [P] [US3] Contract test: LLMPool.route_and_generate() returns tuple[str, str] in tests/contract/test_llm_pool_contract.py
- [ ] T055 [P] [US3] Contract test: LLMPool.swap_to() completes without error in tests/contract/test_llm_pool_contract.py
- [ ] T056 [P] [US3] Unit test: Simultaneous mode auto-routes code-heavy chunks to code LLM in tests/unit/test_llm_pool.py
- [ ] T057 [P] [US3] Unit test: Simultaneous mode auto-routes text-heavy chunks to text LLM in tests/unit/test_llm_pool.py
- [ ] T058 [P] [US3] Unit test: Hot-swap mode loads selected LLM via --llm switch in tests/unit/test_llm_pool.py
- [ ] T059 [P] [US3] Unit test: Insufficient VRAM for multi-LLM logs warning, falls back to hot-swap in tests/unit/test_llm_pool.py
- [ ] T060 [P] [US3] Unit test: Hot-swap between LLMs completes in <60s (mock timing) in tests/unit/test_llm_pool.py
- [ ] T061 [P] [US3] Unit test: No --llm switch + single LLM loaded uses current LLM + logs suggestion in tests/unit/test_llm_pool.py
- [ ] T062 [US3] Integration test: End-to-end query with code LLM routing in tests/integration/test_llm_routing.py

### Implementation for User Story 3

- [ ] T063 [US3] Implement LLMPool.__init__() with VRAM checks and conditional multi-LLM loading in src/krag/synthesis/llm_pool.py
- [ ] T064 [US3] Implement LLMPool.determine_route() analyzing chunk composition in src/krag/synthesis/llm_pool.py
- [ ] T065 [US3] Implement LLMPool.swap_to() with Llama.close() + progress feedback in src/krag/synthesis/llm_pool.py
- [ ] T066 [P] [US3] Implement LLMPool._can_fit_both_llms() using torch.cuda.mem_get_info() in src/krag/synthesis/llm_pool.py
- [ ] T067 [P] [US3] Implement LLMPool._analyze_chunk_composition() counting code vs text metadata in src/krag/synthesis/llm_pool.py
- [ ] T068 [US3] Implement LLMPool.route_and_generate() with routing + swap + generate in src/krag/synthesis/llm_pool.py
- [ ] T069 [P] [US3] Implement LLMPool.get_status() returning slot states and VRAM info in src/krag/synthesis/llm_pool.py
- [ ] T070 [P] [US3] Implement LLMPool.close() releasing all loaded models in src/krag/synthesis/llm_pool.py
- [ ] T071 [US3] Update query command to instantiate LLMPool instead of LLMClient in src/krag/cli/query.py
- [ ] T072 [US3] Update query command to pass --llm parameter to LLMPool.route_and_generate() in src/krag/cli/query.py
- [ ] T073 [US3] Add Rich spinner for hot-swap progress feedback in src/krag/cli/query.py

**Checkpoint**: Multi-LLM routing working - code queries routed to code LLM, hot-swap functional

---

## Phase 6: User Story 4 - Code Prompt Preset (Priority: P4)

**Goal**: Code-specific prompt preset producing answers with code snippets, symbol references, and file/line citations. Auto-coupled to LLM selection.

**Independent Test**: Set preset to "code", run queries, verify answers contain code snippets and symbol references with line numbers.

### Tests for User Story 4

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T074 [P] [US4] Unit test: Code preset includes function signature and file path reference in tests/unit/test_prompt_builder.py
- [ ] T075 [P] [US4] Unit test: Code preset low temperature (0.1) returns insufficient-context phrase when lacking info in tests/unit/test_prompt_builder.py
- [ ] T076 [P] [US4] Unit test: Auto-coupling applies code preset when routing to code LLM in tests/unit/test_prompt_builder.py
- [ ] T077 [US4] Integration test: End-to-end query with code preset produces structured code answer in tests/integration/test_code_preset.py

### Implementation for User Story 4

- [ ] T078 [P] [US4] Add "code" PromptPreset to PROMPT_PRESETS dict in src/krag/synthesis/prompt_builder.py
- [ ] T079 [US4] Update query command to implement preset auto-coupling logic based on LLM route in src/krag/cli/query.py
- [ ] T080 [US4] Update PromptBuilder to format code metadata (line numbers, symbols) into prompt context in src/krag/synthesis/prompt_builder.py

**Checkpoint**: Code preset working - code answers include snippets and structured references

---

## Phase 7: User Story 5 - Enriched Chunk Metadata in Retrieval (Priority: P5)

**Goal**: Retriever boosts results where query terms match function/class names. Query results display structured source references with line numbers.

**Independent Test**: Index project with code plugin, query for specific function name, verify matching chunk gets score boost and displays with line-number context.

### Tests for User Story 5

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T081 [P] [US5] Unit test: Chunk with matching function_name gets score boost in tests/unit/test_retriever_metadata_boost.py
- [ ] T082 [P] [US5] Unit test: QueryResult.format_source_ref() produces "Class.method() at file.py:L45-L68" in tests/unit/test_query_result.py
- [ ] T083 [US5] Integration test: End-to-end query with metadata boosting and enhanced display in tests/integration/test_enriched_metadata.py

### Implementation for User Story 5

- [ ] T084 [P] [US5] Extend QueryResult model with language, function_name, class_name, start_line, end_line fields in src/krag/models/query_result.py
- [ ] T085 [P] [US5] Implement QueryResult.format_source_ref() method in src/krag/models/query_result.py
- [ ] T086 [US5] Update Retriever._metadata_boost() to boost on function_name/class_name matches in src/krag/retrieval/retriever.py
- [ ] T087 [US5] Update Retriever to populate QueryResult extended fields from vector payload in src/krag/retrieval/retriever.py
- [ ] T088 [US5] Update query command result display to use format_source_ref() in src/krag/cli/query.py

**Checkpoint**: Enriched metadata working - symbol-aware boosting and structured source references

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and refinements

- [ ] T089 [P] Update plugin-development.md with get_embedding_model() contract in docs/plugin-development.md
- [ ] T090 [P] Update plugin-user-guide.md with code plugin installation and usage in docs/plugin-user-guide.md
- [ ] T091 [P] Add troubleshooting section for VRAM warnings and hot-swap guidance in docs/troubleshooting.md
- [ ] T092 [P] Update main README with code-aware indexing feature summary in README.md
- [ ] T093 Run full test suite (unit + contract + integration) and verify all pass
- [ ] T094 Run quickstart.md validation scenarios and verify all work
- [ ] T095 Pre-commit validation: ruff format + ruff check + pytest across all code

**Final Checkpoint**: Feature complete, documented, tested, ready for merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: N/A - no foundational work needed
- **User Story 1 (Phase 3)**: Depends on Setup completion
- **User Story 2 (Phase 4)**: Depends on US1 (needs plugin with get_embedding_model())
- **User Story 3 (Phase 5)**: Depends on US2 (needs code metadata in chunks for routing)
- **User Story 4 (Phase 6)**: Depends on US3 (needs LLM routing for auto-coupling)
- **User Story 5 (Phase 7)**: Depends on US1 (needs code metadata from AST chunker)
- **Polish (Phase 8)**: Depends on all desired user stories

### User Story Dependencies

```
US1 (Chunking) ──┬──> US2 (Embedding) ───> US3 (LLM) ───> US4 (Preset)
                 │
                 └──> US5 (Metadata)

Legend:
  A ──> B  means "B depends on A"
  A ──┬──> B
      └──> C  means "B and C both depend on A but are independent of each other"
```

- **US1**: No dependencies (can start immediately after Setup)
- **US2**: Depends on US1 (needs `get_embedding_model()` from plugin)
- **US3**: Depends on US2 (needs code metadata for routing)
- **US4**: Depends on US3 (needs routing decision for auto-coupling)
- **US5**: Depends on US1 (needs code metadata), independent of US2/US3/US4

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- ASTChunker before CodeFileHandler integration
- EmbeddingOrchestrator before Indexer/Retriever wiring
- LLMPool core before query command wiring
- Independent tasks marked [P] can run in parallel

### Parallel Opportunities

- **Setup (Phase 1)**: T003-T010 all run in parallel (different files)
- **US1 Tests**: T011-T018 all run in parallel (different test files)
- **US1 Implementation**: T020-T021 parallel, T027-T028 parallel
- **US2 Tests**: T033-T039 all run in parallel
- **US2 Implementation**: T044-T045 parallel, T047-T048 parallel
- **US3 Tests**: T054-T061 all run in parallel
- **US3 Implementation**: T066-T067 parallel, T069-T070 parallel
- **US4 Tests**: T074-T076 all run in parallel
- **US4 Implementation**: T078 and T080 parallel
- **US5 Tests**: T081-T082 parallel
- **US5 Implementation**: T084-T085 parallel
- **Polish**: T089-T092 all run in parallel

---

## Parallel Example: User Story 1

After Setup (Phase 1) completes:

```bash
# Batch 1: Write ALL tests in parallel
T011: Contract test CodeFileHandler implements FileTypeHandler
T012: Contract test ASTChunker produces valid TextChunk objects
T013-T018: Unit tests for all 6 acceptance scenarios

# Verify all tests FAIL (red phase)

# Batch 2: Core implementation in parallel
T020: Language discovery system
T021: SemanticUnit dataclass

# Batch 3: ASTChunker implementation (sequential - same file)
T022: _extract_semantic_units()
T023: _units_to_chunks()
T024: _split_oversized_unit()
T025: chunk() with fallback
T026: get_chunk_metadata()

# Batch 4: Handler implementation in parallel
T027: supported_extensions()
T028: extract_text() and extract_metadata()

# Batch 5: Integration (sequential)
T029: get_chunking_strategy()
T030: initialize()
T031: Indexer wiring
T032: README

# Verify all tests PASS (green phase)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (~10 tasks, 1 day)
2. Complete Phase 3: User Story 1 (~22 tasks, 3-5 days)
3. **STOP and VALIDATE**: Test US1 independently, demo code chunking
4. Deploy if ready, or continue to US2

**MVP delivers**: AST-based code chunking with complete functions/methods as chunks

### Incremental Delivery (Recommended)

1. Setup (Phase 1) → ~1 day
2. US1 (Phase 3) → ~3-5 days → **Demo 1: Code chunking works** 🎯
3. US2 (Phase 4) → ~4-6 days → **Demo 2: Multi-model embedding + RRF works**
4. US3 (Phase 5) → ~4-6 days → **Demo 3: LLM routing + hot-swap works**
5. US4 (Phase 6) → ~1-2 days → **Demo 4: Code preset works**
6. US5 (Phase 7) → ~2-3 days → **Demo 5: Metadata boosting + display works**
7. Polish (Phase 8) → ~1-2 days → **Feature complete**

**Total estimate**: ~16-25 days for full feature

**Critical path**: Setup → US1 → US2 → US3 (all others branch from these)

### Parallel Team Strategy

With 2-3 developers after Setup completes:

**Week 1-2:**
- **Dev A**: US1 (Code-aware chunking)

**Week 3-4** (after US1 completes):
- **Dev A**: US2 (Multi-model embedding)
- **Dev B**: US5 (Enriched metadata) — depends on US1 but independent of US2

**Week 5-6** (after US2 completes):
- **Dev A**: US3 (Multi-LLM routing)
- **Dev B**: US4 (Code preset) — can start earlier, waits for US3 for auto-coupling

**Week 7:**
- **All**: Polish & integration validation

---

## Notes

- **[P]** = Parallelizable (different files, no dependencies on incomplete work)
- **[Story]** = User story label for traceability
- **TDD**: Write tests first (red), implement (green), refactor
- **Constitution**: All principles verified at plan phase, all gates pass
- **Pre-commit**: `uv run ruff format . && uv run ruff check --fix . && uv run pytest` before every commit
- **Checkpoints**: Stop after each user story to validate independently
- **MVP**: US1 alone is a valuable deliverable (code chunking)
- **Dependencies**: US2 needs US1, US3 needs US2, US4 needs US3, US5 needs US1

---

## Task Count Summary

- **Setup**: 10 tasks
- **US1**: 22 tasks (9 tests + 13 implementation)
- **US2**: 21 tasks (8 tests + 13 implementation)
- **US3**: 20 tasks (9 tests + 11 implementation)
- **US4**: 7 tasks (4 tests + 3 implementation)
- **US5**: 8 tasks (3 tests + 5 implementation)
- **Polish**: 7 tasks

**Total**: 95 tasks

**Parallel opportunities**: 45 tasks marked [P] (47% can run in parallel within constraints)
