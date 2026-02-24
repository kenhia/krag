# API Extensions: Sprint 009

**Date**: 2026-02-21
**Applies to**: kragd FastAPI service (port 8742) and krag_cli HTTP client

---

## Modified Endpoints

### POST /query

**Request body changes**:

| Field | Type | Default | Change |
|-------|------|---------|--------|
| `mode` | `str \| null` | `null` | NEW — mode name to apply (overrides all below) |
| `llm` | `str \| null` | `null` | DEPRECATED — still works, emits warning, maps to mode |

When `mode` is provided, the mode's configuration takes precedence for `llm`, `preset`, `top_k`, and `similarity_threshold`. Explicitly provided query parameters still override mode defaults.

**Response body changes**:

| Field | Type | Change |
|-------|------|--------|
| `sources[].collection` | `str` | NEW — which collection the chunk came from (`code`, `tests`, `docs`, `text`) |
| `debug.critic_scores` | `list[CriticScore] \| null` | NEW — per-chunk critic scores (only in debug mode) |
| `debug.mode` | `str` | NEW — mode name used for this query |
| `debug.lexicon_terms_injected` | `int` | NEW — count of lexicon terms injected into prompt |
| `debug.collections_searched` | `list[str]` | NEW — which collections were queried |
| `debug.chunks_pre_critic` | `int \| null` | NEW — chunk count before critic filtering |
| `debug.chunks_post_critic` | `int \| null` | NEW — chunk count after critic filtering |

**CriticScore schema**:
```json
{
  "chunk_id": "string",
  "score": 3,
  "passed": true,
  "bypassed": false
}
```

---

### POST /retrieve

**Request body changes**: Same as POST /query (`mode` field added, `llm` deprecated).

**Response body changes**:

| Field | Type | Change |
|-------|------|--------|
| `results[].collection` | `str` | NEW — source collection name |

---

### POST /index

**Response body changes**:

| Field | Type | Change |
|-------|------|--------|
| `collections` | `dict[str, int]` | NEW — per-collection document counts |

---

### GET /status

**Response body changes**:

| Field | Type | Change |
|-------|------|--------|
| `lifecycle.timer_paused` | `bool` | NEW — whether idle timer is paused for indexing |
| `collections` | `dict[str, CollectionStatus]` | NEW — per-collection stats |
| `mode_registry` | `list[str]` | NEW — available mode names |
| `lexicon_loaded` | `bool` | NEW — whether a domain lexicon is active |
| `lexicon_entry_count` | `int` | NEW — number of lexicon entries |

---

## New Endpoints

### POST /lexicon/refresh

Reloads the domain lexicon from disk without restarting the service.

**Request body**: Empty (`{}`)

**Response**:
```json
{
  "status": "ok",
  "entries_loaded": 42,
  "path": "/home/user/.config/krag/lexicon.json"
}
```

**Errors**:
- `404` if no lexicon path configured
- `422` if lexicon file is malformed (validation error details in response)
- `500` if file read fails

---

### GET /modes

Lists all available retrieval modes.

**Response**:
```json
{
  "modes": [
    {
      "name": "default",
      "description": "Balanced search across all collections",
      "collections": ["code", "tests", "docs", "text"],
      "llm_slot": "text",
      "preset": "balanced",
      "is_builtin": true
    },
    {
      "name": "code",
      "description": "Optimized for source code queries",
      "collections": ["code", "tests"],
      "llm_slot": "code",
      "preset": "code",
      "is_builtin": true
    }
  ]
}
```

---

### GET /modes/{name}

Returns the full configuration of a specific mode.

**Response**:
```json
{
  "name": "code",
  "description": "Optimized for source code queries",
  "collections": {"code": 0.7, "tests": 0.3},
  "llm_slot": "code",
  "preset": "code",
  "top_k": 10,
  "similarity_threshold": 0.15,
  "critic_enabled": false,
  "critic_threshold": 3,
  "is_builtin": true
}
```

**Errors**:
- `404` if mode name not found

---

## New CLI Commands

### krag modes list

Displays all available modes in a Rich table.

```
$ krag modes list
╭─────────┬──────────────────────────────────────┬─────────────┬──────┬──────────╮
│ Mode    │ Description                          │ Collections │ LLM  │ Preset   │
├─────────┼──────────────────────────────────────┼─────────────┼──────┼──────────┤
│ default │ Balanced search across all           │ all         │ text │ balanced │
│ code    │ Optimized for source code queries    │ code, tests │ code │ code     │
│ docs    │ Documentation-focused search         │ docs        │ text │ balanced │
╰─────────┴──────────────────────────────────────┴─────────────┴──────┴──────────╯
```

### krag modes show \<name\>

Displays full configuration of a mode.

### krag lexicon refresh

Reloads the domain lexicon from disk.

```
$ krag lexicon refresh
Lexicon reloaded: 42 entries from /home/user/.config/krag/lexicon.json
```

---

## Deprecation: --llm flag

The `--llm text|code` flag on `krag query` and `krag-direct query` is deprecated. When used:

1. Warning printed to stderr: `Warning: --llm is deprecated, use --mode instead`
2. `--llm text` maps to `--mode default`
3. `--llm code` maps to `--mode code`
4. If both `--llm` and `--mode` are provided, `--mode` takes precedence with no warning.

The flag will be removed in a future release.

---

## Wire Protocol Compatibility

All changes are **additive** — new fields in responses, new optional fields in requests. Existing clients that don't send `mode` will function identically (the `default` mode is applied). The `llm` field continues to work with deprecation warnings.
