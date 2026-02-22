# Tasks: Polish and Bugs Sprint

**Branch**: `008-polish-and-bugs` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Overview

Ad-hoc sprint — tasks are added as bugs are discovered during manual testing. No upfront task planning. Each task is marked complete when the fix is applied and tests pass.

**Test baseline**: 1056 passed, 2 skipped

## Phase 1: Bugs Already Fixed (Sprint 007 Tail)

These were fixed during Sprint 007 integration testing and are recorded here for completeness.

- [x] T001 [US1] Fix MatchSubstring → MatchText for qdrant-client v2 in src/kragd/service.py
- [x] T002 [US1] Add --exclude-path filter support to debug qdrant in src/kragd/service.py, src/kragd/schemas.py, src/krag_cli/commands/debug.py
- [x] T003 [US1] Fix Qdrant local-mode lock conflict — inject shared vector_store into IndexingOrchestrator in src/krag/orchestration/indexer.py, src/kragd/service.py
- [x] T004 [US1] Unload LLM during indexing to free VRAM for code embedding model in src/kragd/service.py
- [x] T005 [US1] Add missing logger import to src/kragd/service.py
- [x] T006 [US1] Restore file logging for kragd — add setup_logging() call in src/kragd/app.py
- [x] T007 [US1] Apply index request directory/filter overrides (--dir, --type, --exclude) in src/kragd/service.py
- [x] T008 [US2] Create ship-it agent skill in .github/agents/ship-it.agent.md

## Phase 2: New Bugs (Discovered This Sprint)

- [x] T009 [US1] Client shows raw stack trace on httpx timeout — catch expected errors, log trace, show clean message in src/krag_cli/client.py
- [x] T018 [US1] LLM hot-swap fails after indexing — lifecycle_manager holds stale pool reference after _init_llm_pool() recreates pool; re-wire lifecycle_manager._pool in src/kragd/service.py

## Phase 3: Polish (Discovered This Sprint)

- [x] T010 [US2] Make /index return immediately — run indexing in background thread via threading.Thread in src/kragd/service.py; POST /index returns 'running' status immediately
- [x] T011 [US2] Add indexing-in-progress state tracking — _indexing flag + threading.Lock, set status to "running" during indexing, update /index/status to reflect live state in src/kragd/service.py
- [x] T012 [US2] Return "indexing in progress, try again later" for queries received while indexing is active — _require_not_indexing() guard on query(), retrieve(), debug_query(); global RuntimeError→409/503 handler in app.py; 409 handling in client.py
- [x] T013 [US2] Add `--wait` flag to `krag index` CLI — poll /index/status every 5s until complete, show progress messages; without --wait prints job ID and hint
- [x] T014 [US2] Split files_skipped into files_skipped_unchanged + files_skipped_other in IndexingJob model, IndexResponse schema, orchestrator, service, and CLI display
- [x] T015 [US2] Add index job result cache to service — retain last N completed jobs, mark as "delivered" when client retrieves them, always keep most recent
- [x] T016 [US2] Update index-status CLI to display multiple job results from cache
- [x] T017 [US2] Move Job ID out of index report table — display as dim line above table for cleaner layout in src/krag_cli/commands/index.py
- [x] T019 [US1] GPU VRAM reporting uses memory_allocated() (current process only) instead of mem_get_info() (system-wide) — shows full VRAM as free in src/krag/cli/gpu.py
- [x] T020 [US2] `krag config show` default to grep-friendly dotted format, move Rich tables behind --pretty flag in src/krag/cli/config.py
- [x] T021 [US1] Retriever dedup stats not tracked — _deduplicate() never set _last_total_before_dedup so debug_query pre/post-dedup counts were always equal; also fix per-space counts in src/krag/retrieval/retriever.py, src/kragd/service.py

## Dependencies

None — all tasks are independent fixes.

## Notes

- Tasks are added during manual testing sessions
- Each fix must maintain the test baseline (1056+ passed)
- Use `uv run pytest tests/ --tb=short -q --no-cov -p no:cacheprovider` to verify
