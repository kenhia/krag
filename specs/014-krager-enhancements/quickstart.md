# Quickstart: Krager Enhancements

**Feature**: 014-krager-enhancements
**Branch**: `014-krager-enhancements`

## Prerequisites

- Node.js 18+ with pnpm
- Rust toolchain (for Tauri)
- Existing krager app built and functional (from 013-krager)
- A running kragd instance for manual testing

## Setup

```bash
# Ensure you're on the right branch
git checkout 014-krager-enhancements

# Install the new Tauri Store plugin
cd apps/krager
pnpm add @tauri-apps/plugin-store
```

Add to `src-tauri/Cargo.toml` dependencies:
```toml
tauri-plugin-store = "2"
```

Register in `src-tauri/src/lib.rs`:
```rust
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_http::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Add capability file `src-tauri/capabilities/store.json`:
```json
{
  "identifier": "store-capability",
  "description": "Local configuration persistence via Tauri Store",
  "windows": ["main"],
  "permissions": ["store:default"]
}
```

## Development

```bash
cd apps/krager

# Run tests (Vitest)
pnpm test

# Type check (svelte-check)
pnpm check

# Dev mode (Tauri + Vite)
pnpm tauri dev

# Format + lint (Biome)
pnpm exec biome check --write .
```

## Pre-Commit Checklist

Per constitution, before every commit:

```bash
cd apps/krager
pnpm exec biome check --write .   # format + lint
pnpm check                         # svelte-check (0 errors)
pnpm test                          # vitest (all pass)
```

## Build

```bash
# Linux
pnpm tauri build

# Windows cross-compile (from Arch Linux)
pnpm tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc --no-bundle
```

## Config File Location

After running the app and connecting to kragd, the config file is created at:

| Platform | Path |
|----------|------|
| Linux | `~/.local/share/com.krag.krager/settings.json` |
| Windows | `%APPDATA%/com.krag.krager/settings.json` |

You can inspect/edit this file manually (JSON format). The app will pick up changes on next restart.

## Testing Strategy

### New State Modules
- `config-store.ts` — mock Tauri Store API in tests, verify load/save/fallback behavior
- `query.svelte.ts` — test parameter initialization from config, mutation, persistence calls
- `settings.svelte.ts` — test opacity/theme state, validation, clamping

### Modified Components
- `QueryPanel.svelte` — test new controls render, parameter binding, request payload inclusion
- `ConnectionBar.svelte` — test initial values loaded from config
- `SystemStatus.svelte` — test multiple embedding models display
- `SettingsPanel.svelte` — test section rendering, value changes

### New UI Primitives
- `Select.svelte` — test dropdown open/close, option selection, keyboard nav
- `Toggle.svelte` — test on/off state, disabled state
- `Slider.svelte` — test range, clamping, value display

## Architecture Notes

### Config Flow
```
App Startup → configStore.init() → hydrate state modules → render UI
User Action → update $state (instant) → configStore.set() (async, debounced 300ms)
App Restart → configStore.init() → same values restored
```

### Sidebar Navigation (updated)
```
💬 Query     — QueryPanel + QueryAnswer (current answer)
📝 Transcript — TranscriptView (full history with expandable chunks)
📑 Index     — IndexPanel (unchanged)
⚙ System    — SystemStatus (modified: all embedding models)
🔧 Settings  — SettingsPanel (NEW)
🔍 Debug     — DebugPanel (unchanged)
```

### Deferred Items
- **Index path selection** — blocked on kragd API (no endpoint exposes configured source directories)
- **Per-request critic override** — blocked on kragd API (no `critic_enabled` field in QueryRequest)
- Both documented in research.md with recommended kragd API changes
