"""Tests for ObsidianConfig Pydantic schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from krag_plugin_obsidian.config import ObsidianConfig


class TestObsidianConfigValid:
    """T020: ObsidianConfig validates vault mappings correctly."""

    def test_valid_single_vault(self) -> None:
        """Single vault mapping is accepted."""
        config = ObsidianConfig(vaults={"gratch": "~/obsidian/gratch"})
        assert config.vaults == {"gratch": "~/obsidian/gratch"}

    def test_valid_multiple_vaults(self) -> None:
        """Multiple vault mappings are accepted."""
        config = ObsidianConfig(
            vaults={
                "personal": "~/obsidian/personal",
                "work": "/data/vaults/work",
            }
        )
        assert len(config.vaults) == 2
        assert config.vaults["personal"] == "~/obsidian/personal"
        assert config.vaults["work"] == "/data/vaults/work"

    def test_empty_vaults_dict(self) -> None:
        """Empty vaults dict is valid (plugin loads as no-op)."""
        config = ObsidianConfig(vaults={})
        assert config.vaults == {}

    def test_default_vaults_empty(self) -> None:
        """Vaults defaults to empty dict when omitted."""
        config = ObsidianConfig()
        assert config.vaults == {}

    def test_vault_name_with_hyphens_underscores(self) -> None:
        """Vault names can contain hyphens and underscores."""
        config = ObsidianConfig(vaults={"my-vault_2": "/tmp/vault"})
        assert "my-vault_2" in config.vaults


class TestObsidianConfigInvalid:
    """T021: ObsidianConfig rejects invalid vault entries."""

    def test_non_string_vault_path_rejected(self) -> None:
        """Non-string vault path values are rejected."""
        with pytest.raises(ValidationError):
            ObsidianConfig(vaults={"bad": 123})  # type: ignore[dict-item]

    def test_non_string_vault_name_rejected(self) -> None:
        """Non-string vault name keys are rejected."""
        with pytest.raises(ValidationError):
            ObsidianConfig(vaults={123: "/tmp/vault"})  # type: ignore[dict-item]

    def test_empty_vault_path_rejected(self) -> None:
        """Empty string vault path is rejected."""
        with pytest.raises(ValidationError):
            ObsidianConfig(vaults={"bad": ""})

    def test_empty_vault_name_rejected(self) -> None:
        """Empty string vault name is rejected."""
        with pytest.raises(ValidationError):
            ObsidianConfig(vaults={"": "/tmp/vault"})

    def test_vaults_not_a_dict_rejected(self) -> None:
        """Non-dict vaults value is rejected."""
        with pytest.raises(ValidationError):
            ObsidianConfig(vaults="not-a-dict")  # type: ignore[arg-type]
