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

## Code embedding moved into krag

Move the code specific embedding model, `jinaai/jina-embeddings-v2-base-code`, from
`examples/krag-plugin-code/src/krag_plugin_code/handler.py` so it's part of the base krag code; adding config section
`[embedding_code]`. Consider moving "code" settings currently in `[llm]` to `[llm_code]`

- Question: should code have a different `context_size`, `temperature`, etc?

## `query` and `query --debug` use different code paths.

This makes `--debug` not a great tool for debugging 😊  
My thinking is the we combine these code paths into one with the difference that if `--debug` is present we return
more information.

## Incremental indexing treats directory change as full delete+re-add

**Priority**: Medium

When running `krag index -d ~/src/bits-and-pieces/` followed by `krag index -d ~/src/`, the second run
deletes all files from the first run and re-indexes them. The `ChangeDetector.categorize_changes()` compares
the current file scan against `previous_metadata` — but `_load_metadata()` filters metadata to only files
within the *current* `directory_paths`. When the directory changes from `~/src/bits-and-pieces/` to `~/src/`,
the metadata for files under `~/src/bits-and-pieces/` is loaded (since it's a subdirectory of `~/src/`), but
the file scanner discovers all of `~/src/` as new files. The previously indexed `bits-and-pieces` files appear
in the scan *and* in metadata, so they should match as UNCHANGED — **but** metadata is saved with only the
successfully-processed files from the current run. The indexer creates a fresh `Indexer` instance per run
(in `_run_indexing`), and `_save_metadata()` overwrites `metadata.json` with only the current run's
`indexed_files` dict, discarding metadata for files that were unchanged and not re-processed.

This means every directory change causes a full re-index of overlapping files, with unnecessary delete+re-add
cycles against Qdrant. The fix should preserve metadata for unchanged files across runs.

## `index-status` returns stale result while indexing is in progress

**Priority**: Medium

After starting a second indexing run, `krag index-status` returns the completed result from the first run
rather than reporting that indexing is in progress. The root cause: `start_indexing()` sets `self._indexing = True`
and creates a `running_response` stored in `self._last_index_job`, but `get_index_status()` only checks
`self._indexing` when `self._index_job_cache` is empty. After the first run completes, `_index_job_cache`
contains the first run's result. When the second run starts, `_index_job_cache` is still populated, so
`get_index_status()` returns the cached first-run result without ever checking `self._indexing`.

The fix should check `self._indexing` *before* returning cached results, and return a `status="running"`
response whenever indexing is active, regardless of cache state.

## Little tweaks

Things that can be pulled into any sprint (small tweaks/refinements)

- When `kragd` starts, issue a log entry of the effect "KRAGD STARTING UP", then when it is ready to receive
  connections, "KRAGD READY". If we can catch that it's shutting down, then also "KRAGD SHUTTING DOWN". This will "bookmark" things in the logs making it easier to see when things happen.
- Add a `--rotate-logs` switch for the `kragd` command to rotate the logs before startup...helpful when debugging.
- Responses often contain markdown syntax, can we use markdown formatting from `rich`?