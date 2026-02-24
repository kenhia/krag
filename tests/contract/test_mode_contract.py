"""Contract tests validating built-in mode TOML files against the schema — T030.

Every .toml in modes/builtin/ MUST:
  1. Parse into a valid ModeConfiguration.
  2. Contain only allowed sections and fields.
  3. Have collection weights in (0.0, 1.0].
  4. Reference a valid LLM slot and prompt preset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from krag.models.configuration import (
    VALID_COLLECTIONS,
    VALID_LLM_SLOTS,
    VALID_PRESETS,
    ModeConfiguration,
)

BUILTIN_DIR = Path(__file__).resolve().parents[2] / "src" / "krag" / "modes" / "builtin"


def _builtin_toml_files() -> list[Path]:
    """Return all .toml files in the builtin modes directory."""
    assert BUILTIN_DIR.is_dir(), f"Builtin dir missing: {BUILTIN_DIR}"
    return sorted(BUILTIN_DIR.glob("*.toml"))


class TestBuiltinModesContract:
    """Contract: every built-in TOML validates as a ModeConfiguration."""

    @pytest.fixture(params=_builtin_toml_files(), ids=lambda p: p.stem)
    def builtin_mode(self, request: pytest.FixtureRequest) -> ModeConfiguration:
        from krag.modes.mode_loader import ModeLoader

        return ModeLoader.load(request.param)

    def test_parses_successfully(self, builtin_mode: ModeConfiguration) -> None:
        """Every built-in TOML produces a ModeConfiguration without errors."""
        assert isinstance(builtin_mode, ModeConfiguration)

    def test_name_matches_filename(self, builtin_mode: ModeConfiguration) -> None:
        """Mode name should be a non-empty lowercase string."""
        assert builtin_mode.name
        assert builtin_mode.name == builtin_mode.name.lower()

    def test_collections_are_valid(self, builtin_mode: ModeConfiguration) -> None:
        """All collection keys must be in the allowed set."""
        for coll_name in builtin_mode.collections:
            assert coll_name in VALID_COLLECTIONS, (
                f"Unknown collection '{coll_name}' in mode '{builtin_mode.name}'"
            )

    def test_collection_weights_in_range(self, builtin_mode: ModeConfiguration) -> None:
        """Weights must be in (0.0, 1.0]."""
        for coll_name, weight in builtin_mode.collections.items():
            assert 0.0 < weight <= 1.0, (
                f"Bad weight {weight} for '{coll_name}' in mode '{builtin_mode.name}'"
            )

    def test_llm_slot_is_valid(self, builtin_mode: ModeConfiguration) -> None:
        """LLM slot must be one of the valid slots."""
        assert builtin_mode.llm_slot in VALID_LLM_SLOTS, (
            f"Invalid llm_slot '{builtin_mode.llm_slot}' in mode '{builtin_mode.name}'"
        )

    def test_preset_is_valid(self, builtin_mode: ModeConfiguration) -> None:
        """Prompt preset must be a recognized preset name."""
        assert builtin_mode.preset in VALID_PRESETS, (
            f"Invalid preset '{builtin_mode.preset}' in mode '{builtin_mode.name}'"
        )

    def test_top_k_positive(self, builtin_mode: ModeConfiguration) -> None:
        """top_k must be >= 1."""
        assert builtin_mode.top_k >= 1

    def test_similarity_threshold_in_range(self, builtin_mode: ModeConfiguration) -> None:
        """similarity_threshold in [0.0, 1.0]."""
        assert 0.0 <= builtin_mode.similarity_threshold <= 1.0


class TestSchemaCompleteness:
    """Contract: the required three built-in modes exist."""

    def test_required_builtins_exist(self) -> None:
        files = {p.stem for p in _builtin_toml_files()}
        assert files >= {"default", "code", "docs"}, f"Missing required builtins. Found: {files}"
