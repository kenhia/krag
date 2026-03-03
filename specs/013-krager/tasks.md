# Tasks: krager — Tauri Desktop Client for kragd

**Input**: `specs/013-krager/` — plan.md, spec.md, research.md, data-model.md, contracts/kragd-api.ts, quickstart.md
**Branch**: `013-krager`

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Parallelizable — different files, no dependency on incomplete tasks
- **[Story]**: User story label (US1–US8 map to spec.md stories)
- Setup/Foundation phases: no story label
- All paths relative to repo root

### TDD Policy (Constitution §II — NON-NEGOTIABLE)

Every implementation task that creates a `.ts` or `.svelte` module MUST follow Red-Green-Refactor:
1. Write the `*.test.ts` file **first** with failing tests covering the module's contract
2. Implement the module until tests pass
3. Refactor while keeping tests green

Dedicated test tasks (T069, T070, T076) cover the most complex modules. For all other implementation tasks, the test file is an implicit deliverable of that task.

---

## Phase 1: Setup

**Purpose**: Scaffold the Tauri + SvelteKit project and configure all tooling.

- [x] T001 Scaffold `apps/krager/` with `pnpm create tauri-app krager --template svelte-ts` from `apps/`
- [x] T002 Add `@tauri-apps/plugin-http` and register it: `pnpm add @tauri-apps/plugin-http && pnpm tauri add http` in `apps/krager/`
- [x] T003 [P] Add dev dependencies: `pnpm add -D vitest @testing-library/svelte @testing-library/jest-dom jsdom shiki` in `apps/krager/`
- [x] T004 [P] Configure Vitest in `apps/krager/vite.config.ts`: jsdom environment, globals, `setupFiles: ['./src/test-setup.ts']`, include `src/**/*.{test,spec}.ts`
- [x] T005 [P] Create `apps/krager/src/test-setup.ts`: import `@testing-library/jest-dom/vitest`
- [x] T006 [P] Configure `apps/krager/tsconfig.json`: strict mode, `paths: { "$lib/*": ["src/lib/*"] }`
- [x] T007 [P] Create `apps/krager/src-tauri/capabilities/default.json`: `core:window:default` + `core:app:default` + standard permissions
- [x] T008 [P] Create `apps/krager/src-tauri/capabilities/http.json`: `http:default` allow list with `http://**` (any host — FR-003 requires user-configurable connection target, not locked to localhost)

**Checkpoint**: `pnpm install` succeeds, `pnpm tauri dev` starts (placeholder UI), `pnpm test` runs (0 tests), `pnpm lint` runs via biome

> **SAR Remediation (C1)**: T067 added for biome linter/formatter configuration.

- [x] T067 [P] Install and configure biome in `apps/krager/`: `pnpm add -D @biomejs/biome && pnpm biome init`; add `"lint": "biome lint src/"`, `"format": "biome format src/"`, `"check": "biome check src/"` scripts to `package.json`; configure TypeScript + Svelte rules

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core modules used by every user story — types, HTTP client, theme, app shell, notifications.

**⚠️ CRITICAL**: All user story phases depend on this phase being complete.

- [x] T009 Create `apps/krager/src/lib/types.ts`: copy and adapt all interfaces from `specs/013-krager/contracts/kragd-api.ts` — `QueryRequest`, `QueryResponse`, `SourceChunk`, `DebugMetadata`, `IndexRequest`, `IndexResponse`, `ServiceStatus`, `HealthResponse`, `ModeInfo`, `ModeDetailResponse`, `ModeListResponse`, `LexiconRefreshResponse`, `QdrantSearchRequest`, `QdrantSearchResponse`, `DebugQueryRequest`, `DebugQueryResponse`, `KragdError`, `KRAGD_ERROR_CODES`, `QueryStreamEvent`, `IndexStreamEvent` and all supporting types
- [x] T010 [P] Create `apps/krager/src/lib/services/kragd-client.ts`: base singleton with `baseUrl` derived from connection state; wrap `@tauri-apps/plugin-http` `fetch` in a typed helper that deserializes JSON, extracts HTTP errors into `KragdError(status, message, detail)`, and re-throws; export `kragdFetch<T>(path, init?): Promise<T>`
- [x] T011 [P] Create `apps/krager/src/lib/state/theme.svelte.ts`: `export const appTheme = $state({ current: ... })` initialized from `window.matchMedia`; `initTheme()` using `getCurrentWindow().theme()` + `onThemeChanged()` with `window.matchMedia` fallback for Linux (where `theme()` returns `null`)
- [x] T012 [P] Create `apps/krager/src/app.css`: CSS custom properties for dark/light themes (`--bg`, `--fg`, `--accent`, `--surface`, `--border`, `--text-muted`, `--error`, `--success`, `--warning`); base typography and reset; `[data-theme="dark"]` and `[data-theme="light"]` selectors
- [x] T013 [P] Create `apps/krager/src/lib/components/ui/Toast.svelte`: animated toast component accepting `message: string, type: 'error'|'info'|'success'|'warning', duration?: number`; auto-dismiss; accessible (`role="alert"`)
- [x] T014 [P] Create `apps/krager/src/lib/state/notifications.svelte.ts`: `export const notifications = $state({ toasts: [] as ToastEntry[] })`; `addToast(msg, type, duration?)`, `dismissToast(id)`
- [x] T015 [P] Create `apps/krager/src/lib/utils/format.ts`: `formatDuration(ms: number): string`, `formatTimestamp(d: Date): string`, `formatFileSize(bytes: number): string`, `formatUptime(seconds: number): string`
- [x] T016 Update `apps/krager/src/routes/+layout.ts`: `export const ssr = false; export const prerender = false;`
- [x] T017 Update `apps/krager/src/routes/+layout.svelte`: call `initTheme()` in `$effect`; set `document.documentElement.setAttribute('data-theme', appTheme.current)` reactively; render `<Toast>` outlet for notifications; import `app.css`
- [x] T018 Update `apps/krager/src/routes/+page.svelte`: skeleton multi-panel layout (sidebar nav + main content area with placeholder slots for ConnectionBar, panels)

**Checkpoint**: Foundation complete — theme switches on OS toggle, app shell renders, toast appears when triggered manually, `pnpm test` passes unit tests for utilities

> **SAR Remediation (A1, C2)**: T068–T070 added for SSE streaming module and dedicated test tasks.

- [x] T068 [P] Create `apps/krager/src/lib/services/streaming.ts`: SSE POST helper for `POST /query/stream` using `@tauri-apps/plugin-http` fetch + ReadableStream text line parser; SSE GET helper for `GET /index/stream` using EventSource; typed event parsers returning `QueryStreamEvent` and `IndexStreamEvent` discriminated unions; connection error + automatic reconnect logic
- [x] T069 [P] Write unit tests for `kragd-client.ts` and `streaming.ts` (TDD): test `kragdFetch` error extraction per HTTP status code (422/409/503/500/network), each endpoint method returns typed response; test SSE POST event parsing (`query:sources`/`token`/`done`/`error`), SSE GET event parsing (`index:idle`/`progress`/`complete`/`error`); `vi.mock('@tauri-apps/plugin-http')`
- [x] T070 [P] Write unit tests for all state modules (TDD): `connection.svelte.ts` (status transitions, baseUrl derivation), `transcript.svelte.ts` (addEntry, updateEntry, maxEntries trim, clearTranscript), `modes.svelte.ts` (setSelected, clearModes), `indexJob.svelte.ts` (applyStatus, resetJob, filesSkippedUnchanged/Other mapping), `notifications.svelte.ts` (addToast, dismissToast)

---

## Phase 3: User Story 1 — Project Scaffold & Dev Environment (Priority: P1) 🎯 MVP

**Goal**: A developer can clone, install, and run `pnpm tauri dev` to get a working development window. Production build works. Python tests are unaffected.

**Independent Test**: `cd apps/krager && pnpm install && pnpm tauri dev` opens a native window; `uv run pytest` from repo root passes.

- [x] T019 [US1] Create `apps/krager/src/lib/components/ui/Button.svelte`: typed props `label`, `disabled`, `variant: 'primary'|'secondary'|'danger'`, `loading`; emit `click`; keyboard accessible
- [x] T020 [US1] Create `apps/krager/src/lib/components/ui/Input.svelte`: typed props `value`, `placeholder`, `disabled`, `type`; bind two-way; emit `change`
- [x] T021 [US1] Create `apps/krager/src/lib/components/ui/Spinner.svelte`: CSS-only loading indicator; `size: 'sm'|'md'|'lg'` prop
- [x] T022 [US1] Create `apps/krager/README.md`: prerequisites (Rust, Node.js 20+, pnpm, webkit2gtk-4.1-dev on Linux); dev setup (`pnpm install && pnpm tauri dev`); test commands; Linux build; Windows cross-compile (`cargo-xwin`) with link to `specs/013-krager/quickstart.md`
- [x] T023 [US1] Verify `uv run pytest` passes from repo root with `apps/krager/` present (no Python interference — `.gitignore`, `pyproject.toml` exclusions, no stray `.py` files)
- [x] T024 [US1] Verify Linux production build: `cd apps/krager && pnpm tauri build` produces `src-tauri/target/release/bundle/appimage/*.AppImage` and/or `deb/*.deb`

**Checkpoint**: US1 complete — dev window opens, HMR works, Python CI intact, Linux binary built

---

## Phase 4: User Story 2 — Connect to kragd & View System Status (Priority: P1) 🎯 MVP

**Goal**: User enters host:port, app polls `/health`, shows connected/disconnected/error badge, System panel shows full `GET /status` data.

**Independent Test**: Start kragd, launch krager, enter `localhost:11435`, verify green indicator and status panel data.

- [x] T025 [P] [US2] Create `apps/krager/src/lib/state/connection.svelte.ts`: `export const connection = $state({ host, port, status: 'disconnected', lastCheck, errorMsg, version })`; derive `baseUrl`; `ConnectionStatus` type
- [x] T026 [P] [US2] Add `getHealth(host, port): Promise<HealthResponse>` and `getStatus(): Promise<ServiceStatus>` to `apps/krager/src/lib/services/kragd-client.ts`; use `kragdFetch` with connection's `baseUrl`
- [x] T027 [US2] Create `apps/krager/src/lib/components/domain/ConnectionBar.svelte`: host input + port input + Connect/Disconnect button + status badge (`●` green/red/orange with label); wires to `connection` state; on "Connect" sets host/port and triggers first health check
- [x] T028 [US2] Implement health polling `$effect` in `ConnectionBar.svelte`: `setInterval(checkHealth, 5000)` while connected; immediate check on connect; teardown on disconnect or component destroy; updates `connection.status`, `connection.lastCheck`, `connection.errorMsg`
- [x] T029 [US2] Create `apps/krager/src/lib/components/domain/SystemStatus.svelte`: displays `ServiceStatus` data — version, uptime (formatted), LLM slots (text/code loaded status + model name), embedding models list, collection stats (vectors_count per collection), VRAM bar (used_mb / total_mb), lexicon status; calls `getStatus()` on mount and on manual refresh; shows loading spinner
- [x] T030 [US2] Wire `ConnectionBar` and `SystemStatus` into `+page.svelte`; show SystemStatus only when `connection.status === 'connected'`

**Checkpoint**: US2 complete — green indicator on connect, status panel populates, turns red within 10s of kragd stopping

---

## Phase 5: User Story 3 — Query kragd & View Answers (Priority: P1) 🎯 MVP

**Goal**: User types a query, clicks Send, answer and sources appear in scrollable transcript. Multiple queries accumulate with timestamps.

**Independent Test**: With kragd running and indexed, submit a query, verify answer + sources in transcript.

- [x] T031 [P] [US3] Create `apps/krager/src/lib/state/transcript.svelte.ts`: `export const transcript = $state({ entries: [] as TranscriptEntry[], maxEntries: 500 })`; `addEntry(e)` appends and trims to `maxEntries`; `updateEntry(id, patch)` mutates in-place; `clearTranscript()`; `TranscriptEntry` type: `{ id, timestamp, type, request, response, durationMs, error, loading }`; `TranscriptType = 'query'|'retrieve'|'index'|'status'|'debug'|'system'`
- [x] T032 [P] [US3] Add `postQuery(req: QueryRequest): Promise<QueryResponse>` to `apps/krager/src/lib/services/kragd-client.ts`
- [x] T033 [US3] Create `apps/krager/src/lib/components/domain/QueryPanel.svelte`: textarea for query text; Send button with Spinner while `loading`; optional mode selector slot (empty for now, wired in US5); submits `PostQuery`, appends loading transcript entry, updates on response/error; disable Send while disconnected or loading
- [x] T034 [US3] Create `apps/krager/src/lib/components/domain/SourceList.svelte`: renders `SourceChunk[]` — file path (clickable/copyable), score badge, rank, language tag, chunk content in `<pre>`; empty state "No sources"
- [x] T035 [US3] Create `apps/krager/src/lib/components/domain/TranscriptView.svelte`: scrollable list of `TranscriptEntry[]` from transcript state; each entry shows timestamp, type badge, query text, answer (or loading spinner), `<SourceList>` for query entries, error message styled as error; auto-scrolls to bottom on new entry; "Clear" button
- [x] T036 [US3] Wire `QueryPanel` + `TranscriptView` into `+page.svelte`; disable query while `connection.status !== 'connected'`

**Checkpoint**: US3 complete — US1+US2+US3 form the complete MVP: connect, query, read answers

> **SAR Remediation (A1, U1)**: T071–T073 added for SSE streaming in queries and retrieve-only mode.

- [x] T071 [US3] Wire SSE streaming into `QueryPanel.svelte`: use `streaming.ts` POST SSE for `/query/stream` as primary transport; show sources immediately on `query:sources` event; append tokens live to transcript answer on `query:token`; finalize on `query:done`; handle `query:error`; fall back to `POST /query` on SSE connection failure
- [x] T072 [P] [US3] Add `postRetrieve(req: RetrieveRequest): Promise<RetrieveResponse>` to `apps/krager/src/lib/services/kragd-client.ts` (FR-018)
- [x] T073 [US3] Add "Retrieve Only" toggle in `QueryPanel.svelte`: when active, calls `postRetrieve` instead of `postQuery/stream`; shows sources in `SourceList` without answer section; transcript entry with `type: 'retrieve'`

---

## Phase 6: User Story 5 — Mode Discovery & Selection (Priority: P2)

**Goal**: Mode dropdown populated from `GET /modes`; selected mode included in query requests; mode detail visible on selection.

**Independent Test**: Connect to kragd, verify modes populate, select one, verify query uses it, verify detail shows.

- [x] T037 [P] [US5] Create `apps/krager/src/lib/state/modes.svelte.ts`: `export const modesState = $state({ available: [] as ModeInfo[], selected: null as string | null, loading: false, error: null })`; `setSelected(name)`, `clearModes()`
- [x] T038 [P] [US5] Add `getModes(): Promise<ModeListResponse>` and `getModeDetail(name: string): Promise<ModeDetailResponse>` to `apps/krager/src/lib/services/kragd-client.ts`
- [x] T039 [US5] Create `apps/krager/src/lib/components/domain/ModeSelector.svelte`: `<select>` populated from `modesState.available`; null option "(default mode)"; on change updates `modesState.selected`; detail panel below: description, collections, llm_slot, top_k, critic settings (fetched via `getModeDetail`)
- [x] T040 [US5] Fetch modes on connect: add `getModes()` call in `ConnectionBar`'s health-poll `$effect` when status transitions to `'connected'`; clear on disconnect
- [x] T041 [US5] Wire `ModeSelector` into `QueryPanel.svelte` mode slot; pass `modesState.selected` into `PostQuery` as `mode` field when not null

**Checkpoint**: US5 complete — modes load on connect, selected mode sent with queries, detail visible

---

## Phase 7: User Story 4 — Trigger & Monitor Indexing (Priority: P2)

**Goal**: User triggers full or incremental index, panel shows Running → progress counters → Completed/Failed.

**Independent Test**: Trigger incremental index, verify status updates, verify Completed with counts.

- [x] T042 [P] [US4] Create `apps/krager/src/lib/state/indexJob.svelte.ts`: `export const indexJob = $state({ running, jobId, status, mode, filesScanned, filesProcessed, filesSkippedUnchanged, filesSkippedOther, filesErrored, chunksCreated, vectorsStored, durationSeconds, errors, lastUpdated, error })`; `resetJob()`, `applyStatus(r: IndexResponse)` mapping `files_skipped_unchanged` and `files_skipped_other` from API response
- [x] T043 [P] [US4] Add `triggerIndex(req: IndexRequest): Promise<IndexResponse>` and `getIndexStatus(): Promise<IndexResponse[]>` to `apps/krager/src/lib/services/kragd-client.ts`
- [x] T044 [US4] Create `apps/krager/src/lib/components/domain/IndexPanel.svelte`: mode radio (full/incremental); "Start Indexing" button (disabled while `indexJob.running`); status badge (idle/running/completed/failed); progress counters grid (files scanned, processed, skipped-unchanged, skipped-other, errored; chunks created; vectors stored; duration); error list if `indexJob.errors.length`; "Index Now" triggers `triggerIndex`, sets `indexJob.running = true`
- [x] T045 [US4] Implement index job polling `$effect` in `IndexPanel.svelte`: `setInterval(pollStatus, 2000)` active while `indexJob.running`; calls `getIndexStatus()`, takes first result, calls `indexJob.applyStatus()`; stops when `status !== 'running'`; teardown on component destroy
- [x] T046 [US4] Add transcript entry for index operations: on trigger append `{ type: 'index', request: IndexRequest }`; on completion update with final `IndexResponse`

**Checkpoint**: US4 complete — trigger, watch progress counters update, see Completed state

> **SAR Remediation (A1)**: T074 added for SSE streaming in index progress.

- [x] T074 [US4] Wire SSE streaming into `IndexPanel.svelte`: use `streaming.ts` GET SSE for `/index/stream` as primary progress transport; update counters on `index:progress` (current/total/stage); finalize on `index:complete`; handle `index:error` and `index:idle`; fall back to `GET /index/status` polling if SSE disconnects

---

## Phase 8: User Story 7 — Error Handling & Resilience (Priority: P2)

**Goal**: Every error condition (422, 409, 503, 500, timeout, disconnected) shows a toast and never crashes. Query timeout with retry supported.

**Independent Test**: Trigger each error condition, verify appropriate toast, verify app stays responsive.

- [x] T047 [P] [US7] Harden `kragdFetch` in `apps/krager/src/lib/services/kragd-client.ts`: map HTTP status to human-readable messages using `KRAGD_ERROR_CODES`; network error → "Cannot reach kragd at {host}:{port}"; parse FastAPI `422` `detail` array into a readable string; all errors re-thrown as `KragdError`; catch JSON parse / type-assertion failures and surface raw response body with a "schema mismatch" warning toast (EC-1)
- [x] T048 [P] [US7] Create error dispatch helper `apps/krager/src/lib/utils/errors.ts`: `handleKragdError(e: unknown): void` — inspects `KragdError.status`, calls `addToast(msg, 'error')` with status-specific copy: 422→"Validation error: {detail}", 409→"Already indexing — wait for the current job to finish", 503→"kragd is not ready yet, please wait", 500→"Server error: {detail}", network→"Connection lost"
- [x] T049 [US7] Wrap all service calls in `QueryPanel`, `IndexPanel`, `ConnectionBar`, `SystemStatus`, `ModeSelector` with `try/catch → handleKragdError(e)`
- [x] T050 [US7] Add 60-second query timeout in `QueryPanel.svelte`: `AbortController` with `setTimeout(abort, 60000)`; catch `AbortError` → toast "Query timed out after 60 seconds — please retry"
- [x] T051 [US7] Guard all network actions: if `connection.status !== 'connected'`, show toast "Not connected to kragd" and return early without making a request (applies to QueryPanel Send, IndexPanel trigger, ModeSelector fetch, SystemStatus refresh)

**Checkpoint**: US7 complete — each error scenario produces correct toast, app never crashes, timeout + retry work

> **SAR Remediation (C2, E2)**: T075–T076 added for error handling and schema-mismatch test coverage.

- [x] T075 [P] [US7] Write unit tests for `utils/errors.ts` (TDD): test `handleKragdError` dispatches correct toast for 422/409/503/500/network/timeout status codes; test schema-mismatch fallback path with malformed JSON and unexpected response shapes
- [x] T076 [P] [US7] Write unit tests for `utils/format.ts` (TDD): test `formatDuration`, `formatTimestamp`, `formatFileSize`, `formatUptime` with edge cases (zero, negative, very large values, null-safe)

---

## Phase 9: User Story 6 — Debug Tools (Priority: P3)

**Goal**: Power user can run debug queries (full metadata) and raw Qdrant vector searches from a Debug panel.

**Independent Test**: Submit debug query, verify `DebugMetadata` (LLM used, route, timings, critic scores) visible.

- [x] T052 [P] [US6] Add `postDebugQuery(req: DebugQueryRequest): Promise<DebugQueryResponse>` and `postDebugQdrant(req: QdrantSearchRequest): Promise<QdrantSearchResponse>` to `apps/krager/src/lib/services/kragd-client.ts`
- [x] T053 [US6] Create `apps/krager/src/lib/components/domain/DebugMetadataView.svelte`: renders `DebugMetadata` — LLM used + model, route + auto-routed badge, preset, mode, retrieval_time_ms, generation_time_ms, embedding models, vector spaces, candidate counts (before/after dedup), similarity threshold, per_space_result_counts table, lexicon_terms_injected, critic_scores distribution, chunks pre/post critic
- [x] T054 [US6] Create `apps/krager/src/lib/components/domain/DebugPanel.svelte`: tab bar (Debug Query / Qdrant Search); Debug Query tab: query textarea + mode/top_k/preset fields + Send; Qdrant Search tab: query textarea + vector_space + top_k + score_threshold + filter fields + Search; results rendered via `DebugMetadataView` + `SourceList`
- [x] T055 [US6] Wire debug results to transcript: append `{ type: 'debug', request, response }` on each debug operation; show in `TranscriptView` with debug badge

**Checkpoint**: US6 complete — debug query returns full metadata, Qdrant search returns vector results

---

## Phase 10: User Story 8 — Theme & Visual Polish (Priority: P3)

**Goal**: Dark/light theme follows system preference and switches live. Layout stays clean under window resize. Code blocks in answers syntax-highlighted.

**Independent Test**: Toggle OS dark/light mode, verify app updates. Resize window, verify no overflow. Submit query with code answer, verify highlights.

- [x] T056 [P] [US8] Create `apps/krager/src/lib/utils/highlight.ts`: Shiki lazy `createHighlighter` singleton; themes: `one-dark-pro` (dark) + `github-light` (light); langs: `['python','typescript','javascript','bash','json','rust','sql','markdown','text']`; export `highlight(code, lang, theme): Promise<string>`
- [x] T057 [US8] Create `apps/krager/src/lib/components/ui/CodeBlock.svelte`: accepts `code: string, lang: string`; calls `highlight()` in `$effect` reacting to both `code` and `appTheme.current`; renders `{@html html}` with Shiki output; shows raw code during first render
- [x] T058 [US8] Update `TranscriptView.svelte` answer rendering: detect markdown code fences in `answer` text, extract `lang` and `code`, render via `<CodeBlock>` instead of plain `<pre>` 
- [x] T059 [US8] Refine `apps/krager/src/app.css`: complete responsive layout (min-width 800px baseline, flex/grid panels); typography — `font-family: system-ui` for prose, `font-family: monospace` for code; consistent spacing tokens (`--space-xs` through `--space-xl`); smooth `transition: background-color 150ms, color 150ms` on theme switch
- [x] T060 [US8] Update `+layout.svelte` `$effect` to apply `data-theme` to `document.documentElement` (not just container) so CSS `:root[data-theme]` selectors apply globally; verify theme switches on OS preference change

**Checkpoint**: US8 complete — dark/light theme live-switches, code answers highlighted, layout stable under resize

---

## Phase 11: Polish & Cross-cutting

**Purpose**: Remaining FRs (FR-014 lexicon refresh), Windows build, pre-commit setup, final validation.

- [x] T061 Add `refreshLexicon(): Promise<LexiconRefreshResponse>` to `apps/krager/src/lib/services/kragd-client.ts` (`POST /lexicon/refresh`) and add "Refresh Lexicon" button in `SystemStatus.svelte` showing returned `entries` count in success toast
- [x] T062 Configure pre-commit workflow for `apps/krager/` — add to root `Makefile` or pre-commit config: `cd apps/krager && pnpm svelte-check && pnpm lint && pnpm test`; Python pre-commit unchanged
- [x] T063 [P] Windows cross-compile from Linux: install `cargo-xwin` + `nsis`; `rustup target add x86_64-pc-windows-msvc`; run `pnpm tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc`; document NSIS output path and cache location (`~/.cache/xwin`) in `apps/krager/README.md`
- [x] T064 [P] Manual Windows verification checklist: transfer `*_x64-setup.exe` to Windows 10/11; install; launch; connect to kragd; submit query; trigger index; toggle dark/light theme; document results per `specs/013-krager/quickstart.md` verification steps
- [x] T065 Final pre-commit validation: `uv run ruff format . && uv run ruff check --fix . && uv run pytest` (Python); `cd apps/krager && pnpm svelte-check && pnpm lint && pnpm test` (TypeScript); all must pass
- [x] T066 [P] Commit and push feature branch `013-krager`

> **SAR Remediation (E1)**: T077 added for performance measurement (SC-003).

- [x] T077 Add query round-trip timing instrumentation: record client-side overhead per request in `kragdFetch` (timestamp before request → timestamp after response parsed); log overhead to dev console; if measured overhead >500ms, flag in console warning and discuss measured value with user to decide if optimization is needed (SC-003)

**Checkpoint**: All 18 FRs satisfied, 8 SCs verifiable, Windows binary delivered for user testing

---

## Phase 12: Manual Testing Fixes

**Purpose**: Address bugs and UX issues found during Windows manual testing (see `specs/krager-manual-test-observations.md`).

- [x] T078 Add 15s connection timeout via AbortController to `getHealth()` in `apps/krager/src/lib/services/kragd-client.ts` — prevents infinite connection loop on unreachable hosts (especially localhost)
- [x] T079 Fix host input squished by error message — add `min-width: 120px` to `.input-group`, change `.error-msg` to `flex: 0 1 auto` with `overflow: hidden; text-overflow: ellipsis; max-width: 350px` and `title` tooltip in `ConnectionBar.svelte`
- [x] T080 Reverse transcript display order (newest on top) — add `reversedEntries` derived state, change `scrollToBottom` to `scrollToTop`, update `{#each}` in `TranscriptView.svelte`

**Checkpoint**: All manual testing blockers resolved, ready for PR

---

## Dependencies

```
Phase 1 (Setup)
    └── Phase 2 (Foundation)
            ├── Phase 3 (US1) ──> independent deliverable
            ├── Phase 4 (US2) ──> independent deliverable (needs connection state)
            ├── Phase 5 (US3) ──> MVP complete with US1+US2  (needs transcript state)
            │       └── Phase 6 (US5) ──> enhances US3 (adds mode into query)
            ├── Phase 7 (US4) ──> independent of US3/US5 (needs index state)
            ├── Phase 8 (US7) ──> wraps US2+US3+US4+US5 (error handling cross-cut)
            ├── Phase 9 (US6) ──> independent (debug panel, no deps on US4/US5)
            └── Phase 10 (US8) ──> independent (CSS + Shiki, no business logic deps)
                    └── Phase 11 (Polish)
```

**Phase ordering rationale**:
- US5 (Modes) inserted before US4 (Indexing) because modes enhance the US3 query flow and make the MVP more complete sooner
- US7 (Error Handling) treated as a hardening pass after functional stories are in place, not as its own panel
- US6 (Debug) and US8 (Polish) are P3 and do not block any other story

---

## Parallel Execution Examples

### Phase 4 (US2): Start all in parallel after T009/T010 complete
```
T025 connection.svelte.ts   ──┐
T026 kragd-client health    ──┤──> T027 ConnectionBar ──> T028 polling $effect
                               └──> T029 SystemStatus
                                    T030 wire into page
```

### Phase 5 (US3): Start T031+T032 in parallel after T025 complete
```
T031 transcript.svelte.ts   ──┐
T032 postQuery()             ──┤──> T033 QueryPanel ──> T036 wire page
                               └──> T034 SourceList ──> T035 TranscriptView
```

### Phase 6 (US5): Start T037+T038 in parallel
```
T037 modes.svelte.ts   ──┐
T038 getModes()        ──┴──> T039 ModeSelector ──> T040 fetch on connect ──> T041 wire into QueryPanel
```

### Phase 7 (US4): Start T042+T043 in parallel
```
T042 indexJob.svelte.ts   ──┐
T043 triggerIndex()        ──┴──> T044 IndexPanel ──> T045 polling $effect ──> T046 transcript
```

---

## Implementation Strategy

**MVP scope** (deliver US1 + US2 + US3 first = Phases 1–5):
- After T036, a user can: connect to kragd, see system status, submit queries, read answers with sources
- T071–T073 extend MVP with SSE streaming and retrieve-only mode
- All other phases are independently additive and do not require changes to the MVP

**Incremental delivery order**:
1. Phases 1–3: Working dev environment + UI primitives + biome lint
2. Phase 4: Connection + health polling (foundation for everything else)
3. Phase 5: Query + transcript + SSE streaming + retrieve-only (core value proposition)
4. Phase 6: Mode selection (enhances queries)
5. Phase 7: Indexing + SSE index progress (second most common operation)
6. Phase 8: Error hardening + schema-mismatch fallback (robustness pass)
7. Phase 9: Debug tools (power user features)
8. Phase 10: Visual polish (theme + syntax highlight)
9. Phase 11: Windows build + pre-commit + performance measurement + final validation

**Format validation**: All 77 tasks follow the required checklist format — `- [ ] T### [P?] [US?] Description with file path`

---

## Task Count Summary

| Phase | Story | Tasks | Parallelizable |
|-------|-------|-------|----------------|
| 1: Setup | — | T001–T008, T067 (9) | T003–T008, T067 (7) |
| 2: Foundation | — | T009–T018, T068–T070 (13) | T010–T015, T068–T070 (9) |
| 3: US1 | P1 | T019–T024 (6) | 0 |
| 4: US2 | P1 | T025–T030 (6) | T025–T026 (2) |
| 5: US3 | P1 | T031–T036, T071–T073 (9) | T031–T032, T072 (3) |
| 6: US5 | P2 | T037–T041 (5) | T037–T038 (2) |
| 7: US4 | P2 | T042–T046, T074 (6) | T042–T043 (2) |
| 8: US7 | P2 | T047–T051, T075–T076 (7) | T047–T048, T075–T076 (4) |
| 9: US6 | P3 | T052–T055 (4) | T052 (1) |
| 10: US8 | P3 | T056–T060 (5) | T056 (1) |
| 11: Polish | — | T061–T066, T077 (7) | T063–T064, T066 (3) |
| 12: Testing Fixes | — | T078–T080 (3) | 0 |
| **Total** | | **80 tasks** | **34 parallelizable** |
