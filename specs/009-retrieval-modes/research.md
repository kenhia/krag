# Research: Sprint 009 — Retrieval Modes, Multi-Collection Qdrant, Domain Lexicon, and Context Critic

**Date**: 2026-02-21
**Status**: Complete — all NEEDS CLARIFICATION items resolved

---

## R-01: Qdrant Multi-Collection Architecture

### Decision
Use a single `QdrantClient(path="...")` instance to manage four collections (`krag_code`, `krag_tests`, `krag_docs`, `krag_text`). Introduce a `CollectionManager` that owns the shared client and hands it to `QdrantVectorStore` wrappers per collection.

### Rationale
- Qdrant's embedded mode supports multiple collections in a single storage path.
- Only one client can hold the file lock for a given path — sharing a client avoids lock conflicts.
- Each collection independently specifies its own `VectorParams` (different sizes for different embedding models).
- 4 small collections are actually faster per-query than 1 large one (smaller scan set).

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|-------------|
| Separate `QdrantClient` per collection | File lock prevents multiple clients on same path |
| Separate storage paths per collection | Increases disk I/O, complicates path management |
| Single collection with payload-based filtering | Can't use different vector dims per content type |
| Named vector spaces (current approach) | All content in one collection, can't target subsets |

### Implementation Notes
- Refactor `QdrantVectorStore.__init__` to accept an optional pre-created `QdrantClient`.
- `CollectionManager` creates four `QdrantVectorStore` instances sharing one client.
- Collection naming: `krag_code`, `krag_tests`, `krag_docs`, `krag_text` (namespaced).
- For querying: issue separate `search_named()` calls per collection, merge via weighted RRF.
- Empty collections return empty result sets — no errors.

---

## R-02: Lifecycle Timer Pause/Resume

### Decision
Add `pause()` and `resume(slot)` methods to `LLMLifecycleManager`. `pause()` cancels the asyncio timer task; `resume()` re-schedules it. Use `loop.call_soon_threadsafe()` for cross-thread asyncio operations. Add a `_paused` flag with defense-in-depth check in `_unload_after_timeout()`.

### Rationale
- The timer uses `asyncio.create_task()` + `asyncio.sleep()`, but `_run_indexing()` runs in a `threading.Thread`.
- `asyncio.Task.cancel()` must be called from the event loop thread — `call_soon_threadsafe()` is the correct bridge.
- Cancelling the task entirely (not just setting a flag) eliminates TOCTOU race windows.
- Defense-in-depth: `_unload_after_timeout()` also checks `_paused` as a belt-and-suspenders guard.

### Call Sites
- **Pause**: At the start of `_run_indexing()`, before `llm_pool.close()` (service.py ~L601).
- **Resume**: In the `finally` block after `_init_llm_pool()` and re-wiring, before clearing `_indexing` (service.py ~L718).

### Changes to `get_status()`
Add `"timer_paused": self._paused` to the status dict.
Guard in `on_request_end()`: skip scheduling if `_paused`.

---

## R-03: Context Relevance Critic — Prompt Design

### Decision
Score each chunk individually with a constrained prompt requesting a single digit 0–5. Use `temperature=0.0` and `max_tokens=4` for fast, deterministic output.

### Prompt Template
```
Rate how relevant the following text is to the question on a scale of 0-5.
0 = completely irrelevant, 5 = directly answers the question.

Question: {query}

Text: {chunk_content}

Relevance score (respond with ONLY a single number 0-5):
```

### Score Parsing
Regex `\b([0-5])\b` on stripped output. Handles clean digits, verbose responses ("I'd rate this a 4"), and noisy output. Returns `None` on failure → fail-open (include chunk, assign threshold score).

### Performance
| Scenario | Estimate |
|----------|----------|
| Per-call (GPU, Phi-3) | ~100–200ms |
| 15 chunks total (GPU) | ~1.5–3s |
| Per-call (CPU) | ~500–1000ms |
| 15 chunks total (CPU) | ~7.5–15s |

Critic is **disabled by default** (FR-032). Opt-in latency trade-off.

### Optimizations
- Short-circuit chunks < 50 chars (FR-036) — bypass scoring, include automatically.
- Low `max_tokens=4` minimizes generation time per call.
- Consider scoring only bottom-ranked chunks (ranks 8–15) as an optional optimization.

### Batching
Individual calls, one per chunk. Batch-all-in-one-prompt rejected: fragile parsing, context window limits, prevents per-chunk fail-open.

---

## R-04: Domain Lexicon Term Matching

### Decision
Case-insensitive whole-word boundary matching via pre-compiled regex patterns. Rank matches by term length (longer = more specific), cap at 10 entries or 1,500 chars.

### Matching Algorithm
```python
pattern = r'\b' + re.escape(term.lower()) + r'\b'
```
- Matches "query engine" in "how does the query engine work?" but not "engineer" from "engineering".
- Multi-word terms matched as contiguous subsequences with word boundaries.
- Pre-compile all patterns at lexicon load time (~2ms for 500 entries).

### Selection Strategy
- Sort matches by term length descending (more specific first).
- Cap at 10 entries or 1,500 characters (whichever reached first).
- FR-024 satisfied: limits injected content to stay within prompt size constraints.

### Injection Point
Append to the **system prompt** (not user message):
```
Project glossary (use these definitions when the terms appear):
- kragd: The krag service daemon — a FastAPI server...
- RRF: Reciprocal Rank Fusion — a score merging algorithm...
```
System prompt is the instruction layer; lexicon entries are instructions about terminology.

### Performance
- 500 entries: ~0.5ms per query (cached patterns), negligible.
- No new dependencies required.

---

## R-05: Mode TOML Schema Design

### Decision
Modes are defined as TOML files in `~/.config/krag/modes/`. Each file defines one mode with a fixed schema.

### Schema
```toml
[mode]
name = "code"
description = "Optimized for source code queries"

[collections]
code = 0.7    # weight
tests = 0.3   # weight

[llm]
slot = "code"  # "text" or "code"

[prompt]
preset = "code"  # "strict", "balanced", "verbose", "code"

[retrieval]
top_k = 10
similarity_threshold = 0.15

[critic]
enabled = false
threshold = 3
```

### Built-in Modes
| Mode | Collections | LLM | Preset | Critic |
|------|-------------|-----|--------|--------|
| `default` | all (1.0 each) | text | balanced | off |
| `code` | code (0.7), tests (0.3) | code | code | off |
| `docs` | docs (1.0) | text | balanced | off |

### Loading Precedence
1. Built-in modes (shipped with krag in `src/krag/modes/builtin/`)
2. User-defined modes (`~/.config/krag/modes/*.toml`)
3. User modes override built-in modes with the same name.

### Validation
- `name` must match filename (sans `.toml`).
- `collections` keys must be in `{code, tests, docs, text}`.
- `slot` must be in `{text, code}`.
- `preset` must be in `PROMPT_PRESETS`.
- `top_k` must be positive integer.
- `similarity_threshold` must be 0.0–1.0.
- `critic.threshold` must be 0–5.

---

## R-06: Multi-Collection Query Fusion

### Decision
Extend the existing RRF merger to support per-collection weighting. After RRF computes base scores, multiply each document's score by its collection's weight before final ranking.

### Algorithm
1. Query each targeted collection independently (separate `search_named()` calls).
2. Tag each result with its source collection.
3. Merge all results via weighted RRF:
   - Standard RRF score per document per result list.
   - Multiply by the collection's weight from the mode config.
   - Sum weighted scores across all lists for each document.
4. Sort by final weighted score, deduplicate, trim to `top_k`.

### Integration with Existing RRF
`reciprocal_rank_fusion()` in `rrf.py` currently takes `list[list[ScoredPoint]]`. Extend to accept `list[tuple[list[ScoredPoint], float]]` where the float is the collection weight. Default weight = 1.0 (backward compatible).

### Two-Level Fusion
Each collection may have named vector spaces (e.g., code collection has both `text` and `code` spaces). Within a single collection, multi-model search uses the existing RRF. Across collections, a second RRF pass merges cross-collection results:
- Level 1: Multi-model RRF within each collection (existing behavior).
- Level 2: Weighted RRF across collections (new).

---

## R-07: Collection Routing Rules

### Decision
Ordered precedence chain — first matching rule wins.

### Precedence (highest to lowest)

| Priority | Rule Type | Pattern | → Collection |
|----------|-----------|---------|--------------|
| 0 | Plugin override | `handler.preferred_collection()` | plugin-declared |
| 1 | Test directory | Path contains `tests/`, `test/`, `__tests__/`, `spec/`, `e2e/` | `tests` |
| 2 | Test filename | `test_*.py`, `*_test.go`, `*.test.ts`, `*.spec.ts`, `conftest.py`, etc. | `tests` |
| 3 | Well-known docs | Filename is `README`, `CHANGELOG`, `LICENSE`, `CONTRIBUTING`, `AUTHORS` (any ext) | `docs` |
| 4 | Docs extension | `.md`, `.rst`, `.adoc`, `.mdx`, `.org`, `.markdown` | `docs` |
| 5 | Code extension | `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.cpp`, `.c`, `.h`, `.rb`, `.swift`, `.kt`, `.cs`, `.scala`, `.ex`, `.clj`, `.hs`, `.lua`, `.r`, `.jl`, `.pl`, `.php`, `.sh`, `.bash`, `.zsh`, `.fish`, `.sql`, `.proto`, `.graphql` + more | `code` |
| 6 | Config/data | `.json`, `.yaml`, `.yml`, `.toml`, `.csv`, `.xml`, `.ini`, `.cfg`, `.env` | `text` |
| 7 | Fallback | Everything else | `text` |

### Key Decisions
- `conftest.py` → `tests` (test infrastructure)
- `.txt` → `text` (too ambiguous for docs)
- `.html`, `.css` → `text` (markup/styling, not programming)
- `.sql`, `.proto`, `.graphql` → `code` (schema/logic languages)
- Markdown inside `tests/` → `tests` (path rules > extension rules, per FR-005)
- Constants consolidated in `src/krag/routing/rules.py` (single source of truth).

---

## R-08: New Dependencies Assessment

### Decision
No new runtime dependencies needed. All features implementable with the existing tool stack.

| Feature | Required Tech | Already Available |
|---------|--------------|-------------------|
| Multi-collection | qdrant-client | Yes (>=1.8.0) |
| Mode TOML loading | tomllib (stdlib 3.11+) | Yes |
| Lexicon JSON loading | json (stdlib) | Yes |
| Lexicon regex matching | re (stdlib) | Yes |
| Critic scoring | llama-cpp-python (via LLMClient) | Yes |
| Timer pause/resume | asyncio (stdlib) | Yes |
| Mode CLI commands | Typer, Rich | Yes |

The user requested "use existing tool stack, adding to it if research shows new needs" — research confirms no additions needed.
