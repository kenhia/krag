# Feature Specification: Code Quality Sprint

**Feature Branch**: `006-code-quality-sprint`
**Created**: 2026-02-18
**Status**: Draft
**Input**: Fix correctness bugs, eliminate DRY violations, standardize CLI pipeline, improve logging — based on 32 findings from post-005 deep code review.
**Reference**: [`specs/findings-prep-for-006.md`](../findings-prep-for-006.md)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Correct Retrieval Results with Multi-Model Embeddings (Priority: P1)

A user indexes their codebase with the code plugin enabled (producing text + code embedding spaces), then runs a query. The system retrieves relevant chunks, applies rank fusion correctly without distorted scores, and returns results that match the query's intent — including source files like `defaults.py` for configuration questions.

**Why this priority**: Correctness is the foundation. Multi-model retrieval is broken today — keyword/metadata boost weights overwhelm RRF scores, LLM routing never fires for code queries, and incremental re-indexing accumulates stale vectors. Users get wrong or missing results.

**Independent Test**: Index a known corpus, run the eval suite (`krag eval tests/fixtures/eval_queries.toml`), and verify the pass rate returns to 3/3. Verify that code-related queries are routed to the code LLM when a code model is configured.

**Acceptance Scenarios**:

1. **Given** a corpus is indexed with text + code embeddings, **When** a user queries "What is the default chunk size?", **Then** the system retrieves `defaults.py` as a source and answers with the correct value.
2. **Given** a corpus is indexed with multi-model embeddings, **When** results are merged via RRF, **Then** keyword/metadata boosts do not change the relative ordering of the top results by more than ±2 positions compared to RRF-only ranking.
3. **Given** a code model is configured, **When** the user queries about code (e.g., "How does the retriever work?"), **Then** the system routes the query to the code LLM rather than the text LLM.
4. **Given** a file is modified and re-indexed incrementally, **When** queries are run afterward, **Then** only the current version's chunks appear in results — no stale vectors from previous versions.
5. **Given** a vector payload has a missing or empty `file_path`, **When** retrieval runs, **Then** that single result is skipped gracefully without crashing the entire retrieval pipeline.
6. **Given** scores produced by RRF or dot-product distance, **When** the result model validates them, **Then** no validation error is raised for scores outside the [0, 1] range.

---

### User Story 2 — Consistent CLI Experience Across Commands (Priority: P2)

A user switches between `krag index`, `krag query`, and `krag eval` commands. All commands resolve configuration the same way (respecting `$XDG_CONFIG_HOME`), produce consistent error output formatting, and provide the same infrastructure features (LLM routing, vector store pre-checks, plugin loading).

**Why this priority**: Inconsistency causes user confusion and breaks setups with non-default XDG paths. The duplicated setup code also means bug fixes in one command don't propagate to others.

**Independent Test**: Set `$XDG_CONFIG_HOME` to a non-default path, place `config.toml` there, and verify all three commands (`index`, `query`, `eval`) find and use the config. Verify that eval produces the same answer quality as interactive query for the same question.

**Acceptance Scenarios**:

1. **Given** `$XDG_CONFIG_HOME` is set to `/tmp/krag-xdg/krag`, **When** the user runs `krag query`, `krag eval`, or `krag index`, **Then** all three commands find `config.toml` at that path.
2. **Given** no vector store exists on disk, **When** the user runs `krag query` or `krag eval`, **Then** both commands display a user-friendly error message (not a raw exception).
3. **Given** a code model is configured, **When** a code-related query runs via `krag eval`, **Then** it uses the same LLM routing as `krag query` would for the same question.
4. **Given** the user passes `--top-k` on the CLI, **When** no CLI value is provided, **Then** both `query` and `eval` fall back to the config file value, not a hardcoded default.
5. **Given** any CLI command encounters an error, **When** the error is displayed, **Then** the output format (Rich vs plain text) is consistent with the command's intended output mode (human-interactive vs machine-parseable).

---

### User Story 3 — Clean, Actionable Logs (Priority: P3)

A user runs `krag index --full` on a large corpus (10,000+ files) and later reviews the log file. The log contains a compact indexing summary rather than thousands of per-batch "Upserted N vectors" entries. The user can also rotate or clear the log via CLI before a debugging session.

**Why this priority**: Log noise makes debugging harder and wastes disk space. At production scale (100k+ vectors), the current per-batch logging would produce 1000+ upsert lines per index run.

**Independent Test**: Index a corpus, count log lines related to upsert operations — should be ≤10 regardless of corpus size. Run `krag log rotate` and verify the old log is archived and a fresh log starts.

**Acceptance Scenarios**:

1. **Given** a corpus of 6,838 vectors in 69 batches, **When** indexing completes, **Then** the log contains at most 10 entries for the entire upsert operation (e.g., one "Storing 6838 vectors" + periodic batch summaries).
2. **Given** a user runs `krag log rotate`, **Then** the current log is archived (e.g., `krag.log.1` or timestamped), and subsequent log output goes to a new empty log file.
3. **Given** a user runs `krag log clear`, **Then** the current log is truncated to zero bytes and subsequent logging continues to the same file.
4. **Given** a corpus of 100,000+ vectors, **When** indexing completes, **Then** total log output for the indexing operation does not exceed 50 lines.

---

### User Story 4 — Maintainable, DRY Codebase (Priority: P2)

A developer modifies the CLI pipeline initialization (e.g., changes how configs are loaded, adds a new parameter to the embedding generator). The change is made in one place and automatically applies to all commands that use that pipeline.

**Why this priority**: The current ~80 lines of verbatim-duplicated initialization code across query.py and eval.py means every bug fix or feature change must be applied in multiple places — and they've already diverged.

**Independent Test**: After refactoring, verify that the shared pipeline factory is used by both `query` and `eval` commands. Verify grep shows zero duplicate initialization blocks across CLI files.

**Acceptance Scenarios**:

1. **Given** the CLI pipeline code, **When** a developer searches for `EmbeddingOrchestrator(` construction, **Then** it appears in exactly one location (the shared factory), not in each CLI command file.
2. **Given** the CLI pipeline code, **When** a developer searches for `LLMClient(` construction, **Then** it appears in exactly one location.
3. **Given** the indexer code, **When** a developer searches for per-file processing logic (text extraction → chunking → embedding → payload building), **Then** it appears in exactly one method, not duplicated between `index_full` and `index_incremental`.
4. **Given** the codebase, **When** `_get_free_vram()` is searched for, **Then** it is defined in exactly one module.

---

### User Story 5 — Robust Indexer Behavior (Priority: P2)

A user runs incremental indexing after modifying source files. The system correctly replaces old vectors, uses the right chunker for each file type, and doesn't leak internal state between files.

**Why this priority**: Stale vectors from F-02, wrong chunker from F-04, and divergent plugin name resolution from F-12 all cause incorrect index state that degrades retrieval quality silently.

**Independent Test**: Index a file, modify it, run incremental index, query for content unique to the new version — old content should not appear.

**Acceptance Scenarios**:

1. **Given** a file was previously indexed, **When** the file is modified and incrementally re-indexed, **Then** vectors from the previous version are deleted before new ones are inserted.
2. **Given** files of different types (code, markdown, text) are being indexed in sequence, **When** file N uses a plugin chunker and file N+1 does not, **Then** file N+1 uses the default chunker, not the previous file's plugin chunker.
3. **Given** the code plugin is active, **When** incremental indexing resolves the plugin name for chunking config, **Then** it uses the same name resolution strategy as full indexing.

---

### Edge Cases

- What happens when `krag log rotate` is called and no log file exists yet?
- How does the system handle a vector store that was created with a different set of named vector spaces than what the current plugin configuration expects (read-only access at query time)?
- What happens when a file produces zero chunks after plugin processing — does it leave orphaned metadata?
- What happens when `_get_free_vram()` is called on a system with CUDA drivers but no GPU (e.g., WSL without GPU passthrough)?

## Requirements *(mandatory)*

### Functional Requirements

#### Correctness

- **FR-001**: System MUST route queries to the code LLM when the retrieved chunks are predominantly code files and a code model is configured.
- **FR-002**: System MUST delete existing vectors for a file before inserting new vectors during incremental re-indexing of modified files.
- **FR-003**: System MUST scale keyword/metadata boost weights proportionally to the score range — boosts must not change top-result ordering by more than ±2 positions compared to unmodified scores.
- **FR-004**: System MUST reset per-file state (active chunker, plugin handler) at the start of each file processing iteration to prevent state leakage between files.
- **FR-005**: System MUST gracefully skip individual results with missing or invalid payloads (e.g., empty `file_path`) without crashing the entire retrieval pipeline.
- **FR-006**: System MUST accept score values outside the [0, 1] range (e.g., RRF scores, dot-product distances) without validation errors.

#### CLI Consistency

- **FR-007**: All CLI commands (`index`, `query`, `eval`) MUST resolve configuration using the same XDG-aware path resolution logic.
- **FR-008**: All CLI commands MUST provide the same vector-store-exists pre-check with user-friendly error messaging before attempting vector store operations.
- **FR-009**: The `eval` command MUST use the same LLM routing logic (including multi-LLM pool) as the `query` command.
- **FR-010**: CLI commands MUST respect the config file's `top_k` setting as the default, with CLI flags taking precedence when explicitly provided.
- **FR-011**: CLI commands MUST use consistent error output formatting appropriate to their output mode.

#### DRY / Maintainability

- **FR-012**: System MUST provide a single shared pipeline factory for CLI command initialization, eliminating duplicated infrastructure setup.
- **FR-013**: System MUST provide a single per-file processing method for the indexer, shared by both full and incremental indexing paths.
- **FR-014**: System MUST maintain exactly one implementation of VRAM availability checking.
- **FR-015**: System MUST use proper type annotations (not `Any`) for parameters where typed interfaces or protocols exist.

#### Logging

- **FR-016**: System MUST limit upsert-related log entries to at most 10 per indexing operation, regardless of corpus size.
- **FR-017**: System MUST provide a `krag log rotate` command that archives the current log file and creates a fresh log.
- **FR-018**: System MUST provide a `krag log clear` command that truncates the current log file to zero bytes.

#### Cleanup

- **FR-019**: System MUST remove dead code (unused functions, unreferenced protocol definitions).
- **FR-020**: System MUST not rely on `__del__` for resource cleanup when `__enter__`/`__exit__` context managers are available.
- **FR-021**: System MUST use module-level imports consistently, not redundant local re-imports.
- **FR-022**: System MUST allow embedding models with different vector dimensions across named vector spaces (Qdrant supports this natively).

### Key Entities

- **Pipeline**: The shared infrastructure (config → embeddings → vector store → LLM → query engine) used by both `query` and `eval` commands. Single point of construction.
- **FileProcessor**: The extracted per-file processing unit (text extraction → chunking → embedding → payload building) shared by `index_full` and `index_incremental`.
- **LogManager**: The component handling log file rotation, clearing, and path resolution for the `krag log` CLI subcommand group.

## Assumptions

- The existing test suite (800 tests) provides adequate coverage to detect regressions during refactoring.
- The `krag.gpu` module already exists and is the appropriate location for consolidated VRAM checking.
- The `get_krag_config_dir()` utility already exists in the codebase and correctly handles XDG paths.
- Log file location is deterministic via the existing logging configuration (currently `~/.local/state/krag/logs/krag.log`).
- The short name `"text"` for the default vector space is a project-wide convention that can be documented as an invariant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The eval suite (`tests/fixtures/eval_queries.toml`) achieves a pass rate of 3/3 (100%), restored from the current 2/3 (67%).
- **SC-002**: All 800+ existing tests continue to pass with zero regressions.
- **SC-003**: Duplicated initialization code is reduced to zero: `EmbeddingOrchestrator(`, `LLMClient(`, `EmbeddingGenerator(`, and config loading each appear in exactly one construction site.
- **SC-004**: Upsert log entries for a 6,838-vector indexing run are ≤10, down from ~70.
- **SC-005**: `krag log rotate` and `krag log clear` commands are functional and documented.
- **SC-006**: `krag query` and `krag eval` produce consistent behavior for `$XDG_CONFIG_HOME`, error output, and LLM routing.
- **SC-007**: Code LLM routing is verified to fire correctly when a code model is configured and code-heavy chunks are retrieved.
- **SC-008**: No dead code remains: unused functions and unreferenced type definitions are removed.
