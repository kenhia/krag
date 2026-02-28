# Tasks: Obsidian Vault Plugin

**Input**: Design documents from `/specs/011-obsidian-plugin/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: TDD is non-negotiable per constitution. Tests are included for all phases.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, plugin package structure, and core architecture extensions

- [x] T001 Create plugin package directory structure per plan at examples/krag-plugin-obsidian/
- [x] T002 Create pyproject.toml with hatchling build, krag.plugins entry point, pyyaml dependency at examples/krag-plugin-obsidian/pyproject.toml
- [x] T003 [P] Create __init__.py with version and plugin metadata at examples/krag-plugin-obsidian/src/krag_plugin_obsidian/__init__.py
- [x] T004 [P] Create README.md with plugin description and usage at examples/krag-plugin-obsidian/README.md
- [x] T005 Install plugin in editable mode via `uv pip install -e examples/krag-plugin-obsidian`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core architecture extensions that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational

- [x] T006 [P] Test claims_file() default returns False for all existing handlers in tests/unit/test_claims_file.py
- [x] T007 [P] Test _resolve_by_path_claim() returns None when no plugins have has_claims_file in tests/unit/test_registry_path_claim.py
- [x] T008 [P] Test get_handler_for_file() two-phase resolution: path-claim first, then extension fallback in tests/unit/test_registry_path_claim.py
- [x] T009 [P] Test per-chunk target_collection routing splits vectors to correct collections in tests/unit/test_chunk_routing.py
- [x] T010 [P] Test per-chunk routing fallback when target_collection absent uses route_file() in tests/unit/test_chunk_routing.py
- [x] T011 [P] Test merge_entries() adds new terms without overwriting existing in tests/unit/test_lexicon_merge.py

### Implementation for Foundational

- [x] T012 Add claims_file(file_path: Path) -> bool method to FileTypeHandler ABC (default False) in src/krag/plugins/interfaces.py
- [x] T013 Add has_claims_file: bool = False field to PluginMetadata in src/krag/models/configuration.py
- [x] T014 Add _resolve_by_path_claim() method and modify get_handler_for_file() for two-phase resolution in src/krag/plugins/registry.py
- [x] T015 Set has_claims_file flag during discover_plugins() via method resolution check in src/krag/plugins/registry.py
- [x] T016 Add per-chunk target_collection routing logic in index_full() in src/krag/orchestration/indexer.py
- [x] T017 Add per-chunk target_collection routing logic in index_incremental() in src/krag/orchestration/indexer.py
- [x] T018 Add merge_entries(entries: dict[str, str], source: str) method to LexiconStore in src/krag/lexicon/lexicon_store.py
- [x] T019 Run pre-commit validation: ruff format, ruff check --fix, pytest

**Checkpoint**: Foundation ready — path-based claiming, chunk-level routing, and lexicon merging infrastructure all in place. All existing tests still pass.

---

## Phase 3: User Story 1 — Index an Obsidian Vault (Priority: P1) 🎯 MVP

**Goal**: Configure vault paths, index .md files under those paths via the Obsidian plugin, and store chunks with obsidian:// virtual path prefixes.

**Independent Test**: Configure one vault path in config.toml, run krag index, and verify notes from the vault appear in the index with obsidian:// path prefixes.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US1] Test ObsidianConfig Pydantic schema validates vault mappings in examples/krag-plugin-obsidian/tests/test_config.py
- [ ] T021 [P] [US1] Test ObsidianConfig rejects invalid vault entries (non-string, empty) in examples/krag-plugin-obsidian/tests/test_config.py
- [ ] T022 [P] [US1] Test handler.initialize() resolves vault paths, warns on missing in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T023 [P] [US1] Test handler.claims_file() returns True for files under vault paths in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T024 [P] [US1] Test handler.claims_file() returns False for files outside vault paths in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T025 [P] [US1] Test handler.claims_file() returns False when no vaults configured in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T026 [P] [US1] Test handler.extract_text() reads .md file content and strips frontmatter in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T027 [P] [US1] Test handler.extract_metadata() returns frontmatter fields in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T028 [P] [US1] Test handler.supported_extensions() returns [".md", ".markdown"] in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T029 [P] [US1] Test virtual path generation: filesystem path → obsidian://vault-name/relative-path in examples/krag-plugin-obsidian/tests/test_handler.py

### Implementation for User Story 1

- [ ] T030 [US1] Create ObsidianConfig Pydantic model with vaults dict validation in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/config.py
- [ ] T031 [US1] Implement ObsidianFileTypeHandler with name, version, required_api_version, supported_extensions in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T032 [US1] Implement initialize() — parse vaults config, resolve paths, warn on missing, set up vault_paths dict in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T033 [US1] Implement claims_file() — check if file is under any configured vault path in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T034 [US1] Implement config_schema() returning ObsidianConfig in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T035 [US1] Implement extract_text() — read .md file, parse frontmatter, return body text in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T036 [US1] Implement extract_metadata() — parse YAML frontmatter, return as dict in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T037 [US1] Implement _resolve_vault() helper — find which vault a file belongs to and compute virtual path in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T038 [US1] Implement get_chunking_strategy() returning custom ObsidianChunker with vault config in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T039 [US1] Run pre-commit validation: ruff format, ruff check --fix, pytest

**Checkpoint**: Obsidian plugin can be installed, configured with vault paths, claims .md files under those paths, extracts text, and produces chunks with virtual obsidian:// paths. Basic vault indexing works end-to-end.

---

## Phase 4: User Story 2 — Mixed-Content Routing (Priority: P1)

**Goal**: Split note content into prose (→ docs collection) and fenced code blocks (→ code collection) with per-chunk routing metadata.

**Independent Test**: Index a note containing both prose and a fenced Python block, verify via debug/qdrant that code goes to code collection and prose goes to docs collection.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T040 [P] [US2] Test ObsidianChunker splits prose-only note into docs-targeted chunks in examples/krag-plugin-obsidian/tests/test_chunker.py
- [ ] T041 [P] [US2] Test ObsidianChunker splits fenced code block (with language) into code-targeted chunk in examples/krag-plugin-obsidian/tests/test_chunker.py
- [ ] T042 [P] [US2] Test ObsidianChunker treats fenced code block without language as docs-targeted in examples/krag-plugin-obsidian/tests/test_chunker.py
- [ ] T043 [P] [US2] Test ObsidianChunker handles multiple code blocks with different languages in examples/krag-plugin-obsidian/tests/test_chunker.py
- [ ] T044 [P] [US2] Test ObsidianChunker preserves language identifier in chunk metadata in examples/krag-plugin-obsidian/tests/test_chunker.py
- [ ] T045 [P] [US2] Test ObsidianChunker get_chunk_metadata() returns target_collection and content_type in examples/krag-plugin-obsidian/tests/test_chunker.py
- [ ] T046 [P] [US2] Test ObsidianChunker handles nested/varying backtick fence lengths in examples/krag-plugin-obsidian/tests/test_chunker.py
- [ ] T047 [P] [US2] Test ObsidianChunker handles empty note and zero-content gracefully in examples/krag-plugin-obsidian/tests/test_chunker.py

### Implementation for User Story 2

- [ ] T048 [US2] Create ContentSegment dataclass (text, segment_type, language, start_line) in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/chunker.py
- [ ] T049 [US2] Implement _split_content() — parse fenced code blocks vs prose segments using regex state machine in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/chunker.py
- [ ] T050 [US2] Implement ObsidianChunker.chunk() — split content into segments, produce TextChunk objects with virtual paths in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/chunker.py
- [ ] T051 [US2] Implement ObsidianChunker.get_chunk_metadata() — return target_collection, language, vault_name, content_type per chunk in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/chunker.py
- [ ] T052 [US2] Run pre-commit validation: ruff format, ruff check --fix, pytest

**Checkpoint**: Notes with mixed prose and code are split correctly. Code blocks route to code collection, prose to docs. Language metadata preserved.

---

## Phase 5: User Story 3 — Path-Based Plugin Ownership (Priority: P1)

**Goal**: Ensure Obsidian plugin claims only vault-path .md files while the generic markdown plugin handles all other .md files.

**Independent Test**: Index a directory containing both vault and non-vault markdown files, verify each file was handled by the correct plugin.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T053 [P] [US3] Test vault .md file handled by Obsidian plugin, non-vault .md by markdown plugin in tests/integration/test_obsidian_indexing.py
- [ ] T054 [P] [US3] Test no vaults configured → all .md files handled by markdown plugin in tests/integration/test_obsidian_indexing.py
- [ ] T055 [P] [US3] Test two vaults configured → correct virtual path prefix per vault in tests/integration/test_obsidian_indexing.py
- [ ] T056 [P] [US3] Test overlapping vault paths → first vault in config order wins in tests/integration/test_obsidian_indexing.py

### Implementation for User Story 3

- [ ] T057 [US3] Verify end-to-end indexing pipeline handles claims_file priority correctly (integration test fixtures) in tests/integration/test_obsidian_indexing.py
- [ ] T058 [US3] Add handler edge case handling: zero-byte files, binary files, permission errors in examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T059 [US3] Run pre-commit validation: ruff format, ruff check --fix, pytest

**Checkpoint**: Path-based ownership works correctly. Obsidian plugin and markdown plugin coexist without conflicts. All P1 stories complete — MVP delivered.

---

## Phase 6: User Story 4 — Virtual Path Display (Priority: P2)

**Goal**: Query results show clean obsidian://vault-name/path references instead of raw filesystem paths.

**Independent Test**: Query indexed vault content and verify file_path field uses obsidian:// prefix.

### Tests for User Story 4

- [ ] T060 [P] [US4] Test virtual path determinism — same file always produces same virtual path in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T061 [P] [US4] Test multiple vaults produce distinct prefixes (obsidian://gratch/..., obsidian://work/...) in examples/krag-plugin-obsidian/tests/test_handler.py

### Implementation for User Story 4

- [ ] T062 [US4] Verify virtual paths appear correctly in query results via integration test in tests/integration/test_obsidian_indexing.py
- [ ] T063 [US4] Run pre-commit validation: ruff format, ruff check --fix, pytest

**Checkpoint**: Virtual paths appear in all query results for vault-sourced content. Multiple vaults show distinct prefixes.

---

## Phase 7: User Story 5 — Custom Obsidian Retrieval Mode (Priority: P2)

**Goal**: Built-in obsidian retrieval mode targeting docs (1.0) and code (0.7) collections with critic enabled.

**Independent Test**: Query with --mode obsidian and verify results are drawn from docs and code collections.

### Tests for User Story 5

- [ ] T064 [P] [US5] Test obsidian.toml loads as valid ModeConfiguration via ModeLoader in tests/unit/test_obsidian_mode.py
- [ ] T065 [P] [US5] Test obsidian mode has correct collection weights (docs=1.0, code=0.7) in tests/unit/test_obsidian_mode.py
- [ ] T066 [P] [US5] Test obsidian mode has critic enabled with threshold 3 in tests/unit/test_obsidian_mode.py
- [ ] T067 [P] [US5] Test obsidian mode uses balanced prompt preset in tests/unit/test_obsidian_mode.py

### Implementation for User Story 5

- [ ] T068 [US5] Create obsidian.toml retrieval mode definition at src/krag/modes/builtin/obsidian.toml
- [ ] T069 [US5] Run pre-commit validation: ruff format, ruff check --fix, pytest

**Checkpoint**: Users can query with --mode obsidian to get vault-optimized retrieval. Mode auto-discovered by ModeLoader.

---

## Phase 8: User Story 6 — Obsidian-Specific Lexicon (Priority: P3)

**Goal**: Obsidian-specific terminology available in the domain lexicon for improved vault query retrieval.

**Independent Test**: Verify lexicon entries exist for Obsidian terms after plugin initialization.

### Tests for User Story 6

- [ ] T070 [P] [US6] Test lexicon.json contains all required terms (backlink, daily note, canvas, etc.) in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T071 [P] [US6] Test initialize() merges lexicon entries into LexiconStore in examples/krag-plugin-obsidian/tests/test_handler.py
- [ ] T072 [P] [US6] Test merge does not overwrite user-defined terms in examples/krag-plugin-obsidian/tests/test_handler.py

### Implementation for User Story 6

- [ ] T073 [US6] Create lexicon.json with 10 Obsidian terms and definitions at examples/krag-plugin-obsidian/src/krag_plugin_obsidian/lexicon.json
- [ ] T074 [US6] Add lexicon loading and merge_entries() call in initialize() at examples/krag-plugin-obsidian/src/krag_plugin_obsidian/handler.py
- [ ] T075 [US6] Run pre-commit validation: ruff format, ruff check --fix, pytest

**Checkpoint**: Obsidian terms available in lexicon after plugin initialization. User-defined terms not overwritten.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Live tests, documentation, and final validation across all stories

- [ ] T076 [P] Create live test for vault indexing and query against kragd in tests/live/test_live_obsidian.py
- [ ] T077 [P] Create live test for mixed-content routing verification in tests/live/test_live_obsidian.py
- [ ] T078 [P] Create live test for --mode obsidian query in tests/live/test_live_obsidian.py
- [ ] T079 [P] Test path-based resolution adds <10ms overhead per file via timing assertion in tests/unit/test_registry_path_claim.py (SC-005). If target is not met, document actual latency before optimizing.
- [ ] T080 [P] Test indexing 10,000 synthetic .md files completes without errors or timeouts in tests/integration/test_obsidian_indexing.py (SC-007)
- [ ] T081 Validate quickstart.md steps work end-to-end
- [ ] T082 Run full test suite: uv run pytest (all tests pass, no regressions)
- [ ] T083 Run pre-commit validation: ruff format, ruff check --fix, pytest

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories 1–3 (Phases 3–5)**: All P1 — depend on Foundational; Story 3 integration tests depend on Story 1 implementation
- **User Stories 4–5 (Phases 6–7)**: P2 — depend on Foundational; Story 4 validates Story 1 virtual paths
- **User Story 6 (Phase 8)**: P3 — depends on Foundational (merge_entries)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — No dependencies on other stories. This IS the MVP.
- **User Story 2 (P1)**: Can start after Foundational — Needs US1 handler shell but not full implementation. Custom chunker is independent of handler.
- **User Story 3 (P1)**: Depends on US1 handler being implemented (integration tests need a working plugin). Can run in parallel with US2.
- **User Story 4 (P2)**: Depends on US1 (virtual paths are set during US1 implementation). Verification-focused — mostly tests.
- **User Story 5 (P2)**: Fully independent of plugin code — just a TOML file. Can run in parallel with any story.
- **User Story 6 (P3)**: Depends on Foundational (merge_entries). Plugin-side implementation is in handler.initialize().

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Config before handler logic
- Handler before chunker
- Core implementation before integration tests
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks T003–T004 can run in parallel
- All Foundational tests T006–T011 can run in parallel
- All US1 tests T020–T029 can run in parallel
- All US2 tests T040–T047 can run in parallel
- US5 (TOML mode) can run in parallel with any other user story
- US6 (lexicon) can run in parallel with US2–US5

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task T040: "Test ObsidianChunker splits prose-only note"
Task T041: "Test ObsidianChunker splits fenced code block"
Task T042: "Test ObsidianChunker treats untagged code as docs"
Task T043: "Test ObsidianChunker handles multiple code blocks"
Task T044: "Test ObsidianChunker preserves language metadata"
Task T045: "Test ObsidianChunker get_chunk_metadata()"
Task T046: "Test ObsidianChunker nested fences"
Task T047: "Test ObsidianChunker empty note"
```

---

## Implementation Strategy

### MVP First (User Stories 1–3)

1. Complete Phase 1: Setup — plugin package scaffolding
2. Complete Phase 2: Foundational — claims_file, chunk routing, lexicon merge
3. Complete Phase 3: User Story 1 — basic vault indexing with virtual paths
4. **STOP and VALIDATE**: Index a real vault, verify obsidian:// paths in results
5. Complete Phase 4: User Story 2 — mixed-content splitting
6. Complete Phase 5: User Story 3 — ownership coexistence with markdown plugin
7. **MVP DELIVERED**: All P1 stories complete and independently tested

### Incremental Delivery

1. Setup + Foundational → Architecture extensions in place
2. Add User Story 1 → Vault indexing works → Deploy/Demo (MVP!)
3. Add User Story 2 → Code blocks split into code collection → Demo
4. Add User Story 3 → Coexistence verified → P1 Complete
5. Add User Stories 4–5 → Virtual paths + mode → P2 Complete
6. Add User Story 6 → Lexicon → P3 Complete
7. Polish phase → Live tests, docs, final validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution: TDD non-negotiable, pre-commit validation before every commit
