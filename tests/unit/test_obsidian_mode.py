"""Unit tests for the obsidian retrieval mode — Phase 7 / User Story 5.

Validates that ``obsidian.toml`` loads correctly via :class:`ModeLoader`
and that every field matches the requirements contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from krag.models.configuration import ModeConfiguration
from krag.modes.mode_loader import ModeLoader

# Path to the builtin modes directory
_BUILTIN_DIR = Path(__file__).resolve().parents[2] / "src" / "krag" / "modes" / "builtin"


@pytest.fixture()
def obsidian_mode() -> ModeConfiguration:
    """Load the obsidian mode from the builtin directory."""
    toml_path = _BUILTIN_DIR / "obsidian.toml"
    if not toml_path.is_file():
        pytest.skip("obsidian.toml not yet created")
    return ModeLoader.load(toml_path)


# ---------------------------------------------------------------------------
# T064 — obsidian.toml loads as valid ModeConfiguration
# ---------------------------------------------------------------------------


class TestObsidianModeLoads:
    """obsidian.toml loads successfully via ModeLoader."""

    def test_loads_without_error(self, obsidian_mode: ModeConfiguration) -> None:
        """obsidian.toml should parse and validate without exceptions."""
        assert isinstance(obsidian_mode, ModeConfiguration)

    def test_name_is_obsidian(self, obsidian_mode: ModeConfiguration) -> None:
        """Mode name must be 'obsidian'."""
        assert obsidian_mode.name == "obsidian"

    def test_description_non_empty(self, obsidian_mode: ModeConfiguration) -> None:
        """Description should be non-empty."""
        assert obsidian_mode.description


# ---------------------------------------------------------------------------
# T065 — collection weights: docs=1.0, code=0.7
# ---------------------------------------------------------------------------


class TestObsidianModeCollections:
    """Collection targeting matches contract (FR-023)."""

    def test_docs_weight(self, obsidian_mode: ModeConfiguration) -> None:
        """docs collection weight must be 1.0."""
        assert obsidian_mode.collections["docs"] == 1.0

    def test_code_weight(self, obsidian_mode: ModeConfiguration) -> None:
        """code collection weight must be 0.7."""
        assert obsidian_mode.collections["code"] == 0.7

    def test_no_tests_collection(self, obsidian_mode: ModeConfiguration) -> None:
        """tests collection must NOT be targeted (FR-023)."""
        assert "tests" not in obsidian_mode.collections

    def test_no_text_collection(self, obsidian_mode: ModeConfiguration) -> None:
        """text collection must NOT be targeted (FR-023)."""
        assert "text" not in obsidian_mode.collections


# ---------------------------------------------------------------------------
# T066 — critic enabled with threshold 3
# ---------------------------------------------------------------------------


class TestObsidianModeCritic:
    """Critic settings match contract (FR-024)."""

    def test_critic_enabled(self, obsidian_mode: ModeConfiguration) -> None:
        """Critic must be enabled."""
        assert obsidian_mode.critic_enabled is True

    def test_critic_threshold(self, obsidian_mode: ModeConfiguration) -> None:
        """Critic threshold must be 3."""
        assert obsidian_mode.critic_threshold == 3


# ---------------------------------------------------------------------------
# T067 — balanced prompt preset
# ---------------------------------------------------------------------------


class TestObsidianModePreset:
    """Prompt preset matches contract (FR-025)."""

    def test_balanced_preset(self, obsidian_mode: ModeConfiguration) -> None:
        """Prompt preset must be 'balanced'."""
        assert obsidian_mode.preset == "balanced"

    def test_llm_slot_text(self, obsidian_mode: ModeConfiguration) -> None:
        """LLM slot must be 'text'."""
        assert obsidian_mode.llm_slot == "text"

    def test_top_k(self, obsidian_mode: ModeConfiguration) -> None:
        """top_k must be 8."""
        assert obsidian_mode.top_k == 8

    def test_similarity_threshold(self, obsidian_mode: ModeConfiguration) -> None:
        """similarity_threshold must be 0.15."""
        assert obsidian_mode.similarity_threshold == 0.15
