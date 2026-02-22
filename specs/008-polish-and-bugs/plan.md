# Implementation Plan: Polish and Bugs Sprint

**Branch**: `008-polish-and-bugs` | **Date**: 2026-02-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-polish-and-bugs/spec.md`

## Summary

Ad-hoc sprint for manual end-to-end testing of the kragd service architecture and fixing bugs discovered during usage. Tasks are added incrementally as issues surface rather than planned upfront. No new features — focus on reliability and polish.

## Technical Context

**Language/Version**: Python 3.13 (compatible 3.11+)  
**Primary Dependencies**: FastAPI, uvicorn, typer, qdrant-client v2, sentence-transformers, llama-cpp-python  
**Storage**: Qdrant (local file-based, embedded mode)  
**Testing**: pytest (baseline: 1056 passed, 2 skipped)  
**Target Platform**: Linux (WSL2/native)  
**Project Type**: Single project, three packages (krag, kragd, krag_cli)  
**Constraints**: All fixes must maintain test baseline; no regressions

## Approach

This sprint follows an **ad-hoc discovery** pattern:

1. **Manual testing**: Exercise each CLI command against kragd
2. **Bug discovery**: When something breaks, document it as a task
3. **Fix and verify**: Fix the issue, run tests, mark task complete
4. **Repeat**: Continue until all commands work reliably

No formal research or data model changes are expected — this is a stabilization sprint.

**Notable change: Async Indexing** — The `/index` endpoint will be converted from synchronous (blocking until indexing completes) to fire-and-forget (return immediately, index in background thread). This requires:
- Background thread for `service.index()` execution
- Threading-safe state tracking (`_indexing` flag, `threading.Lock`)
- Setting `IndexResponse.status` to `"running"` during indexing (currently dead code)
- Query rejection with clear message while indexing is active
- Client-side error handling for timeouts and connection errors
- Optional `--wait` polling mode in the CLI

## Project Structure

### Documentation (this feature)

```text
specs/008-polish-and-bugs/
├── spec.md              # Minimal spec (this sprint)
├── plan.md              # This file
└── tasks.md             # Growing task list (added as bugs are found)
```

### Source Code (existing — no new packages)

```text
src/
├── krag/                # Core library
├── kragd/               # Service daemon
└── krag_cli/            # CLI client

tests/
├── contract/
├── integration/
└── unit/
```

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
