# Feature Specification: Code-Aware Indexing

**Feature Branch**: `005-code-aware-indexing`  
**Created**: February 16, 2026  
**Status**: Draft  
**Input**: User description: "Improve krag code query results via code-specialized embedding model, AST-aware chunking plugin with tree-sitter, code-specific LLM, and enriched retrieval metadata"

## Clarifications

### Session 2026-02-16

- Q: Should the code plugin use a larger default chunk size than the text default (384 chars)? → A: Code chunk size must be independent and plugin-configurable, with a recommended default of 2048 chars.
- Q: What score normalization strategy for merging results from multiple embedding models? → A: Reciprocal Rank Fusion (RRF, k=60) — merge by rank position rather than raw scores, which are not directly comparable across models. (Updated from min-max normalization based on planning-phase research.)
- Q: How should krag detect available VRAM before loading models? → A: Runtime query via `torch.cuda.mem_get_info()` before each model load, comparing free VRAM against model's estimated footprint (file size + KV cache + overhead) with 20% safety margin. (Updated from pynvml based on planning-phase research — torch is already available, pynvml is not a transitive dependency.)
- Q: Should the prompt preset auto-switch when routing between code and text LLMs? → A: Yes, auto-couple — code LLM gets "code" preset, text LLM gets user's configured preset (default "balanced"), unless user explicitly overrides.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Code-Aware Chunking via Plugin (Priority: P1)

A developer indexes a Python project with krag. When they query "how does the retriever handle deduplication?", krag retrieves complete, self-contained functions and methods rather than fragments split mid-definition. The retrieved chunks include scope context (class name, file path) and are semantically coherent units of code.

**Why this priority**: Chunking is the single highest-impact improvement. Poor chunking produces fragments that neither embed well nor synthesize into useful answers. Everything downstream (embedding quality, LLM reasoning) depends on receiving coherent code units.

**Independent Test**: Install the code plugin, index a Python project, run queries targeting specific functions/classes. Verify returned chunks are complete semantic units (whole functions, whole methods) rather than character-split fragments.

**Acceptance Scenarios**:

1. **Given** a Python file with a 30-line function, **When** the code plugin indexes it, **Then** the function is stored as a single chunk (not split across multiple chunks), including its decorators, docstring, and signature.
2. **Given** a Python class with 5 methods each under the chunk size limit, **When** indexed, **Then** each method is a separate chunk with its parent class name prepended as context.
3. **Given** a Python file with an import block followed by 3 functions, **When** indexed, **Then** the import block is captured either as its own chunk or as context prepended to function chunks.
4. **Given** a code file that tree-sitter cannot parse (syntax errors, unsupported dialect), **When** the plugin attempts to chunk it, **Then** it gracefully falls back to the default character-based TextChunker with no crash or data loss.
5. **Given** a 200-line function that exceeds the configured chunk size, **When** indexed, **Then** the plugin splits it at inner statement boundaries (not mid-expression) and each sub-chunk retains the function signature as context.
6. **Given** a project with `.py`, `.rs`, and `.ps1` files, **When** indexed with the code plugin enabled, **Then** Python and Rust files receive AST-aware chunking while PowerShell files fall back to the default chunker (until a grammar is added).

---

### User Story 2 - Multi-Model Embedding Orchestration (Priority: P2)

A developer installs the code plugin and indexes a mixed project containing Python source, markdown docs, and log files. krag automatically loads both a code-aware embedding model and the general-purpose text embedding model. During indexing, each file is embedded by the model appropriate to its plugin — code files use the code embedder, text files use the text embedder. During queries, krag embeds the query with all active embedding models, searches their respective vector spaces, and merges the results into a unified ranked list.

As a fallback when VRAM is insufficient for simultaneous models, the system performs two sequential indexing passes — one per embedding model — unloading each after its pass completes.

**Why this priority**: A code-trained embedding model understands that a natural-language question about "deduplication" relates to a function named `_deduplicate`. This semantic bridge is missing with general-purpose text embeddings. Running both models simultaneously ensures the best embedder is always used for each file type without user intervention. It is lower priority than chunking because even the best embedding model cannot salvage broken, mid-function chunk fragments.

**Independent Test**: Install code plugin, index a mixed project with `.py` and `.md` files. Verify code files are embedded with the code model and text files with the text model (check vector store metadata). Run queries and verify results from both vector spaces are merged coherently.

**Acceptance Scenarios**:

1. **Given** the code plugin is installed and declares a code embedding model, **When** the user runs `krag index`, **Then** `.py` files are embedded with the code embedding model and `.md` files are embedded with the default text embedding model, with each chunk's metadata recording which model produced its vector.
2. **Given** both embedding models are loaded, **When** a user runs a query, **Then** the query is embedded by both models, results from both vector spaces are retrieved, scores are normalized per-model, and a merged ranked list is returned.
3. **Given** a query "how does the chunker split text", **When** searching with multi-model embeddings, **Then** code chunks from `chunker.py` (embedded by the code model) are ranked alongside relevant text chunks, with the code chunks ranking higher for this code-specific query.
4. **Given** both embedding models are loaded in VRAM, **When** checking memory, **Then** the combined embedding model footprint stays under 1.2 GB (~650 MB code + ~440 MB text), leaving the remaining VRAM budget for the LLM.
5. **Given** insufficient VRAM for simultaneous embedding models (e.g., CPU-only deployment), **When** the user runs `krag index`, **Then** the system performs two sequential passes — code embedder first, text embedder second — unloading each model after its pass completes, with an informational log message explaining the fallback.

---

### User Story 3 - Multi-LLM Routing with Hot-Swap Fallback (Priority: P3)

A developer sets `load_multi_llm = true` in their config to test simultaneous LLM loading on their system. When they query krag about code, krag examines the retrieved chunks and determines the query is code-heavy — the majority of retrieved chunks carry code metadata (language, function_name). It routes synthesis to the code-specialized LLM, which produces answers that reference specific functions, classes, and file paths with high accuracy. For text-heavy queries (documentation, logs), krag routes to the general-purpose text LLM.

When `load_multi_llm = true` and VRAM is sufficient, both LLMs are loaded simultaneously for instant routing. When `load_multi_llm = false` (default) or when VRAM is insufficient for both LLMs, the user selects the LLM via a CLI switch (`--llm code` or `--llm text`). krag hot-loads the selected model, unloading the other if necessary, before responding. This hot-swap path is slower (model load latency) but avoids OOM and works reliably on constrained hardware.

**Why this priority**: The LLM is the final synthesis stage. A code-specialized LLM produces significantly better answers for code queries — referencing symbols, explaining logic, avoiding hallucinated APIs. Simultaneous loading is ideal but the combined ~14 GB LLM footprint plus embedders makes it tight on 16 GB VRAM, so the hot-swap fallback is a pragmatic alternative. Either way, improving synthesis only yields value if retrieval (chunking + embedding) already provides good context.

**Independent Test**: Download both LLMs. Test simultaneous loading: verify both respond correctly. Test hot-swap: run `krag query --llm code "..."`, verify the code LLM loads and answers. Then run `krag query --llm text "..."`, verify the text LLM loads and answers. Compare code query answer quality between the two LLMs on the same retrieved context.

**Acceptance Scenarios**:

1. **Given** `load_multi_llm = true` and both LLMs fit in VRAM (simultaneous mode), **When** a query retrieves mostly code chunks, **Then** krag routes synthesis to the code LLM automatically and the answer references specific function names, file paths, and behavior from the retrieved chunks.
2. **Given** `load_multi_llm = true` and both LLMs fit in VRAM, **When** a query retrieves mostly text/documentation chunks, **Then** krag routes synthesis to the text LLM automatically.
3. **Given** `load_multi_llm = false` or insufficient VRAM for both LLMs, **When** the user runs `krag query --llm code "what does the Retriever class do"`, **Then** krag loads the code LLM (unloading any currently loaded LLM), executes the query, and returns the answer.
4. **Given** `load_multi_llm = true` but loading both LLMs would exceed available VRAM, **When** krag starts up, **Then** it logs a warning that multi-LLM mode was requested but VRAM is insufficient, and falls back to hot-swap mode.
5. **Given** the hot-swap fallback is in use and the text LLM is currently loaded, **When** the user runs `krag query --llm code "..."`, **Then** the text LLM is unloaded, the code LLM is loaded, and the query is answered — with total swap time logged for user visibility.
6. **Given** no `--llm` switch is provided and only one LLM fits in VRAM, **When** the user runs a query, **Then** krag uses whichever LLM is currently loaded (defaulting to the text LLM on first query) and logs a suggestion to use `--llm code` for code-heavy queries.

---

### User Story 4 - Code Prompt Preset (Priority: P4)

A developer sets `prompt.preset = "code"` in config.toml. Code queries produce answers that include code snippets, reference specific symbols (functions, classes, variables), and cite sources with file paths and line numbers.

**Why this priority**: A code-tuned system prompt improves answer formatting and grounding at near-zero implementation cost. It depends on richer chunk metadata (from P1) to reference line numbers and symbols.

**Independent Test**: Set preset to "code", run queries, verify answers contain code snippets and symbol references.

**Acceptance Scenarios**:

1. **Given** `prompt.preset = "code"`, **When** the user queries about a specific function, **Then** the answer includes the function signature and references its file path.
2. **Given** the "code" preset with low temperature (0.1), **When** the context lacks information to answer, **Then** the system returns the standard insufficient-context phrase without fabricating code.
3. **Given** `load_multi_llm = true` and no explicit `prompt.preset` override, **When** a query is routed to the code LLM, **Then** the "code" preset is applied automatically. **When** a query is routed to the text LLM, **Then** the "balanced" preset is applied automatically.

---

### User Story 5 - Enriched Chunk Metadata in Retrieval (Priority: P5)

Chunks produced by the code plugin carry structured metadata (language, function name, class name, start/end line). The retriever uses this metadata to boost results where query terms match symbol names, and the query output displays richer source references.

**Why this priority**: Metadata enrichment builds on P1 (which produces the metadata) and improves retrieval precision and answer presentation. It is a meaningful but incremental enhancement.

**Independent Test**: Index a project with the code plugin, query for a specific function name, verify that the result with a matching `function_name` metadata field is ranked higher and displayed with line-number context.

**Acceptance Scenarios**:

1. **Given** a chunk with metadata `{"function_name": "_deduplicate", "class_name": "Retriever"}`, **When** the query contains "_deduplicate", **Then** the retriever applies a score boost to that chunk.
2. **Given** enriched metadata on retrieved chunks, **When** displaying query results, **Then** each result shows `ClassName.method_name() at file.py:L45-L68` instead of just the file path.

---

### Edge Cases

- **Malformed code files**: Tree-sitter parse errors must not crash indexing; graceful fallback to default chunking.
- **Binary files in code directories**: Plugin must respect `skip_binary_files` and not attempt to parse non-text files.
- **Very large single functions** (>2x chunk size): Must split at statement boundaries, not mid-line.
- **Empty files / files with only comments**: Must produce zero chunks or a single metadata-only chunk, not errors.
- **Mixed-language files** (e.g., Markdown with embedded code blocks): Handled by the existing markdown plugin; the code plugin only processes files matching its registered extensions.
- **Unsupported languages**: Files with extensions not covered by an installed tree-sitter grammar fall back to default chunking with a logged info message.
- **Re-indexing with model dimension change**: If a plugin's embedding model has a different dimension than expected, the system must detect the mismatch and handle it (separate collection per model, or prompt for re-index).
- **VRAM exhaustion during multi-model loading**: Before loading any model, the system must query free GPU VRAM via `torch.cuda.mem_get_info()` and compare against the model's estimated VRAM footprint (file size + KV cache + overhead) with a 20% safety margin. If insufficient, it must fall back to sequential/hot-swap mode with a clear log message — never attempt a load that would cause a CUDA OOM crash.
- **Multi-model score merging**: Results from different embedding models are in different semantic spaces; raw scores are not directly comparable. The system must use Reciprocal Rank Fusion (RRF, k=60) to merge results using rank positions rather than raw scores, producing a fair unified ranking.
- **LLM hot-swap latency**: When hot-swapping LLMs, model load time may be 10-30 seconds. The system must provide progress feedback to the user during the swap, not appear frozen.
- **Query routing ambiguity**: When retrieved chunks are an even mix of code and text, the system must have a deterministic tiebreaker for LLM routing (or use the default LLM).
- **Concurrent VRAM usage**: All resident models (embedding models + LLM(s)) must coexist within the 16 GB VRAM budget; exceeding it should produce a clear error message, not a silent OOM crash.

## Requirements *(mandatory)*

### Functional Requirements

**Code-Aware Chunking Plugin (P1)**

- **FR-001**: System MUST provide a `krag-plugin-code` plugin package that implements `FileTypeHandler` and registers via the `krag.plugins` entry point.
- **FR-002**: The code plugin MUST use tree-sitter to parse source files into ASTs and extract semantic units (functions, methods, classes, import blocks, module-level docstrings).
- **FR-003**: The code plugin MUST support Python as the initial language, with Rust as a fast follow.
- **FR-004**: The code plugin MUST support adding languages incrementally by installing additional tree-sitter grammar packages, without code changes to the plugin itself.
- **FR-005**: The code plugin MUST use an independent, plugin-configurable chunk size separate from the global text chunk size, with a recommended default of 2048 characters. This ensures most functions/methods are stored as whole units without splitting.
- **FR-006**: The code plugin MUST produce chunks where each chunk is a single semantic unit (one function, one method, one class header, or one import block) when the unit fits within the code chunk size.
- **FR-007**: The code plugin MUST split oversized semantic units at inner structural boundaries (statement boundaries, not mid-expression) when a unit exceeds the code chunk size.
- **FR-008**: The code plugin MUST prepend scope context to method chunks: the parent class name and signature, so the method chunk is self-descriptive.
- **FR-009**: The code plugin MUST fall back to the default `TextChunker` when tree-sitter cannot parse a file (syntax errors, missing grammar), logging a warning.
- **FR-010**: The code plugin MUST populate `TextChunk` metadata with: language, function name (if applicable), class name (if applicable), start line, end line.
- **FR-011**: The code plugin MUST register for file extensions matching its installed grammars (e.g., `.py` for Python, `.rs` for Rust) and must not claim extensions for which no grammar is installed.

**Multi-Model Embedding Orchestration (P2)**

- **FR-012**: Plugins MUST be able to declare a preferred embedding model in their configuration or plugin metadata. Plugins that do not declare a model use the system default.
- **FR-013**: The embedding orchestrator MUST load multiple embedding models simultaneously and route each file to the embedding model declared by its plugin during indexing.
- **FR-014**: During queries, the system MUST embed the query with all active embedding models, search their respective vector spaces, and merge results into a unified ranked list using Reciprocal Rank Fusion (RRF, k=60). RRF uses rank positions (which are comparable across models) rather than raw scores (which are in different semantic spaces).
- **FR-015**: The system MUST store vectors from different embedding models in separate named vector spaces within a single Qdrant collection (e.g., `vectors_config={"text": ..., "code": ...}`) so that vectors from different semantic spaces are never compared directly. Points that only have one model's embedding omit the other vector name.
- **FR-016**: The system MUST query available GPU VRAM at runtime (via `torch.cuda.mem_get_info()`) before each model load, comparing free VRAM against the model's estimated VRAM footprint (file size + KV cache + overhead) with a 20% safety margin. When insufficient VRAM is detected, the system MUST fall back to sequential two-pass indexing (for embedding models) or hot-swap mode (for LLMs) with an informational log message — rather than attempting the load and risking a CUDA OOM crash.
- **FR-017**: Each chunk's vector store record MUST include metadata identifying which embedding model produced its vector.

**Multi-LLM Routing with Hot-Swap Fallback (P3)**

- **FR-018**: The system MUST support configuring multiple LLMs (code-specialized and general-purpose) in the `[llm]` config section, including a `load_multi_llm` boolean setting that defaults to `false`.
- **FR-019**: When `load_multi_llm = true` and VRAM permits, the system MUST load both LLMs simultaneously and route queries to the appropriate LLM based on the composition of retrieved chunks (majority code metadata → code LLM, majority text → text LLM).
- **FR-020**: When VRAM is insufficient for simultaneous LLMs, the system MUST support a `--llm` CLI switch (e.g., `--llm code`, `--llm text`) that hot-loads the selected model, unloading any currently loaded LLM, before responding.
- **FR-021**: During hot-swap, the system MUST provide progress feedback to the user (e.g., "Loading code LLM...") and log the swap duration.
- **FR-022**: When no `--llm` switch is provided and only one LLM fits in VRAM, the system MUST use the currently loaded LLM (defaulting to the text LLM on first query) and log a suggestion to use `--llm code` for code-heavy queries.
- **FR-023**: Both LLMs MUST work with krag's existing `LLMClient` chat-completion interface without requiring code changes to `LLMClient` (prompt format auto-detection via llama-cpp-python's GGUF metadata).

**Code Prompt Preset (P4)**

- **FR-024**: System MUST provide a `"code"` prompt preset in `PromptBuilder` optimized for code Q&A, with a system prompt that instructs the LLM to reference specific functions, classes, and file paths, and to include code snippets.
- **FR-025**: The `"code"` preset MUST use a lower temperature (0.1) than the balanced preset to favor precision over creativity.
- **FR-026**: When the system routes a query to the code LLM (via auto-routing or `--llm code`), it MUST automatically apply the `"code"` prompt preset. When routing to the text LLM, it MUST apply the user's configured preset (default `"balanced"`). An explicit `prompt.preset` config value MUST override this automatic coupling.

**Enriched Retrieval Metadata (P5)**

- **FR-027**: The `Retriever` MUST apply a configurable score boost when query terms match a chunk's `function_name` or `class_name` metadata fields.
- **FR-028**: Query result display MUST include structured source references (`ClassName.method() at file.py:L45-L68`) when chunk metadata contains symbol and line information.

### Key Entities

- **CodeChunk**: A `TextChunk` enriched with code-specific metadata (language, function_name, class_name, start_line, end_line, imports). Extends the existing TextChunk model's metadata capabilities.
- **LanguageGrammar**: A mapping from file extension to tree-sitter language grammar. Dynamically discovered based on installed `tree-sitter-*` packages.
- **SemanticUnit**: An intermediate representation of a parsed AST node (function, class, import block) with its source text, line range, and parent scope. Internal to the code plugin.
- **EmbeddingProfile**: A plugin-declared association between a set of file types and the embedding model that should encode them. Links a plugin to its preferred embedder and vector namespace.
- **LLMPool**: A runtime manager that holds one or more loaded LLMs, handles routing decisions based on retrieved chunk composition, and manages hot-swap lifecycle (unload/load/progress feedback).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Code queries return complete, self-contained functions/methods as chunks at least 80% of the time (vs. the current ~20% with character-based splitting), measured across a test suite of 20 code-specific queries.
- **SC-002**: Retrieval relevance for code queries improves by at least 30% (measured by Mean Reciprocal Rank on a fixed query set comparing before/after indexing with the code plugin + code embedding model).
- **SC-003**: Both embedding models (code + text) load simultaneously, with a combined footprint under 1.5 GB, leaving the remaining VRAM budget for LLM(s). When one LLM is loaded alongside both embedders, total VRAM stays under 14 GB (leaving 2 GB headroom for KV cache on a 16 GB GPU).
- **SC-004**: Indexing a 10,000-line Python project with the code plugin completes within 2x the time of default character-based chunking (tree-sitter parsing overhead is acceptable).
- **SC-005**: The code plugin handles tree-sitter parse failures gracefully, with zero crashes across a test corpus that includes 5% intentionally malformed files.
- **SC-006**: Adding support for a new programming language requires only installing its tree-sitter grammar package and adding the extension mapping — no plugin code changes.
- **SC-007**: Users report that code query answers reference specific function names and file locations, improving perceived answer quality on a 1-5 satisfaction scale from baseline.
- **SC-008**: When hot-swapping LLMs, the model swap (unload + load) completes in under 60 seconds and the user receives progress feedback during the swap.

## Assumptions

- **A-001**: The user's GPU is an NVIDIA RTX 4080 SUPER with 16 GB VRAM. VRAM budgets are calculated for this hardware. Users with different GPUs may need to adjust model choices.
- **A-002**: `llama-cpp-python` auto-detects ChatML prompt format from Qwen2.5-Coder GGUF metadata. If not, a minor configuration extension (not a code change) may be needed.
- **A-003**: tree-sitter grammar packages (`tree-sitter-python`, `tree-sitter-rust`, etc.) provide pre-compiled wheels for Linux x86_64. No compilation from source should be required.
- **A-004**: The existing `FileTypeHandler` plugin interface provides sufficient hooks for code-aware chunking. The plugin returns `ChunkingStrategy.CUSTOM` with a custom chunker that produces enriched `TextChunk` objects.
- **A-005**: The combined weight of both LLMs (Phi-3-medium Q5_K_M ~8.5 GB + Qwen2.5-Coder-7B Q5_K_M ~5.4 GB = ~14 GB) plus both embedding models (~1.1 GB) exceeds 16 GB VRAM with KV cache overhead. Therefore, `load_multi_llm` defaults to `false` for safety, but users with >24 GB VRAM can set `load_multi_llm = true` to enable simultaneous LLM loading and automatic routing.
- **A-006**: PowerShell does not have an official tree-sitter grammar in the `tree-sitter-*` ecosystem. PowerShell support may require a community grammar or will fall back to default chunking until one is available.
- **A-007**: The code plugin will be a separate installable package (`krag-plugin-code`) following the same pattern as `krag-plugin-logs` and `krag-plugin-markdown`, distributed alongside krag but independently versioned.

## Scope & Boundaries

### In Scope

- Code-aware chunking plugin with tree-sitter integration (Python + Rust initially)
- Multi-model embedding orchestration: simultaneous loading, plugin-declared model routing, per-model vector namespaces, score normalization and merging
- Two-pass indexing fallback for VRAM-constrained embedding
- Multi-LLM routing based on retrieved chunk composition
- LLM hot-swap via CLI switch (`--llm code` / `--llm text`) as fallback for VRAM-constrained deployments
- Code-specific prompt preset
- Identifier-aware score boosting in retrieval
- Enriched result display with symbol/line references
- Graceful fallback for unsupported languages and parse failures
- VRAM budget detection and automatic fallback selection

### Out of Scope

- Hybrid keyword + semantic search (Qdrant full-text index integration) — deferred to a future enhancement
- Import graph analysis (tracking "what depends on X") — deferred
- Cross-file semantic linking (test-to-implementation pairing) — deferred
- Language-specific chunk size tuning per language within the code plugin — deferred (use a single code chunk size initially, configurable at the plugin level)
- Cross-encoder reranking — deferred to a future enhancement
- Query rewriting / identifier expansion ("dedup" to "deduplicate") — deferred
- Semantic compression / LLM-based chunk summarization — deferred
- Automatic query classification for LLM routing without retrieved chunks (pre-retrieval routing) — out of scope; routing is based on retrieved chunk metadata only

## Dependencies & Constraints

- **tree-sitter** (>=0.23.0): Core parsing library, MIT licensed, pre-compiled wheels
- **tree-sitter-python** (>=0.23.0): Python grammar, MIT licensed
- **tree-sitter-rust** (>=0.23.0): Rust grammar, MIT licensed
- **tree-sitter-javascript** (>=0.23.0): JS/TS grammar (future), MIT licensed
- **jinaai/jina-embeddings-v2-base-code**: Recommended embedding model, Apache-2.0, 161M params, 768-dim
- **Qwen2.5-Coder-7B-Instruct Q5_K_M GGUF**: Recommended code LLM, Apache-2.0, ~5.4 GB
- **torch.cuda**: GPU VRAM detection at runtime via `torch.cuda.mem_get_info()` (already available as transitive dependency of sentence-transformers)
- 16 GB VRAM budget constrains simultaneous model loading; system must support graceful fallback (sequential embedding passes, LLM hot-swap) when models exceed available VRAM

## Language Priority

Languages will be supported in this order, driven by user need and tree-sitter grammar availability:

1. **Python** — initial release
2. **Rust** — initial release
3. **PowerShell** — pending community tree-sitter grammar availability
4. **JavaScript / TypeScript** — fast follow
5. **C** — fast follow
6. **C++** — fast follow
7. **Go** — fast follow
8. Additional languages as grammar packages are installed
