# Implementation Plan: krager — Tauri Desktop Client for kragd

**Branch**: `013-krager` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/013-krager/spec.md`

## Summary

**krager** is a native desktop application (Tauri v2 + SvelteKit + Svelte 5 + TypeScript) that provides a GUI for the krag RAG system. It lives at `apps/krager/` inside the existing monorepo, communicating with a running kragd instance over HTTP with real-time SSE streaming for queries and index progress. The app covers: connection management, query/answer display with live token streaming, indexing with SSE progress monitoring, mode selection, retrieve-only search, debug tools, and system status — all through a dark/light-themed panel layout. Windows build verification is a required deliverable (cross-compiled from Linux via `cargo-xwin` + NSIS, or built natively).

---

## Technical Context

**Language/Version**: TypeScript 5.6, Rust stable (Tauri v2 requirement), Node.js 20+  
**Primary Dependencies**: Tauri v2, SvelteKit 2 (SPA mode, SSR off), Svelte 5 (runes), `@tauri-apps/plugin-http`, Shiki (syntax highlighting), Vitest, `@testing-library/svelte`  
**Storage**: In-memory only — Svelte 5 `$state` reactive objects in `.svelte.ts` modules; no persistence layer  
**Testing**: Vitest + jsdom for unit/component tests; `vi.mock()` for Tauri APIs; manual E2E on Linux and Windows  
**Target Platform**: Linux (primary CI), Windows (manual verification — cross-compile via `cargo-xwin` + NSIS, or native); macOS (expected to work, not formally tested)  
**Project Type**: Desktop application (Tauri) — SvelteKit SPA in Tauri webview  
**Performance Goals**: <500ms added client overhead on query responses; health poll every 5 seconds; Vite HMR <2 seconds on `.svelte` file changes  
**Constraints**: Must not interfere with existing Python toolchain (`uv`, `ruff`, `mypy`, `pytest`); single kragd connection; in-memory transcript capped at 500 entries; Tauri HTTP capability allows any host (user-configurable connection target)  
**Scale/Scope**: Single-user desktop client; 14 kragd endpoints (12 REST + 2 SSE); ~6 UI panels; ~25 TypeScript type definitions mirroring `schemas.py`

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality & Standards** | ✅ PASS | TypeScript strict mode, ESLint + Prettier (or `biome`), Svelte-check on pre-commit |
| **II. TDD** | ✅ PASS | Vitest + `@testing-library/svelte` replaces pytest for this TypeScript project; Red-Green-Refactor applies; `vi.mock()` for Tauri API isolation. Live/E2E tests require running kragd (equivalent to `@pytest.mark.live`). Python TDD unchanged — Python files are unmodified. |
| **III. UX Consistency** | ✅ PASS | Dark/light theme via `getCurrentWindow().theme()` + CSS custom properties; toast error pattern; keyboard navigation on all interactive elements |
| **IV. Performance** | ✅ PASS | Targets defined in Technical Context; health poll interval configurable |
| **Pre-Commit Validation** | ✅ PASS | New pre-commit commands for `apps/krager/`: `pnpm check && pnpm lint && pnpm test`; Python pre-commit unchanged |
| **Terminal Usage & Reuse** | ✅ PASS | Planning only; implementation follows existing terminal discipline |
| **New toolchain introduction** | ✅ JUSTIFIED | Rust/cargo and Node.js/pnpm are the Tauri stack; they are additive and isolated to `apps/krager/`. The Python toolchain in `src/` is unaffected. |

**No gates violated. No complexity tracking required.**

---

## Project Structure

### Documentation (this feature)

```text
specs/013-krager/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── kragd-api.ts     # TypeScript types mirroring schemas.py
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
apps/krager/                              # NEW — Tauri v2 desktop client
├── package.json
├── tsconfig.json
├── svelte.config.js                      # @sveltejs/adapter-static, SPA mode
├── vite.config.ts                        # SvelteKit plugin + Vitest config
├── .gitignore
├── src/
│   ├── app.html
│   ├── app.css                           # CSS custom properties for themes
│   ├── test-setup.ts                     # @testing-library/jest-dom/vitest
│   ├── lib/
│   │   ├── components/
│   │   │   ├── ui/                       # Button, Input, Spinner, Toast
│   │   │   └── domain/                   # QueryPanel, TranscriptView, IndexPanel,
│   │   │                                 # SystemStatus, ModeSelector, DebugPanel
│   │   ├── state/
│   │   │   ├── connection.svelte.ts      # host, port, status, lastCheck, errorMsg
│   │   │   ├── transcript.svelte.ts      # entries[], addEntry(), maxEntries=500
│   │   │   ├── indexJob.svelte.ts        # running, status, progress fields
│   │   │   ├── modes.svelte.ts           # available[], selected
│   │   │   └── theme.svelte.ts           # current, initTheme()
│   │   ├── services/
│   │   │   ├── kragd-client.ts           # all HTTP calls via @tauri-apps/plugin-http
│   │   │   └── streaming.ts             # SSE POST (fetch+ReadableStream) and GET (EventSource)
│   │   ├── types.ts                      # TypeScript interfaces mirroring schemas.py
│   │   └── utils/
│   │       ├── format.ts
│   │       └── highlight.ts             # Shiki lazy singleton
│   └── routes/
│       ├── +layout.ts                   # export const ssr = false
│       ├── +layout.svelte               # theme init, <html data-theme=...>
│       └── +page.svelte                 # main multi-panel layout
└── src-tauri/
    ├── Cargo.toml
    ├── Cargo.lock
    ├── build.rs
    ├── tauri.conf.json
    ├── src/
    │   ├── main.rs
    │   └── lib.rs                        # minimal — no custom Tauri commands needed
    ├── icons/
    └── capabilities/
        ├── default.json                  # core:window:default (includes theme API)
        └── http.json                     # http:default + allow localhost:11435

# Existing Python projects (unchanged)
src/krag/          # Python library
src/krag_cli/      # Python CLI
src/kragd/         # Python FastAPI server
tests/             # Python pytest suite
```

**Structure Decision**: Desktop application layout. `apps/krager/` is a completely self-contained SvelteKit+Tauri project that shares no build tooling with the Python `src/` packages. The only coupling is at the HTTP API boundary (kragd endpoints) and the type contract (`types.ts` mirrors `schemas.py`).
