# Known Issues

## ~~Lifecycle idle timer races with indexing LLM reload~~ — RESOLVED

**Discovered**: 2026-02-21 (Sprint 008, post-merge manual testing)
**Resolved**: 2026-02-22 (Sprint 009, Phase 3 — T009–T015)
**Severity**: Low (cosmetic — scary log message, service continues working)
**Files**: `src/kragd/service.py`, `src/kragd/lifecycle.py`

### Symptom

After indexing completes, the log shows:
```
Failed to reload LLM after indexing — queries will be unavailable until service restart
```
But queries actually work fine.

### Root Cause

Race condition between the lifecycle manager's idle timer and the post-indexing LLM reload:

1. Before indexing, `llm_pool.close()` unloads the LLM to free VRAM
2. The idle timer (300s) is **not paused** — it fires mid-indexing and loads the text LLM back via the old pool
3. When indexing finishes, `_init_llm_pool()` tries to create a **new** LLMPool and load the same LLM — fails because VRAM is already occupied by embedding models + the LLM the idle timer loaded
4. Since `LLMPool()` constructor throws, `self.llm_pool` keeps the old pool reference (which has a working text LLM from the idle timer load) — so queries still work

### Fix

Pause/disable the lifecycle manager's idle timer when `_indexing` is set. Resume it in the `_run_indexing` finally block before attempting the LLM reload. This prevents the timer from loading LLMs while embedding models occupy VRAM.

### Resolution

Implemented in Sprint 009, Phase 3 (Lifecycle Timer Fix — US1):
- Added `pause()` / `resume()` methods to `LLMLifecycleManager`
- `pause()` cancels the idle timer task and sets a `_paused` flag
- `_unload_after_timeout()` returns early if `_paused` is set (defense-in-depth)
- `resume()` clears the flag and re-schedules the idle timer
- `_run_indexing()` calls `pause()` before `llm_pool.close()` and `resume()` after LLM reload
- Covered by unit tests in `tests/unit/kragd/test_lifecycle.py` and integration tests in `tests/integration/test_lifecycle_pause_resume.py`
