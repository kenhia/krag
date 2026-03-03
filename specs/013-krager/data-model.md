# Data Model: krager — Tauri Desktop Client for kragd

**Phase**: 1 | **Feature**: 013-krager | **Date**: 2026-03-01

All entities live in Svelte 5 `$state` reactive objects in `.svelte.ts` module files — no persistence layer.

---

## Entities

### 1. Connection

**Module**: `src/lib/state/connection.svelte.ts`  
**Purpose**: Represents the kragd server connection state and health polling.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | `string` | `'localhost'` | kragd hostname or IP address |
| `port` | `number` | `11435` | kragd port |
| `status` | `ConnectionStatus` | `'disconnected'` | Current connection state |
| `lastCheck` | `Date \| null` | `null` | Timestamp of last health poll |
| `errorMsg` | `string \| null` | `null` | Error detail message (when status='error') |
| `version` | `string \| null` | `null` | kragd version from health response |

**Derived**: `baseUrl` = `http://${host}:${port}`

**Type**:
```typescript
type ConnectionStatus = 'connected' | 'disconnected' | 'error';
```

**State transitions**:
- `disconnected` → `connected`: health poll returns 200 with `{ status: 'healthy' | 'degraded' }`
- `connected` → `disconnected`: health poll fails (network error or non-2xx)
- `connected` → `error`: health poll returns a degraded/unexpected state
- Any → `disconnected`: user manually changes host/port

---

### 2. Transcript Entry

**Module**: `src/lib/state/transcript.svelte.ts`  
**Purpose**: Immutable log record for every user interaction. Appended only; read for display.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` | ✅ | UUID-style unique identifier |
| `timestamp` | `Date` | ✅ | When the interaction occurred |
| `type` | `TranscriptType` | ✅ | Category of interaction |
| `request` | `unknown` | ✅ | Serialized request payload |
| `response` | `unknown \| null` | ✅ | Serialized response (null while loading) |
| `durationMs` | `number \| null` | — | Round-trip time in milliseconds |
| `error` | `string \| null` | — | Error message if interaction failed |
| `loading` | `boolean` | ✅ | True while awaiting response |

**Type**:
```typescript
type TranscriptType = 'query' | 'retrieve' | 'index' | 'debug';
```

**Transcript state**:
```typescript
// src/lib/state/transcript.svelte.ts
export const transcript = $state({
  entries: [] as TranscriptEntry[],
  maxEntries: 500,        // configurable cap; drop oldest when exceeded
});

export function addEntry(entry: TranscriptEntry): void
export function updateEntry(id: string, patch: Partial<TranscriptEntry>): void
export function clearTranscript(): void
```

**Validation rules**:
- Entries are append-only; existing entries are only updated (never removed) except when trimming at `maxEntries`.
- When `entries.length > maxEntries`, shift the oldest from the front.

---

### 3. Mode

**Module**: `src/lib/state/modes.svelte.ts`  
**Purpose**: Available retrieval modes fetched from `GET /modes`. Drives the mode selector.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Unique mode identifier |
| `description` | `string` | Human-readable mode description |
| `collections` | `string[]` | Target collection names |
| `llmSlot` | `'text' \| 'code'` | Which LLM slot is used |
| `preset` | `string` | Prompt preset name |

**Modes state**:
```typescript
// src/lib/state/modes.svelte.ts
export const modesState = $state({
  available: [] as ModeInfo[],
  selected: null as string | null,   // mode name or null (uses kragd default)
  loading: false,
  error: null as string | null,
});
```

**`ModeInfo`** mirrors `kragd/schemas.py::ModeInfo`. Full detail (`ModeDetailResponse`) is fetched on demand from `GET /modes/{name}`.

---

### 4. Index Job

**Module**: `src/lib/state/indexJob.svelte.ts`  
**Purpose**: Tracks the state of an in-progress or completed indexing operation. Populated by `POST /index` and updated via `GET /index/status` polling.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `running` | `boolean` | `false` | True while job is active |
| `jobId` | `string \| null` | `null` | Identifier from `POST /index` response |
| `status` | `IndexStatus \| null` | `null` | `running` / `completed` / `failed` / `none` |
| `mode` | `'full' \| 'incremental' \| null` | `null` | Indexing mode |
| `filesScanned` | `number` | `0` | Files discovered |
| `filesProcessed` | `number` | `0` | Files successfully indexed |
| `filesSkippedUnchanged` | `number` | `0` | Files skipped (unchanged since last index) |
| `filesSkippedOther` | `number` | `0` | Files skipped (other reasons: excluded, filtered) |
| `filesErrored` | `number` | `0` | Files with errors |
| `chunksCreated` | `number` | `0` | New chunks generated |
| `vectorsStored` | `number` | `0` | Vectors written |
| `durationSeconds` | `number \| null` | `null` | Elapsed seconds |
| `errors` | `IndexingFileError[]` | `[]` | Per-file error details |
| `lastUpdated` | `Date \| null` | `null` | Last poll timestamp |
| `error` | `string \| null` | `null` | Top-level error (e.g. 409 conflict) |

**Type**:
```typescript
type IndexStatus = 'running' | 'completed' | 'failed' | 'none';
```

**State transitions**:
- `idle` (running=false, status=null) → `running` (running=true): on trigger via `POST /index`
- `running` → `completed` or `failed`: on poll result from `GET /index/status`
- `running` → `error`: if 409 conflict returned on trigger

**Polling**: `$effect` in `IndexPanel` component, active while `indexJob.running === true`, polls every 2 seconds via `GET /index/status`.

---

### 5. System Status

**Module**: In-memory fetch result, not persisted in a separate state module. Fetched on demand (System panel) and stored as a local `$state` inside the SystemStatus component, or as part of a lightweight `systemState.svelte.ts`.

| Field | Type | Description |
|-------|------|-------------|
| `version` | `string` | krag version |
| `uptimeSeconds` | `number` | Seconds since service start |
| `llm` | `Record<string, LLMSlotStatus>` | Per-slot LLM status (text/code) |
| `embeddingModels` | `string[]` | Loaded embedding model names |
| `vectorStore` | `VectorStoreStatus` | Collection stats |
| `collections` | `Record<string, CollectionStatus>` | Per-collection stats |
| `modes` | `ModeInfo[]` | Registered modes |
| `lexiconLoaded` | `boolean` | Domain lexicon active |
| `lexiconEntryCount` | `number` | Lexicon term count |
| `vram` | `VRAMStatus \| null` | GPU memory (null if no CUDA) |

**`ServiceStatus`** mirrors `kragd/schemas.py::ServiceStatus` exactly.

---

## Entity Relationships

```
Connection ──── drives ────► kragd-client.ts (all HTTP calls)
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              TranscriptEntry   IndexJob       ModeInfo[]
              (append-only)    (poll-driven)  (fetch on connect)
                                   │
                              SystemStatus
                              (fetch on demand)
```

---

## State Initialization Sequence

1. App launches → `connection.status = 'disconnected'`
2. User enters host:port → trigger health poll
3. Health poll succeeds → `connection.status = 'connected'`
4. On connect → fetch `GET /modes` → populate `modesState.available`
5. User selects mode → `modesState.selected = name`
6. User submits query → `POST /query` → append `TranscriptEntry` with `loading=true` → update with response
7. User triggers index → `POST /index` → `indexJob.running = true` → poll starts → update until done
