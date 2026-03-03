# Feature Specification: krager — Tauri Desktop Client for kragd

**Feature Branch**: `013-krager`
**Created**: 2026-03-01
**Status**: Draft
**Input**: User description: "Tauri + Svelte desktop client for kragd — remote GUI for querying, indexing, and managing the krag RAG system"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Project Scaffold & Dev Environment (Priority: P1)

A developer clones the krag repo and wants to set up the krager desktop client for local development. They navigate to `apps/krager/`, install dependencies, and launch the app in dev mode. The app opens a native window with a basic Svelte UI served by Vite's dev server, wrapped in a Tauri webview.

**Why this priority**: Nothing else can be built until the project structure exists. This establishes the monorepo layout, build toolchain, and developer workflow.

**Independent Test**: Run `cd apps/krager && pnpm install && pnpm tauri dev` — a native window opens showing a placeholder UI.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the krag repo, **When** the developer runs `cd apps/krager && pnpm install && pnpm tauri dev`, **Then** a native desktop window opens with a Svelte-rendered page.
2. **Given** the project is set up, **When** the developer edits a `.svelte` file, **Then** the change hot-reloads in the running window within 2 seconds.
3. **Given** the project exists at `apps/krager/`, **When** `uv run pytest` is run from the repo root, **Then** existing Python tests still pass (no interference between toolchains).
4. **Given** the project exists, **When** `pnpm tauri build` is run, **Then** a native binary is produced for the current platform.

---

### User Story 2 — Connect to kragd & View System Status (Priority: P1)

A user launches krager and enters the kragd host and port (defaulting to `localhost:11435`). The app polls the health endpoint and shows a connection status indicator (connected/disconnected/error). Once connected, the system status panel displays service version, uptime, loaded LLM info, embedding models, collections, and VRAM usage.

**Why this priority**: Connection management is the foundation — every other feature depends on communicating with kragd.

**Independent Test**: Start kragd, launch krager, verify the connection indicator turns green and system status populates.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** the user enters `localhost:11435` and clicks connect, **Then** the status indicator shows "Connected" within 5 seconds.
2. **Given** no kragd is running, **When** the user attempts to connect, **Then** the status indicator shows "Disconnected" with a meaningful error message.
3. **Given** a connected session, **When** kragd stops unexpectedly, **Then** the status indicator changes to "Disconnected" within 10 seconds (one health poll cycle).
4. **Given** a connected session, **When** the user views the System panel, **Then** version, uptime, LLM slot info, embedding models, and collection counts are displayed.
5. **Given** kragd is in degraded mode, **When** the health endpoint returns `{ status: 'degraded' }`, **Then** the connection badge shows a warning state (orange indicator with "Degraded" label).

---

### User Story 3 — Query kragd & View Answers (Priority: P1)

A user types a natural-language question into the query panel, optionally selects a mode from the mode dropdown, and submits. The answer appears in the transcript area along with source citations. Each interaction is logged in a scrollable transcript.

**Why this priority**: Querying is the primary use case for krag. This delivers the core value proposition — a GUI for RAG queries.

**Independent Test**: With kragd running and indexed, type a question, submit, verify the answer and sources appear in the transcript.

**Acceptance Scenarios**:

1. **Given** a connected session with indexed data, **When** the user types a query and clicks Send, **Then** the answer and source chunks appear in the transcript within the LLM generation time.
2. **Given** the mode selector shows available modes, **When** the user selects a specific mode before querying, **Then** the query is sent with that mode and the response reflects mode-specific retrieval.
3. **Given** multiple queries have been submitted, **When** the user scrolls the transcript, **Then** all past interactions are visible with timestamps and can be reviewed.
4. **Given** a query is in progress, **When** the user waits, **Then** a loading indicator is shown until the response arrives.
5. **Given** a query fails (e.g., service error), **When** the error response arrives, **Then** the error message is displayed in the transcript without crashing the app.

---

### User Story 4 — Trigger & Monitor Indexing (Priority: P2)

A user navigates to the Index panel, selects full or incremental mode, and triggers an indexing job. The panel shows the job status (running/completed/failed) through polling, with file counts, chunk counts, and duration updating as the job progresses.

**Why this priority**: Indexing is the second most common operation. Users need to (re)index their codebase from the GUI.

**Independent Test**: Trigger an incremental index from the UI, verify the status updates show progress and eventual completion.

**Acceptance Scenarios**:

1. **Given** a connected session, **When** the user clicks "Index" with incremental mode selected, **Then** a job starts and the panel shows "Running" status.
2. **Given** an indexing job is running, **When** the user views the Index panel, **Then** current progress (files scanned, files processed, vectors stored) is visible and updates periodically.
3. **Given** an indexing job completes, **When** the status updates, **Then** the panel shows "Completed" with final counts and duration.
4. **Given** an indexing job fails, **When** the error is received, **Then** the panel shows "Failed" with the error message.

---

### User Story 5 — Mode Discovery & Selection (Priority: P2)

A user sees a dropdown populated with all available kragd modes (fetched from `GET /modes`). Selecting a mode shows its description and configuration. The selected mode is used for subsequent queries.

**Why this priority**: Modes control retrieval scope and behavior. Making them discoverable and selectable is essential for effective querying.

**Independent Test**: Connect to kragd, verify modes appear in dropdown, select a mode, verify queries use it.

**Acceptance Scenarios**:

1. **Given** a connected session, **When** the mode selector loads, **Then** all modes from `GET /modes` are listed with their names.
2. **Given** a mode is selected, **When** the user submits a query, **Then** the `mode` parameter is included in the query request.
3. **Given** a mode is selected, **When** the user views mode details, **Then** the mode description and collection configuration are displayed.

---

### User Story 6 — Debug Tools (Priority: P3)

A power user accesses the Debug panel to run debug queries (with full metadata) and raw Qdrant vector searches. Debug query responses include LLM routing info, timing, critic scores, and retrieval statistics.

**Why this priority**: Debug tools are valuable but only for power users investigating retrieval quality or LLM behavior.

**Independent Test**: Submit a debug query, verify debug metadata (LLM used, route, timings, critic scores) appears in the response.

**Acceptance Scenarios**:

1. **Given** a connected session, **When** the user submits a debug query, **Then** the response includes answer, sources, and full debug metadata.
2. **Given** the debug panel, **When** the user runs a raw Qdrant search, **Then** vector search results with scores and payloads are displayed.
3. **Given** a debug response, **When** the user views it, **Then** retrieval time, generation time, LLM route, and critic scores are clearly shown.

---

### User Story 7 — Error Handling & Resilience (Priority: P2)

The app gracefully handles all kragd error states: connection failures, validation errors (422), indexing conflicts (409), service not ready (503), and server errors (500). Errors are surfaced to the user through a notification/toast system without crashing the app.

**Why this priority**: Robustness is critical for user trust. The app must fail gracefully in all error scenarios.

**Independent Test**: Trigger each error condition (bad query, index while indexing, disconnect) and verify the UI shows appropriate messages.

**Acceptance Scenarios**:

1. **Given** the user submits an empty query, **When** the server returns 422, **Then** a validation error message is shown.
2. **Given** indexing is in progress, **When** the user triggers another index, **Then** a 409 conflict message explains indexing is already running.
3. **Given** kragd is starting up, **When** the user sends a request, **Then** a 503 "service not ready" message is shown.
4. **Given** any unexpected server error (500), **When** the response arrives, **Then** a generic error notification is displayed with the error detail.

---

### User Story 8 — Theme & Visual Polish (Priority: P3)

The app supports dark mode (matching system preference) with a consistent color scheme. The layout is responsive within reasonable window sizes and the typography is optimized for reading code and prose.

**Why this priority**: Visual quality affects usability but is not functional. Can be refined after core features work.

**Independent Test**: Toggle system dark/light mode, verify the app UI switches themes. Resize the window, verify the layout adapts.

**Acceptance Scenarios**:

1. **Given** the system is set to dark mode, **When** the app launches, **Then** the UI renders in dark theme.
2. **Given** the app is running, **When** the user resizes the window, **Then** the layout adjusts without content being clipped or overflowing.
3. **Given** a query response with code blocks, **When** the answer is displayed, **Then** code is rendered with syntax-appropriate formatting.

---

### Edge Cases

- What happens when kragd returns an unexpected response shape (e.g., API version mismatch)? — Display raw JSON as fallback with a "schema mismatch" warning.
- What happens when the transcript grows very large (thousands of entries)? — Implement virtual scrolling or cap at a configurable limit (default 500 entries).
- What happens when the user submits a query while disconnected? — Show "Not connected" error immediately without making a network request.
- What happens when kragd is on a non-standard port or remote host? — The connection bar accepts any host:port; no localhost assumption in the client.
- What happens when a query takes longer than 60 seconds? — Show a timeout notification and allow the user to retry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST be scaffolded as a Tauri v2 + Svelte + TypeScript application at `apps/krager/` within the existing krag monorepo.
- **FR-002**: The build toolchain (Rust/cargo, Node.js/pnpm) MUST NOT interfere with the existing Python toolchain (uv, ruff, mypy, pytest).
- **FR-003**: The app MUST provide a configurable connection to kragd via host:port input, defaulting to `localhost:11435`.
- **FR-004**: The app MUST poll `GET /health` at regular intervals (default 5 seconds) and display connection status as connected, disconnected, or error.
- **FR-005**: The app MUST provide a query input panel that sends `POST /query` with optional mode, top_k, and preset parameters.
- **FR-006**: The app MUST display query answers with source citations, showing file path, score, rank, and chunk content for each source.
- **FR-007**: The app MUST maintain a scrollable transcript of all interactions (queries, retrieves, index operations, debug operations) with timestamps.
- **FR-008**: The app MUST provide a mode selector dropdown populated dynamically from `GET /modes`.
- **FR-009**: The app MUST provide an index panel to trigger `POST /index` (full or incremental) and display job status by polling `GET /index/status`.
- **FR-010**: The app MUST provide a system status panel displaying data from `GET /status` (version, uptime, LLM info, embedding models, collections, VRAM usage).
- **FR-011**: The app MUST provide debug tools: debug query (`POST /debug/query`) and raw Qdrant search (`POST /debug/qdrant`).
- **FR-012**: The app MUST handle all kragd error responses (422, 409, 503, 500) with user-friendly notifications that do not crash the application.
- **FR-013**: The app MUST support dark and light themes, defaulting to the system preference.
- **FR-014**: The app MUST provide a lexicon refresh action that calls `POST /lexicon/refresh`.
- **FR-015**: TypeScript types for all kragd request/response schemas MUST be defined in a shared types module mirroring `kragd/schemas.py`.
- **FR-016**: The API client layer MUST centralize all HTTP communication with kragd, handling errors consistently.
- **FR-017**: The app MUST produce a working native binary via `pnpm tauri build` on Linux. Windows build verification MUST be performed by the user, either via cross-compilation from the Linux environment or by following documented Windows build instructions.
- **FR-018**: The app MUST provide a retrieve-only action that sends `POST /retrieve` with optional mode and top_k, displaying source chunks without LLM generation.

### Key Entities

- **Connection**: Represents the kragd server connection state — host, port, status (connected/disconnected/error), last health check timestamp.
- **Transcript Entry**: A timestamped record of a user interaction — type (query/retrieve/index/debug/system), request payload, response data, optional debug metadata, duration, and error state.
- **Mode**: A named retrieval configuration fetched from kragd — name, description, collections, weights. Drives the mode selector.
- **Index Job**: Represents an indexing operation — job ID, status (running/completed/failed), file counts, chunk counts, duration, errors.
- **System Status**: Snapshot of kragd service state — version, uptime, LLM slot info, embedding models, vector store info, collections, VRAM usage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can install prerequisites, run `pnpm install && pnpm tauri dev` in `apps/krager/`, and have a working desktop window within 3 minutes.
- **SC-002**: A user can connect to a running kragd instance and see system status within 10 seconds of launching the app.
- **SC-003**: A user can submit a query and receive an answer with sources displayed in the transcript within the time it takes kragd to generate the response (no added client overhead > 500ms).
- **SC-004**: A user can trigger an indexing job and monitor its progress to completion without leaving the app.
- **SC-005**: All 6 kragd error status codes (422, 409, 503, 500, connection refused, timeout) display meaningful user-facing messages without crashing.
- **SC-006**: The app launches and operates correctly on Linux and Windows with dark and light system themes.
- **SC-007**: Existing Python tests (`uv run pytest`) continue to pass with zero regressions after adding the `apps/krager/` directory.
- **SC-008**: `pnpm tauri build` produces a native binary on Linux that launches and connects to kragd successfully. A Windows binary is manually verified by the user (cross-compiled or built natively on Windows).

## Assumptions

- kragd is already running and accessible at the configured host:port. krager does not start or manage the kragd process (deferred to a future version).
- The user has Rust, Node.js 20+, and pnpm installed. Setup documentation covers prerequisites.
- Transcript data is in-memory only for v1 — it does not persist across app restarts.
- Single kragd connection at a time — multi-server support is deferred.
- Linux is the primary build target. Windows requires manual build verification by the user in v1 — either via cross-compilation from the Linux environment (if the Tauri cross-compile toolchain supports it) or by following documented Windows setup instructions (Rust, Node.js 20+, pnpm, WebView2). macOS is expected to work but is not formally tested.
- The Tauri backend (`src-tauri/main.rs`) is minimal — all business logic lives in the Svelte frontend communicating with kragd over HTTP.
- SSE streaming for query answers (`POST /query/stream`) and index progress (`GET /index/stream`) — added in sprint 012 — MUST be integrated as the primary real-time transport. Polling via `GET /index/status` serves as fallback when SSE connections drop.
