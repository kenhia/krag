"""Pydantic configuration schema for the Obsidian vault plugin."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ObsidianConfig(BaseModel):
    """Validation schema for ``[plugins.obsidian]`` configuration.

    Each key in *vaults* is a human-readable vault name (used in the
    ``obsidian://`` virtual path prefix) and each value is the filesystem
    path to the vault root directory.

    Example TOML::

        [plugins.obsidian.vaults]
        gratch = "~/obsidian/gratch"
        work   = "/data/vaults/work"
    """

    vaults: dict[str, str] = Field(
        default_factory=dict,
        description="Vault name → filesystem path mappings",
    )

    @field_validator("vaults")
    @classmethod
    def validate_vault_entries(cls, v: dict[str, str]) -> dict[str, str]:
        """Reject empty vault names or paths."""
        for name, path in v.items():
            if not name:
                raise ValueError("Vault name must be a non-empty string")
            if not path:
                raise ValueError(f"Vault path for '{name}' must be a non-empty string")
        return v
