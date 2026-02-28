# Quickstart: Infrastructure Improvements & Polish

**Sprint**: 010-infrastructure-polish
**Date**: 2026-02-23

---

## Prerequisites

- Python 3.11+
- `uv` for dependency management
- Existing krag development environment set up
- Qdrant running (for integration tests)

## Setup

```bash
# Switch to the feature branch
git checkout 010-infrastructure-polish

# Sync dependencies (will be leaner after llama-index removal)
uv sync --group dev
```

## Verification Commands

### After Each User Story

```bash
# Format, lint, test — mandatory before every commit
uv run ruff format .
uv run ruff check --fix .
uv run pytest
```

### US1: Incremental Indexing Fix
```bash
# Unit test: metadata merge preserves unchanged files across directory changes
uv run pytest tests/unit/test_metadata_merge.py -v

# Integration test: end-to-end with actual metadata.json
uv run pytest tests/integration/test_metadata_roundtrip.py -v

# Manual verification:
# 1. Index a subdirectory
krag index -d ~/src/some-project/
# 2. Index parent directory
krag index -d ~/src/
# 3. Confirm files from step 1 show as "unchanged"
krag index-status --json | jq '.files_skipped_unchanged'
```

### US2: Index-Status Accuracy
```bash
uv run pytest tests/unit/test_index_status_accuracy.py -v

# Manual: start indexing, immediately check status
krag index -d ~/src/ &
sleep 1
krag index-status  # Should show "running", not previous result
```

### US3: Query/Debug-Query Unification
```bash
uv run pytest tests/unit/test_query_debug_unified.py -v

# Manual: same query, compare outputs
krag query "what is krag?"
krag query "what is krag?" --debug
# answer and sources should be identical
```

### US4: Code Embedding Config
```bash
uv run pytest tests/unit/test_embedding_code_config.py -v

# Manual: add [embedding_code] to config, index, verify named vectors
krag status  # Should list both embedding models
```

### US5: Operational UX
```bash
# Manual: start kragd, check log for banners
kragd --rotate-logs
grep "KRAGD STARTING" ~/.cache/krag/kragd.log
grep "KRAGD READY" ~/.cache/krag/kragd.log

# Rich markdown: query and observe formatted output
krag query "show me a code example"
```

### US6: Concurrency Safety
```bash
uv run pytest tests/unit/test_concurrency_safety.py -v

# Manual: concurrent queries with different modes
for i in (seq 1 10)
    krag query "test" --mode default &
    krag query "test" --mode code &
end
wait
```

### US7: Dead Code Cleanup
```bash
# Verify removed files don't exist
test ! -f src/kragd/routers/health.py && echo "health.py removed"

# Verify dependencies
grep -c "llama-index" pyproject.toml  # Should be 0
grep -c "tomli" pyproject.toml         # Should be 0 (tomli-w stays)

# Verify single definition
grep -c "DEFAULT_VECTOR_STORE_PATH" src/krag/config/defaults.py  # Should be 1

# Full test suite
uv run pytest
```

### US8: Exception Architecture
```bash
uv run pytest tests/unit/test_domain_exceptions.py -v
uv run pytest tests/contract/test_api_error_codes.py -v

# Verify no string matching in app.py
grep -c '"in msg"' src/kragd/app.py   # Should be 0
grep -c "isinstance" src/kragd/app.py  # Should be > 0
```

### US9: CLI Consistency
```bash
# Verify path aliases work
krag query "test" --debug  # Sources should use aliases if configured

# Verify --mode on debug query
krag debug query "test" --mode code
```

### US10: Plugin Registry
```bash
uv run pytest tests/unit/test_plugin_registry.py -v

# Verify extension map auto-builds
# (covered by unit test — no manual steps needed)
```

## Recommended Implementation Order

1. **US7** (dead code cleanup) — simplest, reduces noise for subsequent work
2. **US8** (exception architecture) — foundational for US2, US3, US6
3. **US1** (metadata merge) — correctness bug, independent of other changes
4. **US2** (index-status) — small fix, benefits from US8 exceptions
5. **US10** (plugin registry) — small, self-contained
6. **US9** (CLI consistency) — small fixes, benefits from US8
7. **US3** (query/debug unification) — moderate, benefits from US6 approach
8. **US6** (concurrency safety) — most invasive, benefits from US3 being done first
9. **US4** (code embedding config) — builds on US10 plugin fixes
10. **US5** (operational UX) — lowest priority, no dependencies
