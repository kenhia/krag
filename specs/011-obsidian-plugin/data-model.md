# Data Model: 011-obsidian-plugin

**Branch**: `011-obsidian-plugin` | **Date**: 2026-02-27

## Entities

### Vault

A named mapping from a human-readable identifier to a local filesystem path.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `name` | `str` | Non-empty, alphanumeric + hyphens/underscores | Config key, used in virtual path prefix |
| `path` | `Path` | Must be a directory (warn if missing, don't error) | Resolved via `expanduser().resolve()` |

**Source**: `[plugins.obsidian.vaults]` section in `config.toml`

**Example**:
```toml
[plugins.obsidian.vaults]
gratch = "~/obsidian/gratch"
work = "/data/vaults/work"
```

**Pydantic model**: `ObsidianConfig` in plugin's `config.py`:
```python
class ObsidianConfig(BaseModel):
    vaults: dict[str, str] = Field(default_factory=dict)
```

---

### ContentSegment

A contiguous section of a note — either prose or a fenced code block. Internal to the plugin chunker; not persisted directly but translated into `TextChunk` objects with routing metadata.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `text` | `str` | Non-empty | Raw text content of the segment |
| `segment_type` | `Literal["prose", "code"]` | | Determines target collection |
| `language` | `str \| None` | | Language identifier from fence (e.g., `python`). `None` for prose and untagged code blocks |
| `start_line` | `int` | >= 0 | Line number in the original note |

**Routing rules**:
- `segment_type == "code"` AND `language is not None` → `target_collection = "code"`
- `segment_type == "code"` AND `language is None` → `target_collection = "docs"` (treated as prose per FR-012)
- `segment_type == "prose"` → `target_collection = "docs"`

---

### Virtual Path

Synthetic path replacing filesystem location in stored payloads. Not a separate entity — a transformation applied during chunk creation.

| Component | Value | Example |
|-----------|-------|---------|
| Scheme | `obsidian://` | |
| Vault name | From config key | `gratch` |
| Relative path | File path relative to vault root | `projects/todo.md` |
| Full virtual path | `obsidian://<vault>/<relative>` | `obsidian://gratch/projects/todo.md` |

**Determinism** (FR-017): Same file + same vault config → same virtual path (no random components).

---

### Chunk Payload Extensions

Additional fields in vector payloads produced by the Obsidian plugin, beyond the standard krag payload fields.

| Field | Type | When Present | Notes |
|-------|------|-------------|-------|
| `target_collection` | `str` | Always (removed after routing) | `"code"` or `"docs"` — consumed by indexer, not stored |
| `language` | `str` | Code segments with language tag | e.g., `"python"`, `"javascript"` |
| `vault_name` | `str` | Always | Which vault this chunk came from |
| `content_type` | `str` | Always | `"prose"` or `"code"` |

---

## Relationships

```
Vault (1) ────── (*) Note (.md file)
  │                    │
  │                    ├── (*) ContentSegment (prose)
  │                    │        └── target: docs collection
  │                    │
  │                    └── (*) ContentSegment (code)
  │                             └── target: code collection
  │
  └── Virtual Path = obsidian://{vault.name}/{note.relative_path}
```

## State Transitions

### Plugin Initialization

```
UNINITIALIZED
  → initialize(config, context)
    → Validate ObsidianConfig
    → Resolve vault paths
    → Skip missing vaults (warn)
    → Merge lexicon entries
  → READY (vault_paths populated)
```

### File Processing

```
FILE_RECEIVED (via claims_file → extract_text)
  → Resolve vault membership (which vault?)
  → Read file content
  → Parse frontmatter (YAML between --- delimiters)
  → Split into ContentSegments
  → Apply virtual path prefix
  → SEGMENTS_READY

SEGMENTS_READY (via custom chunker)
  → Chunk each segment
  → Annotate chunks with target_collection + metadata
  → CHUNKS_READY (returned to indexer)
```

## Validation Rules

| Rule | Entity | Constraint |
|------|--------|-----------|
| V-01 | Vault name | Must be non-empty string, valid as path component |
| V-02 | Vault path | Must be a directory; missing paths logged as warning, not error |
| V-03 | ContentSegment | Text must be non-empty after stripping whitespace |
| V-04 | Virtual path | Must start with `obsidian://` and contain vault name as second component |
| V-05 | Fenced code block | Opening and closing fence backtick count must match |
| V-06 | Language identifier | If present, must be a non-empty string (no validation of actual language names) |
