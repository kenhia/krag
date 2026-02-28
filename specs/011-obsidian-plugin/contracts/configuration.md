# Contract: Obsidian Plugin Configuration

**Scope**: `[plugins.obsidian]` section in user's `config.toml`

## Configuration Schema

```toml
[plugins.obsidian]
# Plugin is auto-discovered via entry point; enabled by default.
# Set enabled = false to disable.
# enabled = false

[plugins.obsidian.vaults]
# Each key is a vault name (used in obsidian:// path prefix).
# Each value is a filesystem path to the vault root directory.
gratch = "~/obsidian/gratch"
work = "/data/vaults/work"
```

## Pydantic Validation Model

```python
from pydantic import BaseModel, Field

class ObsidianConfig(BaseModel):
    """Validation schema for [plugins.obsidian] configuration."""

    vaults: dict[str, str] = Field(
        default_factory=dict,
        description="Vault name → filesystem path mappings",
    )
```

Returned by `ObsidianFileTypeHandler.config_schema()` → `ObsidianConfig`.

## Validation Rules

| Rule | Field | Constraint | Behavior on Violation |
|------|-------|-----------|----------------------|
| C-01 | `vaults` | Must be a dict (or absent → empty) | Pydantic validation error → plugin disabled with warning |
| C-02 | Vault name (key) | Non-empty string | Pydantic validation error |
| C-03 | Vault path (value) | Non-empty string | Pydantic validation error |
| C-04 | Vault path (resolved) | Should be an existing directory | Warning logged, vault skipped (not an error) |
| C-05 | Empty vaults dict | No vaults configured | Plugin loads but `claims_file()` always returns `False` (no-op) |

## Initialization Behavior

```
1. config_schema() → ObsidianConfig (Pydantic validates structure)
2. initialize(config, context) →
   a. Parse vaults from config
   b. For each vault:
      - Expand ~ and resolve to absolute path
      - Check if directory exists
      - If exists: add to active vault_paths dict
      - If missing: log warning, skip
   c. Merge lexicon entries into LexiconStore (if context available)
   d. Log summary: "Obsidian plugin initialized with N vaults: [names]"
```
