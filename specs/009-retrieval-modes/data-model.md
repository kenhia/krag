# Data Model: Sprint 009 — Retrieval Modes, Multi-Collection Qdrant, Domain Lexicon, and Context Critic

**Date**: 2026-02-21
**Source**: [spec.md](spec.md), [research.md](research.md)

---

## Entity Overview

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  CollectionStore │     │ ModeConfiguration│     │  LexiconStore    │
│                  │◄────│                  │     │                  │
│  name            │     │  name            │     │  path            │
│  embedding_model │     │  collections{}   │     │  entries{}       │
│  vector_params   │     │  llm_slot        │     │  patterns[]      │
│  vector_store    │     │  preset          │     └──────────────────┘
└──────────────────┘     │  retrieval{}     │            │
        │                │  critic{}        │            │
        │                └──────────────────┘            │
        ▼                        │                      ▼
┌──────────────────┐             │              ┌──────────────────┐
│ CollectionManager│             │              │ LexiconInjector  │
│                  │             ▼              │                  │
│  client (shared) │     ┌──────────────────┐   │  match_terms()   │
│  stores{}        │     │ RelevanceCritic  │   │  format_glossary │
│  router          │     │                  │   └──────────────────┘
└──────────────────┘     │  llm_client      │
        │                │  threshold       │
        ▼                │  enabled         │
┌──────────────────┐     └──────────────────┘
│ CollectionRouter │
│                  │
│  route(path) →   │
│    collection    │
└──────────────────┘
```

---

## Entities

### 1. CollectionStore

Represents one of the four content-type-specific Qdrant collections.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Collection identifier: `code`, `tests`, `docs`, `text` |
| `collection_name` | `str` | Qdrant collection name: `krag_code`, `krag_tests`, `krag_docs`, `krag_text` |
| `embedding_model` | `str` | HuggingFace model name for this collection's content type |
| `vector_size` | `int` | Embedding dimension (768 for code models, 768 for bge-base) |
| `vector_store` | `QdrantVectorStore` | Qdrant wrapper instance (shares client with siblings) |

**Relationships**:
- Owned by `CollectionManager` (1 manager → 4 stores)
- Referenced by `ModeConfiguration.collections` (many-to-many via weights)
- Uses shared `QdrantClient` from `CollectionManager`

**Validation Rules**:
- `name` must be one of: `code`, `tests`, `docs`, `text`
- `collection_name` = `f"krag_{name}"`
- `embedding_model` must be loadable by `sentence-transformers`

---

### 2. CollectionManager

Manages the lifecycle of the shared Qdrant client and the four collection stores.

| Field | Type | Description |
|-------|------|-------------|
| `client` | `QdrantClient` | Shared embedded Qdrant client (single path) |
| `storage_path` | `Path` | Qdrant storage directory |
| `stores` | `dict[str, CollectionStore]` | Map of collection name → store |
| `router` | `CollectionRouter` | File-to-collection routing logic |

**Lifecycle**:
- Created once at service/indexer startup
- Owns the `QdrantClient` file lock
- `close()` closes the shared client
- All stores share the same client instance

---

### 3. CollectionRouter

Routes files to the appropriate collection based on path patterns and file extensions.

| Field | Type | Description |
|-------|------|-------------|
| `plugin_overrides` | `dict[str, str]` | Plugin name → preferred collection |

**Methods**:
| Method | Signature | Returns |
|--------|-----------|---------|
| `route` | `(file_path: Path, file_ext: str, plugin_name: str \| None) -> str` | Collection name |

**Routing Precedence** (first match wins):
1. Plugin override → plugin-declared collection
2. Test directory pattern → `tests`
3. Test filename pattern → `tests`
4. Well-known doc filename → `docs`
5. Docs extension → `docs`
6. Code extension → `code`
7. Config/data extension → `text`
8. Fallback → `text`

**State**: Stateless (pure function with configuration). May cache compiled path patterns.

---

### 4. ModeConfiguration

A named retrieval configuration loaded from a TOML file.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | — | Mode identifier (case-insensitive) |
| `description` | `str` | `""` | Human-readable description |
| `collections` | `dict[str, float]` | all at 1.0 | Target collections with weights |
| `llm_slot` | `str` | `"text"` | LLM to use: `"text"` or `"code"` |
| `preset` | `str` | `"balanced"` | Prompt preset name |
| `top_k` | `int` | `5` | Number of results to retrieve |
| `similarity_threshold` | `float` | `0.2` | Minimum similarity score |
| `critic_enabled` | `bool` | `False` | Whether context critic is active |
| `critic_threshold` | `int` | `3` | Minimum critic score (0–5) |

**Validation Rules**:
- `name` must be non-empty, lowercase alphanumeric + hyphens
- `collections` keys must be subset of `{code, tests, docs, text}`
- `collections` values must be in range (0.0, 1.0]
- `llm_slot` must be `"text"` or `"code"`
- `preset` must be in `PROMPT_PRESETS` keys
- `top_k` must be >= 1
- `similarity_threshold` must be in [0.0, 1.0]
- `critic_threshold` must be in [0, 5]

**State Transitions**: None — modes are immutable configurations loaded from disk.

---

### 5. ModeRegistry

Registry of available modes (built-in + user-defined).

| Field | Type | Description |
|-------|------|-------------|
| `modes` | `dict[str, ModeConfiguration]` | Registered modes (name → config) |
| `builtin_dir` | `Path` | Path to built-in mode TOML files |
| `user_dir` | `Path` | Path to user-defined mode TOML files |

**Methods**:
| Method | Signature | Returns |
|--------|-----------|---------|
| `get` | `(name: str) -> ModeConfiguration` | Mode config (raises `ValueError` if not found) |
| `list_modes` | `() -> list[ModeConfiguration]` | All registered modes |
| `reload` | `() -> None` | Re-scan directories, reload all modes |

**Loading Precedence**: Built-in first, then user-defined (user overrides built-in on name collision).

---

### 6. LexiconStore

Project-specific terminology glossary loaded from a JSON file.

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path \| None` | Source JSON file path |
| `entries` | `dict[str, str]` | Term → definition mapping |
| `_patterns` | `dict[str, re.Pattern]` | Pre-compiled regex patterns per term |

**Methods**:
| Method | Signature | Returns |
|--------|-----------|---------|
| `match_terms` | `(query: str) -> list[tuple[str, str]]` | Matched (term, definition) pairs |
| `select_top` | `(matches, max_entries=10, max_chars=1500) -> list[tuple[str, str]]` | Top-N by specificity |
| `reload` | `() -> None` | Reload from disk, recompile patterns |
| `format_glossary` | `(entries) -> str` | Format for prompt injection |

**Validation Rules**:
- JSON must be `dict[str, str]` (all keys and values are strings)
- Malformed JSON raises `LexiconValidationError` at load time (FR-026)
- Empty lexicon is valid (no entries injected)

**State Transitions**: Loaded → Reloaded (via `refresh` command)

---

### 7. RelevanceCritic

Scores retrieved chunks for relevance to the query.

| Field | Type | Description |
|-------|------|-------------|
| `llm_client` | `LLMClient` | The LLM used for scoring |
| `enabled` | `bool` | Whether critic is active |
| `threshold` | `int` | Minimum passing score (0–5, default 3) |

**Methods**:
| Method | Signature | Returns |
|--------|-----------|---------|
| `score_chunks` | `(query: str, chunks: list[QueryResult]) -> list[ScoredChunk]` | Chunks with scores |
| `filter_chunks` | `(scored: list[ScoredChunk]) -> list[QueryResult]` | Passing chunks only |

**Nested Type: ScoredChunk**:
| Field | Type | Description |
|-------|------|-------------|
| `chunk` | `QueryResult` | Original chunk |
| `critic_score` | `int` | Relevance score 0–5 |
| `bypassed` | `bool` | True if scoring was skipped (too short, or error) |
| `passed` | `bool` | Whether score >= threshold |

**Behavior Rules**:
- Chunks < 50 chars → bypass scoring, assign threshold score, `bypassed=True` (FR-035)
- LLM error → fail-open, assign threshold score, `bypassed=True` (FR-034)
- Score parse failure → fail-open, assign threshold score (FR-034)
- All chunks filtered → return empty list (caller handles insufficient context, FR-033)

---

### 8. RoutingRule (Value Object)

Defines a single file-to-collection routing rule.

| Field | Type | Description |
|-------|------|-------------|
| `priority` | `int` | Evaluation order (lower = higher priority) |
| `rule_type` | `str` | `"plugin"`, `"path"`, `"filename"`, `"well_known"`, `"extension"`, `"fallback"` |
| `pattern` | `str \| re.Pattern \| set[str]` | Match pattern (path regex, extension set, etc.) |
| `target_collection` | `str` | Destination collection name |

---

## Configuration Extensions

### New fields on `Configuration`

| Field | Type | Default | TOML Section |
|-------|------|---------|-------------|
| `modes_dir` | `Path` | `~/.config/krag/modes` | `[modes]` |
| `default_mode` | `str` | `"default"` | `[modes]` |
| `lexicon_path` | `Path \| None` | `None` | `[lexicon]` |
| `lexicon_max_entries` | `int` | `10` | `[lexicon]` |
| `lexicon_max_chars` | `int` | `1500` | `[lexicon]` |
| `critic_enabled` | `bool` | `False` | `[critic]` |
| `critic_threshold` | `int` | `3` | `[critic]` |

### Updated `ServiceConfiguration`

No new fields — mode, lexicon, and critic settings come from mode configs and global config.

---

## Relationships Diagram

```
Configuration
  ├── modes_dir ──────────► ModeRegistry
  │                            ├── ModeConfiguration "default"
  │                            ├── ModeConfiguration "code"
  │                            └── ModeConfiguration "docs"
  ├── lexicon_path ───────► LexiconStore
  │                            └── entries: {term: definition}
  └── vector_store_path ──► CollectionManager
                               ├── QdrantClient (shared)
                               ├── CollectionStore "code"
                               ├── CollectionStore "tests"
                               ├── CollectionStore "docs"
                               └── CollectionStore "text"
                                    └── CollectionRouter (routing rules)

Query Flow:
  User ──[--mode code]──► ModeConfiguration
                            ├── collections: {code: 0.7, tests: 0.3}
                            ├── llm_slot: "code"
                            ├── preset: "code"
                            └── critic: {enabled: false}
                                    │
                                    ▼
                          CollectionManager.query(collections, query)
                            ├── search krag_code (weighted 0.7)
                            ├── search krag_tests (weighted 0.3)
                            └── merge via weighted RRF
                                    │
                                    ▼
                          [RelevanceCritic.score_chunks() — if enabled]
                                    │
                                    ▼
                          [LexiconStore.match_terms() → inject glossary]
                                    │
                                    ▼
                          PromptBuilder.build(context, query, glossary)
                                    │
                                    ▼
                          LLMClient.generate() — via "code" slot
```
