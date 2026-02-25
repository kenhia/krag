# Infrastructure Polish — Comprehensive Scan Report

*Generated: 2026-02-23*

---

## Task 1: ALL TODO/FIXME/HACK/XXX/NOQA Comments

### NOQA Suppressions (legitimate)

| # | File | Line | Comment |
|---|------|------|---------|
| 1 | `src/krag_cli/main.py` | 38 | `from krag.cli.config import config_app  # noqa: E402` |
| 2 | `src/krag_cli/main.py` | 39 | `from krag.cli.gpu import gpu_app  # noqa: E402` |
| 3 | `src/krag_cli/main.py` | 40 | `from krag.cli.log import log_app  # noqa: E402` |
| 4 | `src/krag_cli/main.py` | 41 | `from krag.cli.plugin import plugin_app  # noqa: E402` |
| 5 | `src/krag_cli/main.py` | 50 | `from krag_cli.commands.modes import modes_app  # noqa: E402` |
| 6 | `src/krag_cli/main.py` | 56 | `from krag_cli.commands.lexicon import lexicon_app  # noqa: E402` |
| 7 | `src/krag_cli/main.py` | 102 | `from krag_cli.commands.debug import debug_app  # noqa: E402` |
| 8 | `src/krag_cli/main.py` | 103 | `from krag_cli.commands.query import query_command  # noqa: E402` |
| 9 | `src/krag_cli/main.py` | 111 | `from krag_cli.commands.index import index_command, index_status_command  # noqa: E402` |
| 10 | `src/krag_cli/main.py` | 119 | `from krag_cli.commands.status import health_command, status_command  # noqa: E402` |
| 11 | `src/krag_cli/main.py` | 127 | `from krag_cli.commands.service import start_command, stop_command  # noqa: E402` |
| 12 | `src/krag_cli/display.py` | 22 | `class OutputFormat(str, Enum):  # noqa: UP042` — suppressing pyupgrade for `str, Enum` inheritance |
| 13 | `src/krag/evaluation/runner.py` | 107 | `assert self.llm_pool is not None  # noqa: S101` |
| 14 | `src/krag/synthesis/llm_pool.py` | 167 | `assert slot.instance is not None  # noqa: S101` |
| 15 | `src/krag/synthesis/llm_pool.py` | 254 | `except Exception:  # noqa: BLE001` — bare exception in cleanup path |
| 16 | `src/krag/plugins/interfaces.py` | 207 | `def get_chunking_strategy(self) -> ... | None:  # noqa: B027` — empty method in ABC |
| 17 | `src/krag/plugins/interfaces.py` | 229 | `def initialize(self, ...) -> None:  # noqa: B027` — empty method in ABC |
| 18 | `src/krag/plugins/interfaces.py` | 251 | `def cleanup(self) -> None:  # noqa: B027` — empty method in ABC |
| 19 | `src/krag/plugins/interfaces.py` | 279 | `def get_embedding_model(self) -> str | None:  # noqa: B027` — empty method in ABC |
| 20 | `src/krag/cli/gpu.py` | 41 | `import torch  # noqa: F811` — conditional re-import |

### Notes
- **Zero TODO/FIXME/HACK/XXX comments found in any Python source file.** The codebase is clean of deferred work markers.
- The `"TODO"` and `"TODO.md"` strings in `src/krag/routing/rules.py:101-102` are data values (filename routing rules), not code comments.
- `src/krag/cli/utils.py:9` references noqa in a docstring explaining WHY the wrapper function exists — not a suppression itself.

---

## Task 2: print() Statements in Non-Test Code

### In `src/krag/` (core library — should use logger)

| # | File | Line | Code | Verdict |
|---|------|------|------|---------|
| 1 | `src/krag/cli/eval.py` | 67 | `print(f"Error loading eval file: {e}", file=sys.stderr)` | Should be `logger.error()` |
| 2 | `src/krag/cli/eval.py` | 71 | `print("No queries found in eval file.", file=sys.stderr)` | Should be `logger.error()` |
| 3 | `src/krag/cli/eval.py` | 105 | `print(f"Running {len(queries)} evaluation queries...", file=sys.stderr)` | Should be `logger.info()` |
| 4 | `src/krag/cli/eval.py` | 121 | `print(format_json(report))` | Intentional — JSON output to stdout for piping |
| 5 | `src/krag/cli/eval.py` | 124 | `print(format_summary(report), file=sys.stderr)` | Should be `console.print()` for consistency |
| 6 | `src/krag/cli/eval.py` | 133 | `print(f"Eval failed: {e}", file=sys.stderr)` | Should be `logger.error()` or `console.print()` |
| 7 | `src/krag/cli/pipeline.py` | 111 | `print("Error: No indexed data found...", file=sys.stderr)` | Should be `console.print("[red]Error:...")` |
| 8 | `src/krag/cli/config.py` | 304 | `print(f'{key} = "{value}"')` | Intentional — machine-parseable output to stdout |

### In `src/krag_cli/` and `src/kragd/` (CLI and daemon)
All `print()` calls in `krag_cli/` and `kragd/` use `console.print()` from Rich — these are **correct** for CLI user-facing output. No raw `print()` calls found in these packages (96+ occurrences of `console.print()` are appropriate).

### In docstrings (not actual code)
- `src/krag/plugins/chunking.py:367` — `print()` in docstring example
- `src/krag/plugins/failures.py:30,32,106` — `print()` in docstring examples

---

## Task 3: Bare Except Clauses and Overly Broad Exception Handling

### Bare `except:` (no exception type)
**None found.** All except clauses specify at least `Exception`.

### `except Exception` (overly broad) — 88 instances in `src/`

#### High-priority (swallowing errors silently):

| # | File | Line | Context | Issue |
|---|------|------|---------|-------|
| 1 | `src/krag_cli/client.py` | 161 | `except Exception:` | Silently swallowing connection errors |
| 2 | `src/krag_cli/commands/query.py` | 103 | `except Exception:` | Silent catch-all |
| 3 | `src/kragd/app.py` | 119 | `except Exception:` | In `_get_version()` — returns `"0.0.0-dev"` |
| 4 | `src/krag_cli/commands/service.py` | 122 | `except Exception:` | Silent catch in stop logic |
| 5 | `src/krag_cli/commands/index.py` | 102 | `except Exception:` | Silently catching poll errors |
| 6 | `src/krag/cli/modes.py` | 41 | `except Exception: pass` | **Worst offender** — silently ignores all config load failures |
| 7 | `src/krag/cli/main.py` | 77 | `except Exception:` | Silent catch |
| 8 | `src/krag/cli/main.py` | 459 | `except Exception:` | Silent catch |
| 9 | `src/krag/cli/pipeline.py` | 200 | `except Exception:` | Silent lexicon load failure |
| 10 | `src/krag/cli/query.py` | 260 | `except Exception:` | Silent catch in query path |

#### Medium-priority (logged but overly broad):

| # | File | Line(s) | Context |
|---|------|---------|---------|
| 1 | `src/kragd/service.py` | 286, 333, 361, 686, 973, 1014, 1132, 1147, 1166, 1183, 1215 | 11 `except Exception` in service — all logged but could be narrower |
| 2 | `src/krag/orchestration/indexer.py` | 381, 415, 450, 455, 484, 502, 551, 608, 734, 772, 856, 899, 960, 997 | 14 `except Exception` in indexer — all logged |
| 3 | `src/krag/plugins/registry.py` | 109, 138, 350, 408, 488, 541, 551, 613, 642 | 9 in plugin registry |
| 4 | `src/krag/plugins/loader.py` | 179, 204, 244, 265 | 4 in plugin loader |
| 5 | `src/krag/synthesis/llm_client.py` | 176, 201, 208, 260, 360, 374 | 6 in LLM client |
| 6 | `src/krag/retrieval/retriever.py` | 312, 439 | 2 in retriever |
| 7 | `src/krag/cli/plugin.py` | 171, 254, 323, 374, 425, 500 | 6 in CLI plugin commands |
| 8 | `src/krag/cli/config.py` | 130, 274 | 2 in CLI config |
| 9 | `src/krag/cli/main.py` | 299, 379, 468, 476, 580 | 5 more in CLI main |

**Total: 88 `except Exception` in source code.** While many are logged and intentional (resilience in plugin loading, graceful error handling in CLI), several swallow errors silently.

---

## Task 4: Inconsistent Naming Patterns

### Findings
The codebase is **generally well-named and consistent**. Observations:

1. **Two parallel CLI architectures well-named**:
   - `krag.cli` — direct-mode CLI (imports krag internals directly)
   - `krag_cli` — service-backed CLI (delegates to kragd via HTTP)
   - This is intentional design but the coexistence of `krag.cli.main:app` + `krag_cli.main:app` may confuse contributors.

2. **Test file naming is consistent**: `test_<module>.py` pattern throughout.

3. **Module naming**: All snake_case, consistent. `__init__.py` re-exports follow a consistent pattern.

4. **Class naming**: PascalCase throughout — `KragService`, `FileScanner`, `EmbeddingGenerator`, etc.

5. **Minor inconsistency**: Both `collection_router.py` and `rules.py` exist in `routing/` — `rules.py` defines `qdrant_collection_name()` which is more of a helper, while `collection_router.py` defines `CollectionRouter` class. This is fine but `rules.py` could be merged into `collection_router.py`.

---

## Task 5: Dead/Unreachable Code

### Dead Files

| # | File | Issue |
|---|------|-------|
| 1 | `src/kragd/routers/health.py` | **Dead file** — defines `/health`, `/status`, `/shutdown` routes but is never imported. `system.py` provides the same endpoints and IS imported in `app.py`. |
| 2 | `tests/performance/__init__.py` | Empty test directory — no performance tests exist yet. |

### Dead Dependency
- `pyproject.toml` line 21: `"tomli>=2.0.0 ; python_version < '3.11'"` — Since `requires-python = ">=3.11"`, this dependency can **never be installed**. The code correctly uses `import tomllib` (stdlib). This line is dead.

### Duplicate Dependency Groups
- `pyproject.toml` has BOTH `[dependency-groups] dev` (lines 30-41) AND `[project.optional-dependencies] dev` (lines 43-48). The `[project.optional-dependencies] dev` has **outdated versions** (`pytest>=7.4.0`, `pytest-cov>=4.1.0`, `mypy>=1.5.0`, `ruff>=0.1.0`) vs the `[dependency-groups] dev` which specifies newer versions. The optional-dependencies section appears to be a leftover.

### Unused Imports
`ruff check --select F401` reports **all clean** — no unused imports.

### Unreachable Code
No unreachable code after `return`/`raise` detected.

---

## Task 6: pyproject.toml Analysis

### Issues Found

| # | Issue | Severity | Details |
|---|-------|----------|---------|
| 1 | Dead `tomli` dependency | Low | `"tomli>=2.0.0 ; python_version < '3.11'"` — impossible to activate given `requires-python = ">=3.11"`. Remove. |
| 2 | Duplicate dev dependencies | Medium | Both `[dependency-groups] dev` and `[project.optional-dependencies] dev` exist with conflicting versions. The `[project.optional-dependencies] dev` section has stale minimum versions and should be removed. |
| 3 | `llama-index` dependency unused | High | `"llama-index>=0.9.0"` is declared but **zero imports** of `llama_index` exist anywhere in the source code. This is a heavyweight dependency (~100+ transitive packages). Remove. |
| 4 | Three script entry points | Info | `krag`, `kragd`, and `krag-direct` are all defined. This is intentional (service-backed vs direct CLI) but `krag-direct` should be documented or removed if deprecated. |
| 5 | Placeholder author email | Low | `email = "ken@example.com"` — should be a real email or removed. |
| 6 | Version only in two places | Info | Version `0.1.0` in `pyproject.toml` and `src/krag/__init__.py`. Consider using `importlib.metadata.version()` or hatchling's `dynamic = ["version"]` to have a single source of truth. |

### Dependency Health

| Dependency | Used? | Notes |
|------------|-------|-------|
| `typer` | Yes | CLI framework |
| `sentence-transformers` | Yes | Embeddings |
| `qdrant-client` | Yes | Vector store |
| `llama-cpp-python` | Yes | LLM inference |
| `llama-index` | **NO** | Not imported anywhere — remove |
| `pydantic` | Yes | Data models |
| `pydantic-settings` | Yes | Settings |
| `rich` | Yes | CLI output |
| `tomli` | **Dead marker** | Never installed (`python_version < '3.11'` but `requires-python >= 3.11`) |
| `tomli-w` | Yes | Writing TOML files |
| `pyyaml` | Yes | YAML config support |
| `tree-sitter` | Yes | Via code plugin |
| `tree-sitter-python` | Yes | Via code plugin |
| `tree-sitter-rust` | Yes | Via code plugin |
| `fastapi` | Yes | kragd API |
| `uvicorn` | Yes | ASGI server |
| `httpx` | Yes | HTTP client |

---

## Task 7: Test Coverage Analysis

### Source Modules vs Test Coverage

| Source Module | Has Unit Test? | Has Contract/Integration Test? | Notes |
|--------------|---------------|-------------------------------|-------|
| `krag/__init__.py` | — | — | Just version |
| `krag/cli/config.py` | No | No | **No tests** |
| `krag/cli/eval.py` | No | No | **No tests** |
| `krag/cli/gpu.py` | Yes (`test_gpu.py` — 3 tests) | Yes (`test_gpu_acceleration.py`) | |
| `krag/cli/index.py` | No | No | **No tests** (only krag_cli index tested) |
| `krag/cli/log.py` | No | No | **No tests** |
| `krag/cli/main.py` | No | No | **No tests** |
| `krag/cli/modes.py` | No | No | **No tests** (only mode_loader/registry tested) |
| `krag/cli/pipeline.py` | No | No | **No tests** |
| `krag/cli/plugin.py` | Yes (`cli/test_plugin.py`) | No | |
| `krag/cli/query.py` | No | No | **No tests** |
| `krag/cli/utils.py` | No | No | **No tests** |
| `krag/config/defaults.py` | No | No | Constants only — low priority |
| `krag/config/logging.py` | No | Yes (`test_logging.py`) | |
| `krag/config/path_reducer.py` | Yes (`test_path_reducer.py`) | No | |
| `krag/config/settings.py` | Yes (`test_config_*.py`) | Yes | Well tested |
| `krag/config/xdg.py` | Yes (`test_xdg.py`) | No | |
| `krag/critic/relevance_critic.py` | Yes (`test_relevance_critic.py`) | Yes (`test_critic_*.py`) | |
| `krag/discovery/scanner.py` | Yes (`test_discovery.py`) | No | |
| `krag/embeddings/generator.py` | No directly | Yes (`test_embedding_*.py`) | Tested via orchestrator |
| `krag/embeddings/orchestrator.py` | Yes | Yes | |
| `krag/evaluation/checks.py` | Yes (`test_eval_checks.py`) | No | |
| `krag/evaluation/loader.py` | Yes (`test_eval_loader.py`) | No | |
| `krag/evaluation/reporter.py` | Yes (`test_eval_report.py`) | No | |
| `krag/evaluation/runner.py` | Yes (`test_eval_runner.py`) | Yes (`test_evaluation_pipeline.py`) | |
| `krag/extraction/chunker.py` | Yes (`test_chunker.py`) | No | |
| `krag/extraction/text_extractor.py` | Yes (`test_extraction.py`) | No | |
| `krag/lexicon/lexicon_injector.py` | Yes | Yes | |
| `krag/lexicon/lexicon_store.py` | Yes | Yes | |
| `krag/models/configuration.py` | Yes (`test_configuration.py`) | No | |
| `krag/models/exceptions.py` | No | No | Simple exception classes |
| `krag/models/query_result.py` | Yes (`test_query_result.py`) | No | |
| `krag/modes/mode_loader.py` | Yes | Yes | |
| `krag/modes/mode_registry.py` | Yes | Yes | |
| `krag/orchestration/incremental.py` | Yes (`test_incremental.py`) | Yes | |
| `krag/orchestration/indexer.py` | No directly | Yes (integration tests) | Complex module — unit tests would help |
| `krag/orchestration/query_engine.py` | Yes (`test_query_engine.py`) | Yes | |
| `krag/plugins/*` | Yes (7 test files) | Yes (5 contract tests) | Well covered |
| `krag/retrieval/retriever.py` | Yes (3 test files) | Yes | |
| `krag/retrieval/rrf.py` | Yes (`test_rrf_merge.py`) | No | |
| `krag/routing/collection_router.py` | Yes | No | |
| `krag/routing/rules.py` | No | No | **No tests** |
| `krag/storage/collection_manager.py` | Yes | No | |
| `krag/storage/qdrant_impl.py` | No directly | Yes (contract) | |
| `krag/storage/vector_store.py` | No | Yes (contract) | ABC only |
| `krag/synthesis/llm_client.py` | Yes | Yes | |
| `krag/synthesis/llm_pool.py` | Yes | Yes | |
| `krag/synthesis/prompt_builder.py` | Yes | No | |
| `kragd/app.py` | No | Yes (service tests) | |
| `kragd/lifecycle.py` | Yes (`test_lifecycle.py`) | Yes | |
| `kragd/__main__.py` | No | No | **No tests** |
| `kragd/pid.py` | Yes (`test_pid.py`) | No | |
| `kragd/schemas.py` | Yes (`test_schemas.py`) | No | |
| `kragd/service.py` | Yes (`test_service.py`) | Yes | |
| `kragd/routers/*.py` | No unit tests | Yes (contract API tests) | |
| `krag_cli/client.py` | Yes (`test_client.py`) | No | |
| `krag_cli/main.py` | No | No | **No tests** |
| `krag_cli/config.py` | No | No | **No tests** |
| `krag_cli/display.py` | No | No | **No tests** |
| `krag_cli/commands/*.py` | No | No | **No tests** for any command module |

### Summary of Coverage Gaps

**Modules with NO tests at all (16):**
1. `krag/cli/config.py` — config validate/show/edit commands
2. `krag/cli/eval.py` — eval CLI command
3. `krag/cli/index.py` — index CLI command
4. `krag/cli/log.py` — log CLI command
5. `krag/cli/main.py` — direct-mode CLI main
6. `krag/cli/modes.py` — modes CLI command
7. `krag/cli/pipeline.py` — query pipeline builder
8. `krag/cli/query.py` — query CLI command
9. `krag/cli/utils.py` — CLI utilities
10. `krag/routing/rules.py` — routing rule constants/helpers
11. `kragd/__main__.py` — daemon entry point
12. `krag_cli/main.py` — service-backed CLI main
13. `krag_cli/config.py` — CLI config reader
14. `krag_cli/display.py` — CLI output formatting
15. `krag_cli/commands/*.py` (7 files) — all service-backed CLI commands
16. `kragd/routers/health.py` — dead file (see Task 5)

### Test Files with Very Few Tests
| File | Test Count |
|------|-----------|
| `tests/integration/test_multi_model_query.py` | 2 |
| `tests/integration/test_code_preset.py` | 3 |
| `tests/integration/test_custom_storage_paths.py` | 3 |
| `tests/integration/test_evaluation_pipeline.py` | 3 |
| `tests/integration/test_gpu_acceleration.py` | 3 |
| `tests/unit/test_gpu.py` | 3 |

---

## Task 8: Type Hint Completeness

### mypy Status
`uv run mypy src/ --ignore-missing-imports` reports **"Success: no issues found in 104 source files"** under `strict = true` mode.

### Functions Missing Return Type Annotations

Despite mypy passing (strict), the following functions lack explicit return type annotations on `def` lines (may have `-> None` inferred or be Typer commands where the return isn't used):

**CLI command functions** (Typer commands — return type is never used but missing annotation):

| # | File | Line | Function |
|---|------|------|----------|
| 1 | `src/krag/cli/plugin.py` | 88 | `def list_plugins(` |
| 2 | `src/krag/cli/plugin.py` | 177 | `def plugin_info(` |
| 3 | `src/krag/cli/plugin.py` | 329 | `def enable_plugin(` |
| 4 | `src/krag/cli/plugin.py` | 380 | `def disable_plugin(` |
| 5 | `src/krag/cli/plugin.py` | 431 | `def install_plugin(` |
| 6 | `src/krag/cli/index.py` | 30 | `def index_command(` |
| 7 | `src/krag/cli/index.py` | 258 | `def _perform_dry_run(` |
| 8 | `src/krag/cli/eval.py` | 16 | `def eval_command(` |
| 9 | `src/krag/cli/config.py` | 31 | `def config_validate(` |
| 10 | `src/krag/cli/config.py` | 136 | `def config_show(` |
| 11 | `src/krag/cli/config.py` | 372 | `def config_edit(` |
| 12 | `src/krag/cli/main.py` | 107 | `def main_callback(` |
| 13 | `src/krag/cli/main.py` | 149 | `def init(` |
| 14 | `src/krag/cli/main.py` | 305 | `def migrate(` |
| 15 | `src/krag/cli/main.py` | 385 | `def status(` |
| 16 | `src/krag/cli/main.py` | 482 | `def reset(` |
| 17 | `src/krag/cli/main.py` | 588 | `def completion(` |
| 18 | `src/krag/cli/modes.py` | 24 | `def _build_registry(config_path):` — **missing return type** |
| 19 | `src/krag/cli/modes.py` | 48 | `def modes_list(` |
| 20 | `src/krag/cli/modes.py` | 84 | `def modes_show(` |
| 21 | `src/krag/cli/pipeline.py` | 72 | `def build_query_pipeline(` |
| 22 | `src/krag/cli/query.py` | 28 | `def query_command(` |
| 23 | `src/krag/cli/query.py` | 299 | `def _display_full_response(` |

Since mypy strict passes, these are all either type-inferred or have the annotation on subsequent lines (multiline signatures). The one notable case is `_build_registry()` at `src/krag/cli/modes.py:24` which lacks both return type and parameter type on `config_path`.

---

## Task 9: Hardcoded Values

### Hardcoded Timeouts

| # | File | Line | Value | Suggestion |
|---|------|------|-------|------------|
| 1 | `src/krag_cli/commands/query.py` | 45 | `timeout=120.0` | Should be configurable or use a constant |
| 2 | `src/krag_cli/commands/debug.py` | 42 | `timeout=120.0` | Same timeout, different command |
| 3 | `src/krag_cli/commands/debug.py` | 115 | `timeout=60.0` | Different timeout for qdrant debug |
| 4 | `src/krag_cli/commands/service.py` | 114 | `timeout=5.0` | Health check timeout |
| 5 | `src/kragd/routers/system.py` | 46 | `time.sleep(0.5)` | Arbitrary delay before SIGTERM |

### Hardcoded Magic Numbers

| # | File | Line | Value | Context |
|---|------|------|-------|---------|
| 1 | `src/krag/orchestration/indexer.py` | 598 | `batch_size = 100` | Vector upsert batch |
| 2 | `src/krag/orchestration/indexer.py` | 756 | `batch_size = 100` | Repeated in 3 places |
| 3 | `src/krag/orchestration/indexer.py` | 981 | `batch_size = 100` | Same batch size hardcoded 3x |
| 4 | `src/krag/orchestration/indexer.py` | 132 | `max_file_size_mb=100` | Max file size for extraction |
| 5 | `src/krag/plugins/chunking.py` | 46 | `chunk_size=1000, chunk_overlap=200` | Fallback chunker defaults |
| 6 | `src/krag/synthesis/prompt_builder.py` | 52,67,82,99 | `max_tokens=256/512/1024/768` | Per-preset (intentional, but not overridable) |
| 7 | `src/krag/cli/pipeline.py` | 165,175 | `max_tokens=2000` | Hardcoded in pipeline builder |
| 8 | `src/krag/cli/query.py` | 150 | `max_tokens=2000` | Hardcoded override |
| 9 | `src/krag/cli/eval.py` | 98 | `max_tokens=2000` | Hardcoded in eval |
| 10 | `src/kragd/schemas.py` | 29,48,56 | `max_length=10000` | Query max length in API schemas |
| 11 | `src/krag/embeddings/orchestrator.py` | 145 | `free_vram * 0.8` | 20% safety margin factor |

### Hardcoded Network Values

| # | File | Line | Value | Notes |
|---|------|------|-------|-------|
| 1 | `src/krag/models/configuration.py` | 263 | `default="0.0.0.0"` | Bind address — OK as Pydantic default |
| 2 | `src/krag/models/configuration.py` | 267 | `default=8742` | Port — OK as Pydantic default |
| 3 | `src/krag_cli/config.py` | 51 | `return "0.0.0.0", 8742` | Fallback values — should reference the same defaults as configuration model |

### Hardcoded URLs

| # | File | Line | URL | Notes |
|---|------|------|-----|-------|
| 1 | `src/krag/cli/plugin.py` | 497 | `https://astral.sh/uv/install.sh` | Install instruction — OK |
| 2 | `src/krag/cli/gpu.py` | 180 | `https://download.pytorch.org/whl/cu121` | Install instruction — OK |

---

## Task 10: Deprecated Python Patterns

### Old-style % string formatting
All `%` formatting found is in **`logger.*()` calls** (e.g., `logger.info("Loaded %d entries from %s", count, path)`). This is the **correct and idiomatic** pattern for logging — lazy string formatting avoids string construction overhead when the log level is disabled. **No issues.**

One instance uses `%(...)s` format in logging formatters (`config/logging.py:86-95`) — also correct.

### typing module imports (Python 3.11+ built-ins)
All `from typing import` statements in `src/` use only:
- `TYPE_CHECKING` — required, not deprecated
- `Any` — still required in Python 3.11+ (no built-in equivalent)

**No deprecated typing imports found** (no `List`, `Dict`, `Optional`, `Union`, `Tuple`, etc.). The codebase correctly uses `list[...]`, `dict[...]`, `X | None`, pipe unions throughout. Clean.

### ruff pyupgrade (UP) checks
`ruff check --select UP` reports **all checks passed** — no deprecated patterns detected.

---

## Summary of Highest-Priority Findings

### Critical / High Priority
1. **Dead dependency: `llama-index>=0.9.0`** — Not imported anywhere, heavyweight package. Remove from pyproject.toml.
2. **Dead file: `src/kragd/routers/health.py`** — Superseded by `system.py`, never imported. Delete.
3. **Duplicate dev dependency groups** — `[project.optional-dependencies] dev` has stale versions conflicting with `[dependency-groups] dev`. Remove the former.
4. **Silent `except Exception: pass`** in `src/krag/cli/modes.py:41` — Swallows all config loading failures without any logging or indication.

### Medium Priority
5. **Dead `tomli` dependency** with impossible env marker.
6. **`batch_size = 100` hardcoded 3 times** in `orchestration/indexer.py` — extract to a constant.
7. **`max_tokens=2000` hardcoded 4 times** across CLI modules — should be configurable or a constant.
8. **`timeout=120.0` hardcoded** in 2 CLI command files — should be a shared constant or config.
9. **`print()` instead of `logger`** in `src/krag/cli/eval.py` (5 occurrences) and `pipeline.py` (1 occurrence).
10. **No tests for 16+ source modules**, particularly ALL of `krag_cli/commands/` and most of `krag/cli/`.

### Low Priority
11. **Placeholder email** `ken@example.com` in pyproject.toml. [Ken: fixed; updated name and email]
12. **Version string duplicated** in pyproject.toml and `__init__.py`.
13. **`krag_cli/config.py:51`** hardcodes `"0.0.0.0", 8742` — should reference `Configuration` model defaults.
14. **88 `except Exception`** throughout — many are intentional resilience but some (10 silent ones) should at minimum log.
15. **`tests/performance/`** directory is empty (only `__init__.py`).
