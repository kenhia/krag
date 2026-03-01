# Feature Specification: krager Prep — API Normalization & Hardening

**Feature Branch**: `012-krager-prep`
**Created**: 2026-02-28
**Status**: Draft
**Input**: User description: "Prep for remote sprint — P1 API normalization, P2 tests for API changes, plus all pre-sprint work items including SSE index progress and SSE streaming queries"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Consistent API Responses (Priority: P1)

A remote client developer integrating with kragd needs every endpoint to return a predictable, well-documented response shape. Today, `/index/status` sometimes returns a single object and sometimes a list, and three response models are scattered across router files instead of living in the central schema module. The developer should be able to trust the OpenAPI spec as the single source of truth for all request and response shapes.

**Why this priority**: A remote client cannot be built reliably against an API with polymorphic return types and inconsistent schema locations. This is the foundational prerequisite for the krager UI sprint.

**Independent Test**: Call every kragd endpoint and verify each response matches its documented schema exactly — no polymorphic surprises, all models importable from the central schema module.

**Acceptance Scenarios**:

1. **Given** no indexing jobs have run, **When** a client calls `GET /index/status`, **Then** the response is an empty list (`[]`), not a single object or null.
2. **Given** one indexing job has completed, **When** a client calls `GET /index/status`, **Then** the response is a list containing one `IndexResponse` object.
3. **Given** multiple indexing jobs have completed, **When** a client calls `GET /index/status`, **Then** the response is a list of `IndexResponse` objects ordered by recency.
4. **Given** a developer examining the project, **When** they look for `LexiconRefreshResponse`, `ModeListResponse`, or `ModeDetailResponse`, **Then** all three are defined in the central schema module alongside all other response models.

---

### User Story 2 — Cross-Origin Access for Remote Clients (Priority: P1)

A desktop client (or any browser-based tool) connecting to kragd from a different origin needs the server to include proper CORS headers. Without CORS middleware, browser-based clients are blocked from making requests to kragd. The CORS configuration must be flexible enough for development (permissive) and production (restricted origins).

**Why this priority**: CORS is a hard blocker for any browser-rendered client, including the Tauri webview that powers krager.

**Independent Test**: Make a cross-origin request to kragd from a browser context and verify the response includes the appropriate `Access-Control-Allow-Origin` headers.

**Acceptance Scenarios**:

1. **Given** kragd is running with default configuration, **When** a browser client on a different origin makes a request, **Then** the response includes CORS headers permitting the request.
2. **Given** an operator has configured specific allowed origins, **When** a browser client from a non-allowed origin makes a request, **Then** the response omits `Access-Control-Allow-Origin`, causing the browser to block the request.
3. **Given** kragd is running, **When** a browser client sends a preflight `OPTIONS` request, **Then** the server responds with correct `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`.

---

### User Story 3 — CLI JSON Output for All Commands (Priority: P2)

A script author or automation pipeline needs machine-readable output from every krag CLI command. Today, five commands (`health`, `modes list`, `modes show`, `lexicon refresh`, `stop`) only produce human-readable text. Adding `--json` to these commands enables consistent scripting, monitoring, and integration with external tools.

**Why this priority**: While krager bypasses the CLI entirely (it calls kragd HTTP endpoints directly), consistent `--json` support across the CLI improves the developer experience, enables scripting, and ensures parity across all commands.

**Independent Test**: Run each of the five CLI commands with `--json` and verify the output is valid, parseable JSON that includes all the information shown in the default text output.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** a user runs `krag health --json`, **Then** the output is valid JSON containing `status` and `version` fields.
2. **Given** kragd is running with modes configured, **When** a user runs `krag modes list --json`, **Then** the output is valid JSON listing all available modes with their names and descriptions.
3. **Given** kragd is running with a mode named "default", **When** a user runs `krag modes show default --json`, **Then** the output is valid JSON with the full mode configuration.
4. **Given** kragd is running, **When** a user runs `krag lexicon refresh --json`, **Then** the output is valid JSON with entry count and status.
5. **Given** kragd is running, **When** a user runs `krag stop --json`, **Then** the output is valid JSON confirming the shutdown.

---

### User Story 4 — OpenAPI Spec Quality (Priority: P2)

A client developer generating TypeScript types from the kragd OpenAPI spec needs complete, accurate schema documentation — including tags on every endpoint, descriptions on every field, and representative examples for request and response bodies. This allows auto-generation tooling to produce usable client code without manual intervention.

**Why this priority**: The OpenAPI spec is the contract between kragd and krager. Incomplete documentation means manual type authoring and guesswork in the client.

**Independent Test**: Fetch the OpenAPI spec from `/openapi.json`, verify every endpoint has a tag assignment and a summary, and verify every schema field has a description.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** a developer fetches `/openapi.json`, **Then** every endpoint has at least one tag and a non-empty summary.
2. **Given** the OpenAPI spec, **When** inspecting schema definitions for all request and response models, **Then** every field has a `description` property.
3. **Given** the OpenAPI spec, **When** inspecting endpoint definitions, **Then** every endpoint with a request body includes at least one example.

---

### User Story 5 — Real-Time Index Progress (Priority: P3)

A user monitoring an indexing job wants to see progress updates as files are scanned and chunks are created, rather than polling repeatedly. An event stream endpoint provides real-time updates that clients can subscribe to, replacing the poll-based workflow for index status.

**Why this priority**: Polling works for v1, but an event stream dramatically improves UX for long-running index jobs and eliminates wasteful polling traffic. Including this in the prep sprint means krager can use it from day one.

**Independent Test**: Start an indexing job, subscribe to the event stream, and verify that progress events arrive in real time as files are processed.

**Acceptance Scenarios**:

1. **Given** an indexing job is in progress, **When** a client subscribes to the index progress event stream, **Then** the client receives progress events as files are scanned and chunks are created.
2. **Given** an indexing job completes, **When** the client is subscribed to the event stream, **Then** the client receives a final completion event and the stream closes.
3. **Given** no indexing job is running, **When** a client subscribes to the index progress event stream, **Then** the client receives a message indicating no active job and the stream closes (or remains open waiting for the next job).

---

### User Story 6 — Streaming Query Answers (Priority: P3)

A user submitting a long or complex query wants to see the answer appear incrementally as the LLM generates it, rather than waiting for the entire response to be synthesized. A streaming endpoint delivers tokens as they're produced, providing immediate feedback and a more responsive experience.

**Why this priority**: Blocking queries can take several seconds for complex prompts. Streaming makes the UI feel alive and lets users start reading before generation completes. Including this in the prep sprint means krager gets streaming from launch.

**Independent Test**: Submit a query to the streaming endpoint and verify that partial answer tokens arrive before the full response is complete.

**Acceptance Scenarios**:

1. **Given** kragd is running and a mode is active, **When** a client submits a query to the streaming endpoint, **Then** the client receives partial answer tokens as they are generated.
2. **Given** a streaming query is in progress, **When** the LLM finishes generating, **Then** the client receives a final event containing the complete response (including sources and optional debug metadata).
3. **Given** a streaming query encounters an error mid-generation, **When** the error occurs, **Then** the client receives an error event with a descriptive message and the stream closes gracefully.

---

### User Story 7 — Comprehensive Test Coverage for All Changes (Priority: P1)

Every API normalization change, new middleware, and new endpoint must have corresponding automated tests. A developer making future changes needs confidence that the prep work is solid and that regressions will be caught immediately.

**Why this priority**: Tests are essential for every change in this sprint. Without them, the krager client is built on an unverified foundation.

**Independent Test**: Run the full test suite and verify all new tests pass, covering the normalized `/index/status` response, schema consolidation, CORS headers, CLI `--json` output, OpenAPI completeness, SSE index progress, and streaming queries.

**Acceptance Scenarios**:

1. **Given** the test suite, **When** tests run for `/index/status`, **Then** tests verify the endpoint always returns a list regardless of the number of results (zero, one, many).
2. **Given** the test suite, **When** tests run for schema consolidation, **Then** tests verify `LexiconRefreshResponse`, `ModeListResponse`, and `ModeDetailResponse` are importable from the central schema module and the routers use them from there.
3. **Given** the test suite, **When** tests run for CORS, **Then** tests verify CORS headers are present on responses and that the configuration is respected.
4. **Given** the test suite, **When** tests run for CLI commands, **Then** tests verify `--json` output is valid JSON for `health`, `modes list`, `modes show`, `lexicon refresh`, and `stop`.
5. **Given** the test suite, **When** tests run for the index progress event stream, **Then** tests verify events are emitted during indexing and a completion event is sent when finished.
6. **Given** the test suite, **When** tests run for streaming queries, **Then** tests verify partial tokens are delivered and a final complete response event is sent.

---

### Edge Cases

- What happens when CORS middleware receives a request with no `Origin` header? (Non-browser clients should still work without restriction.)
- What happens when `/index/status` is called while an indexing job is actively running? (Should return the in-progress job status in the list.)
- What happens when a streaming query client disconnects mid-stream? (Server should stop generation gracefully and release resources.)
- What happens when `GET /index/stream` is called and the current indexing job completes between the client's subscription attempts? (Should receive the completion event or an idle event, not hang indefinitely.)
- What happens when `krag stop --json` is called but kragd is not running? (Should return a JSON error, not crash.)
- What happens when `krag modes show nonexistent --json` is called? (Should return a JSON error with 404/422 semantics.)

## Requirements *(mandatory)*

### Functional Requirements

**API Normalization**

- **FR-001**: The `/index/status` endpoint MUST always return a list of `IndexResponse` objects, even when zero or one results exist.
- **FR-002**: `LexiconRefreshResponse` MUST be defined in the central schema module and the lexicon router MUST import it from there.
- **FR-003**: `ModeListResponse` and `ModeDetailResponse` MUST be defined in the central schema module and the modes router MUST import them from there.
- **FR-004**: Moving schemas MUST NOT change the shape or content of any response — this is a refactor, not a behavior change.

**CORS Middleware**

- **FR-005**: The server MUST include CORS middleware that adds appropriate `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, and `Access-Control-Allow-Headers` headers to all responses.
- **FR-006**: CORS allowed origins MUST be configurable, with a permissive default (`["*"]`) suitable for local development.
- **FR-007**: The CORS middleware MUST handle preflight `OPTIONS` requests correctly.
- **FR-008**: Non-browser clients (no `Origin` header) MUST continue to work without restriction.

**CLI JSON Output**

- **FR-009**: `krag health` MUST support a `--json` flag producing valid JSON output with `status` and `version` fields.
- **FR-010**: `krag modes list` MUST support a `--json` flag producing valid JSON output listing all modes.
- **FR-011**: `krag modes show <name>` MUST support a `--json` flag producing valid JSON output with the full mode configuration.
- **FR-012**: `krag lexicon refresh` MUST support a `--json` flag producing valid JSON output with entry count and status.
- **FR-013**: `krag stop` MUST support a `--json` flag producing valid JSON output confirming the shutdown action.
- **FR-014**: All `--json` output MUST be parseable by standard JSON tools and contain all information present in the default text output.

**OpenAPI Spec Quality**

- **FR-015**: Every endpoint MUST have at least one tag and a non-empty summary in the OpenAPI spec.
- **FR-016**: Every schema field MUST have a description in the OpenAPI spec.
- **FR-017**: Every endpoint with a request body MUST include at least one example in the OpenAPI spec.

**SSE Index Progress**

- **FR-018**: The server MUST provide an event stream endpoint for real-time index progress updates.
- **FR-019**: The index progress stream MUST emit events as files are scanned, chunks are created, and vectors are stored.
- **FR-020**: The index progress stream MUST emit a completion event when the indexing job finishes.
- **FR-021**: The index progress stream MUST handle the case where no indexing job is active.

**Streaming Query Answers**

- **FR-022**: The server MUST provide a streaming endpoint for query answers that delivers partial tokens as the LLM generates them.
- **FR-023**: The streaming endpoint MUST deliver a final event containing the complete response (answer, sources, optional debug metadata).
- **FR-024**: The streaming endpoint MUST handle mid-stream errors gracefully, sending an error event and closing the stream.
- **FR-025**: The streaming endpoint MUST release resources when the client disconnects mid-stream.

**Test Coverage**

- **FR-026**: All API normalization changes MUST have corresponding automated tests.
- **FR-027**: CORS middleware MUST have tests verifying headers are present and configuration is respected.
- **FR-028**: All five CLI `--json` commands MUST have tests verifying valid JSON output.
- **FR-029**: The SSE index progress endpoint MUST have tests verifying event delivery during indexing.
- **FR-030**: The streaming query endpoint MUST have tests verifying partial token delivery and final response.

### Key Entities

- **IndexResponse**: Represents the result of an indexing job — job ID, status, file counts, chunk counts, vector counts, duration, collections, and errors. The `/index/status` endpoint now always returns a list of these.
- **LexiconRefreshResponse**: Result of a lexicon refresh operation — entry count and status. Moved from the lexicon router to the central schema module.
- **ModeListResponse**: List of available modes with summary info. Moved from the modes router to the central schema module.
- **ModeDetailResponse**: Full configuration for a single mode — name, description, collections, LLM slot, preset, top_k, similarity threshold, critic settings. Moved from the modes router to the central schema module.
- **CORS Configuration**: Set of allowed origins, methods, and headers controlling cross-origin access to the server.

## Assumptions

- The Tauri v2 webview sends an `Origin` header that triggers browser CORS enforcement, making CORS middleware necessary. If testing reveals otherwise, the middleware is still valuable for other browser-based clients and debugging tools.
- The existing `--json` pattern used by other CLI commands (`krag status`, `krag index`, etc.) is the model for the five new `--json` additions — a boolean flag that switches output from formatted text to JSON.
- SSE (Server-Sent Events) is the appropriate mechanism for index progress streaming, as it is unidirectional (server to client) and well-supported by browsers and HTTP clients.
- The streaming query endpoint will use SSE as the transport, matching the index progress pattern for consistency.
- The LLM backend supports token-by-token streaming. If it only supports full-response generation, the streaming endpoint will deliver the complete answer as a single event (graceful degradation).
- Schema consolidation is a pure refactor — no fields are added, removed, or renamed.
- The default CORS configuration allows all origins (`*`) for development convenience, matching common FastAPI development practices.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every kragd endpoint returns a response that matches its OpenAPI schema exactly — no polymorphic return types, no undocumented shapes.
- **SC-002**: A browser-based client on a different origin can successfully call all kragd endpoints without CORS errors.
- **SC-003**: All five CLI commands support `--json` output that is valid, parseable JSON containing the same information as text output.
- **SC-004**: The OpenAPI spec at `/openapi.json` is complete — 100% of endpoints are tagged, 100% of fields have descriptions, and all request bodies have examples.
- **SC-005**: Indexing progress events are delivered to subscribed clients within 1 second of each file being processed.
- **SC-006**: Streaming query answers begin delivering tokens within 2 seconds of query submission (given a running LLM).
- **SC-007**: All new functionality has automated test coverage — the test suite passes with zero failures.
- **SC-008**: All existing tests continue to pass — zero regressions from the normalization and consolidation work.
