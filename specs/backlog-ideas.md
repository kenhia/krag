# Backlog Ideas

Future sprint candidates and plugin ideas.

## Agent Instructions

As items are moved into sprints/specs, they should be removed from this document
and moved to `specs/archived-backlog.md` (create if it doesn't exist).

---

## Debug Metadata Accuracy (krag core)

Found during 014-krager-enhancements UAT. Two issues with `per_space_result_counts`
and multi-model retrieval in multi-collection mode.

> **Retest on both `krag` CLI (`--debug`) and `krager` (debug toggle) when addressed.**

### 1. `per_space_result_counts` shows `{'default': 120}` instead of per-collection breakdown

`_multi_collection_retrieve` in `retriever.py` does not set `_last_per_space_counts`.
The debug builder in `service.py` falls back to labelling all candidates as `"default"`.
Should report per-collection counts (e.g. `{'code': 60, 'tests': 60}`).

- `src/krag/retrieval/retriever.py` — `_multi_collection_retrieve` needs to populate
  `_last_per_space_counts` with per-collection result counts.
- `src/kragd/service.py` — debug metadata builder (lines ~629-656) should consume
  per-collection counts when available.

### 2. Multi-model embeddings not used during multi-collection retrieval

`_multi_collection_retrieve` calls `self.embedding_generator.generate_single(query)`
(primary model only) and then `vs.search()` which falls back to the `"text"` vector
space. The secondary embedding model (e.g. jina-code) stored in named vector spaces
is never searched in multi-collection mode. Multi-model and multi-collection
retrieval strategies are currently mutually exclusive.

- Consider a combined path: for each collection, do `_multi_model_retrieve`-style
  named-space search, then merge across collections via weighted RRF.

---

## Next Idea?

Add your next sprint idea here.

