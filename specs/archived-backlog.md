# Archived Backlog

Items moved from `backlog-ideas.md` when they were included in a sprint.

---

## Sprint 010 — Infrastructure Improvements & Polish

### Code embedding moved into krag

Move the code specific embedding model, `jinaai/jina-embeddings-v2-base-code`, from
`examples/krag-plugin-code/src/krag_plugin_code/handler.py` so it's part of the base krag code; adding config section
`[embedding_code]`. Consider moving "code" settings currently in `[llm]` to `[llm_code]`

- Question: should code have a different `context_size`, `temperature`, etc?

### `query` and `query --debug` use different code paths

This makes `--debug` not a great tool for debugging 😊  
My thinking is the we combine these code paths into one with the difference that if `--debug` is present we return
more information.

### Incremental indexing treats directory change as full delete+re-add

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

### `index-status` returns stale result while indexing is in progress

**Priority**: Medium

After starting a second indexing run, `krag index-status` returns the completed result from the first run
rather than reporting that indexing is in progress. The root cause: `start_indexing()` sets `self._indexing = True`
and creates a `running_response` stored in `self._last_index_job`, but `get_index_status()` only checks
`self._indexing` when `self._index_job_cache` is empty. After the first run completes, `_index_job_cache`
contains the first run's result. When the second run starts, `_index_job_cache` is still populated, so
`get_index_status()` returns the cached first-run result without ever checking `self._indexing`.

The fix should check `self._indexing` *before* returning cached results, and return a `status="running"`
response whenever indexing is active, regardless of cache state.

### Little tweaks

Things that can be pulled into any sprint (small tweaks/refinements)

- When `kragd` starts, issue a log entry of the effect "KRAGD STARTING UP", then when it is ready to receive
  connections, "KRAGD READY". If we can catch that it's shutting down, then also "KRAGD SHUTTING DOWN". This will "bookmark" things in the logs making it easier to see when things happen.
- Add a `--rotate-logs` switch for the `kragd` command to rotate the logs before startup...helpful when debugging.
- Responses often contain markdown syntax, can we use markdown formatting from `rich`?
