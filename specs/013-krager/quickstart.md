# Quickstart: krager — Tauri Desktop Client for kragd

**Phase**: 1 | **Feature**: 013-krager | **Date**: 2026-03-01

---

## Prerequisites

### System dependencies (Linux — Ubuntu/Debian)

```bash
# Tauri system dependencies [See Arch Linux note below]
sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev

# Rust (if not installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# Node.js 20+ (via fnm or nvm)
curl -fsSL https://fnm.vercel.app/install | bash
fnm install 20 && fnm use 20

# pnpm
npm install -g pnpm
```

Arch Linux Note:
```
λ sudo pacman -S webkit2gtk gtk3 libappindicator-gtk3 librsvg
resolving dependencies...
:: There are 11 providers available for ttf-font:
:: Repository extra
   1) gnu-free-fonts  2) noto-fonts  3) ttf-bitstream-vera  4) ttf-croscore  5) ttf-dejavu  6) ttf-droid
   7) ttf-ibm-plex  8) ttf-input  9) ttf-input-nerd  10) ttf-liberation  11) ttf-roboto

Enter a number (default=1): 2
```

### Windows build dependencies (cross-compile from Linux)

```bash
# Ubuntu/Debian: NSIS installer builder + linker tools
sudo apt install lld llvm clang nsis

# Arch Linux: NSIS is not in standard repos; install linker tools only
sudo pacman -S lld llvm clang
# (NSIS unavailable — use --no-bundle flag, see Build section below)

# Windows Rust target
rustup target add x86_64-pc-windows-msvc

# cargo-xwin (fetches Windows SDK automatically, ~1-2 GB on first run)
cargo install --locked cargo-xwin
```

### Windows-native build (building on Windows directly)

1. Install [Rust](https://rustup.rs/) (stable, MSVC toolchain)
2. Install [Node.js 20+](https://nodejs.org/)
3. Install pnpm: `npm install -g pnpm`
4. Install [Visual Studio Build Tools 2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) — select "Desktop development with C++"
5. WebView2 Runtime: ships with Windows 10 21H2+ and Windows 11; otherwise install from Microsoft

---

## Project Scaffold

```bash
# From the krag repo root
mkdir -p apps
cd apps

# Scaffold with the official Tauri CLI (svelte-ts = SvelteKit + Svelte 5 + TypeScript)
pnpm create tauri-app krager --template svelte-ts
cd krager

# Add required Tauri plugin
pnpm add @tauri-apps/plugin-http
pnpm tauri add http          # registers the plugin in Cargo.toml and tauri.conf.json

# Add development dependencies
pnpm add -D vitest @testing-library/svelte @testing-library/jest-dom jsdom shiki
```

---

## Development Workflow

### Start the dev server (Linux)

```bash
cd apps/krager
pnpm tauri dev
```

This launches:
1. Vite dev server (default port 1420)
2. Tauri webview window wrapping `http://localhost:1420`
3. Hot-reload for `.svelte` changes (< 2 seconds)

> **Note**: kragd must be running separately at `localhost:8742` for the app to connect. Start it with `uv run kragd` from the repo root.

### Run tests

```bash
cd apps/krager
pnpm test           # Vitest unit + component tests
pnpm svelte-check   # TypeScript + Svelte type checking
```

### Pre-commit validation (for `apps/krager/` changes)

```bash
cd apps/krager
pnpm svelte-check && pnpm lint && pnpm test
```

> The existing Python pre-commit (`uv run ruff format . && uv run ruff check --fix . && uv run pytest`) still applies to changes in `src/` and `tests/`.

---

## Build for Production

### Linux (AppImage + deb)

```bash
cd apps/krager
pnpm tauri build
# Output: src-tauri/target/release/bundle/
#   appimage/krager_*_amd64.AppImage
#   deb/krager_*_amd64.deb
```

### Windows (NSIS installer, cross-compiled from Linux)

```bash
cd apps/krager
pnpm tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc
# First run: downloads ~1-2 GB Windows SDK (cached at ~/.cache/xwin)
# Output: src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/krager_*_x64-setup.exe
```

> **Arch Linux note**: `makensis` (NSIS) is not available in the standard Arch repos. The Rust cross-compile succeeds but the NSIS bundling step fails. Use `--no-bundle` to produce a bare `.exe` instead:
> ```bash
> pnpm tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc --no-bundle
> # Output: src-tauri/target/x86_64-pc-windows-msvc/release/krager.exe
> ```
> On Ubuntu/Debian, install NSIS with `sudo apt install nsis` for full installer packaging.

Transfer the `.exe` to a Windows machine for smoke testing (see Manual Verification below).

### Windows (native build on Windows)

```powershell
cd apps/krager
pnpm tauri build
# Output: src-tauri\target\release\bundle\
#   msi\krager_*_x64.msi
#   nsis\krager_*_x64-setup.exe
```

---

## Manual Verification (Windows)

After building the Windows NSIS installer:

1. Run `krager_*_x64-setup.exe` on a Windows 10/11 machine
2. Launch `krager.exe` from the Start Menu or install directory
3. Verify the app window opens with no errors
4. Enter `<kragd-host>:8742` (use a kragd instance accessible over the network or localhost if kragd is also running on Windows)
5. Verify the connection indicator turns green
6. Submit a test query — verify the answer and sources appear in the transcript
7. Trigger an incremental index — verify status shows Running → Completed
8. Toggle system dark/light mode — verify the app theme follows
9. Resize the window — verify layout adapts without overflow

---

## Capabilities Configuration

### `src-tauri/capabilities/default.json`

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "main-capability",
  "description": "Core window and app permissions",
  "windows": ["main"],
  "permissions": [
    "core:path:default",
    "core:event:default",
    "core:window:default",
    "core:app:default",
    "core:resources:default",
    "core:menu:default",
    "core:tray:default"
  ]
}
```

### `src-tauri/capabilities/http.json`

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "http-capability",
  "description": "HTTP access to kragd (any host — user-configurable connection target)",
  "windows": ["main"],
  "permissions": [
    {
      "identifier": "http:default",
      "allow": [
        { "url": "http://*:*" }
      ]
    }
  ]
}
```

> **Security note**: The `allow` list uses `http://*:*` to permit connections to any HTTP host and port, since the user configures the kragd target at runtime. Tauri's HTTP plugin uses [URLPattern](https://urlpattern.spec.whatwg.org/) syntax — `*` matches any host, `:*` matches any port. Use `http://localhost:8742/**` to restrict to localhost only.

---

## Project Directory Reference

```
apps/krager/
├── package.json
├── tsconfig.json
├── svelte.config.js               # adapter-static, ssr=false
├── vite.config.ts                 # SvelteKit + Vitest
├── src/
│   ├── app.html                   # SvelteKit HTML shell
│   ├── app.css                    # CSS custom properties for themes
│   ├── test-setup.ts              # @testing-library/jest-dom
│   ├── lib/
│   │   ├── components/
│   │   │   ├── ui/                # Button, Input, Spinner, Toast
│   │   │   └── domain/            # QueryPanel, TranscriptView, IndexPanel,
│   │   │                          # SystemStatus, ModeSelector, DebugPanel
│   │   ├── state/
│   │   │   ├── connection.svelte.ts
│   │   │   ├── transcript.svelte.ts
│   │   │   ├── indexJob.svelte.ts
│   │   │   ├── modes.svelte.ts
│   │   │   └── theme.svelte.ts
│   │   ├── services/
│   │   │   ├── kragd-client.ts    # HTTP wrappers using @tauri-apps/plugin-http
│   │   │   └── streaming.ts       # SSE helpers
│   │   ├── types.ts               # Re-exported from contracts/kragd-api.ts
│   │   └── utils/
│   │       ├── format.ts
│   │       └── highlight.ts       # Shiki singleton
│   └── routes/
│       ├── +layout.ts             # export const ssr = false
│       ├── +layout.svelte         # theme init, app shell
│       └── +page.svelte           # main multi-panel UI
└── src-tauri/
    ├── Cargo.toml
    ├── Cargo.lock
    ├── build.rs
    ├── tauri.conf.json
    ├── src/
    │   ├── main.rs
    │   └── lib.rs                 # minimal — no custom commands needed
    ├── icons/
    └── capabilities/
        ├── default.json
        └── http.json
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `webkit2gtk-4.1` not found | Missing system dep | `sudo apt install libwebkit2gtk-4.1-dev` |
| CORS error in browser console | Using native `fetch` instead of plugin | Import `fetch` from `@tauri-apps/plugin-http` |
| SSE not streaming on Linux | WebKitGTK body buffering | Use `@tauri-apps/plugin-http` fetch for SSE POST |
| `cargo-xwin` fails to download SDK | Network / proxy issue | Set `XWIN_CACHE_DIR=~/.cache/xwin`; check firewall |
| Windows build: "MSVC not found" | Building on Linux without `cargo-xwin` | Use `--runner cargo-xwin` flag or build on Windows |
| App theme doesn't follow system on Linux | GTK environment doesn't expose theme | `window.matchMedia` fallback is active; manually select theme via settings if needed |
| `pnpm tauri dev` port conflict | Another process on 1420 | Edit `vite.config.ts` to change the port |
