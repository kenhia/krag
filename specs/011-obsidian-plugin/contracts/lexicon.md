# Contract: Lexicon Extension

**Scope**: `src/krag/lexicon/lexicon_store.py` — `LexiconStore` class

## New Method: `merge_entries`

```python
def merge_entries(self, entries: dict[str, str], source: str = "plugin") -> int:
    """Merge additional entries into the lexicon without replacing existing ones.

    Entries are added to the existing glossary. Existing entries with the
    same key are NOT overwritten (user-defined terms take priority).

    Args:
        entries: Term → definition mapping to merge.
        source: Label for logging (e.g., plugin name).

    Returns:
        Number of new entries added (excludes duplicates).
    """
```

### Behavior

| Scenario | Result |
|----------|--------|
| New term not in lexicon | Added |
| Term already exists (from user JSON) | Skipped (user definition preserved) |
| Empty entries dict | No-op, returns 0 |
| Invalid entry (non-string value) | Skipped with warning |

### Pattern Compilation

After merging, `_compile_patterns()` is called to rebuild regex patterns for the new entries.

---

## Obsidian Lexicon Entries (FR-027)

```json
{
  "backlink": "A link from one note to another note, creating bidirectional navigation between related concepts",
  "daily note": "A dated note automatically created for journaling, daily logs, or capturing ephemeral thoughts",
  "canvas": "An Obsidian visual workspace for arranging and connecting notes spatially on an infinite board",
  "dataview": "An Obsidian community plugin for querying notes as a database using inline metadata and frontmatter fields",
  "template": "A reusable note structure applied when creating new notes to ensure consistent formatting",
  "frontmatter": "YAML metadata block at the top of a markdown note enclosed between triple-dash delimiters",
  "wikilink": "A double-bracket link [[like this]] used to connect notes within an Obsidian vault",
  "MOC": "Map of Content — an index note that organizes links to related notes by topic or theme",
  "tag": "A hash-prefixed label (#tag) used to categorize, filter, and discover notes across a vault",
  "vault": "A root folder containing Obsidian notes, configuration, themes, and community plugins"
}
```

Shipped as `lexicon.json` inside the plugin package. Loaded during `initialize()` and merged via `lexicon_store.merge_entries()`.
