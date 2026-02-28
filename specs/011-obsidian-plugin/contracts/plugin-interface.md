# Contract: FileTypeHandler Interface Extension

**Scope**: `src/krag/plugins/interfaces.py` — `FileTypeHandler` ABC

## New Method: `claims_file`

Added to `FileTypeHandler` as a non-abstract method with `False` default.

```python
def claims_file(self, file_path: Path) -> bool:
    """Claim ownership of a file by path, regardless of extension.

    Path-claiming plugins take priority over extension-based resolution
    in PluginRegistry.get_handler_for_file(). Default returns False
    (no path-based claiming).

    Args:
        file_path: Absolute path to the file.

    Returns:
        bool: True if this plugin claims exclusive ownership.

    Notes:
        - Should be fast — use path prefix checks, not file I/O.
        - Should not raise exceptions (return False on error).
        - When True, this plugin handles the file instead of extension-based lookup.
        - If file_path is not absolute, resolve it before comparison. Return False for paths that cannot be resolved.
    """
    return False
```

### Breaking Change: None

Default `False` preserves all existing plugin behavior. No existing plugin overrides this method.

### Affected Tests

- Unit tests for `FileTypeHandler` subclasses: verify `claims_file()` returns `False` by default
- New tests for Obsidian handler: verify `claims_file()` returns `True` for vault paths, `False` otherwise

---

## Contract: PluginRegistry Resolution Order

**Scope**: `src/krag/plugins/registry.py` — `get_handler_for_file()`

### Current Resolution

```
Extension lookup → can_handle_file() → handler or None
```

### New Resolution (FR-009)

```
Phase 1: Path-claiming plugins (claims_file) → handler
Phase 2: Extension lookup → can_handle_file() → handler or None
```

### Method Signature (unchanged)

```python
def get_handler_for_file(
    self, file_path: Path, context: PluginContext | None = None
) -> FileTypeHandler | None:
```

### New Internal Method

```python
def _resolve_by_path_claim(
    self, file_path: Path, context: PluginContext | None = None
) -> FileTypeHandler | None:
    """Check path-claiming plugins for a file match.

    Only iterates plugins whose metadata has has_claims_file=True.
    Returns the first plugin that claims the file, or None.
    """
```

### PluginMetadata Extension

```python
# In src/krag/models/configuration.py
has_claims_file: bool = Field(
    default=False,
    description="Whether plugin overrides claims_file() for path-based resolution",
)
```

Set during `discover_plugins()` via:
```python
has_claims_file = type(handler).claims_file is not FileTypeHandler.claims_file
```

---

## Contract: Chunk-Level Collection Routing

**Scope**: `src/krag/orchestration/indexer.py` — `index_full()` and `index_incremental()`

### Payload Convention

Plugins that need per-chunk routing add `target_collection` to chunk metadata via their chunker's `get_chunk_metadata()` method. The field flows into the vector payload through the existing `payload.update(code_meta)` pipeline.

### Routing Behavior

```python
# Post _process_file(), before storing:
if any vector payload has "target_collection":
    for each vector:
        collection = payload.pop("target_collection", fallback_via_route_file())
        route to that collection
else:
    route all vectors to route_file() result (existing behavior)
```

### Field Lifecycle

| Stage | `target_collection` |
|-------|-------------------|
| Chunker creates chunk | Added to chunk metadata |
| `_process_file()` builds payload | Present in `payload` dict |
| Indexer routes vectors | Read and **removed** (`pop`) |
| Stored in Qdrant | **Not present** (routing hint only) |

### Backward Compatibility

Existing plugins produce no `target_collection` field → `any(...)` check is `False` → entire file routed via `route_file()` as before. Zero behavior change for existing plugins.
