# Code Quality & Cleanup Audit Report

**Project:** krag — Personal Multimodal RAG System  
**Audit Date:** 2025  
**Scope:** All Python source files in `src/krag/`, `src/krag_cli/`, `src/kragd/`, and `tests/`

---

## 1. Code Quality & Consistency

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 1.1 | `config/defaults.py` | 115, 121 | **HIGH** | `DEFAULT_VECTOR_STORE_PATH` defined twice — line 121 silently overwrites line 115 with the same value | Remove the duplicate at line 121 |
| 1.2 | `config/defaults.py` | 128 | LOW | `DEFAULT_PLUGIN_SETTINGS: dict[str, dict] = {}` — inner `dict` missing type parameters | Change to `dict[str, dict[str, Any]]` |
| 1.3 | `config/settings.py` | 55–245 | **MEDIUM** | ~200 lines of repetitive manual TOML field-to-model mapping (`if "key" in section: config_dict["field"] = section["key"]`) — repeated 3× for `_load_toml`, `create_default`, and `migrate_yaml_to_toml` | Extract a shared mapping dict or serialization layer; consider using Pydantic's built-in TOML/dict round-tripping |
| 1.4 | `kragd/schemas.py` | 211 | **MEDIUM** | `class IndexError(BaseModel)` shadows the Python builtin `IndexError` | Rename to `IndexingError` or `FileIndexError` |
| 1.5 | `krag_cli/display.py` | 22 | LOW | `class OutputFormat(str, Enum): # noqa: UP042` — suppresses the StrEnum upgrade suggestion | Replace with `class OutputFormat(StrEnum)` (Python 3.11+), remove noqa |
| 1.6 | `krag/cli/query.py` | 20 | NONE | Already uses `StrEnum` correctly | — (contrast with krag_cli duplicate) |
| 1.7 | `krag_cli/display.py` + `krag/cli/query.py` | — | LOW | Two separate `OutputFormat` enums with the same values in two packages | Extract to a shared location |
| 1.8 | `orchestration/indexer.py` | 548 | LOW | `except Exception: pass` swallows errors from `get_chunk_metadata()` silently | At minimum `logger.debug()` the exception |
| 1.9 | `orchestration/indexer.py` | 167, 172 | LOW | Two `# type: ignore` suppressions for vector_store initialization | Add proper Optional typing or restructure init flow |
| 1.10 | `plugins/loader.py` | 131 | LOW | Bare `# type: ignore` without error code | Specify the exact mypy code: `# type: ignore[return-value]` |
| 1.11 | `plugins/registry.py` | 84 | LOW | Bare `# type: ignore` without error code | Same as above |
| 1.12 | `models/text_chunk.py` | 41 | LOW | `# type: ignore[type-arg]` on validator | Fix the annotation to satisfy mypy |
| 1.13 | `krag/cli/gpu.py` | 16 | LOW | `torch = None  # type: ignore[assignment]` — conditional import anti-pattern | Consider `TYPE_CHECKING` guard or explicit protocol |

## 2. Error Handling

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 2.1 | `kragd/service.py` | 259 | **MEDIUM** | `except RuntimeError: pass` — silently swallows asyncio event loop errors during lifecycle init | Log at debug level or handle specifically |
| 2.2 | `kragd/service.py` | 1133, 1148, 1167 | **MEDIUM** | Multiple `except Exception: pass` blocks in `get_status()` (vector store stats, named spaces, VRAM) — errors are invisible | Use `logger.debug("...", exc_info=True)` |
| 2.3 | `kragd/service.py` | 687 | LOW | `except Exception: pass` after Qdrant `get_collection()` in debug_query — masks connection/schema errors | Log at debug level |
| 2.4 | `orchestration/indexer.py` | 548 | **MEDIUM** | `except Exception: pass` when getting chunk metadata — could hide bugs in chunker plugins | At minimum log at warning or debug level |
| 2.5 | `synthesis/llm_pool.py` | 254 | LOW | `except Exception: pass  # noqa: BLE001` when closing LLM instance | Log at debug level; the noqa hints this was a deliberate choice |
| 2.6 | `krag/cli/modes.py` | 43 | LOW | `except Exception: pass` when loading config for mode registry — user gets no feedback on config errors | Log at debug level |
| 2.7 | `krag/cli/pipeline.py` | ~198 | LOW | `except Exception:` when loading lexicon with no log or re-raise | Add `logger.warning("Failed to load lexicon", exc_info=True)` |
| 2.8 | `config/logging.py` | 147 | LOW | f-string in `logger.debug(f"...")` — should use lazy % formatting per logging best practices | Change to `logger.debug("... %s", value)` |
| 2.9 | Multiple files | — | INFO | ~50 instances of `except Exception` across the codebase; majority log the error properly, but ~10 do `pass` | Audit each `pass` handler individually |

## 3. Logging

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 3.1 | All files | — | NONE | Consistent `logger = logging.getLogger(__name__)` pattern throughout | Good — no action needed |
| 3.2 | Many files | — | LOW | f-strings used in ~30 logger calls (e.g., `logger.info(f"...")`) instead of lazy % formatting | Replace with `logger.info("...", arg)` for perf — low priority since these aren't hot paths |
| 3.3 | `krag/cli/pipeline.py` | 107 | LOW | Uses bare `print(..., file=sys.stderr)` for error output instead of logging or Rich console | Use `console.print("[red]Error:...")` for consistency |

## 4. Configuration

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 4.1 | `pyproject.toml` + `mypy.ini` | — | **HIGH** | `pyproject.toml` has `[tool.mypy]` with `strict = true`, while `mypy.ini` disables 11 error codes and sets `strict_optional = False`. `mypy.ini` takes precedence, making pyproject.toml's mypy config dead/misleading | Consolidate into one location — move the mypy.ini overrides into pyproject.toml or remove the pyproject.toml section |
| 4.2 | `pyproject.toml` | 22 | **MEDIUM** | `"tomli>=2.0.0 ; python_version < '3.11'"` — project requires `>=3.11`, so this dependency is **never installed** | Remove the dependency |
| 4.3 | `pyproject.toml` | 17 | **MEDIUM** | `"llama-index>=0.9.0"` is declared as a dependency but **never imported** anywhere in the codebase | Remove unless planned for future use |
| 4.4 | `pyproject.toml` | 35–44, 47–52 | **MEDIUM** | Duplicate dev dependency groups: `[dependency-groups] dev` (PEP 735) and `[project.optional-dependencies] dev` with **conflicting versions** (e.g., pytest >=9.0.2 vs >=7.4.0, mypy >=1.19.1 vs >=1.5.0) | Consolidate into `[dependency-groups]` (the modern approach) and remove the optional-dependencies one |
| 4.5 | `models/configuration.py` vs `config/defaults.py` | — | LOW | `supported_file_types` default list in `Configuration` includes `.lua`, `.ps1`, `.psm1`, `.psd1` which aren't in `DEFAULT_SUPPORTED_FILE_TYPES` in defaults.py | Align the two lists — have Configuration reference the defaults constant |
| 4.6 | `krag_cli/config.py` | 55 | LOW | Default service host is `"0.0.0.0"` when no config found — should be `"127.0.0.1"` for a client connecting to localhost | Change fallback to `"127.0.0.1"` |
| 4.7 | `kragd/schemas.py` | 32, 59 | LOW | `llm` field marked as "deprecated — use mode" in schemas but no deprecation warning is emitted at runtime | Add `warnings.warn()` or a Pydantic `model_validator` that warns when `llm` is set |
| 4.8 | `krag/cli/query.py` | 69 | LOW | `--llm` flag marked deprecated via help text + `hidden=True` but is still fully functional | Either remove in next major version or add runtime deprecation warning |

## 5. API / Interface Issues

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 5.1 | `kragd/routers/health.py` | — | **MEDIUM** | Dead file — `health.py` defines `/health`, `/status`, `/shutdown` routes but is **never mounted** in `app.py`. `system.py` provides the same endpoints and IS mounted. | Delete `routers/health.py` |
| 5.2 | `kragd/service.py` + `kragd/app.py` | — | LOW | `_get_version()` function is duplicated in both files (identical implementation) | Extract to a shared utility, e.g., `kragd/_version.py` |
| 5.3 | `kragd/__main__.py` | 45–56 | **MEDIUM** | `_write_pid()` and `_remove_pid()` duplicate the functionality in `kragd/pid.py` (`write_pid()` and `remove_pid()`) | Remove the private versions in `__main__.py` and use the `pid` module |
| 5.4 | `kragd/service.py` | 411 | LOW | Accesses `self.query_engine._lexicon_injector` — reaches into private internals | Add a public method to `QueryEngine` for setting the lexicon injector |
| 5.5 | `kragd/service.py` | 434, 559, 610, 644, 687, 1140 | **MEDIUM** | 6+ accesses to `self.llm_pool._slot_for()`, `self.llm_pool._text_slot`, `self.llm_pool._code_slot` — private API coupling | Expose `slot_for()`, `text_slot`, `code_slot` as public properties on `LLMPool` |
| 5.6 | `kragd/service.py` | 621, 641, 1140 | LOW | Accesses `self.embedding_orchestrator._model_names` (private dict) | Add public `get_model_names()` method to `EmbeddingOrchestrator` |
| 5.7 | `orchestration/indexer.py` | 546 | LOW | Accesses `self.embedding_orchestrator._model_names.get(vector_name, "")` — same private access pattern | Same fix as 5.6 |
| 5.8 | Config discovery | Multiple | LOW | Config file discovery logic duplicated in 4 places: `kragd/__main__.py:_find_config()`, `krag_cli/config.py:find_config()`, `krag/cli/pipeline.py:resolve_config_path()`, and inline in `krag/cli/index.py` | Consolidate into a single `krag.config.discovery.find_config()` utility |
| 5.9 | `krag/cli/modes.py`, `krag_cli/commands/query.py` | 38, 101 | **HIGH (BUG)** | Calls `ConfigManager.find_and_load()` which does **not exist** on `ConfigManager` — will raise `AttributeError` at runtime | Implement `find_and_load()` on `ConfigManager`, or replace with `ConfigManager.load(resolve_config_path())` |

## 6. Documentation

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 6.1 | `models/exceptions.py` | 5–52 | LOW | All exception classes except `FileProcessingError` have only `pass` with no docstring explaining when to use each | Add one-line docstrings to each exception class |
| 6.2 | `plugins/interfaces.py` | 4× | INFO | `# noqa: B027` on empty interface methods — these are intentional optional hooks | Document that these are no-op default implementations (already partially done) |
| 6.3 | `kragd/routers/__init__.py` | — | LOW | `__all__: list[str] = []` — empty `__all__` in routers package init | Either populate with router names or remove |
| 6.4 | `config/defaults.py` | 121 | LOW | Comment `# GPU defaults` precedes the duplicate `DEFAULT_VECTOR_STORE_PATH` which is not GPU-related | Remove the duplicate line; the comment is fine |

## 7. Tests

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 7.1 | `tests/` | — | **MEDIUM** | No test coverage for `krag/config/xdg.py` migration functions (`migrate_from_legacy`, `should_migrate_from_legacy`) | Add unit tests |
| 7.2 | `tests/` | — | LOW | No tests for `krag/cli/log.py` (rotate, clear, path commands) | Add basic CLI invoke tests |
| 7.3 | `tests/` | — | LOW | `tests/unit/cli/` contains only `test_plugin.py` — no tests for `cli/config.py`, `cli/index.py`, `cli/query.py`, `cli/modes.py`, `cli/gpu.py` | Add CLI command unit tests using `CliRunner` |
| 7.4 | `tests/unit/krag_cli/` | — | LOW | Only `test_client.py` — no tests for display formatting, config reading, or individual commands | Add tests for `display.py`, `config.py`, and command modules |
| 7.5 | `evaluation/runner.py` | 107 | INFO | `assert` used as runtime validation (`# noqa: S101`) | Fine for test helper code; could use a descriptive error instead |

## 8. Dependencies

| # | File | Line(s) | Severity | Issue | Suggested Fix |
|---|------|---------|----------|-------|---------------|
| 8.1 | `pyproject.toml` | 22 | **MEDIUM** | `tomli>=2.0.0 ; python_version < '3.11'` — dead dependency (project requires >=3.11) | Remove |
| 8.2 | `pyproject.toml` | 17 | **MEDIUM** | `llama-index>=0.9.0` — declared but never imported anywhere in the codebase | Remove unless planned for future use |
| 8.3 | `pyproject.toml` | 35–52 | **MEDIUM** | Duplicate dev dep groups with conflicting version pins (see 4.4) | Consolidate |
| 8.4 | `routing/rules.py` vs `synthesis/llm_pool.py` | — | LOW | Both define `CODE_EXTENSIONS` frozensets with overlapping but **different** content (llm_pool has `.go`, `.rb`, `.swift` etc. that routing/rules doesn't) | Extract to a single `krag.constants.CODE_EXTENSIONS` |

---

## Summary

| Category | Critical/High | Medium | Low | Info |
|----------|:---:|:---:|:---:|:---:|
| 1. Code Quality | 1 | 1 | 9 | 0 |
| 2. Error Handling | 0 | 3 | 5 | 1 |
| 3. Logging | 0 | 0 | 2 | 0 |
| 4. Configuration | 1 | 3 | 4 | 0 |
| 5. API / Interface | 1 | 3 | 4 | 0 |
| 6. Documentation | 0 | 0 | 3 | 1 |
| 7. Tests | 0 | 1 | 3 | 1 |
| 8. Dependencies | 0 | 3 | 1 | 0 |
| **Totals** | **3** | **14** | **31** | **3** |

### Top 5 Priority Items

1. **BUG — `ConfigManager.find_and_load()` does not exist** (5.9) — will crash `krag modes list` and `krag query` in krag_cli at runtime
2. **Dead/conflicting mypy configuration** (4.1) — pyproject.toml's `strict = true` is silently overridden by mypy.ini
3. **Duplicate `DEFAULT_VECTOR_STORE_PATH`** (1.1) — silent redefinition, confusing to maintainers
4. **Duplicate PID utilities** (5.3) and **duplicate `_get_version()`** (5.2) — DRY violations
5. **Dead dependencies: `llama-index` and `tomli`** (8.1, 8.2) — unnecessary install weight

### Positive Observations

- Consistent logging pattern (`logging.getLogger(__name__)`) across all modules
- No bare `except:` clauses anywhere
- Good use of `typing.TYPE_CHECKING` for import-time performance
- Comprehensive test suite: unit, contract, and integration layers with good module coverage
- Clean separation of concerns: core library / CLI client / daemon service
- Well-structured plugin system with clear interfaces
- Pydantic models with field validators and constraints throughout
- Context manager support on `IndexingOrchestrator`
