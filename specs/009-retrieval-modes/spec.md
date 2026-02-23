# Feature Specification: Retrieval Modes, Multi-Collection Qdrant, Domain Lexicon, and Context Critic

**Feature Branch**: `009-retrieval-modes`
**Created**: 2026-02-22
**Status**: Draft
**Input**: User description: "Retrieval Modes, Multi-Collection Qdrant, Domain Lexicon, and Context Critic"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Fix Lifecycle Timer Race Condition (Priority: P1)

As a krag user running long indexing jobs, I want the service to reliably reload the LLM after indexing completes, so that I don't see alarming error messages in the logs and can trust that the system is functioning correctly.

Currently, the lifecycle manager's idle timer can fire mid-indexing, loading an LLM while embedding models still occupy VRAM. When indexing finishes, the post-indexing LLM reload fails because VRAM is already occupied. The service still works (the old pool reference survives), but the log emits a scary "Failed to reload LLM after indexing" error. This must be fixed before building new features on top of the lifecycle and retrieval systems.

**Why this priority**: This is a known bug from Sprint 008 that causes confusing log output and represents a race condition in the service lifecycle. Fixing it first ensures a stable foundation for the remaining Sprint 009 features which interact with the same lifecycle and LLM loading paths.

**Independent Test**: Can be tested by triggering an indexing job that takes longer than the idle timeout, then verifying the LLM reloads cleanly without errors in the log.

**Acceptance Scenarios**:

1. **Given** the service is running with a 300-second idle timeout, **When** an indexing job runs for longer than the idle timeout, **Then** the idle timer does not fire during indexing, and the post-indexing LLM reload succeeds without error messages.
2. **Given** the service is idle after indexing completes, **When** the idle timeout elapses, **Then** the idle timer fires normally and the secondary LLM is unloaded as expected.
3. **Given** an indexing job is in progress, **When** the user queries the service status, **Then** the status reflects that the idle timer is paused and indexing is active.

---

### User Story 2 — Multi-Collection Qdrant Setup (Priority: P1)

As a krag user indexing a mixed codebase (source code, tests, documentation, and prose), I want my indexed content partitioned into separate Qdrant collections by content type, so that queries can target specific content types or combine them with per-collection weighting for more relevant results.

Today, all content goes into a single Qdrant collection (`krag_embeddings`) with named vector spaces for different embedding models. This sprint introduces four distinct collections — **code**, **tests**, **docs**, and **text** — each holding content appropriate to its type. Files are routed to collections based on file type and path patterns. Each collection uses the embedding model best suited to its content type.

**Why this priority**: Multi-collection storage is the foundational data layer change that the mode system (Story 3) builds upon. Without separate collections, modes cannot selectively query subsets of indexed content.

**Independent Test**: Can be tested by indexing a mixed project directory and verifying that files land in the correct collections, with each collection using its designated embedding model. Query results should indicate which collection each chunk came from.

**Acceptance Scenarios**:

1. **Given** a project directory containing `.py`, `.ts`, and `.rs` source files, **When** indexing runs, **Then** those files are stored in the **code** collection.
2. **Given** a project directory containing files under `tests/` or `test/` directories, or files matching `test_*.py` / `*_test.go` patterns, **When** indexing runs, **Then** those files are stored in the **tests** collection.
3. **Given** a project directory containing `.md`, `.rst`, and `.adoc` files, **When** indexing runs, **Then** those files are stored in the **docs** collection.
4. **Given** a project directory containing `.txt`, `.log`, `.csv`, and other general text files, **When** indexing runs, **Then** those files are stored in the **text** collection.
5. **Given** content is indexed into multiple collections, **When** a query runs without a mode override, **Then** results are retrieved from all collections and merged via a fusion strategy, with each result annotated with its source collection.

**Edge Cases**:

- A file that could match multiple collections (e.g., a test file with `.md` extension) should be routed by the most specific rule (path-based rules take precedence over extension-based rules).
- Plugins may override collection routing for file types they handle (e.g., the code plugin could route certain file types to **code** regardless of path).
- Empty collections (e.g., a project with no tests) should not cause errors during querying.

---

### User Story 3 — Mode System (Priority: P1)

As a krag user, I want to select a retrieval **mode** (e.g., `code`, `docs`, `research`, `debug`) instead of manually choosing an LLM, so that a single flag controls which collections are searched, which LLM generates the answer, which prompt preset is used, and what retrieval parameters apply.

Today, the `--llm text|code` flag only switches the LLM. The new `--mode` flag replaces it and bundles together: target collections (with per-collection weights), LLM selection, prompt preset, retrieval parameters (top_k, similarity threshold), and optional context critic settings — all defined in a TOML configuration file per mode.

**Why this priority**: The mode system is the central user-facing feature of this sprint. It ties together multi-collection retrieval, LLM routing, prompt selection, and the context critic into a single, coherent user experience. It replaces the current `--llm` flag with a richer abstraction.

**Independent Test**: Can be tested by creating a mode TOML file, querying with `--mode <name>`, and verifying that the correct collections are queried, the correct LLM is used, and the correct prompt preset is applied.

**Acceptance Scenarios**:

1. **Given** a mode named `code` is defined (targeting the **code** and **tests** collections, using the code LLM, and the `code` prompt preset), **When** the user runs `krag query --mode code "How does the retry logic work?"`, **Then** only the code and tests collections are searched, the code LLM generates the response, and the code prompt preset is applied.
2. **Given** no `--mode` flag is provided, **When** the user runs a query, **Then** a built-in `default` mode is used that searches all collections with balanced weights, uses the text LLM, and applies the balanced prompt preset (preserving current behavior).
3. **Given** the user provides `--mode docs`, **When** the query runs, **Then** only the docs collection is searched, the text LLM is used, and a documentation-focused prompt is applied.
4. **Given** a mode configuration file specifies collection weights (e.g., code: 0.7, tests: 0.3), **When** results are merged from those collections, **Then** the weights influence the final ranking of results.
5. **Given** the `--llm` flag is still present (deprecated), **When** the user uses `--llm code`, **Then** a deprecation warning is shown and the flag is translated to the equivalent `--mode code` behavior.
6. **Given** the user runs `krag modes list`, **Then** all available modes are displayed with their descriptions, target collections, and LLM assignments.
7. **Given** the user runs `krag modes show <name>`, **Then** the full configuration of that mode is displayed.

**Edge Cases**:

- If a mode references a collection that has no indexed content, the mode should still work (returning results from other targeted collections, or an empty result set with a clear message).
- If a mode references a code LLM but no code model is configured, the system should fall back to the text LLM with a warning (preserving current fallback behavior).
- Mode names are case-insensitive.

---

### User Story 4 — Domain Lexicon (Priority: P2)

As a krag user working on a project with specialized terminology (internal codenames, acronyms, domain-specific terms), I want to maintain a glossary of project terms that krag injects into prompts, so that the LLM correctly interprets and uses my project's vocabulary when answering questions.

The domain lexicon is a JSON file containing term definitions, abbreviations, and context hints. When enabled, lexicon entries relevant to the user's query are selected and injected into the prompt as additional context, helping the LLM understand project-specific language without hallucinating definitions.

**Why this priority**: The lexicon improves answer quality for domain-heavy projects but is not a prerequisite for other Sprint 009 features. It can be developed and tested independently after the mode system is in place.

**Independent Test**: Can be tested by creating a lexicon file with known terms, querying with a question that uses those terms, and verifying that the LLM response correctly uses the terminology as defined in the lexicon.

**Acceptance Scenarios**:

1. **Given** a lexicon file exists at the configured path containing the entry `{"kragd": "The krag service daemon — a FastAPI server that loads models once and serves queries over HTTP"}`, **When** the user asks "What is kragd?", **Then** the prompt sent to the LLM includes the lexicon definition, and the response uses the correct definition.
2. **Given** a lexicon file is configured, **When** the user queries with terms not in the lexicon, **Then** the query proceeds normally without lexicon injection (only matching terms are injected).
3. **Given** the user runs `krag lexicon refresh`, **Then** the lexicon file is reloaded from disk without restarting the service.
4. **Given** no lexicon file is configured, **When** the user queries, **Then** the system operates exactly as before (no lexicon injection, no errors).
5. **Given** a lexicon file contains 500+ entries, **When** the user queries, **Then** only the entries most relevant to the query are selected for injection (not the entire glossary), staying within prompt size limits.

**Edge Cases**:

- Lexicon entries with overlapping or related terms (e.g., "krag" and "kragd") should both be injected when relevant.
- Malformed lexicon files should produce a clear validation error at load time, not at query time.
- The lexicon path can be per-project (relative to project root) or global (absolute path).

---

### User Story 5 — Context Relevance Critic (Priority: P2)

As a krag user, I want retrieved chunks to be evaluated for relevance before they are sent to the LLM for synthesis, so that irrelevant or tangentially related chunks are filtered out, leading to more focused and accurate answers.

The context critic is a post-retrieval, pre-synthesis step that scores each retrieved chunk on a 0–5 relevance scale relative to the user's query. Chunks scoring below a configurable threshold are dropped before prompt construction. The critic can be enabled, disabled, or configured per mode, and its scores are visible in debug output.

**Why this priority**: The critic improves answer quality by reducing noise in the LLM's context window, but it adds latency (each chunk requires a scoring call). It is best implemented after the mode system so that modes can control critic behavior.

**Independent Test**: Can be tested by running a query in debug mode with the critic enabled, verifying that each chunk receives a relevance score, and that chunks below the threshold are excluded from the final prompt.

**Acceptance Scenarios**:

1. **Given** the context critic is enabled (via mode or global config), **When** a query retrieves 10 chunks, **Then** each chunk is scored on a 0–5 scale, and only chunks scoring at or above the threshold (default: 3) are passed to prompt construction.
2. **Given** the critic is enabled, **When** the user runs `krag debug query "..."`, **Then** the debug output shows each chunk's relevance score, whether it passed or failed the threshold, and the total number of chunks before/after critic filtering.
3. **Given** the critic is disabled (default for most modes), **When** a query runs, **Then** all retrieved chunks are passed to prompt construction as they are today (no additional latency).
4. **Given** a mode configuration sets `critic.enabled = true` and `critic.threshold = 4`, **When** a query runs with that mode, **Then** only chunks scoring 4 or 5 are included in the prompt.
5. **Given** all chunks score below the threshold, **When** the critic filters them all out, **Then** the system returns the standard "insufficient context" response rather than sending an empty context to the LLM.
6. **Given** the critic scores chunks, **When** debug output is requested, **Then** each chunk displays its critic score alongside its retrieval score.

**Edge Cases**:

- If the scoring process fails for a chunk (e.g., LLM error), that chunk should be included (fail-open) to avoid silently dropping content.
- The critic should respect prompt size limits — if many chunks pass the threshold, the existing context length limit still applies.
- Very short chunks (under 50 characters) may receive unreliable scores; the critic should pass them through without scoring.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Lifecycle Timer Fix

- **FR-001**: The system MUST pause the lifecycle manager's idle timer when an indexing job begins and resume it only after indexing completes and the post-indexing LLM reload has been attempted.
- **FR-002**: The system MUST successfully reload the LLM after indexing without error, regardless of how long the indexing job takes relative to the idle timeout period.
- **FR-003**: The system MUST log a clear, informative message when the idle timer is paused for indexing and when it resumes.

#### Multi-Collection Qdrant

- **FR-004**: The system MUST support four named collections: **code** (source code files), **tests** (test files), **docs** (documentation files), and **text** (general text files).
- **FR-005**: The system MUST route files to collections based on a combination of file path patterns and file extensions, with path-based rules taking precedence over extension-based rules when conflicts arise.
- **FR-006**: Each collection MUST use the embedding model best suited to its content type — the code-optimized model for code and tests collections, and the text-optimized model for docs and text collections.
- **FR-007**: The system MUST support querying across multiple collections simultaneously, merging results via a weighted fusion strategy.
- **FR-008**: Each query result MUST indicate which collection it originated from.
- **FR-009**: The system MUST handle empty collections gracefully — querying a collection with no content must return an empty result set without errors.
- **FR-010**: Incremental indexing MUST work correctly with multi-collection storage — file changes, additions, and deletions must update the correct collection.

#### Mode System

- **FR-011**: The system MUST support a `--mode` flag on query commands that selects a named retrieval mode.
- **FR-012**: Each mode MUST be defined as a TOML configuration file specifying: target collections (with optional per-collection weights), LLM selection (text or code), prompt preset, retrieval parameters (top_k, similarity_threshold), and optional context critic settings.
- **FR-013**: The system MUST provide built-in default modes: `default` (all collections, text LLM, balanced preset), `code` (code + tests collections, code LLM, code preset), and `docs` (docs collection, text LLM, balanced preset).
- **FR-014**: Users MUST be able to create custom modes by adding TOML files to a designated modes configuration directory.
- **FR-015**: The existing `--llm` flag MUST be preserved as deprecated, emitting a deprecation warning and mapping to the equivalent mode behavior.
- **FR-016**: The system MUST provide `krag modes list` and `krag modes show <name>` commands for mode discovery and inspection.
- **FR-017**: Mode names MUST be case-insensitive.
- **FR-018**: When a mode references a code LLM but no code model is configured, the system MUST fall back to the text LLM with a warning.
- **FR-019**: The `--mode` flag MUST work identically across `krag` (client), `krag-direct` (in-process), and `kragd` (service) execution paths.

#### Domain Lexicon

- **FR-020**: The system MUST support loading a domain lexicon from a JSON file containing term-definition pairs.
- **FR-021**: When a lexicon is loaded and a query contains terms matching lexicon entries, the system MUST inject relevant definitions into the prompt sent to the LLM.
- **FR-022**: Lexicon term matching MUST be case-insensitive and use word-boundary matching for both single-word and multi-word terms.
- **FR-023**: The system MUST limit the number of injected lexicon entries to avoid exceeding prompt size constraints, selecting the most relevant entries when the full set would exceed limits.
- **FR-024**: The system MUST support a `krag lexicon refresh` command (and equivalent service endpoint) that reloads the lexicon from disk without restarting the service.
- **FR-025**: The lexicon file path MUST be configurable — supporting both project-relative paths and absolute paths.
- **FR-026**: The system MUST validate the lexicon file format at load time and produce clear error messages for malformed files.
- **FR-027**: When no lexicon is configured, the system MUST operate identically to its current behavior with no performance impact.

#### Context Relevance Critic

- **FR-028**: The system MUST support a post-retrieval, pre-synthesis step that scores each retrieved chunk's relevance to the query on a 0–5 integer scale.
- **FR-029**: Chunks scoring below a configurable threshold (default: 3) MUST be excluded from prompt construction.
- **FR-030**: The context critic MUST be configurable per mode — modes can enable/disable the critic and set the threshold independently.
- **FR-031**: The context critic MUST be disabled by default to preserve current performance characteristics.
- **FR-032**: When running in debug mode, the system MUST display each chunk's critic score alongside its retrieval score, and show the count of chunks before/after critic filtering.
- **FR-033**: If all chunks are filtered out by the critic, the system MUST return the standard "insufficient context" response.
- **FR-034**: If scoring fails for a chunk (e.g., LLM error during scoring), the system MUST include that chunk (fail-open behavior) to avoid silently dropping content.
- **FR-035**: Chunks shorter than 50 characters MUST bypass critic scoring and be included automatically.

### Key Entities

- **Collection**: A named Qdrant collection storing vector embeddings for a specific content type (code, tests, docs, text). Each collection has its own embedding model, vector dimensions, and content routing rules. Collections are queried independently and results are merged via weighted fusion.

- **Mode**: A named retrieval configuration that bundles together target collections (with weights), LLM selection, prompt preset, retrieval parameters, and critic settings. Modes are defined as TOML files and selected at query time via the `--mode` flag. Built-in modes provide sensible defaults; users can create custom modes.

- **Lexicon**: A JSON-formatted glossary of project-specific terminology. Each entry maps a term to its definition. The lexicon is loaded at service startup (or on demand via refresh), and relevant entries are injected into prompts when query terms match. The lexicon is optional and project-specific.

- **Critic Score**: A 0–5 integer relevance rating assigned to each retrieved chunk by the context critic. The score represents how relevant the chunk content is to the user's query. Scores are used for threshold-based filtering and are visible in debug output.

## Assumptions

- The four collection types (code, tests, docs, text) cover the content categories relevant to the current user base. If additional categories emerge (e.g., config files, data files), they can be added in a future sprint.
- Test file detection uses well-known conventions: `tests/` and `test/` directories, `test_` prefixes, `_test` suffixes. Unusual project layouts may require user-configurable routing rules in a future sprint.
- The domain lexicon uses a simple JSON key-value format. More complex lexicon structures (e.g., hierarchical terms, term relationships) are out of scope for this sprint.
- The context critic uses the currently loaded LLM for scoring. A dedicated lightweight scoring model is out of scope.
- Mode TOML files are stored in a well-known directory (e.g., `~/.config/krag/modes/`) alongside the main config. Per-project mode directories are a potential future enhancement.
- The existing `--llm` flag will be preserved for backward compatibility in this sprint but may be removed in a future release.

## Out of Scope

- Automatic collection routing learning (ML-based file-to-collection classification).
- Per-project mode file discovery (modes in project root directories).
- Lexicon auto-generation from indexed content.
- Critic model fine-tuning or dedicated scoring models.
- Web UI for mode management or lexicon editing.
- Cross-collection deduplication (same chunk indexed in multiple collections).

## Dependencies

- Sprint 008 (merged) — GPU VRAM fix, config show, dedup stats.
- Known issue fix (lifecycle timer race) must be completed before mode system work begins, as the mode system interacts with LLM lifecycle management.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Indexing a mixed project (code + tests + docs + text files) correctly routes 95%+ of files to the appropriate collection without manual configuration, as verified by inspecting collection contents.
- **SC-002**: Users can switch between retrieval modes in under 1 second (mode selection adds negligible latency to query processing).
- **SC-003**: Queries using the `code` mode return results that are 80%+ from source code and test files, as measured by collection origin tracking in debug output.
- **SC-004**: Domain lexicon injection improves answer accuracy for terminology-heavy queries — queries using project-specific terms receive contextually correct definitions in responses when the lexicon is enabled.
- **SC-005**: The context critic, when enabled, reduces the average number of irrelevant chunks in the prompt by at least 30%, as measured by comparing pre-critic and post-critic chunk counts in debug output.
- **SC-006**: The lifecycle timer race condition is eliminated — no "Failed to reload LLM" error messages appear during or after indexing, regardless of indexing duration.
- **SC-007**: All existing `--llm` flag usage continues to work with deprecation warnings, ensuring backward compatibility for current users and scripts.
- **SC-008**: The `krag-direct` execution path supports all new features identically to the `krag`/`kragd` client-server path.
