# Research: krager — Tauri Desktop Client for kragd

**Phase**: 0 | **Feature**: 013-krager | **Date**: 2026-03-01

All NEEDS CLARIFICATION items from Technical Context resolved below.

---

## R-001: Tauri v2 Windows Cross-Compilation from Linux

**Decision**: Provide both a cross-compilation path (`cargo-xwin` + NSIS) AND documented Windows-native instructions. Recommend CI (GitHub Actions `windows-latest`) for production artifacts.

**Rationale**:
- Tauri v2 officially documents Linux → Windows cross-compile via `cargo-xwin` (MSVC target) + NSIS. It is explicitly labeled "last resort" and "not tested as much."
- Output is NSIS `.exe` only — WiX MSI cannot be cross-compiled from Linux (WiX Toolset is Windows-only).
- The compiled binary cannot be run on Linux (WebView2 is Windows-only), so runtime testing always requires a Windows environment regardless of build host.
- For our purposes: provide `cargo-xwin` instructions for the developer to build a Windows artifact locally on Linux, and require the user to smoke-test it on Windows.

**Recommendations**:
1. Primary: Linux build on developer machine (AppImage/deb). Python pre-commit + `pnpm check && pnpm test` run here.
2. Windows: cross-compile with `cargo-xwin` from Linux to produce `*_x64-setup.exe`, then user smoke-tests on Windows (or in a VM).
3. Future: add GitHub Actions matrix for proper multi-platform release artifacts.

**Cross-compile toolchain**:
```bash
# Prerequisites (Ubuntu/Debian)
sudo apt install lld llvm clang nsis
rustup target add x86_64-pc-windows-msvc
cargo install --locked cargo-xwin

# Build Windows NSIS installer from Linux
pnpm tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc
# Output: src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/*_x64-setup.exe
```

**Windows-native prerequisites** (for building directly on Windows):
- Rust stable (rustup)
- Visual Studio Build Tools 2022 (MSVC + Windows SDK)
- Node.js 20+ + pnpm
- WebView2 Runtime (ships with Windows 10/11)

**Limitation flags**:
- MSI installer: not producible from Linux cross-compile (NSIS only)
- Code signing: requires `osslsigncode` on Linux or `signtool.exe` on Windows — deferred
- `xwin` downloads ~1–2 GB Windows SDK on first build; cache at `~/.cache/xwin`

**Alternatives considered**:
- `x86_64-pc-windows-gnu` (MinGW): Unsupported by Tauri's bundler; WebView2Loader.dll handling messier. Rejected.
- GitHub Actions only: Valid for CI, but user requested a local cross-compile path.

---

## R-002: Tauri v2 + Svelte Template Scaffold

**Decision**: Use `pnpm create tauri-app --template svelte-ts` which generates a **SvelteKit 2 SPA** (not plain Svelte) with `@sveltejs/adapter-static` and SSR disabled.

**Key facts**:
- As of `create-tauri-app` v4.0.0+, the `svelte`/`svelte-ts` templates use SvelteKit in SPA mode (`ssr = false`, `adapter-static`).
- Generated stack: SvelteKit 2, Svelte 5, TypeScript 5.6, Vite 6, `@tauri-apps/api@^2`, `@tauri-apps/cli@^2`.
- `src/routes/+layout.ts` exports `const ssr = false` — required since Tauri has no Node server.

**Project layout** (after scaffold + additions):
```
apps/krager/
├── package.json
├── svelte.config.js         # adapter-static, SSR off
├── vite.config.ts           # SvelteKit + Vitest
├── src/
│   ├── app.html / app.css
│   ├── lib/
│   │   ├── components/ui/ + domain/
│   │   ├── state/*.svelte.ts
│   │   ├── services/kragd-client.ts + streaming.ts
│   │   ├── types.ts
│   │   └── utils/
│   └── routes/+layout.ts, +layout.svelte, +page.svelte
└── src-tauri/
    ├── tauri.conf.json
    ├── capabilities/default.json + http.json
    └── src/main.rs + lib.rs  # minimal
```

**Alternatives considered**:
- Plain Svelte (no SvelteKit): Possible with `--template svelte` (v3 template) but not the current default and loses file-based routing, `$lib` alias, and build pipeline improvements.
- Vue / React templates: Not appropriate; Svelte is the chosen stack.

---

## R-003: Svelte 4 Stores vs Svelte 5 Runes

**Decision**: Write all shared app state as **Svelte 5 rune-based reactive objects** in `.svelte.ts` module files.

**Pattern**: Export a `$state({...})` object — mutate properties directly, no subscription syntax needed:
```typescript
// src/lib/state/connection.svelte.ts
export const connection = $state({
  host: 'localhost',
  port: 11435,
  status: 'disconnected' as 'connected' | 'disconnected' | 'error',
  lastCheck: null as Date | null,
  errorMsg: null as string | null,
});
```

**Rationale**: Svelte 5 runes are the idiomatic forward path; Svelte 4 stores still work but require `$store` subscription syntax. Since the official template now ships Svelte 5, we align with it throughout.

**Svelte 4 stores retained for**: compatibility shims with any third-party library that requires a store interface.

---

## R-004: HTTP Client in Tauri Webview

**Decision**: Use **`@tauri-apps/plugin-http`** for all HTTP requests to kragd.

**Rationale**:
- The Tauri webview origin is `tauri://localhost`, which differs from `http://localhost:11435`. Native `window.fetch` triggers CORS and requires kragd to respond with `Access-Control-Allow-Origin: *` (which kragd does since Sprint 012, but is a fragile dependency).
- `@tauri-apps/plugin-http` routes requests through Rust (`reqwest`) — not the browser — bypassing CORS entirely and providing consistent behavior across platforms.
- Drop-in Web Fetch API compatible; no extra syntax overhead.
- Critical for Linux SSE streaming: WebKitGTK (Linux webview) buffers HTTP response bodies, preventing `ReadableStream` delivery. The plugin's Rust-side streaming is unafflicted.

**Alternatives considered**:
- Native `window.fetch`: CORS-dependent, unreliable SSE on Linux. Rejected as primary.
- `axios`: Browser-side like native fetch; same CORS exposure; adds bundle weight. Rejected.
- Use CORS (Sprint 012 already added it): Still leaves SSE buffering issue on Linux. Plugin preferred.

**Required capability** (`src-tauri/capabilities/http.json`):
```json
{
  "permissions": [{
    "identifier": "http:default",
    "allow": [
      { "url": "http://localhost:11435/**" },
      { "url": "http://127.0.0.1:11435/**" }
    ]
  }]
}
```

---

## R-005: SSE Streaming Strategy

**Decision**:
- `POST /query/stream` (SSE over POST): Use `@tauri-apps/plugin-http` `fetch` + `ReadableStream` manually parsed (data lines, `[DONE]` sentinel).
- `GET /index/stream` (SSE over GET): Native `EventSource` (simpler, no body needed). Fall back to `@tauri-apps/plugin-http` if WebKitGTK buffering is observed on Linux.
- **v1 baseline is polling** (not SSE); SSE is a fast-follow enhancement.

**Linux SSE issue**: WebKitGTK buffers HTTP response bodies and does not deliver them incrementally to `ReadableStream`. The `@tauri-apps/plugin-http` routes through Rust's `reqwest`, which streams properly. This is the definitive reason to prefer the plugin over native fetch for all network requests, not just SSE.

**AbortController** pattern to cancel in-flight streams when user navigates away.

---

## R-006: State Management Pattern

**Decision**: Svelte 5 rune objects in `.svelte.ts` modules (see R-003).

**Polling cleanup**: `$effect` with teardown return value manages `setInterval`:
```typescript
$effect(() => {
  if (!connection.connected) return;
  const id = setInterval(checkHealth, 5000);
  return () => clearInterval(id);
});
```

**Index job polling**: conditional `$effect` that activates only while `indexJob.running` is true; polls at 2s intervals; stops when status is no longer `running`.

---

## R-007: Dark/Light Theme

**Decision**: `getCurrentWindow().theme()` for initial value + `onThemeChanged()` for live updates; `window.matchMedia` as synchronous fallback for the initial render frame (avoids flash).

**Platform note**: On Linux, `theme()` may return `null` (many GTK environments don't expose theme to WebView). The `matchMedia` fallback covers this.

**CSS approach**: `data-theme` attribute on `<html>` root element, driven by CSS custom properties:
```css
:root[data-theme="dark"] { --bg: #1e1e2e; --fg: #cdd6f4; --accent: #89b4fa; }
:root[data-theme="light"] { --bg: #eff1f5; --fg: #4c4f69; --accent: #1e66f5; }
```

**Tauri API used**: `core:window:default` permission (no extra plugin needed).

---

## R-008: Code Syntax Highlighting

**Decision**: **Shiki** with lazy `createHighlighter` singleton; dual-theme support built in.

**Rationale**:
- Native dual-theme (dark + light) without re-highlighting on theme change.
- Same TextMate grammars as VS Code — accurate for Python, TypeScript, Rust, SQL.
- Vite tree-shakes to only loaded languages. WASM bundled with assets; no CDN.
- Works in Tauri webview without special config.

**Languages preloaded**: `python`, `typescript`, `javascript`, `bash`, `json`, `rust`, `sql`, `markdown`.

**Alternatives considered**:
- `highlight.js`: No built-in dual-theme; requires manual theme toggle. Larger bundle for `common` preset.
- `prism.js`: Small core but no dual-theme; needs custom CSS for every theme combo.

---

## R-009: Testing Strategy

**Decision**: Vitest + jsdom + `@testing-library/svelte` + `@testing-library/jest-dom`.

**Unit tests**: Logic in `services/` and `state/` modules — mock Tauri APIs via `vi.mock()`.
**Component tests**: Render Svelte components with mocked state/services.
**E2E / live tests**: Manual — launch kragd + krager and exercise each panel. Documented in `quickstart.md`.

**Pre-commit commands for `apps/krager/`**:
```bash
pnpm svelte-check    # TypeScript + Svelte type checking
pnpm lint            # ESLint or Biome
pnpm test            # Vitest
```

**Tauri API mocking pattern**:
```typescript
vi.mock('@tauri-apps/plugin-http', () => ({
  fetch: vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }),
}));
vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    theme: vi.fn().mockResolvedValue('dark'),
    onThemeChanged: vi.fn().mockResolvedValue(() => {}),
  }),
}));
```

---

## R-010: Additional Tools Not Previously Mentioned

The following tools/packages are introduced by this feature and were not covered in the planning or research docs:

| Tool | Purpose | Scope |
|------|---------|-------|
| `cargo-xwin` | Linux → Windows cross-compilation | Build only |
| `nsis` (system) | Windows NSIS installer bundler (cross-compile) | Build only |
| `@tauri-apps/plugin-http` | Rust-backed HTTP fetch (CORS bypass, SSE on Linux) | Runtime |
| `shiki` | Syntax highlighting with dual-theme | Runtime |
| `@testing-library/svelte` | Svelte component testing | Dev |
| `@testing-library/jest-dom` | DOM assertion matchers | Dev |
| `vitest` | Test runner | Dev |
| `biome` (optional) | Unified linter + formatter replacing ESLint + Prettier | Dev |
| `@sveltejs/adapter-static` | SPA build adapter for SvelteKit | Build |
