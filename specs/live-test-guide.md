# Live Test Guide

Live tests exercise a real running `kragd` service — they index actual directories, run real queries through the LLM, and verify end-to-end behavior. They are excluded from the default test run and must be invoked explicitly.

## Prerequisites

1. `kragd` is running: `uv run kragd`
2. A corpus directory exists that `kragd` can index
3. For the Obsidian tests: the `krag-plugin-obsidian` is installed and the vault path is configured in `config.toml`

`kragd` skips all tests automatically if it is not reachable at the configured host and port — no tests fail, they all skip.

---

## Quick Reference

```bash
# Default run — live tests excluded (marked as deselected)
uv run pytest

# Run all live tests against a running kragd
uv run pytest -m live --no-cov -v

# Run only the Obsidian vault live tests
KRAG_TEST_OBSIDIAN_VAULT=/home/ken/obsidian/gratch uv run pytest -m live --no-cov -v -k obsidian

# Custom corpus directories
KRAG_TEST_DIR_SMALL=~/src/krag/specs KRAG_TEST_DIR_LARGE=~/src/krag uv run pytest -m live --no-cov -v

# Full run with all variables set
KRAG_TEST_DIR_SMALL=~/src/krag/specs \
KRAG_TEST_DIR_LARGE=~/src/krag \
KRAG_TEST_OBSIDIAN_VAULT=/home/ken/obsidian/gratch \
uv run pytest -m live --no-cov -v
```

---

## Environment Variables

All variables are optional. Defaults assume a typical local setup.

| Variable | Default | Description |
|----------|---------|-------------|
| `KRAG_TEST_HOST` | `localhost` | `kragd` host |
| `KRAG_TEST_PORT` | `8742` | `kragd` port |
| `KRAG_TEST_DIR_SMALL` | `~/src/bits-and-pieces` | Small corpus for quick indexing tests. Should have tens to low hundreds of files. |
| `KRAG_TEST_DIR_LARGE` | `~/src` | Large corpus for stress/regression tests. Should have thousands of files. |
| `KRAG_TEST_TIMEOUT` | `3600` | Max seconds to wait for any indexing job to complete. Raise this if your machine is slow or the corpus is very large. |
| `KRAG_TEST_OBSIDIAN_VAULT` | `~/obsidian` | Path to an Obsidian vault directory for `test_live_obsidian.py`. |

### Good `DIR_SMALL` choices

- `~/src/krag/specs` — the spec files in this repo (~50 markdown files, fast)
- `~/src/krag/docs` — documentation directory
- Any directory with a few hundred small text/code files

### Good `DIR_LARGE` choices

- `~/src/krag` — this entire repository
- `~/src` — your full source tree (may take several minutes)

---

## Test Files

### `tests/live/test_live_kragd.py`

General `kragd` service tests. Run sequentially — later tests depend on state built up by earlier ones.

| Class | What it tests |
|-------|---------------|
| `Test00ServiceBaseline` | Health, status, modes list, lexicon refresh |
| `Test01IndexSmallDir` | Incremental index of `DIR_SMALL`, job completion, file counts |
| `Test02QueryAfterSmallIndex` | Retrieve and query against the small corpus |
| `Test03IndexLargeDir` | Incremental index of `DIR_LARGE`, verifies no cross-dir deletion |
| `Test04QueryAfterLargeIndex` | Query, mode selection, LLM slot verification |
| `Test05DebugEndpoints` | `/debug/qdrant`, `/modes/default`, `/status` |
| `Test06FullReindex` | Full (non-incremental) re-index of `DIR_SMALL` |
| `Test07DryRun` | Dry-run index — reports changes without writing |
| `Test08ErrorHandling` | Empty query, invalid mode, nonexistent directory |

### `tests/live/test_live_obsidian.py`

Obsidian vault plugin tests. Requires the plugin installed and `KRAG_TEST_OBSIDIAN_VAULT` set.

| Class | What it tests |
|-------|---------------|
| `Test00VaultIndexing` | Index the vault, verify completion and results |
| `Test01MixedContentRouting` | Prose → `docs`, code blocks → `code` collection routing |
| `Test02ObsidianMode` | `--mode obsidian` queries, mode detail endpoint |

---

## Running Against a Remote kragd

```bash
KRAG_TEST_HOST=192.168.1.50 KRAG_TEST_PORT=8742 uv run pytest -m live --no-cov -v
```

---

## Filtering Tests

```bash
# Only the service baseline (health, status)
uv run pytest -m live --no-cov -v -k "Baseline"

# Skip the large-dir index (slow)
uv run pytest -m live --no-cov -v -k "not LargeDir"

# Only query tests
uv run pytest -m live --no-cov -v -k "Query"

# Full kragd suite, no Obsidian
uv run pytest -m live --no-cov -v --ignore=tests/live/test_live_obsidian.py
```

---

## Notes

- **`--no-cov`** is recommended for live tests. Coverage instrumentation adds overhead and the live tests are timing-sensitive.
- **Sequential order matters** in `test_live_kragd.py`. Pytest collects tests in file order by default; do not use `-p no:randomly` or similar plugins that reorder tests.
- **State accumulates** across the live test session. The large-dir index in `Test03` intentionally does not wipe vectors from `Test01`. The test verifies vector counts are stable (not shrinking), catching the cross-directory deletion bug.
- **Skipped tests** are the expected outcome when a corpus directory doesn't exist — not failures. If `DIR_SMALL` doesn't exist, the tests that depend on it skip gracefully.
- **Obsidian plugin**: if `kragd` logs `Obsidian plugin initialized with 0 vault(s)`, check that `[plugins.obsidian.vaults]` is correctly set in `~/.config/krag/config.toml` and restart `kragd`.
- **Indexing timeouts**: the default `KRAG_TEST_TIMEOUT=3600` (1 hour) is intentionally generous. Large vaults (295 notes) took ~630s in testing. Set lower if you want faster failures during development.

---

## Typical Full Run

```bash
KRAG_TEST_DIR_SMALL=~/src/krag/specs \
KRAG_TEST_DIR_LARGE=~/src/krag \
KRAG_TEST_OBSIDIAN_VAULT=/home/ken/obsidian/gratch \
uv run pytest -m live --no-cov -v
```

Expected output structure:
```
tests/live/test_live_kragd.py::Test00ServiceBaseline::test_health_endpoint PASSED
tests/live/test_live_kragd.py::Test00ServiceBaseline::test_status_structure PASSED
...
tests/live/test_live_kragd.py::Test01IndexSmallDir::test_trigger_index PASSED
tests/live/test_live_kragd.py::Test01IndexSmallDir::test_wait_for_completion PASSED  (may take minutes)
...
tests/live/test_live_obsidian.py::Test00VaultIndexing::test_vault_exists PASSED
tests/live/test_live_obsidian.py::Test00VaultIndexing::test_trigger_vault_index PASSED
tests/live/test_live_obsidian.py::Test00VaultIndexing::test_wait_for_index PASSED    (may take minutes)
...
tests/live/test_live_obsidian.py::Test02ObsidianMode::test_obsidian_mode_exists PASSED
tests/live/test_live_obsidian.py::Test02ObsidianMode::test_query_with_obsidian_mode PASSED
```
