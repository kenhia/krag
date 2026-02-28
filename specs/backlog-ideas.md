# Backlog Ideas

Future sprint candidates and plugin ideas.

## Agent Instructions

As items are moved into sprints/specs, they should be removed from this document
and moved to `specs/archived-backlog.md` (create if it doesn't exist).

---

## Obsidian Plugin

**Priority**: Medium
**Depends on**: Sprint 009 (retrieval modes, multi-collection Qdrant)

### Overview

A plugin specifically designed for indexing local Obsidian vault content. Unlike the current markdown plugin which handles `.md` files generically, this plugin understands Obsidian vault structure and routes content intelligently across collections.

### Key Features

- **Path-based ownership**: Plugin claims all markdown files under a configured vault path, rather than claiming the `.md` extension globally. This requires extending krag's plugin architecture to support path-based (not just extension-based) file type handler registration.

- **Mixed-content routing**: Obsidian notes often contain fenced code blocks declared with a language identifier. The plugin will split note content so that:
  - Declared code blocks (e.g., ` ```python `) are indexed into the `code` collection
  - Remaining markdown prose is indexed into the `docs` collection
  - This exercises the plugin collection routing override (Level 1 in `CollectionRouter`) which currently has no real consumers

- **Virtual path generation**: File paths stored in the index will use a synthetic `obsidian::` prefix, replacing the vault root. For example:
  - Actual path: `~/obsidian/gratch/todo/mynote.md`
  - Stored path: `obsidian::/gratch/todo/mynote.md`
  - Configuration will need a way to declare vault name → local path mappings (e.g., `[plugins.obsidian.vaults]` section)

- **Sprint 009 integration**: An explicit goal is to exercise the new retrieval modes, domain lexicon, and multi-collection features end-to-end:
  - Plugin override routing for mixed code/docs content
  - Custom retrieval mode (e.g., `obsidian` mode targeting `docs` + `code` with vault-appropriate weights)
  - Lexicon entries for Obsidian-specific terminology (backlinks, daily notes, canvas, etc.)
  - Context critic for filtering low-relevance vault fragments

### Architecture Considerations

- Plugin architecture change needed: current `FileTypeHandler.supported_extensions()` is the only mechanism for claiming files. A path-based claim mechanism (e.g., `supported_paths() -> list[Path]` or `claims_file(path: Path) -> bool`) would be needed.
- Conflict resolution with the existing markdown plugin when both are installed — vault-path files should be handled by the Obsidian plugin, non-vault `.md` files by the generic markdown plugin.
- The virtual path scheme needs to integrate with `path_aliases` and the display layer.

