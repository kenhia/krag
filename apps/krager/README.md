# krager — Tauri Desktop Client for kragd

A native desktop GUI for the [krag](../../README.md) RAG system, built with Tauri v2 + SvelteKit + Svelte 5.

## Prerequisites

### All platforms

- **Rust** (stable): <https://rustup.rs/>
- **Node.js 20+**: via [fnm](https://github.com/schniz/fnm), [nvm](https://github.com/nvm-sh/nvm), or [nodejs.org](https://nodejs.org/)
- **pnpm**: `npm install -g pnpm`

### Linux (Arch)

```bash
sudo pacman -S webkit2gtk-4.1 gtk3 libappindicator-gtk3 librsvg
```

### Linux (Ubuntu/Debian)

```bash
sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev
```

### Windows (native build)

1. [Visual Studio Build Tools 2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022) — select "Desktop development with C++"
2. WebView2 Runtime: ships with Windows 10 21H2+ and Windows 11

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Svelte](https://marketplace.visualstudio.com/items?itemName=svelte.svelte-vscode) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer).

## Development Setup

```bash
cd apps/krager
pnpm install
pnpm tauri dev
```

This starts the Vite dev server (port 1420) and opens the Tauri window with hot-reload.

> **Note**: kragd must be running separately — start it with `uv run kragd` from the repo root.

## Commands

| Command | Description |
|---------|-------------|
| `pnpm tauri dev` | Development mode with HMR |
| `pnpm test` | Vitest unit + component tests |
| `pnpm test:watch` | Tests in watch mode |
| `pnpm lint` | Biome lint check |
| `pnpm format` | Biome auto-format |
| `pnpm build` | SvelteKit production build |
| `pnpm check` | Svelte + TypeScript type checking |

## Linux Build

```bash
cd apps/krager
pnpm tauri build
# Output: src-tauri/target/release/bundle/
#   appimage/krager_*_amd64.AppImage
#   deb/krager_*_amd64.deb
```

## Windows Cross-Compile (from Linux)

```bash
# One-time setup
sudo pacman -S lld llvm clang   # Arch; Ubuntu: sudo apt install lld llvm clang nsis
rustup target add x86_64-pc-windows-msvc
cargo install --locked cargo-xwin

# Build (bare exe — no NSIS installer)
cd apps/krager
pnpm tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc --no-bundle
# First run downloads ~1-2 GB Windows SDK (cached at ~/.cache/xwin)
# Output: src-tauri/target/x86_64-pc-windows-msvc/release/krager.exe

# Build with NSIS installer (requires makensis — available on Ubuntu/Debian, not Arch)
# sudo apt install nsis   # Ubuntu/Debian only
# pnpm tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc
# Output: src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/krager_*_x64-setup.exe
```

> **Note**: On Arch Linux, NSIS is not in standard repos. The bare `.exe` can be built and transferred to Windows directly. For NSIS installer packaging, use Ubuntu/Debian or build natively on Windows.

See [quickstart.md](../../specs/013-krager/quickstart.md) for detailed platform instructions and manual verification steps.

## Architecture

```
src/
├── lib/
│   ├── components/
│   │   ├── ui/          # Button, Input, Spinner, Toast
│   │   └── domain/      # ConnectionBar, SystemStatus, QueryPanel, etc.
│   ├── state/           # Svelte 5 $state modules (.svelte.ts)
│   ├── services/        # HTTP client, SSE streaming
│   ├── utils/           # Formatting, highlighting
│   └── types.ts         # TypeScript interfaces (mirrors kragd schemas.py)
├── routes/
│   ├── +layout.svelte   # Theme init, ToastContainer
│   └── +page.svelte     # Multi-panel layout
└── app.css              # Theme CSS custom properties
```

The app communicates with a running kragd instance over HTTP. All state is in-memory using Svelte 5 `$state` runes — no persistence layer.

## Pre-commit

```bash
cd apps/krager && pnpm check && pnpm lint && pnpm test
```

Python pre-commit (`uv run ruff format . && uv run ruff check --fix . && uv run pytest`) is unaffected.
