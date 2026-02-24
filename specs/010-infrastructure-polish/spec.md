# Feature Specification: Infrastructure Improvements & Polish

**Feature Branch**: `010-infrastructure-polish`
**Created**: 2026-02-23
**Status**: Draft

## Overview

This sprint addresses a collection of correctness bugs, code quality debt, and user-experience improvements identified during Sprint 009 testing. Items are drawn from the project backlog and grouped around making krag more reliable, easier to configure, and more transparent to operate.

Items in scope:
1. Fix incremental indexing metadata loss across directory changes
2. Fix index-status staleness while indexing is active
3. Unify the query and debug-query code paths
4. Move code-embedding model configuration into krag core
5. Operational UX tweaks (startup log banners, log rotation, rich markdown output)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Incremental indexing preserves unchanged files across directory changes (Priority: P1)

A developer has previously indexed `~/src/project-a/`. They now run a broader index of `~/src/` (which includes `project-a/` as a subdirectory). They expect the previously-indexed files to be recognised as unchanged and skipped — not deleted and re-added.

**Why this priority**: Data correctness bug. Every directory expansion causes unnecessary delete+re-add cycles in the vector store, increases indexing time, and produces misleading change counts.

**Independent Test**: Index a directory, then index a parent directory. Confirm files from the first run appear as `unchanged` in the second run, that no deletions are logged for those files, and that the vector count does not change for already-indexed files.

**Acceptance Scenarios**:

1. **Given** `~/src/proj/` has been indexed, **When** `krag index -d ~/src/` is run, **Then** all files under `~/src/proj/` are reported as `unchanged` and zero deletions are logged for those files.
2. **Given** metadata exists for 50 files, **When** the next run covers a superset directory and those files are unmodified, **Then** `files_skipped_unchanged` equals 50.
3. **Given** a file was indexed in run 1 and genuinely modified before run 2, **When** run 2 covers a parent directory, **Then** that file is reported as `modified` and re-indexed.
4. **Given** a file was indexed in run 1 but deleted before run 2, **When** run 2 covers a parent directory, **Then** that file is reported as `deleted` and removed from the index.

---

### User Story 2 — Index-status accurately reflects a running indexing job (Priority: P1)

A user triggers a large indexing run and immediately polls `krag index-status`. They expect to see that indexing is in progress, not the result of the previous run.

**Why this priority**: Correctness bug. The status command is the primary tool for monitoring indexing progress; returning stale data misleads the user into thinking the previous run is the current state.

**Independent Test**: Start a long indexing run, immediately poll `krag index-status`, and confirm it returns `status: running` rather than the prior completed result.

**Acceptance Scenarios**:

1. **Given** a previous run completed (status: completed), **When** a new indexing run is started and `index-status` is called before it finishes, **Then** the response shows `status: running`.
2. **Given** indexing is running, **When** `index-status` is polled repeatedly, **Then** all responses show `status: running` until the job completes.
3. **Given** an indexing run just completed, **When** `index-status` is called, **Then** the response shows the completed run's full statistics.

---

### User Story 3 — Debug mode is a transparent superset of standard query (Priority: P2)

A developer investigating unexpected query results runs the same query with `--debug` added. They expect identical retrieval results and LLM output — the flag must never change the answer, only add observability metadata.

**Why this priority**: The current two-path architecture creates subtle behavioural differences. Unifying the paths eliminates a class of hard-to-diagnose bugs and makes `--debug` a trustworthy diagnostic tool.

**Independent Test**: Run the same query with and without `--debug`. Confirm both return identical `answer` and `sources`. The `--debug` response additionally contains populated `debug` metadata.

**Acceptance Scenarios**:

1. **Given** any query and mode, **When** the same query is run with and without `--debug`, **Then** the `answer` and `sources` are identical.
2. **Given** a mode with `critic_enabled = true`, **When** a query is run with `--debug`, **Then** `debug.critic_scores`, `debug.chunks_pre_critic`, and `debug.chunks_post_critic` are populated and reflect the same filtering as the non-debug run.
3. **Given** a mode with `llm.slot = "code"`, **When** a query is run with `--debug`, **Then** `debug.llm_used` equals `"code"`.
4. **Given** a query with `--debug`, **When** the response is returned, **Then** all timing, routing, and retrieval metadata fields are populated.

---

### User Story 4 — Code embedding is configured in krag core without a plugin (Priority: P2)

A user who wants code-aware search enables the code embedding model by adding an `[embedding_code]` section to their krag config, without needing to install or configure a separate plugin.

**Why this priority**: The current situation couples a capability (dual-embedding for code) to the plugin distribution mechanism. Users building on krag core should not need a plugin just to get code-quality embeddings.

**Independent Test**: Remove the code plugin's embedding model declaration. Add `[embedding_code]` to the base krag config. Run indexing and confirm that code chunks are embedded using the code model and that named vector spaces (`text`, `code`) are present in the vector store.

**Acceptance Scenarios**:

1. **Given** a krag config with `[embedding_code]` section, **When** indexing runs, **Then** code files are embedded using the code embedding model and stored in the `code` named vector space.
2. **Given** a krag config without `[embedding_code]`, **When** indexing runs, **Then** all files use the default embedding model (single vector space, backwards-compatible).
3. **Given** both krag core `[embedding_code]` and a plugin that registers a code embedding model, **When** indexing runs, **Then** the plugin takes precedence.
4. **Given** `[embedding_code]` is configured, **When** `krag status` is called, **Then** both embedding models are listed under `embedding_models`.

---

### User Story 5 — Operational visibility: log bookmarks, log rotation, and rich responses (Priority: P3)

An operator monitoring kragd can clearly see in the log when the service started, became ready, and shut down. They can rotate logs before a debugging session with one flag. Query responses that contain markdown render with appropriate formatting in the terminal.

**Why this priority**: Quality-of-life improvements. Log bookmarks make it faster to find relevant log sections. Log rotation is a common operational need. Rich markdown rendering improves readability. None are correctness issues.

**Independent Test**: Start kragd and confirm `KRAGD STARTING` and `KRAGD READY` appear in the log. Stop kragd and confirm `KRAGD SHUTTING DOWN` appears. Run `kragd --rotate-logs` and confirm a fresh log file is started. Run a query whose answer contains a code block and confirm it renders with syntax highlighting.

**Acceptance Scenarios**:

1. **Given** kragd starts, **Then** the log contains a clearly visible `KRAGD STARTING` entry, followed by `KRAGD READY` once the service is accepting connections.
2. **Given** kragd receives a shutdown signal, **Then** the log contains a `KRAGD SHUTTING DOWN` entry.
3. **Given** `kragd --rotate-logs` is used at startup, **Then** any existing log file is archived and a fresh log file is started.
4. **Given** a query response contains markdown (code blocks, bullet lists, headings), **When** displayed in an interactive terminal, **Then** the output renders with rich formatting rather than raw markdown syntax.

---

### Edge Cases

- Indexing directory changes from `/dir/a` to `/dir/b` (non-overlapping): previously indexed files in `/dir/a` must be correctly identified as deleted.
- Empty or corrupted metadata file: indexer must fall back to a fresh state without crashing.
- Index-status called concurrently as a running job finishes: the transition from `running` to `completed` must be atomic.
- `[embedding_code]` model file not present: indexer must fail with a clear actionable error, not silently fall back to single-model mode.
- Log rotation when no existing log file is present: must succeed without error.
- Query response is plain text with no markdown: rich rendering must not add spurious formatting.
- `krag` output is piped or redirected: rich markdown rendering must be suppressed (no ANSI codes in non-TTY output).

---

## Requirements *(mandatory)*

### Functional Requirements

**Incremental indexing metadata (US1)**

- **FR-001**: When an indexing run completes, the saved metadata MUST include all files ever indexed — not just files processed in the current run — updated with the current run's results.
- **FR-002**: On a subsequent indexing run covering a different or broader directory, previously-indexed unchanged files MUST be classified as `unchanged` and not deleted and re-added to the vector store.
- **FR-003**: The metadata store MUST be the single source of truth for what is indexed; per-run state MUST be merged into the persistent store, not replace it.

**Index-status accuracy (US2)**

- **FR-004**: `GET /index/status` MUST return `status: running` whenever an indexing job is active, regardless of whether a previous completed job exists in the cache.
- **FR-005**: The active-indexing check MUST be evaluated before returning any cached results.

**Query / debug-query unification (US3)**

- **FR-006**: The `query` and `debug_query` service methods MUST share a single retrieval-and-synthesis code path; logic MUST NOT be duplicated between them.
- **FR-007**: The `--debug` flag MUST produce identical `answer` and `sources` to the non-debug run for the same query and mode.
- **FR-008**: Debug metadata (timing, routing, critic scores, vector spaces) MUST be collected and returned only when `include_debug` is requested.

**Code embedding in core (US4)**

- **FR-009**: A `[embedding_code]` configuration section MUST be supported in the krag core config file, specifying a code embedding model and its named vector space.
- **FR-010**: When `[embedding_code]` is configured, the indexer MUST embed code files using the code model and store them in the `code` named vector space.
- **FR-011**: The absence of `[embedding_code]` MUST preserve existing single-model behaviour with no breaking changes to existing configs or data.
- **FR-012**: Plugin-registered embedding models MUST continue to take precedence over the built-in `[embedding_code]` setting.

**Operational UX (US5)**

- **FR-013**: kragd MUST log a prominent startup banner when the process begins initialising.
- **FR-014**: kragd MUST log a prominent ready banner once the HTTP server is accepting requests.
- **FR-015**: kragd MUST log a prominent shutdown banner when shutdown is initiated.
- **FR-016**: kragd MUST support a `--rotate-logs` flag that archives the existing log file before starting a new one.
- **FR-017**: The CLI `query` command MUST render markdown in responses using rich formatting when stdout is an interactive terminal.

### Assumptions

- Metadata is stored as a single global `metadata.json` (not per-directory). The fix merges per-run results into this store rather than replacing it.
- Log rotation archives by renaming the existing log file with a timestamp suffix; it does not delete the old file.
- Rich markdown rendering uses the existing `rich` library dependency; no new dependencies are required.
- Rich markdown is suppressed when stdout is not a TTY to avoid polluting piped output with ANSI escape codes.
- The default code embedding model for `[embedding_code]` is `jinaai/jina-embeddings-v2-base-code`, matching what `krag-plugin-code` currently uses, but any model path is configurable.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Re-indexing a parent directory of a previously-indexed directory produces zero deletions and zero re-additions for unchanged files; `files_skipped_unchanged` equals the count of previously-indexed unmodified files.
- **SC-002**: `krag index-status` returns `status: running` within one second of a new indexing job starting, even when a previous completed result is cached.
- **SC-003**: Running the same query with and without `--debug` produces identical `answer` and `sources` fields 100% of the time (for the same mode and index state).
- **SC-004**: A fresh krag install with `[embedding_code]` in config (no extra plugins) successfully indexes a mixed codebase and produces both `text` and `code` named vector spaces in the vector store.
- **SC-005**: kragd startup, ready, and shutdown events are each identifiable in the log file by a single `grep` producing exactly one matching line per event.
- **SC-006**: A query response containing a fenced code block renders with visible syntax highlighting in an interactive terminal session.
