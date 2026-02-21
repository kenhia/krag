# Feature Specification: Service Architecture

**Feature Branch**: `007-service-architecture`
**Created**: 2026-02-19
**Status**: Draft
**Input**: User description: "Convert krag into a service-based architecture with kragd daemon, krag CLI client, and debug/introspection features"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start Service and Query via CLI (Priority: P1)

A user starts the kragd service on their machine. It loads the configured LLM(s) and embedding models, then listens for requests. The user runs `krag query "How does the plugin system work?"` from any terminal. The CLI sends the query to kragd over HTTP. kragd retrieves relevant chunks, synthesizes an answer, and returns it. The CLI displays the answer and sources identically to the current direct-mode output. The LLM stays loaded between queries, eliminating the 5-15 second cold-start on subsequent queries.

**Why this priority**: This is the core value proposition — persistent LLM loading with the same user experience. Every other feature depends on the service running and accepting queries.

**Independent Test**: Start kragd, run a query via CLI, verify the answer and sources display correctly. Time a second query to confirm no cold-start delay.

**Acceptance Scenarios**:

1. **Given** kragd is running with a valid configuration and indexed data, **When** the user runs `krag query "What is krag?"`, **Then** the CLI displays an answer panel and source list formatted identically to the current direct-mode output.
2. **Given** kragd is running, **When** the user runs two queries in sequence, **Then** the second query completes without LLM loading delay (under 2 seconds for retrieval + generation start, excluding LLM inference time).
3. **Given** kragd is not running, **When** the user runs `krag query "..."`, **Then** the CLI displays a clear error message indicating kragd is not reachable and suggests `kragd start`.
4. **Given** kragd is running, **When** the user runs `krag query "..." --format json`, **Then** the response is valid JSON matching the current JSON output schema.

---

### User Story 2 - Service Lifecycle Management (Priority: P1)

A user starts kragd in the foreground for development or as a background daemon for daily use. They can check its status (loaded models, VRAM usage, uptime, vector store stats) at any time. They can shut it down gracefully from the CLI. The service writes a PID file so the CLI can locate and stop it.

**Why this priority**: Users need reliable start/stop/status to trust the service model. Without lifecycle management, the service is unusable in practice.

**Independent Test**: Start kragd, verify PID file is written, run `krag status`, verify output shows loaded models and uptime, run `krag stop`, verify clean shutdown.

**Acceptance Scenarios**:

1. **Given** no kragd instance is running, **When** the user runs `kragd` (foreground) or `kragd start` (background), **Then** the service starts, loads configured models, writes a PID file, and begins accepting requests.
2. **Given** kragd is running, **When** the user runs `krag status`, **Then** the CLI displays service version, uptime, loaded LLM(s) with primary/secondary designation, embedding models, vector store statistics, and VRAM usage.
3. **Given** kragd is running, **When** the user runs `krag stop`, **Then** the service unloads all models, removes the PID file, and exits cleanly.
4. **Given** kragd is running, **When** the user runs `krag health`, **Then** the CLI displays a simple up/running confirmation.
5. **Given** kragd is already running, **When** the user attempts to start a second instance, **Then** the system detects the existing PID file/port conflict and reports the error clearly.

---

### User Story 3 - Configurable LLM Lifecycle (Priority: P2)

A user configures which LLM is their "primary" model (always loaded) and which is secondary (loaded on demand, unloaded after an idle timeout). For example, the text LLM is primary and stays in VRAM permanently, while the code LLM loads only when a code-heavy query triggers auto-routing, then unloads after 5 minutes of inactivity. If no primary is configured, both LLMs unload after the idle timeout. The primary LLM is reloaded after the secondary is unloaded to reclaim VRAM if needed.

**Why this priority**: VRAM management is critical for users running on consumer GPUs. Without lifecycle management, dual-LLM setups consume VRAM permanently even when only one model is used.

**Independent Test**: Configure text as primary with a short idle timeout, trigger a code query to load the code LLM, wait for timeout, verify code LLM is unloaded via `krag status`.

**Acceptance Scenarios**:

1. **Given** `primary_llm = "text"` and `idle_timeout = 60` in config, **When** kragd starts, **Then** only the text LLM is loaded initially.
2. **Given** the code LLM is not loaded, **When** a query triggers code routing, **Then** the code LLM loads on demand, the query is answered, and a timer begins for the idle timeout.
3. **Given** the code LLM is loaded and idle for longer than `idle_timeout`, **Then** the code LLM is unloaded and VRAM is freed.
4. **Given** `primary_llm` is not set in config, **When** both LLMs are idle past the timeout, **Then** both are unloaded.
5. **Given** the secondary LLM is loaded and the primary was displaced from VRAM (hot-swap scenario), **When** the secondary's idle timeout fires, **Then** the primary LLM is reloaded.

---

### User Story 4 - Debug Query Mode (Priority: P2)

A user wants to understand why a query returned certain results. They run `krag debug query "How does chunking work?"` and receive the standard answer and sources, plus detailed metadata: which LLM generated the answer, whether it was auto-routed or manually selected, the routing reason, which embedding models and vector spaces contributed, retrieval timing, generation timing, candidate counts before/after deduplication, and whether RRF was active.

**Why this priority**: Debugging query quality has been a recurring pain point. This metadata enables data-driven tuning without reading log files.

**Independent Test**: Run a debug query, verify all metadata fields are present and contain plausible values.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** the user runs `krag debug query "How does chunking work?"`, **Then** the output includes the answer, sources, and a debug metadata section.
2. **Given** auto-routing selects the code LLM, **When** debug mode is active, **Then** the metadata shows `llm_used: code`, `auto_routed: true`, and a `route_reason` explaining the selection (e.g., "67% code chunks").
3. **Given** the user specifies `--llm text`, **When** debug mode is active, **Then** metadata shows `auto_routed: false` and `llm_used: text`.
4. **Given** multi-model embeddings are configured, **When** debug mode is active, **Then** metadata includes all embedding models used, all vector spaces searched, and per-space result counts.
5. **Given** kragd is running, **When** the user runs `krag query "..." --debug`, **Then** the same debug metadata is included (shorthand for `krag debug query`).

---

### User Story 5 - Raw Qdrant Search (Priority: P2)

A user wants to see exactly what Qdrant returns for a query without krag's retrieval pipeline (no deduplication, boosting, or RRF fusion). They run `krag debug qdrant "plugin architecture" --space text --top-k 20` and get raw vector search results with similarity scores, payload data, and optional filtering by file type or path.

**Why this priority**: Direct vector store access is essential for diagnosing retrieval quality issues — understanding whether problems originate in the vector search, the retrieval pipeline, or the LLM synthesis.

**Independent Test**: Run a raw Qdrant search, compare results to a normal query to verify the pipeline stages that are bypassed.

**Acceptance Scenarios**:

1. **Given** kragd is running with indexed data, **When** the user runs `krag debug qdrant "plugin architecture"`, **Then** the output shows raw results from all vector spaces with unmodified similarity scores.
2. **Given** the user specifies `--space text`, **When** the search runs, **Then** only the text vector space is searched.
3. **Given** the user specifies `--filter-type code`, **When** the search runs, **Then** results are filtered to chunks with `file_type == "code"`.
4. **Given** the user specifies `--filter-path "plugins"`, **When** the search runs, **Then** results are filtered to chunks whose file path contains "plugins".
5. **Given** the user specifies `--threshold 0.5`, **When** the search runs, **Then** only results with score >= 0.5 are returned.

---

### User Story 6 - Indexing via Service (Priority: P3)

A user runs `krag index` or `krag index --full` while kragd is running. The CLI sends an indexing request to kragd, which performs incremental or full indexing using its already-loaded embedding models. The CLI displays progress (files scanned, processed, errors) and final statistics when complete.

**Why this priority**: Indexing via the service avoids reloading embedding models. Important but less frequently used than querying.

**Independent Test**: Run `krag index` via the CLI, verify the index completes and returns statistics matching the existing direct-mode output.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** the user runs `krag index`, **Then** an incremental index is performed and the CLI displays file counts and completion status.
2. **Given** kragd is running, **When** the user runs `krag index --full`, **Then** a full reindex is performed.
3. **Given** kragd is running, **When** the user runs `krag index --dir /path/to/docs`, **Then** only the specified directory is indexed (overriding config).
4. **Given** kragd is running, **When** the user runs `krag index --dry-run`, **Then** the response shows what would be indexed without modifying the vector store.
5. **Given** indexing is in progress, **When** the user runs `krag status`, **Then** the status includes information about the running index job.

---

### User Story 7 - Network Access from Other Machines (Priority: P3)

A user runs kragd on their primary workstation and queries it from a laptop or other machine on the same local network. The service binds to `0.0.0.0` (configurable) so it is accessible from other hosts. The CLI on the remote machine is configured with the kragd host address.

**Why this priority**: Multi-machine access multiplies the value of the service model but is not required for the core single-machine workflow.

**Independent Test**: Start kragd with `host = "0.0.0.0"`, run `krag query` from another machine on the same network, verify the response.

**Acceptance Scenarios**:

1. **Given** kragd is configured with `host = "0.0.0.0"`, **When** the service starts, **Then** it listens on all network interfaces.
2. **Given** the CLI on a remote machine is configured with the server's address, **When** the user runs `krag query "..."`, **Then** the query is sent to the remote kragd and the response is displayed locally.
3. **Given** kragd is configured with `host = "127.0.0.1"`, **When** a remote machine attempts to connect, **Then** the connection is refused.
4. **Given** the CLI cannot reach the configured kragd server, **When** the user runs any command, **Then** a clear error is displayed with the unreachable URL.

---

### User Story 8 - Direct Mode Fallback (Priority: P3)

A developer or advanced user wants to run krag without starting a service — for quick debugging, testing, or environments where a persistent service is unnecessary. They use `krag-direct query "..."` which behaves identically to the current pre-service-architecture CLI, running everything in-process.

**Why this priority**: Development workflow and backward compatibility. Important for testing and debugging but not the primary user path.

**Independent Test**: Run `krag-direct query "..."` without kragd running, verify it produces identical output to the current CLI.

**Acceptance Scenarios**:

1. **Given** kragd is not running, **When** the user runs `krag-direct query "What is krag?"`, **Then** the query is executed in-process (loading LLM, querying, and displaying results) exactly as the current CLI does.
2. **Given** kragd is running, **When** the user runs `krag-direct query "..."`, **Then** the query still runs in-process (does not use the service), demonstrating independence.
3. **Given** a user's existing workflow uses `krag query "..."`, **When** they switch to `krag-direct query "..."`, **Then** all existing flags (`--top-k`, `--preset`, `--format`, `--no-synthesis`, etc.) work identically.

---

### Edge Cases

- What happens when kragd runs out of VRAM during LLM loading? The service should report a clear error via the API and remain running (without the failed LLM).
- What happens when kragd crashes or is killed without clean shutdown? The stale PID file should be detected on next start (check if PID is alive) and overwritten.
- What happens when a query arrives while the secondary LLM is loading on demand? The request should block until the LLM is ready (with a timeout), not fail immediately.
- What happens when the idle timeout fires while a query using that LLM is in progress? The unload should be deferred until the in-flight request completes.
- What happens when the vector store is corrupted or missing when kragd starts? The service should start in a degraded state (health endpoint reports unhealthy, queries return clear errors, indexing still works).
- What happens when configuration changes on disk while kragd is running? The running service uses its startup configuration. A restart is required to pick up changes (document this).
- What happens when the CLI client times out waiting for a response (e.g., during long indexing)? The CLI should report a timeout error with instructions to check `krag status` or increase the timeout.

## Requirements *(mandatory)*

### Functional Requirements

#### Service Daemon (kragd)

- **FR-001**: System MUST expose a REST API that accepts query, retrieval, indexing, debug, and system management requests over HTTP.
- **FR-002**: System MUST keep configured LLM(s) loaded in memory between requests, eliminating per-request model loading.
- **FR-003**: System MUST support configurable LLM lifecycle management with a primary LLM (always loaded) and secondary LLM (loaded on demand, unloaded after idle timeout).
- **FR-004**: When no primary LLM is configured, system MUST unload all LLMs after the configured idle timeout.
- **FR-005**: System MUST reload the primary LLM after the secondary is unloaded if the primary was displaced (e.g., during a hot-swap).
- **FR-006**: System MUST defer LLM unloading if a request using that LLM is in progress.
- **FR-007**: System MUST write a PID file on startup and remove it on clean shutdown.
- **FR-008**: System MUST detect stale PID files (process no longer running) and handle them gracefully on startup.
- **FR-009**: System MUST bind to a configurable host and port (default: `0.0.0.0:8742`).
- **FR-010**: System MUST provide a health endpoint that returns service availability.
- **FR-011**: System MUST provide a status endpoint that returns loaded models, VRAM usage, uptime, vector store statistics, and embedding model information.
- **FR-012**: System MUST accept a graceful shutdown request via API, unloading models and closing connections before exiting.
- **FR-013**: System MUST support both foreground and background (daemonized) startup modes.
- **FR-014**: System MUST keep embedding models loaded for the lifetime of the service (not subject to idle timeout).
- **FR-015**: System MUST auto-generate interactive API documentation accessible at a standard path.

#### Query & Retrieval

- **FR-016**: System MUST accept query requests with configurable `top_k`, prompt preset, LLM selection, and optional debug metadata inclusion.
- **FR-017**: System MUST return query responses containing the synthesized answer and ranked source chunks.
- **FR-018**: System MUST support retrieval-only requests (no LLM synthesis) returning ranked chunks with scores.
- **FR-019**: When debug metadata is requested, system MUST include: LLM used, model filename, routing decision (auto vs. manual), routing reason, prompt preset, retrieval time, generation time, embedding models used, vector spaces searched, candidate counts (pre/post-dedup), and per-space result counts.
- **FR-020**: System MUST support raw vector store search bypassing the retrieval pipeline (no dedup, boost, or RRF), with filtering by vector space, file type, and file path substring.

#### Indexing

- **FR-021**: System MUST accept indexing requests specifying mode (full/incremental), optional directory overrides, file type filters, exclusion patterns, and dry-run flag.
- **FR-022**: System MUST return indexing results including file counts (scanned, processed, skipped, errored), chunk/vector counts, duration, and any errors.
- **FR-023**: System MUST support querying the status of the last completed indexing job.

#### CLI Client (krag)

- **FR-024**: CLI MUST provide the same user-facing commands and flags as the current direct-mode CLI (`query`, `index`, `config`, `plugin`, `gpu`, `log`, `status`). Commands that operate locally (`config`, `plugin`, `gpu`, `log`) delegate to existing `krag.cli` modules. The `eval` command remains available only via `krag-direct`.
- **FR-025**: CLI MUST produce output formatting (panels, tables, colors) identical to the current direct-mode CLI.
- **FR-026**: CLI MUST detect when kragd is unreachable and display a helpful error message with instructions to start the service.
- **FR-027**: CLI MUST support a `debug query` subcommand that displays retrieval and generation metadata alongside the standard answer output.
- **FR-028**: CLI MUST support a `debug qdrant` subcommand with flags for vector space, top-k, score threshold, file type filter, and file path filter.
- **FR-029**: CLI MUST read server connection details (host, port) from the shared configuration file.
- **FR-030**: CLI MUST support configurable request timeout for long-running operations (indexing).

#### Direct Mode

- **FR-031**: The existing CLI MUST remain available as `krag-direct`, running all operations in-process without requiring kragd.
- **FR-032**: `krag-direct` MUST support all existing flags and produce identical output to the pre-service CLI.

#### Configuration

- **FR-033**: Configuration MUST support a `[service]` section with host, port, primary LLM designation, idle timeout, and request logging toggle.
- **FR-034**: All `[service]` fields MUST have sensible defaults so the service works without explicit configuration.

### Key Entities

- **KragService**: Central service object managing lifecycle of all heavyweight components (LLMs, embeddings, vector store). Provides a unified interface for API route handlers.
- **LLMLifecycleManager**: Manages loading, unloading, and idle timeout tracking for primary and secondary LLMs. Monitors VRAM and defers unloading during in-flight requests.
- **QueryPipeline**: Immutable bundle of initialized query components (embedding generator, vector store, LLM client/pool, query engine). Used by `krag-direct` via `build_query_pipeline()`. KragService builds equivalent components individually (per R-05) for LLM lifecycle control.
- **KragClient**: HTTP client wrapper in the CLI package. Handles connection management, error translation, and timeout configuration for communication with kragd.
- **ServiceConfiguration**: New configuration section holding service-specific settings (host, port, primary LLM, idle timeout, request logging).
- **DebugMetadata**: Data structure capturing retrieval and generation diagnostics (timings, routing decisions, candidate counts, model identifiers).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can issue a second query within 2 seconds of the first query completing (no LLM reload, excluding inference time), compared to 5-15 seconds cold-start currently.
- **SC-002**: The CLI output for `krag query` via the service is visually indistinguishable from the current direct-mode output for the same query.
- **SC-003**: `krag debug query` returns at least 10 distinct metadata fields covering retrieval and generation diagnostics for every query.
- **SC-004**: `krag debug qdrant` returns raw vector search results that can be independently verified against direct Qdrant client queries.
- **SC-005**: The service remains responsive (health endpoint returns within 500ms) while the secondary LLM is loading on demand.
- **SC-006**: After idle timeout, VRAM used by the secondary LLM is fully reclaimed (verified by `krag status` VRAM reporting).
- **SC-007**: All existing tests (800+) continue to pass without modification after the service architecture changes.
- **SC-008**: New service, API, and CLI client code achieves test coverage comparable to the existing codebase standard.
- **SC-009**: `krag query` from a remote machine on the same network receives a valid response when kragd is configured for network access.
- **SC-010**: Service startup-to-ready time (including LLM loading) is reported in the startup output and is no longer than the current `krag query` cold-start.

## Assumptions

- The existing orchestration and core layers (`krag.orchestration`, `krag.retrieval`, `krag.synthesis`, `krag.embeddings`, `krag.storage`) require zero modifications. The service layer is a new consumer alongside the existing CLI.
- `build_query_pipeline()` in `krag.cli.pipeline` provides a clean factory for assembling query components. KragService extracts the same initialization pattern but builds components individually (per R-05) for error handling control and LLM lifecycle management. `build_query_pipeline()` itself remains unchanged for `krag-direct`.
- LLM inference via llama-cpp-python is inherently synchronous and blocking. API routes will use synchronous handler functions so the ASGI framework dispatches them to a thread pool.
- Qdrant remains embedded (not client-server) — the vector store is accessed via filesystem path, not a network connection.
- The system targets single-user usage. Concurrent requests from the same user are serialized through the existing LLMPool threading lock.
- Network exposure (`0.0.0.0` binding) for local-network access is desired but authentication is deferred to a future sprint. Users accept the risk of unauthenticated access on their local network.
- Streaming responses (SSE/WebSocket) are deferred. The initial API returns complete responses.
- `XDG_RUNTIME_DIR` is available for PID file storage on Linux systems; fallback to `/tmp` for other platforms.
- Configuration changes require a service restart to take effect.

## Scope Boundaries

**In scope:**
- kragd service daemon with REST API
- krag CLI client (thin HTTP wrapper with Rich output)
- krag-direct preserved as in-process fallback
- LLM lifecycle management (primary/secondary, idle timeout, load-on-demand)
- Debug query mode with full retrieval/generation metadata
- Raw Qdrant search endpoint bypassing retrieval pipeline
- Indexing via service with full/incremental/dry-run/directory override
- Service status, health, and shutdown endpoints
- Network accessibility via configurable bind address
- PID file-based process management
- Auto-generated API documentation

**Out of scope:**
- `eval` command via service — batch operation, remains available only via `krag-direct eval`
- Web UI (krag-web) — separate sprint
- Streaming SSE/WebSocket responses — future enhancement
- Authentication and authorization — future sprint when network binding goes beyond trusted LAN
- systemd/launchd service files — future sprint
- Multi-user or multi-tenant support
- Configuration hot-reload without restart
