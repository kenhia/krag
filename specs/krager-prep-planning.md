# krager — Prep Planning

Sprint planning for krager, the Tauri + Svelte remote desktop client for kragd.

---

## Decision: Monorepo at `apps/krager/`

**Rationale:** See [krager-prep-research.md §3](krager-prep-research.md) for the
full comparison. The key factors favoring monorepo:

- Atomic commits across API + client changes
- No CI to break (no workflows exist today)
- Build systems are completely orthogonal (`uv`/`hatchling` vs `cargo`/`pnpm`)
- Specs, docs, and tasks stay together
- Existing multi-project precedent in `examples/`

**Directory:** `apps/krager/` — establishes `apps/` convention for UI clients,
parallel to `src/` (core), `examples/` (plugins), and `specs/` (planning).

---

## Pre-Sprint Prep Tasks

These tasks clean up kragd's API surface before building the client.
They can be their own micro-sprint or the first phase of the krager sprint.

### P1 — API Normalization

| # | Task | Files | Priority |
|---|------|-------|----------|
| 1 | Normalize `/index/status` → always return `list[IndexResponse]` | `src/kragd/routers/index.py`, `src/kragd/schemas.py` | Must |
| 2 | Move `LexiconRefreshResponse` into `schemas.py` | `src/kragd/routers/lexicon.py`, `src/kragd/schemas.py` | Must |
| 3 | Move `ModeListResponse`, `ModeDetailResponse` into `schemas.py` | `src/kragd/routers/modes.py`, `src/kragd/schemas.py` | Must |
| 4 | Add CORS middleware (configurable origins, default `*` for dev) | `src/kragd/app.py` | Must |
| 5 | Review OpenAPI spec: tags, descriptions, examples | All routers | Should |
| 6 | Add `--json` to `krag health` | `src/krag_cli/commands/system.py` | Should |
| 7 | Add `--json` to `krag modes list` / `krag modes show` | `src/krag_cli/commands/modes.py` | Should |
| 8 | Add `--json` to `krag lexicon refresh` | `src/krag_cli/commands/lexicon.py` | Should |
| 9 | Add `--json` to `krag shutdown` | `src/krag_cli/commands/lifecycle.py` | Should |

### P2 — Tests for API Changes

| # | Task | Files |
|---|------|-------|
| 10 | Test: `/index/status` always returns list | `tests/test_kragd/` |
| 11 | Test: schema imports from `schemas.py` (no router imports) | `tests/test_kragd/` |
| 12 | Test: CORS headers present on responses | `tests/test_kragd/` |
| 13 | Tests: `--json` output for all 5 CLI commands | `tests/test_krag_cli/` |

---

## Sprint: krager v0.1

### Phase 1 — Scaffold (Setup)

| # | Task | Notes |
|---|------|-------|
| T01 | Create `apps/krager/` directory structure | See research doc §4 |
| T02 | Initialize Tauri v2 project (`pnpm create tauri-app`) | In `apps/krager/` |
| T03 | Configure `tauri.conf.json` — window title, size, dev URL | Title: "krager" |
| T04 | Configure Vite + Svelte for TypeScript | `vite.config.ts`, `svelte.config.js` |
| T05 | Add `.nvmrc` (Node 20) and `rust-toolchain.toml` in `apps/krager/` | Scoped to subdir |
| T06 | Update root `.gitignore` — `**/target/`, `**/node_modules/`, etc. | See research doc §3 |
| T07 | Root README update — new "krager" section with setup instructions | Brief, links to krager README |
| T08 | Create `apps/krager/README.md` with dev setup | Prerequisites, install, run |

### Phase 2 — API Client Layer

| # | Task | Notes |
|---|------|-------|
| T09 | Create `src/lib/types.ts` — TypeScript types mirroring kragd schemas | Mirror `schemas.py` |
| T10 | Create `src/lib/api.ts` — HTTP client class wrapping all 12 endpoints | `fetch()` based, configurable base URL |
| T11 | Create `src/lib/errors.ts` — error types matching kragd exception map | 422, 409, 503, 500 |
| T12 | Unit tests for API client (mock fetch) | Vitest |

### Phase 3 — Svelte Stores

| # | Task | Notes |
|---|------|-------|
| T13 | `connectionStore` — host, port, status (connected/disconnected/error) | Health polling every 5 s |
| T14 | `modesStore` — available modes from `GET /modes`, selected mode | Auto-populated on connect |
| T15 | `transcriptStore` — array of `{timestamp, type, request, response, debug?}` | Append-only log of all interactions |
| T16 | `indexStore` — current index job status, polling state | Polls `/index/status` when active |
| T17 | `systemStore` — service status (from `GET /status`) | Periodically refreshed |

### Phase 4 — Core UI Components

| # | Task | Notes |
|---|------|-------|
| T18 | `App.svelte` — root layout with sidebar + main panel | CSS grid or flexbox |
| T19 | `ConnectionBar.svelte` — host:port input, status indicator, connect/disconnect | Top bar |
| T20 | `ModeSelector.svelte` — dropdown populated from `modesStore` | Shows mode description |
| T21 | `QueryPanel.svelte` — text input, submit button, loading state | Sends `POST /query` or `/retrieve` |
| T22 | `TranscriptViewer.svelte` — scrollable list of interactions | Shows request + response + timestamp |
| T23 | `TranscriptEntry.svelte` — single interaction display | Markdown rendering for answers |

### Phase 5 — System Commands & Tools

| # | Task | Notes |
|---|------|-------|
| T24 | `SystemPanel.svelte` — status display (version, uptime, VRAM, collections) | Renders `ServiceStatus` |
| T25 | `IndexPanel.svelte` — trigger indexing, show progress, poll status | `POST /index` + polling |
| T26 | `DebugPanel.svelte` — raw debug query, qdrant search | For power users |
| T27 | `LexiconRefresh.svelte` — button to trigger lexicon refresh | Simple action |

### Phase 6 — Polish & Ship

| # | Task | Notes |
|---|------|-------|
| T28 | Error handling — toast/notification system for API errors | 422, 409, 503 gracefully shown |
| T29 | Theme — dark mode, consistent color scheme | System preference detection |
| T30 | App icon and metadata | Tauri build config |
| T31 | Build verification — `pnpm tauri build` produces working binary | Linux at minimum |
| T32 | End-to-end test — launch kragd, open krager, run a query | Manual or Playwright |
| T33 | Update root README with krager screenshot/description | After UI exists |

---

## TypeScript Type Map

Key types krager needs, derived from kragd's Pydantic schemas:

```typescript
// Connection
interface KragdConfig {
  host: string;    // default: "127.0.0.1"
  port: number;    // default: 11435
}

// Query
interface QueryRequest {
  query: string;
  top_k?: number;
  preset?: string;
  llm?: string;
  mode?: string;
  include_debug?: boolean;
}

interface QueryResponse {
  answer: string;
  sources: SourceChunk[];
  debug?: DebugMetadata;
}

interface SourceChunk {
  content: string;
  source: string;
  score: number;
  collection?: string;
  metadata?: Record<string, unknown>;
}

// Modes
interface ModeListResponse {
  modes: ModeSummary[];
}

interface ModeDetailResponse {
  name: string;
  description: string;
  collections: CollectionConfig[];
  weights: Record<string, number>;
  // ... full mode config
}

// Index
interface IndexRequest {
  mode: "full" | "incremental";
  directories?: string[];
  file_types?: string[];
  exclude_patterns?: string[];
  dry_run?: boolean;
}

interface IndexResponse {
  job_id: string;
  status: string;
  files_scanned: number;
  files_processed: number;
  chunks_created: number;
  vectors_stored: number;
  duration_seconds: number;
  collections: string[];
  errors: string[];
}

// System
interface HealthResponse {
  status: string;
  version: string;
}

interface ServiceStatus {
  version: string;
  uptime_seconds: number;
  llm: LlmInfo;
  embedding_models: EmbeddingInfo[];
  vector_store: VectorStoreInfo;
  collections: CollectionInfo[];
  modes: string[];
  vram?: VramInfo;
}

// Transcript (krager-only, not from kragd)
interface TranscriptEntry {
  id: string;
  timestamp: Date;
  type: "query" | "retrieve" | "index" | "debug" | "system";
  request: unknown;
  response: unknown;
  debug?: DebugMetadata;
  error?: string;
  duration_ms: number;
}
```

---

## Widget Architecture

```
┌───────────────────────────────────────────────────────┐
│  ConnectionBar  [host:port]  [●Connected]  [Settings] │
├────────────────┬──────────────────────────────────────┤
│                │                                      │
│  Sidebar       │  Main Panel                          │
│                │                                      │
│  [Mode ▾]      │  ┌─ QueryPanel ──────────────────┐   │
│                │  │  [Enter query...]  [Send]      │   │
│  System        │  └────────────────────────────────┘   │
│  ├ Status      │                                      │
│  ├ Index       │  ┌─ TranscriptViewer ────────────┐   │
│  └ Lexicon     │  │                               │   │
│                │  │  [12:03] query "what is..."    │   │
│  Debug         │  │  → Answer: ...                 │   │
│  ├ Query       │  │  → Sources: [3 chunks]         │   │
│  └ Qdrant      │  │                               │   │
│                │  │  [12:01] index incremental     │   │
│                │  │  → 42 files, 128 chunks        │   │
│                │  │                               │   │
│                │  └────────────────────────────────┘   │
└────────────────┴──────────────────────────────────────┘
```

Each panel is a standalone Svelte component backed by its own store.
Panels are composable — the sidebar can be collapsed, panels can be
reorganized or hidden via settings.

---

## Open Questions

1. **CORS**: Does Tauri v2's webview send an `Origin` header that triggers
   CORS? Needs testing. If so, add `CORSMiddleware` to kragd. If not,
   skip it and avoid the security surface.

2. **Persistent transcript**: Should transcript survive app restarts?
   Options: (a) in-memory only (simplest), (b) localStorage, (c) SQLite
   via Tauri plugin. Start with (a), add (b) if users request.

3. **Multi-server**: Support connecting to multiple kragd instances
   simultaneously? Probably not for v0.1 — single connection is sufficient.

4. **Auto-start kragd**: Should krager be able to launch kragd if it's
   not running? Via Tauri sidecar or shell command. Deferred to v0.2+.

5. **Theme**: Match system dark/light preference or standalone toggle?
   Start with system preference + manual override.
