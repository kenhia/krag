# Data Model: Krager Enhancements

**Feature**: 014-krager-enhancements
**Date**: 2026-03-03

## Entities

### UserConfig

The root configuration object persisted to the Tauri Store. Represents all user preferences that survive app restarts.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `connection.host` | string | `"localhost"` | Last successful connection host |
| `connection.port` | number | `8742` | Last successful connection port |
| `query.top_k` | number \| null | `null` | Default top-k (null = server default) |
| `query.preset` | string \| null | `null` | Default preset name (null = server default) |
| `query.include_debug` | boolean | `false` | Include debug metadata in query responses |
| `query.show_sources` | boolean | `true` | Display source chunks in answer view |
| `critic.enabled` | boolean | `false` | Enable critic score display |
| `critic.cut_off` | number | `0.5` | Critic score threshold (0.0–1.0) |
| `display.opacity` | number | `1.0` | Window opacity (0.3–1.0) |
| `display.theme` | 'light' \| 'dark' \| null | `null` | Theme preference override (null = OS default) |

**Storage**: JSON file at `$APPDATA/<bundle-id>/settings.json` via Tauri Store plugin.

**Validation rules**:
- `connection.port`: integer, 1–65535
- `query.top_k`: null or integer, 1–100
- `query.preset`: null or one of `["strict", "balanced", "verbose", "code"]`
- `critic.cut_off`: number, 0.0–1.0
- `display.opacity`: number, 0.3–1.0
- Invalid values fall back to their defaults silently

**State transitions**: None — this is a value object that is read on startup and written on change. No lifecycle states.

---

### QueryParameters

Runtime state for current query configuration. Derived from UserConfig defaults but can be overridden per-session.

| Field | Type | Default (from config) | Description |
|-------|------|-----------------------|-------------|
| `top_k` | number \| null | `config.query.top_k` | Top-k for current session |
| `preset` | string \| null | `config.query.preset` | Preset for current session |
| `include_debug` | boolean | `config.query.include_debug` | Debug mode for current session |
| `show_sources` | boolean | `config.query.show_sources` | Source display for current session |
| `retrieve_only` | boolean | `false` | Retrieve without synthesis (existing) |

**Relationship**: Initialized from `UserConfig.query.*` on startup. Changes to defaults via the settings page are written back to UserConfig (and thus persisted) and propagated to query state immediately. Per-query overrides in the query panel are session-only and do NOT persist to config.

---

### CriticConfig

Runtime state for critic display configuration.

| Field | Type | Default (from config) | Description |
|-------|------|-----------------------|-------------|
| `enabled` | boolean | `config.critic.enabled` | Whether to show critic scores |
| `cut_off` | number | `config.critic.cut_off` | Threshold for flagging low-quality answers |

**Relationship**: When `enabled` is true, the query automatically includes `include_debug: true` to fetch critic metadata from the server. The display layer uses `DebugMetadata.critic_scores` to flag results below `cut_off`.

---

### TranscriptEntry (extended)

Existing entity with display-layer extension for chunk collapse/expand.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| *(existing fields)* | — | — | id, type, query, answer, sources, debug, timestamp, duration, loading, error |
| `chunksExpanded` | boolean | `false` | Whether source chunk text is visible (transcript view only) |

**State transitions**: `chunksExpanded` toggles between `false` (collapsed, showing only file path + score) and `true` (expanded, showing full chunk content). Only relevant in the Transcript panel view.

---

### SourceReference (display-only)

A lightweight projection of `SourceChunk` for the query page answer view. Not a persisted entity.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `file_path` | string | `SourceChunk.file_path` | Path to the source file |
| `score` | number | `SourceChunk.score` | Relevance score (0.0–1.0) |
| `collection` | string | `SourceChunk.collection` | Collection the chunk belongs to |
| `rank` | number | `SourceChunk.rank` | Result rank |

**Relationship**: Derived from `SourceChunk` by omitting `chunk_content` and other detail fields. Used in `QueryAnswer.svelte` to show compact source references on the query page.

---

### PresetOption (static)

Static reference data for the preset dropdown. Hardcoded to match kragd's `VALID_PRESETS`.

| Field | Type | Description |
|-------|------|-------------|
| `value` | string | Preset identifier (`"strict"`, `"balanced"`, `"verbose"`, `"code"`) |
| `label` | string | Display label |
| `description` | string | Brief description shown in dropdown |

**Values**:

| value | label | description |
|-------|-------|-------------|
| `strict` | Strict | Concise, source-grounded answers only |
| `balanced` | Balanced | Detailed answers with numbered citations (default) |
| `verbose` | Verbose | Exploratory answers with full context |
| `code` | Code | Code-focused answers with snippets and file references |

---

## Relationships

```
UserConfig ──loads-at-startup──→ QueryParameters
UserConfig ──loads-at-startup──→ CriticConfig
UserConfig ──loads-at-startup──→ ConnectionBar (host/port)
UserConfig ──loads-at-startup──→ Display (opacity/theme)

QueryParameters ──used-by──→ QueryPanel (controls)
QueryParameters ──included-in──→ QueryRequest (API call)

CriticConfig ──forces──→ include_debug: true (when enabled)
CriticConfig ──used-by──→ QueryAnswer (score flagging)

TranscriptEntry ──rendered-by──→ QueryAnswer (latest, compact)
TranscriptEntry ──rendered-by──→ TranscriptView (history, expandable)

SourceChunk ──projected-to──→ SourceReference (query page)
SourceChunk ──displayed-full──→ TranscriptView (when expanded)

PresetOption ──populates──→ QueryPanel preset dropdown
```
