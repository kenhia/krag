# Feature Specification: Debug Metadata Accuracy & Retrieval Completeness

**Feature Branch**: `015-retrieval-accuracy`
**Created**: 2025-03-13
**Status**: Draft
**Input**: User description: "Sprint 015 — fix per_space_result_counts in multi-collection retrieval, enable multi-model embeddings in multi-collection mode, and suppress repetitive health endpoint logging."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Accurate per-collection result counts in debug output (Priority: P1)

A developer queries krag in a multi-collection mode (e.g. `code` + `tests`) and enables debug output (`--debug` on the CLI, or the debug toggle in krager). The debug metadata should report how many candidates came from each collection (e.g. `{'code': 60, 'tests': 60}`) instead of lumping everything under `{'default': 120}`.

**Why this priority**: Incorrect debug metadata directly misleads developers tuning retrieval weights and diagnosing relevance problems. This is a data-correctness bug with no workaround.

**Independent Test**: Run a multi-collection query with `--debug` and verify `per_space_result_counts` keys match the collection names and their values sum to the total candidate count.

**Acceptance Scenarios**:

1. **Given** krag is configured with two collections (`code` weight 1.0, `tests` weight 0.5) each containing indexed documents, **When** a user runs a query with debug enabled, **Then** `per_space_result_counts` contains keys `"code"` and `"tests"` with integer counts reflecting the results retrieved from each collection.
2. **Given** a multi-collection query where one collection returns zero results, **When** debug output is rendered, **Then** that collection still appears in `per_space_result_counts` with a value of `0`.
3. **Given** a single-collection query (no mode or default mode), **When** debug output is rendered, **Then** `per_space_result_counts` continues to report per-vector-space counts as it does today (no regression).

---

### User Story 2 — Multi-model embeddings used during multi-collection retrieval (Priority: P2)

A developer has configured a secondary embedding model (e.g. `jina-code`) alongside the primary model. When querying in multi-collection mode, both models should be used — each collection should be searched across all configured named vector spaces, and results should be merged via weighted RRF — rather than falling back to the primary model and the `"text"` vector space only.

**Why this priority**: Without this, multi-model and multi-collection retrieval are mutually exclusive. Users who invest in a code-specialised embedding model lose its benefit as soon as they enable cross-collection search.

**Independent Test**: Configure two collections and two embedding models, query with debug enabled, and verify `vector_spaces_searched` lists both vector space names and `per_space_result_counts` includes entries for every (collection × vector-space) combination.

**Acceptance Scenarios**:

1. **Given** two collections and two embedding models (primary + secondary) are configured, **When** a user runs a multi-collection query, **Then** each collection is searched in every named vector space the collection supports, and results are merged via RRF within each collection before cross-collection weighted RRF.
2. **Given** a collection that only has the primary vector space (no secondary), **When** the multi-collection query runs, **Then** that collection is searched in the primary space only, with no errors or warnings for the missing secondary space.
3. **Given** a search in one vector space of one collection fails, **When** the query proceeds, **Then** the failure is logged as a warning, remaining spaces and collections are still searched, and the user receives results from the successful searches.

---

### User Story 3 — Suppress repetitive health-check log entries (Priority: P3)

An operator running kragd behind a load balancer or monitoring probe sees the log flooded with `GET /health` entries. The system should log only the first health check in a consecutive run of health checks, then resume normal logging when a different endpoint is hit, and log the next health check that follows.

**Why this priority**: This is a quality-of-life improvement for operators. It reduces log noise but does not affect correctness or functionality.

**Independent Test**: Send a burst of `GET /health` requests to kragd, verify only the first is logged. Then send a non-health request, verify it is logged. Then send another `GET /health` and verify it is logged.

**Acceptance Scenarios**:

1. **Given** kragd is running, **When** five consecutive `GET /health` requests arrive, **Then** only the first request produces an INFO-level log entry (the remaining four are logged at DEBUG level).
2. **Given** health-check logging has been suppressed after a burst, **When** a `GET /query` request arrives followed by a `GET /health`, **Then** both the query request and the subsequent health request are logged.
3. **Given** a single `GET /health` request (not part of a burst), **When** the request arrives, **Then** it is logged normally.

---

### Edge Cases

- Multi-collection query where all collections are empty — `per_space_result_counts` should show `0` for each collection; no crash.
- Multi-collection query with a collection name that doesn't exist — warning logged, collection skipped, other collections still searched.
- Multi-model retrieval where the secondary model's vector space doesn't exist in a particular collection — space skipped with a warning, no crash.
- Health-check suppression across interleaved slow requests — the "consecutive" determination is based on the most-recently-logged endpoint, not on timing.
- Server restart resets the health-check suppression state (no stale state carried across restarts).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `_multi_collection_retrieve` MUST populate `_last_per_space_counts` with a mapping of collection name → result count before returning.
- **FR-002**: The debug metadata builder in kragd MUST consume per-collection counts from `_last_per_space_counts` when available, and reflect them in `per_space_result_counts` in the response.
- **FR-003**: When `_last_per_space_counts` is not populated (single-collection path), the debug metadata builder MUST fall back to existing vector-space introspection behaviour (no regression).
- **FR-004**: `_multi_collection_retrieve` MUST perform named-vector-space search (multi-model style) within each collection when the collection has named vector spaces, using all configured embedding models.
- **FR-005**: Within each collection, results from different vector spaces MUST be merged via RRF before cross-collection weighted RRF fusion.
- **FR-006**: If a collection lacks a named vector space for a secondary model, the system MUST skip that space for that collection with a warning and continue.
- **FR-007**: `per_space_result_counts` in debug output MUST report counts at the collection level (e.g. `{'code': 60, 'tests': 60}`) for multi-collection single-model queries, at the vector-space level (e.g. `{'text': 60, 'code-embeddings': 60}`) for single-collection multi-model queries, and at the composite `collection:space` level (e.g. `{'code:text': 60, 'code:code-embeddings': 58, 'tests:text': 45}`) for multi-collection multi-model queries.
- **FR-008**: kragd MUST suppress consecutive `GET /health` log entries after the first, resuming logging when a different endpoint is accessed.
- **FR-009**: After a non-health endpoint is logged, the next `GET /health` MUST be logged again (resetting the suppression cycle).
- **FR-010**: Health-check suppression state MUST reset on server startup.

### Key Entities

- **`_last_per_space_counts`**: Internal dict on the retriever that stores result counts keyed by vector-space name (single-collection) or collection name (multi-collection). Consumed by the debug metadata builder.
- **`DebugMetadata.per_space_result_counts`**: Field in the query response that surfaces the counts to the user.
- **Health-log suppression state**: Server-scoped state tracking whether the most-recently-logged request was a health check.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Multi-collection debug output shows per-collection keys matching the configured collection names in `per_space_result_counts`, with counts summing to `total_candidates_before_dedup`.
- **SC-002**: Multi-collection queries with multiple embedding models return results from all configured vector spaces; `vector_spaces_searched` in debug output lists all spaces searched across all collections.
- **SC-003**: During a burst of 100 consecutive health checks, log output contains exactly 1 INFO-level health-check entry.
- **SC-004**: US1 and US2 verified on both `krag` CLI (`--debug`) and `krager` (debug toggle). US3 verified by kragd server log inspection.

## Assumptions

- The existing `reciprocal_rank_fusion` utility supports the two-level merge (intra-collection then inter-collection) without modification. If it requires a weighting parameter, that is an implementation detail for the plan phase.
- Collections that do not have named vector spaces will be searched using the unnamed/default vector space with the primary embedding model, matching current behaviour.
- The health-check log suppression applies only to kragd's access log (uvicorn or middleware), not to any external reverse-proxy logs.
- "Consecutive" health checks are determined by request order, not by wall-clock proximity. Any non-health request resets the suppression.
