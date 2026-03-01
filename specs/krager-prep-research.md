# krager — Prep Research

Research findings for the krager remote desktop client (Tauri + Svelte).

---

## 1. kragd API Surface Audit

### Endpoint Inventory

12 endpoints across 6 routers, all returning JSON by default (FastAPI `response_model`).
No WebSocket or streaming/SSE endpoints exist today.

| # | Method | Path | Request Schema | Response Schema | Notes |
|---|--------|------|---------------|-----------------|-------|
| 1 | `GET` | `/health` | — | `HealthResponse` | `{status, version}` |
| 2 | `GET` | `/status` | — | `ServiceStatus` | Heavyweight: LLM slots, VRAM, collections, modes |
| 3 | `POST` | `/shutdown` | — | `ShutdownResponse` | Self-SIGTERM after 0.5 s delay |
| 4 | `POST` | `/query` | `QueryRequest` | `QueryResponse` | Full RAG with LLM synthesis |
| 5 | `POST` | `/retrieve` | `RetrieveRequest` | `RetrieveResponse` | Retrieval only (no LLM) |
| 6 | `POST` | `/debug/query` | `DebugQueryRequest` | `DebugQueryResponse` | Same as /query with `include_debug=True` |
| 7 | `POST` | `/debug/qdrant` | `QdrantSearchRequest` | `QdrantSearchResponse` | Raw vector search, bypasses Retriever |
| 8 | `POST` | `/index` | `IndexRequest` | `IndexResponse` | Returns immediately; indexing runs in background |
| 9 | `GET` | `/index/status` | — | `IndexResponse` or `list[IndexResponse]` | Polymorphic return type |
| 10 | `GET` | `/modes` | — | `ModeListResponse` | Dynamic mode list |
| 11 | `GET` | `/modes/{name}` | Path param | `ModeDetailResponse` | Full mode config with weights |
| 12 | `POST` | `/lexicon/refresh` | — | `LexiconRefreshResponse` | Reload lexicon from disk |

### Request/Response Schemas

All Pydantic models. Main schemas in `src/kragd/schemas.py`; three response models
defined inline in their routers (`LexiconRefreshResponse`, `ModeListResponse`,
`ModeDetailResponse`) — these should be consolidated into `schemas.py` during
the sprint.

**Key request models:**

- `QueryRequest` — `{query, top_k?, preset?, llm?, mode?, include_debug?}`
- `RetrieveRequest` — `{query, top_k?, mode?}`
- `IndexRequest` — `{mode: "full"|"incremental", directories?, file_types?, exclude_patterns?, dry_run?}`
- `QdrantSearchRequest` — `{query, vector_space?, top_k, score_threshold?, with_payload, filters?}`

**Key response models:**

- `QueryResponse` — `{answer, sources: [SourceChunk], debug?: DebugMetadata}`
- `ServiceStatus` — `{version, uptime_seconds, llm, embedding_models, vector_store, collections, modes, vram, ...}`
- `IndexResponse` — `{job_id, status, files_scanned, files_processed, chunks_created, vectors_stored, duration_seconds, collections, errors, ...}`

### Exception Handling (app.py)

| Exception | HTTP Status | Notes |
|-----------|------------|-------|
| `ValueError` | 422 | Bad request data (e.g., invalid mode) |
| `ServiceNotReadyError` | 503 | kragd still starting up |
| `IndexingInProgressError` | 409 | Index already running |
| `ResourceNotConfiguredError` | 500 | Missing resource |
| `KragError` | 500 | Generic domain error |
| `ResponseValidationError` | 500 | Internal serialization bug |

### API Gaps for krager

1. **No streaming** — Long queries block until the full answer is ready.
   The initial sprint can poll, but streaming (SSE or WebSocket) would
   improve UX for large responses and index progress. *Not blocking for v1.*
2. **Index polling** — `/index` returns immediately; client must poll
   `/index/status`. Consider adding SSE for real-time progress. *Not
   blocking for v1; polling works fine.*
3. **Polymorphic `/index/status`** — Returns either `IndexResponse` or
   `list[IndexResponse]`. The client must handle both. This should be
   normalized to always return a list.

---

## 2. CLI JSON Support Audit

### Current CLI `--json` / `--format` Status

| CLI Command | JSON Flag | Status |
|-------------|-----------|--------|
| `krag query` | `--format json` | ✅ Supported |
| `krag index` | `--json` | ✅ Supported |
| `krag index-status` | `--json` | ✅ Supported |
| `krag status` | `--json` | ✅ Supported |
| `krag debug query` | `--json` | ✅ Supported |
| `krag debug qdrant` | `--json` | ✅ Supported |
| `krag health` | — | ❌ Missing |
| `krag modes list` | — | ❌ Missing |
| `krag modes show` | — | ❌ Missing |
| `krag lexicon refresh` | — | ❌ Missing |
| `krag stop` / `krag shutdown` | — | ❌ Missing |
| `krag start` | — | N/A (subprocess, no HTTP) |

### Impact Assessment

**krager doesn't use the CLI at all** — it calls kragd HTTP endpoints directly
and always receives JSON. The CLI `--json` gaps don't block krager.

However, for consistency and scriptability, we should add `--json` to the
5 missing commands during this sprint. It's small work and benefits both
the CLI and any future automation.

### Inconsistency: `--format` vs `--json`

`krag query` uses `--format text|json|markdown` while all other commands
use `--json` (boolean). Consider normalizing to one pattern. *Low priority;
doesn't affect krager since it bypasses the CLI entirely.*

---

## 3. Repo Structure: Monorepo vs Separate Repo

### Option A — Separate Repository

**Pros:**
- Clean language/tool separation
- Independent versioning and releases
- No risk of Python tool confusion (ruff, mypy, pytest)
- Tauri-specific CI without touching krag's (nonexistent) pipeline

**Cons:**
- Two repos to coordinate during API changes
- No atomic commits across API + client changes
- Separate issue trackers / PRs for related features
- Developer must clone both repos to work on the full stack
- Spec docs split across repos (or duplicated)

### Option B — Monorepo (recommended)

**Pros:**
- Atomic commits when API and client change together
- Single PR for end-to-end features
- Specs, docs, and tasks in one place
- The repo already has a multi-project precedent (`examples/` plugins)
- Zero CI to disrupt (no `.github/workflows/` today)
- Python and Tauri build systems are completely orthogonal:
  - `uv`/`hatchling` only sees `src/` and `examples/`
  - `ruff`/`mypy` already scoped to `src/` and `tests/`
  - `pytest` already scoped to `tests/`
  - Tauri uses `cargo` + `pnpm`/`npm` in its own directory
- Lockfile coexistence: `uv.lock`, `Cargo.lock`, `pnpm-lock.yaml` — different tools, no conflicts

**Cons:**
- New system dependencies for anyone building krager (Rust, Node.js, webkit2gtk)
- Root directory gets wider
- Contributors may be confused by unfamiliar toolchain
- `git clone` fetches everything even if you only want one piece

**Mitigations:**
- README section explaining the two development environments
- `.gitignore` additions for `target/`, `node_modules/`, `dist/`
- Root config files (`.nvmrc`, `rust-toolchain.toml`) scoped to krager subdir
- Clear docs: "to work on Python: `uv sync`; to work on krager: `cd apps/krager && pnpm install`"

### Placement Within the Repo

| Option | Path | Reasoning |
|--------|------|-----------|
| Top-level peer | `/krager/` | Simple, visible, no invented conventions |
| Under `apps/` | `/apps/krager/` | Establishes `apps/` for future UIs |
| Under `examples/` | `/examples/krager/` | Semantically wrong — it's not an example |

**Recommendation:** `apps/krager/` — establishes a clean `apps/` directory for
desktop/mobile clients, parallel to `examples/` for plugins and `src/` for core.

### .gitignore Additions Needed

```gitignore
# Rust (Tauri backend)
**/target/

# Node.js (Svelte frontend)
**/node_modules/
**/dist/
**/.svelte-kit/
```

---

## 4. Tauri + Svelte Technical Notes

### Architecture

```
apps/krager/
├── package.json              # Node.js dependencies (svelte, vite, tauri-cli)
├── svelte.config.js          # SvelteKit / Svelte config
├── vite.config.ts            # Vite bundler config
├── src/                      # Svelte frontend source
│   ├── App.svelte            # Root component
│   ├── lib/                  # Shared stores, API client, types
│   │   ├── api.ts            # HTTP client for kragd
│   │   ├── stores.ts         # Svelte stores (modes, transcript, etc.)
│   │   └── types.ts          # TypeScript types mirroring kragd schemas
│   └── components/           # UI widgets
│       ├── QueryPanel.svelte
│       ├── ModeSelector.svelte
│       ├── TranscriptViewer.svelte
│       ├── SystemCommands.svelte
│       └── ...
├── src-tauri/                # Rust Tauri backend
│   ├── Cargo.toml
│   ├── tauri.conf.json       # Window config, permissions, build settings
│   └── src/
│       └── main.rs           # Tauri entry point (minimal — most logic in Svelte)
├── static/                   # Static assets (icons, etc.)
└── tests/                    # Vitest / Playwright tests
```

### Key Design Decisions

1. **HTTP-only client** — krager talks to kragd via `fetch()` / `httpx`
   equivalent. No Tauri IPC commands needed for v1 (kragd is the backend).
2. **Dynamic mode discovery** — `GET /modes` populates the mode selector
   dropdown; no hardcoded mode list.
3. **Structured transcript** — Every interaction (query, index, status check)
   is logged as `{timestamp, type, request, response, debug?}` in a Svelte store.
4. **Connection management** — kragd host:port configurable in the UI;
   health polling to show connection status.

### System Dependencies

| Dependency | Purpose | Install |
|------------|---------|---------|
| Rust toolchain | Tauri backend compilation | `rustup` |
| Node.js 20+ | Svelte build tooling | `nvm` / system package |
| pnpm | Package manager (preferred for Tauri) | `corepack enable` |
| webkit2gtk (Linux) | WebView rendering | `apt install libwebkit2gtk-4.1-dev` |
| build-essential (Linux) | Native compilation | `apt install build-essential` |

### Tauri v2 vs v1

Tauri v2 (stable since late 2024) is the clear choice:
- Plugin-based permission system
- Better cross-platform support (and mobile if ever needed)
- Improved IPC performance
- Active development focus

---

## 5. Pre-Sprint Work Items

Tasks that should be completed to prepare for the krager sprint:

### Must-Do (Blocking)

1. **Normalize `/index/status` return type** — Always return `list[IndexResponse]`
   so the client doesn't need polymorphic handling.
2. **Consolidate response schemas** — Move `LexiconRefreshResponse`,
   `ModeListResponse`, `ModeDetailResponse` from router files into `schemas.py`.

### Should-Do (Non-blocking but improves quality)

3. **Add `--json` to 5 missing CLI commands** — `health`, `modes list`,
   `modes show`, `lexicon refresh`, `shutdown`. Benefits scripting and consistency.
4. **OpenAPI spec review** — FastAPI auto-generates `/docs` and `/openapi.json`.
   Verify schema descriptions, examples, and tags are complete so we can
   auto-generate TypeScript types for krager.
5. **Add CORS middleware** — kragd runs on `localhost:11435`; the Tauri
   webview may or may not need CORS depending on Tauri's webview origin.
   Research needed; if required, add `CORSMiddleware` to `app.py` with
   configurable origins.

### Nice-to-Have (Future)

6. **SSE endpoint for index progress** — Not needed for v1 (polling works),
   but would improve UX.
7. **WebSocket for streaming query answers** — Not needed for v1 but
   desirable for long-running LLM synthesis.

---

## 6. CORS Research: Tauri v2 Webview + FastAPI

### Question 1: Does Tauri v2's webview send an Origin header?

**Yes.** Tauri v2's webview serves the frontend from a custom protocol, and
the webview engine (webkit2gtk on Linux, WKWebView on macOS, WebView2 on
Windows) enforces standard CORS rules for `fetch()` calls to external origins.

#### Origin by platform

| Platform | Webview Engine | Frontend Origin | Source |
|----------|---------------|-----------------|--------|
| **Linux** | webkit2gtk 4.1 | `tauri://localhost` | Custom scheme; confirmed by Tauri config docs: "`<scheme>://localhost` protocols used on macOS and Linux" |
| **macOS** | WKWebView | `tauri://localhost` | Same custom scheme as Linux |
| **Windows** | WebView2 | `http://tauri.localhost` | Default; `https://tauri.localhost` if `useHttpsScheme: true` in `tauri.conf.json` |

Evidence from Tauri v2 docs:

- The `useHttpsScheme` config option documentation states: *"Sets whether the
  custom protocols should use `https://<scheme>.localhost` instead of the
  default `http://<scheme>.localhost` on Windows and Android. [...] will not
  match the behavior of the `<scheme>://localhost` protocols used on macOS and
  Linux."*
- The HTTP Headers doc shows a response header example:
  `access-control-allow-origin: http://tauri.localhost` — this is the built-in
  ACAO header Tauri sets on its own protocol responses, confirming the origin
  scheme.
- The CSP configuration example includes `"connect-src": "ipc:
  http://ipc.localhost"`, showing the webview treats external HTTP calls as
  cross-origin requests subject to CSP `connect-src` directives.

#### Does the webview bypass CORS?

**No.** Webkit2gtk and the other webview engines enforce CORS for `fetch()`
calls originating from custom schemes. When the Tauri webview at
`tauri://localhost` makes a `fetch()` to `http://localhost:11435`, this is a
cross-origin request. The webview will:

1. Send a preflight `OPTIONS` request (for non-simple requests like POST with
   JSON body).
2. Check the response for `Access-Control-Allow-Origin` matching the webview's
   origin.
3. Block the response in JavaScript if the CORS headers are missing or
   don't match.

**CORS middleware is required on kragd.**

### Question 2: FastAPI CORSMiddleware Configuration

#### Recommended configuration for kragd

```python
from fastapi.middleware.cors import CORSMiddleware

# Default: allow all origins for local dev tool
# Override via KRAGD_CORS_ORIGINS env var (comma-separated)
# e.g. KRAGD_CORS_ORIGINS="tauri://localhost,http://tauri.localhost"
import os

_default_origins = ["*"]
_env_origins = os.environ.get("KRAGD_CORS_ORIGINS", "")
cors_origins: list[str] = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Design decisions with rationale

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Default origins** | `["*"]` (wildcard) | krag is a personal local tool. The server only binds to `localhost:11435`. Wildcard is safe because the network exposure is already limited to loopback. Requiring users to configure the exact Tauri origin before the app works would be a poor DX. |
| **`allow_credentials`** | `False` | krag has no authentication, no cookies, no Bearer tokens. Setting this to `True` would be misleading and would prohibit the `["*"]` wildcard for origins (per the CORS spec: wildcards + credentials is forbidden). |
| **`allow_methods`** | `["*"]` | kragd uses GET and POST today; SSE may use GET. Wildcard avoids needing to update this list as endpoints evolve. |
| **`allow_headers`** | `["*"]` | The Tauri webview and other clients may send various headers (Content-Type, Accept, custom headers). Wildcard avoids friction. |
| **Configurability** | `KRAGD_CORS_ORIGINS` env var | Simple override without touching config files. Comma-separated string is easy to set. If the env var is set, it replaces the wildcard — this allows locking down origins in a multi-user or networked deployment. |
| **`max_age`** | Default (600s) | Fine for local use; preflight caching reduces OPTIONS requests. |

#### How CORSMiddleware handles requests with no Origin header

Requests without an `Origin` header (e.g., `curl`, `httpx`, direct HTTP
clients) pass through the middleware unmodified — **no CORS headers are added
to the response, and the request is not blocked.** This is correct behavior:
CORS is a browser-enforced mechanism. Non-browser clients don't send `Origin`
and don't check CORS headers. The middleware only activates when it sees an
`Origin` header.

This means:
- `curl http://localhost:11435/health` → works, no CORS headers in response
- `httpx.get("http://localhost:11435/health")` → works, no CORS headers
- Tauri webview `fetch("http://localhost:11435/health")` → works, CORS headers
  included because the webview sends `Origin: tauri://localhost`

#### Why `["*"]` is safe for krag specifically

1. **Localhost-only binding** — kragd binds to `127.0.0.1:11435` by default.
   No remote host can reach it regardless of CORS settings.
2. **No credentials** — `allow_credentials=False` means the wildcard is
   spec-compliant and doesn't open credential-forwarding attacks.
3. **Personal tool** — krag is a single-user local RAG system, not a
   multi-tenant service. The threat model doesn't include malicious origins
   on the same machine.
4. **DX priority** — A user who runs `kragd` and opens the Tauri client
   should have it Just Work without configuring origins. The wildcard
   achieves this across all platforms (Linux `tauri://localhost`, Windows
   `http://tauri.localhost`, dev server `http://localhost:5173`, etc.).

#### Platform-specific Tauri CSP note

When building the Tauri client, the CSP in `tauri.conf.json` must allow
`connect-src` to reach kragd:

```json
{
  "app": {
    "security": {
      "csp": "default-src 'self'; connect-src ipc: http://ipc.localhost http://localhost:11435"
    }
  }
}
```

This is a Tauri-side configuration, not a kragd concern, but documenting it
here since it's the other half of the CORS puzzle.

### Summary: implementation plan for kragd

1. Add `CORSMiddleware` to `create_app()` in `src/kragd/app.py`
2. Default: `allow_origins=["*"]`, `allow_credentials=False`,
   `allow_methods=["*"]`, `allow_headers=["*"]`
3. Read `KRAGD_CORS_ORIGINS` env var; if set, use its comma-separated
   values instead of `["*"]`
4. Add contract tests in `tests/test_kragd/test_cors_contract.py`:
   - Request with `Origin` header → response has `Access-Control-Allow-Origin`
   - `OPTIONS` preflight → 200 with correct CORS headers
   - Request without `Origin` → no CORS headers, request succeeds
   - Custom origins via env var → only matching origins allowed
