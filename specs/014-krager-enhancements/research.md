# Research: Krager Enhancements

**Feature**: 014-krager-enhancements
**Date**: 2026-03-03

## R1: Configuration Persistence — Tauri Store Plugin

### Decision: Use `@tauri-apps/plugin-store` for local config persistence

### Rationale
The Tauri Store plugin provides batteries-included JSON key-value persistence with built-in debounced auto-save, change listeners, and per-key operations. It stores files in the OS-native app data directory — no custom file handling needed.

### Alternatives Considered
- **`@tauri-apps/plugin-fs` + manual JSON**: Full control over format (TOML, etc.) and schema validation, but requires implementing debounce, change listeners, and error recovery manually. Rejected because the Store plugin handles all of this out of the box.
- **`localStorage`/`sessionStorage`**: Not available in Tauri (no browser context). N/A.
- **Rust-side config (serde + TOML)**: Would require Tauri commands for every read/write. Rejected — unnecessary complexity for simple key-value preferences.

### Implementation Details

**Installation**:
```bash
pnpm add @tauri-apps/plugin-store
# Cargo.toml: tauri-plugin-store = "2"
# Rust: .plugin(tauri_plugin_store::Builder::default().build())
```

**File locations** (automatic):
| Platform | Path |
|----------|------|
| Linux | `~/.local/share/<bundle-id>/settings.json` |
| Windows | `%APPDATA%/<bundle-id>/settings.json` |
| macOS | `~/Library/Application Support/<bundle-id>/settings.json` |

**Key behaviors**:
- `autoSave: 300` — 300ms debounce satisfies FR-004 (≤1 write/sec)
- `defaults` option provides fallback values (FR-003)
- `load()` throws on corrupt file — use try/catch with `createNew: true` fallback
- `onChange()` listener keeps reactive state in sync
- All methods are async — write to `$state` synchronously for instant UI, fire-and-forget the async persist

**Capability**: `store:default` in capabilities file.

**Error recovery pattern**:
```typescript
try {
  store = await load('settings.json', { autoSave: 300, defaults: DEFAULTS });
} catch {
  store = await load('settings.json', { autoSave: 300, defaults: DEFAULTS, createNew: true });
}
```

---

## R2: Window Opacity / Transparency

### Decision: Use CSS `opacity` on root element (not native Tauri transparency)

### Rationale
Tauri v2 does not have a direct `setOpacity()` or `setAlpha()` window method. The available alternatives (`setBackgroundColor` with alpha, `setEffects`) have significant platform limitations:
- `setBackgroundColor` alpha is ignored on Windows
- `setEffects` (blur/acrylic/mica) is unsupported on Linux
- Both require `transparent: true` in window config which can cause rendering issues
- macOS requires `macOSPrivateApi: true` for transparency

CSS `opacity` on the root element is universally supported, simple to implement, and doesn't require any Tauri configuration changes.

### Alternatives Considered
- **Tauri `setBackgroundColor` with alpha**: Cross-platform inconsistent (alpha ignored on Windows). Rejected.
- **Tauri `setEffects`**: Platform-native blur/acrylic. Unsupported on Linux (primary dev platform). Rejected.
- **Tauri `transparent: true` + CSS backdrop**: Requires OS-level compositing support. Too fragile across platforms. Rejected.

### Implementation Details
- CSS `opacity` on `<html>` or app root container
- Range: 0.3 (30%) to 1.0 (100%), clamped
- Applied via reactive `$effect` watching the settings state
- Persisted in config store as `display.opacity` (number)
- Note: CSS `opacity` makes the entire window semi-transparent (content + background), not just the background. This is acceptable for the overlay use case (seeing through to reference material).

---

## R3: Query Controls — API Parameter Support

### Decision: Expose top-k, preset, debug, and sources controls; "sources" is client-side display filtering

### Rationale
The kragd API already supports `top_k`, `preset`, and `include_debug` in `QueryRequest`. The `no_sources` option does not exist as an API parameter — it should be implemented as client-side display filtering (hide source chunks from the answer view while retaining them in the transcript).

### Existing API Support
| Control | API Field | Status |
|---------|-----------|--------|
| top-k | `QueryRequest.top_k` | ✅ Supported |
| preset | `QueryRequest.preset` | ✅ Supported |
| debug | `QueryRequest.include_debug` | ✅ Supported |
| mode | `QueryRequest.mode` | ✅ Already exposed via ModeSelector |
| sources | — | ❌ No API field; client-side display toggle |

### Preset List
No `/presets` endpoint exists on kragd. Valid presets are hardcoded on the server:
- `strict` — Concise, source-grounded answers only
- `balanced` — Detailed answers with numbered citations (default)
- `verbose` — Exploratory answers with full context
- `code` — Code-focused answers with snippets, symbols, and file references

**Approach**: Hardcode the preset list in krager as a constant. Document that adding new presets on the server requires updating the krager constant. Future enhancement: add a `/presets` endpoint to kragd.

---

## R4: Critic Controls — Per-Request Override

### Decision: Expose critic toggle and cut-off score as client-side overrides; pass via `include_debug` + filter results client-side

### Rationale
The kragd `QueryRequest` has no `critic_enabled` or `critic_threshold` fields. The critic is currently server-side only, controlled by mode configuration (`mode_config.critic_enabled`, `mode_config.critic_threshold`).

However, `DebugMetadata` already returns `critic_scores`, `chunks_pre_critic`, and `chunks_post_critic` — meaning the client can see critic results when `include_debug: true`.

### Approach

**Phase 1 (this feature)**: Expose critic as a **display-layer feature**:
1. The critic toggle + cut-off score control the display of results, not the API request
2. When enabled, automatically set `include_debug: true` to get critic metadata
3. Use `DebugMetadata.critic_scores` to flag/filter answers below the cut-off threshold
4. The server still runs the critic based on mode config — krager just surfaces the results

**Phase 2 (future, requires kragd API change)**: Add `critic_enabled` and `critic_threshold` fields to `QueryRequest` on the server to allow per-request overrides.

### DebugMetadata Critic Fields
```typescript
interface DebugMetadata {
  critic_scores: number[];       // Per-chunk critic scores
  chunks_pre_critic: number;     // Chunks before critic filtering
  chunks_post_critic: number;    // Chunks after critic filtering
  // ... other fields
}
```

---

## R5: Transcript Redesign — Two-View Architecture

### Decision: Split query page into "current answer" view and "transcript history" panel

### Rationale
Users report that source chunks dominate the display, making it hard to find the actual answer. The solution separates the two concerns:
1. **Query page** (active panel) — shows the latest answer + compact source references (file name, score) + debug info if enabled. No raw chunk text.
2. **Transcript panel** (sidebar nav entry) — shows full history with expandable chunk content per source.

### Implementation Details
- **New component: `QueryAnswer.svelte`** — renders the latest transcript entry's answer with a compact `SourceReference` list (file path + relevance score only). Chunks are omitted.
- **Modified `TranscriptView.svelte`** — adds expand/collapse for each source entry. Chunk text is hidden by default, revealed on click.
- **Sidebar change**: Add a "Transcript" entry (📝) between Query and Index. Query panel shows `QueryPanel` + `QueryAnswer` (no more `TranscriptView`). Transcript panel shows `TranscriptView`.
- **`TranscriptEntry` extension**: No data model change needed — existing `sources: SourceChunk[]` already has all fields. The display difference is in components.

---

## R6: Index Path Selection — API Dependency

### Decision: Defer to future sprint; kragd `/status` does not expose configured source directories

### Rationale
The kragd `ServiceStatus` response does not include the list of configured source directories (`directory_paths` from KragConfig). The `IndexRequest.directories` field exists and accepts override paths, but there is no way for krager to discover what paths are configured on the server.

### Options for Future
1. **Add a `/config/paths` endpoint to kragd** — returns the configured `directory_paths` list
2. **Extend `ServiceStatus`** — add a `source_directories: list[str]` field
3. **Manual entry in krager settings** — user enters paths manually (poor UX)

**Recommendation**: Option 2 (extend ServiceStatus) is the simplest. File a kragd enhancement to add `source_directories` to the status response.

### Current Plan
For this sprint, the index panel remains as-is (Full/Incremental with all configured paths). The UI for path selection will be built when the API supports it — mark as "API pending" in the settings page if shown.

---

## R7: Embedding Model Display

### Decision: Parse `ServiceStatus.embedding_models` list and display all entries

### Rationale
The `ServiceStatus.embedding_models` field is already a `list[str]`. The current `SystemStatus.svelte` only displays the first entry. Fix is trivial — iterate the list instead of showing `[0]`.

### Server Behavior
- `ServiceStatus.embedding_models` is populated as `[self.config.embedding_model]` — currently always a single-element list from config
- `DebugMetadata.embedding_models_used` can return multiple models (one per vector space) from the embedding orchestrator
- Future: if kragd adds multi-model config support, the status field will naturally return multiple entries

### Implementation
Change `SystemStatus.svelte` from showing a single model string to iterating `embedding_models` array. No API change needed.

---

## R8: Settings Page — Section Organization

### Decision: Four settings sections matching the spec (Connection, Query, Critic, Display)

### Rationale
Centralizes all configurable options in one discoverable location. Sections map to the persisted config structure for consistency.

### Section Layout
| Section | Settings |
|---------|----------|
| **Connection** | Default host, default port |
| **Query** | Default top-k, default preset, show sources (on/off), include debug (on/off) |
| **Critic** | Enable/disable, cut-off score |
| **Display** | Window opacity, theme preference |

### Interaction Pattern
- All changes apply immediately (no save button) — write to reactive `$state`, async persist via store
- Settings page is a new sidebar entry (⚙ icon, between System and Debug)
- Non-default values shown with a "reset to default" affordance

---

## R9: Svelte 5 Runes Integration Pattern

### Decision: Follow existing state module pattern — `$state` object + pure functions + async config bridge

### Rationale
The existing codebase uses a consistent pattern: export a `$state` reactive object and pure functions that mutate it. The config store adds an async persistence layer that bridges between the sync reactive state and async Tauri Store.

### Pattern
```
┌─────────────┐     sync      ┌──────────────┐     async      ┌─────────────┐
│  Component   │ ──────────── │  State Module │ ──────────────│ Config Store │
│  ($derived)  │   $state     │  (.svelte.ts) │  store.set()  │  (Tauri)     │
└─────────────┘               └──────────────┘               └─────────────┘
                                    ↑                              │
                                    └──────── store.onChange() ────┘
```

1. Components read from `$state` (synchronous, reactive)
2. State mutation functions update `$state` immediately (instant UI)
3. State mutation functions also call `configStore.set(key, value)` (async, debounced)
4. On startup, `configStore.load()` hydrates all state modules from persisted values
5. `store.onChange()` listener keeps state in sync if file is externally modified
