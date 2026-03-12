# Implementation Plan: Krager Enhancements

**Branch**: `014-krager-enhancements` | **Date**: 2026-03-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-krager-enhancements/spec.md`

## Summary

Enhance the krager Tauri desktop GUI with persistent settings, expanded query controls (top-k, preset, debug, sources, critic), a settings page, transcript redesign separating current-answer from history, window opacity control, selective index path handling, and complete embedding model display. Infrastructure centers on adding the Tauri Store plugin for local JSON configuration persistence using Svelte 5 runes reactive state, with debounced writes and graceful fallback to defaults.

## Technical Context

**Language/Version**: TypeScript 5.6 (frontend), Rust (Tauri shell, no custom commands needed)
**Primary Dependencies**: SvelteKit 2, Svelte 5 (runes), Tauri v2, `@tauri-apps/plugin-http`, `@tauri-apps/plugin-store` (to add)
**Storage**: Tauri Store plugin — JSON file in OS-native app data directory (`$APPDATA/krager/settings.json`)
**Testing**: Vitest 4 + @testing-library/svelte (172 existing tests)
**Target Platform**: Linux native, Windows cross-compile via cargo-xwin
**Project Type**: Desktop application (Tauri + SvelteKit SPA)
**Performance Goals**: Config load <50ms on startup; UI interactions <16ms (60fps); debounced config writes ≤1/second
**Constraints**: No network dependency for config (local-only); graceful fallback on config corruption; minimum opacity 30%
**Scale/Scope**: Single-user desktop app; ~9 new/modified components; ~5 new state modules/services

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality & Standards | ✅ PASS | All new code follows existing patterns (Svelte 5 runes, TypeScript strict, Biome formatting) |
| II. TDD | ✅ PASS | Tests written for all new state modules and services; component tests for new UI controls; existing 172 tests preserved |
| III. User Experience Consistency | ✅ PASS | New controls follow existing UI patterns (Button, Input, Spinner); settings page uses same sidebar nav pattern; error messages remain actionable |
| IV. Performance & Optimization | ✅ PASS | Config writes debounced (≤1/sec); config load is synchronous at startup; no runtime performance impact on query path |
| Pre-Commit Validation | ✅ PASS | Biome format + Biome check + Vitest + svelte-check before every commit |
| Terminal Reuse | ✅ PASS | Single terminal for all commands |

**Gate Result**: ✅ ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/014-krager-enhancements/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── config-schema.ts # Config file TypeScript interface
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
apps/krager/
├── src-tauri/
│   ├── Cargo.toml                    # + tauri-plugin-store
│   └── capabilities/
│       └── store.json                # NEW: store plugin capability
├── src/
│   └── lib/
│       ├── services/
│       │   ├── kragd-client.ts       # MODIFIED: no changes needed (types already support top_k, preset, etc.)
│       │   ├── config-store.ts       # NEW: Tauri Store wrapper — load, save, debounce
│       │   └── streaming.ts          # UNCHANGED
│       ├── state/
│       │   ├── connection.svelte.ts  # MODIFIED: load/save host+port from config
│       │   ├── query.svelte.ts       # NEW: query parameters state (top_k, preset, debug, sources, critic)
│       │   ├── settings.svelte.ts    # NEW: global settings state (opacity, theme overrides)
│       │   ├── transcript.svelte.ts  # MODIFIED: support chunk collapse/expand
│       │   └── ...                   # Other state modules unchanged
│       ├── components/
│       │   ├── domain/
│       │   │   ├── ConnectionBar.svelte    # MODIFIED: read initial values from config
│       │   │   ├── QueryPanel.svelte       # MODIFIED: add top-k, preset, debug, sources, critic controls
│       │   │   ├── QueryAnswer.svelte      # NEW: current answer display (answer + source refs, no chunks)
│       │   │   ├── TranscriptView.svelte   # MODIFIED: expandable chunks, moved to Transcript panel
│       │   │   ├── IndexPanel.svelte       # MODIFIED: path selection checkboxes (future — depends on kragd API)
│       │   │   ├── SystemStatus.svelte     # MODIFIED: show all embedding models
│       │   │   ├── SettingsPanel.svelte    # NEW: settings page with sections
│       │   │   └── ...
│       │   └── ui/
│       │       ├── Slider.svelte           # NEW: range slider for opacity
│       │       ├── Select.svelte           # NEW: dropdown for preset selection
│       │       ├── Toggle.svelte           # NEW: toggle switch for boolean settings
│       │       └── ...
│       ├── types.ts                        # MODIFIED: add UserConfig, QueryConfig, CriticConfig types
│       └── utils/
│           └── ...                         # UNCHANGED
│   └── routes/
│       └── +page.svelte                   # MODIFIED: add Settings + Transcript sidebar entries
└── package.json                           # + @tauri-apps/plugin-store
```

**Structure Decision**: Extends the existing krager application structure. No new top-level directories. New components follow the established `domain/` vs `ui/` split. New state modules follow the existing `$state` rune pattern. The Tauri Store plugin is the only new dependency.

## Complexity Tracking

No constitution violations — table not needed.