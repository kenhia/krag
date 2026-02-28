# Research: 011-obsidian-plugin

**Branch**: `011-obsidian-plugin` | **Date**: 2026-02-27

## Research Topics

### R-01: Chunk-Level Collection Routing

**Context**: The current indexer routes an entire file to one collection via `CollectionManager.route_file()`. The Obsidian plugin needs fenced code blocks routed to `code` and prose to `docs` — from the same file.

**Decision**: Per-chunk `target_collection` payload metadata (Option D).

**Rationale**: The existing `get_chunk_metadata()` → `payload.update()` pipeline already flows custom metadata from chunkers into vector payloads. The Obsidian plugin's custom chunker adds `target_collection` to each chunk's metadata. The indexer inspects the payload field post-`_process_file()` and routes per-chunk instead of per-file. This requires ~10 lines of new indexer code in two places (`index_full()` and `index_incremental()`), zero changes to `_process_file()`, and zero changes to `FileTypeHandler` or `FileProcessingResult`.

**Alternatives Considered**:

| Option | Description | Rejected Because |
|--------|-------------|------------------|
| A — Extend `FileProcessingResult` | Add `routed_vectors: dict[str, list]` to the result dataclass | Conflates processing with routing; redundant since grouping can happen post-return |
| B — New `extract_content_segments()` method | New ABC method returning `list[ContentSegment]` with text + target collection | Creates a parallel code path through extract→chunk→embed; largest change surface; mixes routing concern into extraction |
| C — Multiple `_process_file()` calls | Capability-flagged multi-call per file | Invasive loop rewrite; ambiguous file-level bookkeeping (error counts, progress) |

**Implementation sketch**:

```python
# In index_full() and index_incremental(), after _process_file():
if self.collection_manager is not None:
    has_chunk_routing = any(
        v.get("payload", {}).get("target_collection")
        for v in result.vectors
    )
    if has_chunk_routing:
        for vec in result.vectors:
            coll = vec.get("payload", {}).pop("target_collection", None)
            if coll is None:
                coll = self.collection_manager.route_file(
                    file_metadata.file_path, plugin_name=plugin_name
                )
            routed_vectors.setdefault(coll, []).append(vec)
    else:
        collection = self.collection_manager.route_file(
            file_metadata.file_path, plugin_name=plugin_name
        )
        routed_vectors.setdefault(collection, []).extend(result.vectors)
```

---

### R-02: Path-Based Plugin Claiming

**Context**: `get_handler_for_file()` resolves handlers by extension only. The Obsidian plugin needs to claim `.md` files only when they reside under a vault path, without conflicting with the generic markdown plugin.

**Decision**: Add `claims_file(file_path: Path) -> bool` to `FileTypeHandler` (default `False`), add `has_claims_file` metadata flag to `PluginMetadata`, modify `get_handler_for_file()` to check path-claiming plugins first.

**Rationale**: Two-phase resolution — Phase 1 iterates only `has_claims_file=True` plugins (detected at discovery via method resolution check) and calls `claims_file()`. Phase 2 falls through to existing extension-based logic. The `has_claims_file` flag ensures non-claiming plugins (all existing ones) are never iterated, keeping overhead at zero for the common case.

**Alternatives Considered**:

| Option | Description | Rejected Because |
|--------|-------------|------------------|
| Merge into `can_handle_file()` | Overload the existing method to support path-based claiming | Breaks semantic contract — `can_handle_file()` is "can I process this type", not "do I own this path". Extension-based plugins would need to be aware of path priority. |
| Static path prefixes | A `claimed_path_prefixes()` method returning `list[Path]` for trie-based lookup | Over-engineered for 1–2 claiming plugins; vault paths are dynamic (from config, not static on class) |
| Always eager-load all plugins | Load all plugins at startup so `claims_file()` works | Defeats lazy loading; increases startup time for no benefit when most users don't have claiming plugins |

**Performance**: Path check is `file_path.resolve().is_relative_to(vault_path)` — pure string comparison, <1μs per vault. With the `has_claims_file` filter, only the Obsidian plugin is checked. SC-005 (<10ms overhead per file) is easily met.

---

### R-03: Fenced Code Block Splitting

**Context**: The plugin must split Obsidian note content into prose segments and fenced code blocks (FR-010 through FR-014). Standard CommonMark fencing uses triple backticks with optional language identifier.

**Decision**: Custom `ObsidianChunker` that splits content using regex-based fenced code block detection, then produces separate `TextChunk` objects with routing metadata.

**Rationale**: CommonMark fenced code block syntax is well-defined: line starting with ```` ``` ```` + optional language, terminated by matching ```` ``` ````. A simple state machine or regex is sufficient. The chunker annotates each chunk with `target_collection` and optional `language` metadata via `get_chunk_metadata()`.

**Implementation approach**:

1. Split raw content using `re.split()` on fence patterns
2. Classify each segment as `prose` or `code` with optional language tag
3. For each prose segment: chunk normally into `TextChunk` objects, mark `target_collection = "docs"`
4. For each code segment: chunk as-is (code blocks are typically small enough for one chunk), mark `target_collection = "code"` and `language = <identifier>`
5. Code blocks without a language identifier are treated as prose (FR-012) → `target_collection = "docs"`

**Regex pattern**: ```^(`{3,})(\w+)?\s*$``` (matches opening fence), ```^`{3,}\s*$``` (matches closing fence)

**Edge cases**:
- Indented code blocks (4 spaces) — NOT treated as fenced, stay as prose
- Nested fences with different counts — handled by matching fence length
- Language identifiers with special chars (`c++`, `c#`) — captured as-is

---

### R-04: Virtual Path Scheme

**Context**: FR-016 through FR-018 require replacing filesystem paths with `obsidian://vault-name/relative-path` in all stored metadata.

**Decision**: The plugin's `extract_text()` and `extract_metadata()` methods receive the real file path. Virtual path replacement happens at chunk creation time in the custom chunker, which has access to the vault configuration. The `file_path` field in each chunk's payload is set to the virtual path.

**Rationale**: Replacing the path at chunk/payload level means the indexer doesn't need to know about virtual paths — it just stores what the plugin puts in `chunk.file_path`. The real path is still needed for file I/O (reading content), but the stored path for retrieval display is virtual.

**Scheme**: `obsidian://<vault-name>/<relative-path>` where `<vault-name>` is the configured vault key and `<relative-path>` is the file path relative to the vault root.

**Example**: File at `~/obsidian/gratch/projects/todo.md` with vault config `gratch = "~/obsidian/gratch"` → stored as `obsidian://gratch/projects/todo.md`.

**Implementation**: The `TextChunk` objects use `file_path` (a string in payloads). The chunker sets this to the virtual path. The `FileMetadata.file_path` passed to `_process_file()` remains the real path for file reading.

---

### R-05: Lexicon Contribution Pattern

**Context**: FR-026/FR-027 require the plugin to contribute Obsidian-specific terms to the domain lexicon on initialization.

**Decision**: Ship a bundled `obsidian-lexicon.json` file inside the plugin package. During `initialize()`, the plugin loads this JSON and merges it into the `LexiconStore` via the `PluginContext`.

**Rationale**: The `LexiconStore` loads terms from a JSON file (`dict[str, str]`). The `PluginContext` provides access to krag services. The plugin can either: (a) write a temporary JSON and call `lexicon_store.load()`, or (b) contribute entries directly (requires a small extension to `LexiconStore`).

**Preferred**: Add a `merge_entries(entries: dict[str, str])` method to `LexiconStore` that adds entries without replacing the existing loaded file. This is cleaner than file I/O and supports multiple plugins contributing terms.

**Terms** (minimum per FR-027):
- backlink: "A link from one note to another, creating bidirectional navigation"
- daily note: "A dated note automatically created for journaling or daily logs"
- canvas: "An Obsidian visual workspace for arranging notes spatially"
- dataview: "An Obsidian plugin for querying notes as a database using metadata"
- template: "A reusable note structure applied when creating new notes"
- frontmatter: "YAML metadata at the top of a markdown note between --- delimiters"
- wikilink: "A double-bracket link [[like this]] connecting notes within a vault"
- MOC: "Map of Content — a note that organizes links to related notes by topic"
- tag: "A #-prefixed label used to categorize and filter notes"
- vault: "A root folder containing Obsidian notes, settings, and plugins"

---

### R-06: Plugin Package Structure

**Context**: The plugin needs to be a separate installable package following the existing krag plugin conventions.

**Decision**: Follow the `krag-plugin-markdown` pattern exactly — `hatchling` build, `krag.plugins` entry point group, `krag` as a dependency.

**Structure**:
```
examples/krag-plugin-obsidian/
├── pyproject.toml
├── README.md
├── src/
│   └── krag_plugin_obsidian/
│       ├── __init__.py
│       ├── handler.py          # ObsidianFileTypeHandler
│       ├── chunker.py          # ObsidianChunker (content splitting)
│       ├── config.py           # Pydantic config schema
│       └── lexicon.json        # Bundled Obsidian terms
└── tests/
    ├── test_handler.py
    ├── test_chunker.py
    └── test_config.py
```

**Entry point**: `obsidian = "krag_plugin_obsidian.handler:ObsidianFileTypeHandler"`

**Dependencies**: `krag` (core), `pyyaml` (for frontmatter parsing, same as markdown plugin).

---

### R-07: Retrieval Mode Definition

**Context**: FR-023 through FR-025 require a built-in `obsidian` retrieval mode.

**Decision**: Add `src/krag/modes/builtin/obsidian.toml` following the exact pattern of existing modes.

**Rationale**: The `ModeLoader` loads all `.toml` files from the builtin directory automatically. No code changes needed — just add the file.

**Configuration**:
```toml
[mode]
name = "obsidian"
description = "Optimized for Obsidian vault content queries"

[collections]
docs = 1.0
code = 0.7

[llm]
slot = "text"

[prompt]
preset = "balanced"

[retrieval]
top_k = 8
similarity_threshold = 0.15

[critic]
enabled = true
threshold = 3
```

Weights: `docs = 1.0` (primary vault prose), `code = 0.7` (inline code snippets). `tests` and `text` excluded — vaults don't typically contain test files or config data.
