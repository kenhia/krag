# Handoff: krag as the RAG backend for multae-viae

**Date**: 2026-06-11
**Status**: **SUPERSEDED (2026-06-12)** — multae-viae chose **klams** as its
RAG/memory backend instead (klams already provides the MCP server, auth,
retrieval, ingestion, and kubs0 deployment this handoff planned to build; see
`multae-viae/specs/010-klams-rag/`). krag continues as a standalone tool with
no m-v coupling. Retained for the record: §5 bug triage and §6 review charter
remain useful inputs to krag's own backlog.
**Consumers**: krag (implements), multae-viae sprint 010 / Phase 5.5 (consumes)
**m-v references**: `docs/08-rag-integration.md`, `docs/09-roadmap.md` Phase 5.5

## 1. Context & decision

multae-viae (m-v) Phase 5.5 needs retrieval-augmented context for agent
workflows. Decision (2026-06-11): **use krag as the RAG service**, exposed to
m-v through an MCP server boundary, deployed on kubs0. A future Rust port
remains an open option — the MCP contract below is the seam that makes the
backend swappable without m-v changes, and it shrinks any future rewrite to
"reimplement these tools," not "reimplement krag."

m-v brings its own models, routing, and synthesis. It needs **retrieval** (and
eventually ingestion) from krag — never krag's LLM synthesis path. krag's own
CLI/query features continue to work unchanged; the MCP facade is additive.

```
┌──────────────────────────┐                ┌─────────────────────────────────┐
│  multae-viae (dev box)   │                │  kubs0                          │
│                          │  MCP over      │  ┌───────────────────────────┐  │
│  rmcp MCP client         │  Streamable    │  │ krag MCP facade (new)     │  │
│  (mcp-servers.yaml) ◄────┼────HTTP────────┼──│   wraps kragd service     │  │
│                          │                │  │   layer (retrieval-only   │  │
│  agent toolset merge     │                │  │   profile: no LLM loaded) │  │
│  (rag_* tools)           │                │  └─────────────┬─────────────┘  │
└──────────────────────────┘                │      embedded Qdrant + BGE      │
                                            │      embeddings (eager)         │
                                            └─────────────────────────────────┘
```

## 2. Grounding: what krag actually provides today

Facts the contract is built on (verified against source 2026-06-11):

- `POST /retrieve` exists and is **LLM-free**: `{query, top_k?, mode?}` →
  `{sources: [SourceChunk]}` where `SourceChunk` carries `chunk_id`,
  `file_path`, `score`, `rank`, `chunk_content`, `file_type`, `language?`,
  `function_name?`, `class_name?`, `start_line?`, `end_line?`, `collection?`
  (`src/kragd/schemas.py`).
- **Scores are not uniformly comparable**: cosine (0–1, single-model path) vs
  RRF (~0.016–0.03, multi-model/multi-collection path). Thresholds apply only
  to the cosine path. The response does not currently say which was used.
- Content targeting is via **retrieval modes** (named configs with
  collection-weight maps, e.g. built-in `default`, `code`, `docs`,
  `obsidian`), not raw collections. Collections are the four fixed content
  types `code` / `tests` / `docs` / `text`.
- Ingestion is **pull-based only**: `POST /index` (full | incremental) scans
  configured directories. There is no push-a-document API.
- **Retrieval-only startup works by config today**: with `llm_model` unset,
  embeddings + collections + mode registry initialize, `/retrieve` and
  `/index` work, `/query` fails. Embedding models always load eagerly.
- Qdrant is **embedded** (in-process, file-backed); there is no remote-Qdrant
  mode. One shared client, four collections (`krag_code`, `krag_tests`,
  `krag_docs`, `krag_text`).
- **No MCP support and no Dockerfile** exist today. Python `>=3.11,<3.14`;
  FastAPI ≥0.115, qdrant-client ≥1.8, sentence-transformers ≥2.3.

### Deviations from m-v's original sketch (docs/08)

| docs/08 sketch | This contract | Why |
|---|---|---|
| `search_documents(collection, min_score)` | `rag_search(mode)`; no `min_score` param | krag targets content via modes, not raw collections; a flat `min_score` is meaningless on the RRF path (krag lesson F-03). Thresholds stay mode-level config. |
| `ingest_document(content, metadata)` | **Deferred to contract v2** | krag has no push-ingestion; building one is real design work (unbacked-by-file chunks, dedup, deletion). v1 exposes pull-based reindex instead. |
| `delete_document(id)` | **Deferred to contract v2** | Pairs with push-ingestion. |
| `list_collections` | `rag_list_modes` | Modes are the real query-targeting unit. |
| MCP resources (`rag://...`) | Tools only in v1 | Keeps the m-v client surface minimal; resources can be added additively later. |
| Embedding via Ollama `nomic-embed-text` on the m-v side | Embedding stays **server-side in krag** (BGE) | m-v sends text queries; it never embeds. m-v roadmap Phase 5.5 task list needs this amendment. |

## 3. MCP tool contract — v0.1 draft

Transport: **MCP Streamable HTTP** (m-v's rmcp client already supports
url-configured servers via `mcp-servers.yaml`). Server identifies as
`krag-mcp` with its version in MCP `serverInfo`. Tool names are `rag_`-prefixed
because m-v merges MCP tools into one agent toolset alongside built-ins
(`file_read`, `http_get`, …) — unprefixed names like `search` are ambiguous to
the agent.

### `rag_search`

Search the knowledge base. The primary tool; everything else is supporting.

```yaml
input:
  query: string          # required, 1–10000 chars
  mode: string           # optional; a registered retrieval mode name
                         # (default: "default"); invalid name is an error
                         # listing valid modes
  top_k: integer         # optional, 1–100; default = the mode's top_k
output:
  results:               # ordered by rank
    - rank: integer            # 1-based; the authoritative ordering
      score: number            # informative only — NOT comparable across score_kinds
      score_kind: string       # "cosine" | "rrf"  (NEW field — krag change K4)
      chunk_content: string
      file_path: string
      collection: string       # "code" | "tests" | "docs" | "text"
      file_type: string
      language: string|null
      function_name: string|null
      class_name: string|null
      start_line: integer|null
      end_line: integer|null
      chunk_id: string
```

Contract rule: consumers MUST use `rank` for ordering/cutoffs and MUST NOT
compare `score` values across responses or score kinds.

### `rag_list_modes`

```yaml
input: {}
output:
  modes:
    - name: string
      description: string
      collections: object      # collection -> weight
      top_k: integer
```

### `rag_index_status`

```yaml
input: {}
output:
  state: string                # "idle" | "running" | "error"
  last_job:                    # null if never indexed
    mode: string               # "full" | "incremental"
    completed_at: string|null  # ISO 8601
    files_processed: integer
    chunks_generated: integer
    error: string|null
```

### `rag_trigger_index`

```yaml
input:
  mode: string                 # "full" | "incremental" (default "incremental")
output:
  accepted: boolean            # false + reason if a job is already running
  reason: string|null
```

Deliberately does NOT expose `directories` / `vector_store_path` overrides
over the network — indexed roots are server-side config on kubs0.

### Error behavior

Tool errors return MCP tool-error results with actionable messages (mirroring
kragd's type-based exception mapping: not-ready, index-in-progress, bad mode
name). m-v treats an unreachable/failed RAG server as a degraded-mode signal
(MCP server failures are logged and skipped, not fatal — already m-v behavior).

### Versioning

This document is the contract source of truth. v1.0 = frozen at M1. Additive
changes (new tools, new optional output fields) are fine without coordination;
breaking changes (renames, removed/retyped fields, semantics changes) require
a version bump here and a coordinated m-v change.

## 4. krag-side work items

| ID | Item | Notes |
|----|------|-------|
| K1 | **MCP facade** implementing §3 over the existing service layer | Official `mcp` Python SDK (FastMCP), Streamable HTTP. Thin: maps tools onto the same orchestration `kragd` routers use. Whether it lives in-process with kragd or as a sibling app is implementer's choice. |
| K2 | **Retrieval-only deployment profile** | Works by config today (`llm_model` unset). Make it first-class: documented config, a test asserting `/retrieve` + indexing work with no LLM configured, clean `/status` in that state. |
| K3 | **Bug fixes on the contract path** (see §5 triage) | F-05, F-06, F-03 (retrieval correctness); F-02, F-04 (incremental indexing — required for a long-running service); plus whatever the Fable review adds. |
| K4 | **`score_kind` in retrieve results** | Retriever knows which path produced a result set; surface it. Small, additive to the HTTP API too. |
| K5 | **Containerize for kubs0** | Dockerfile (Python 3.11–3.13 base, sentence-transformers; **no llama-cpp needed** in the retrieval-only image), volumes for embedded Qdrant storage + HF model cache, health endpoint already exists. No standalone Qdrant server — embedded-in-container is the v1 deployment (m-v roadmap's "Qdrant via Docker" task is amended by this). |
| K6 | **Seed corpus + smoke test on kubs0** | Index a real corpus (e.g. the m-v repo docs + krag docs), verify `rag_search` end-to-end from a remote MCP client. |

## 5. Known-bug triage (daemon path)

From krag's own AUDIT-REPORT.md / findings-prep-for-006.md, scoped to what the
contract touches:

| Bug | Where | Contract impact | Verdict |
|-----|-------|-----------------|---------|
| F-05 empty `file_path` payload crashes retrieval | `retrieval/retriever.py:155` | One corrupt chunk kills `rag_search` | **Must fix (M2)** |
| F-06 score validator rejects >1.0 | `models/query_result.py:12` | Boosted/dot-product scores crash retrieval | **Must fix (M2)** |
| F-03 boost weights drown RRF rank fusion | `retrieval/retriever.py:29–31,97–114` | `rag_search` result *quality* broken on multi-collection modes | **Must fix (M2)** |
| F-02 incremental indexing leaves stale vectors | `orchestration/indexer.py:730–760` | Long-running service accumulates stale results | **Must fix (M2)** (interim mitigation: scheduled full reindex) |
| F-04 stale `chunker` across loop iterations | `orchestration/indexer.py:570–610` | Wrong chunking after first file | **Should fix (M2)** |
| Silent `except: pass` in service.py | `kragd/service.py:259,1133–1167` | Failures invisible to MCP clients | **Should fix (M2)** |
| F-01 LLM routing never fires | `synthesis/llm_pool.py:415–425` | `/query` only — m-v never calls it | krag backlog, not gating |
| `ConfigManager.find_and_load` missing | `krag_cli/...` | CLI only | krag backlog, not gating |

## 6. Review charter (Fable review of krag)

Purpose: validate the codepaths this contract stands on **before freezing it**,
and sanity-check the rest of the codebase (the m-v Fable review surfaced
serious issues; assume krag has comparable blind spots).

**Deep review — the contract-critical paths:**

1. Retrieval: `src/krag/retrieval/` (retriever, RRF merge, boosts, thresholds)
   and `src/kragd/` retrieve router + schemas — correctness, the F-03/F-05/F-06
   findings, and anything else that would corrupt `rag_search` results or
   ordering.
2. Indexing: `src/krag/orchestration/indexer.py` + incremental change
   detection — staleness (F-02), the chunker leak (F-04), failure handling for
   a long-running unattended service.
3. Service lifecycle: `src/kragd/service.py`, `app.py` — startup with no LLM
   configured, shutdown, the silent exception swallowing, concurrent
   index-while-retrieve behavior.
4. Embedding orchestration: `src/krag/embeddings/` — multi-model spaces,
   anything that breaks when only retrieval traffic exists.

**Sanity sweep — everything else** (config/XDG, plugins, chunking, CLI,
eval): not exhaustive, but flag anything severe — crashes, data loss, security
(the facade will listen on a LAN port), and dead/misleading code that would
trip up the facade work.

**Outputs wanted**: confirmations/refutations of §5, new daemon-path findings
(which amend §5 and possibly §3), and a severity-ranked list for krag's own
backlog.

## 7. Milestones

### M1 — contract freeze (gates *starting* m-v sprint 010)

- [ ] Fable review of krag complete; findings triaged into §5
- [ ] Contract §3 amended for any review fallout and marked **v1.0 frozen**
- [ ] m-v roadmap Phase 5.5 task list amended (embedding server-side; no
      standalone Qdrant; ingestion = pull-based reindex in v1)

No krag implementation is required for M1 — m-v sprint 010 develops and tests
hermetically against a fake MCP server implementing v1.0. Once M1 is reached,
m-v development proceeds; krag work (K1–K6) runs in parallel.

### M2 — live service (gates m-v sprint 010's *e2e checkpoint*, not its start)

- [ ] K1–K5 complete; K6 smoke test passes from a remote client
- [ ] krag MCP facade deployed on kubs0, retrieval-only profile, seeded corpus
- [ ] m-v `mcp-servers.yaml` entry pointed at it; live `rag_search` through an
      m-v workflow returns sane results (the Phase 5.5 roadmap deliverable)

After M2, krag development continues freely under the versioning rule in §3.

## 8. Open questions (decide at/before M1)

1. **Facade placement**: in-process with kragd (one service, one port) vs
   sibling process. Suggest: implementer's choice in K1, contract is silent.
2. **Auth**: docs/08 suggests API keys/mTLS for the MCP connection; krag has
   none today and kubs0 is a trusted LAN. Suggest: defer, note as accepted
   risk in v1; revisit if the facade ever leaves the LAN.
3. **Seed corpus** for K6: which directories on kubs0 get indexed first?
4. **Push-ingestion (v2)**: does m-v's Phase 6 (always-on agent, persistent
   memory) want `ingest_document` badly enough to schedule it, or does
   file-drop + incremental reindex cover it?
