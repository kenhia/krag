"""Unit tests for ModeRegistry — T029.

Tests registration, lookup, listing, and builtin loading.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from krag.models.configuration import ModeConfiguration


def _make_mode(name: str, **overrides: object) -> ModeConfiguration:
    """Helper to build a ModeConfiguration with minimal boilerplate."""
    defaults: dict[str, object] = {
        "name": name,
        "description": "",
        "collections": {"code": 1.0, "tests": 1.0, "docs": 1.0, "text": 1.0},
        "llm_slot": "text",
        "preset": "balanced",
        "top_k": 5,
        "similarity_threshold": 0.2,
        "critic_enabled": False,
        "critic_threshold": 3,
    }
    defaults.update(overrides)
    return ModeConfiguration(**defaults)  # type: ignore[arg-type]


class TestModeRegistryRegister:
    """Test register/get operations."""

    def test_register_and_get(self) -> None:
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        mode = _make_mode("code", llm_slot="code", preset="code")
        registry.register(mode)

        assert registry.get("code") is mode

    def test_get_case_insensitive(self) -> None:
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        mode = _make_mode("code")
        registry.register(mode)

        assert registry.get("Code") is mode
        assert registry.get("CODE") is mode

    def test_get_unknown_raises(self) -> None:
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()

        with pytest.raises(ValueError, match="nope"):
            registry.get("nope")

    def test_register_overwrites(self) -> None:
        """Re-registering a mode name replaces the existing entry."""
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        old = _make_mode("code", preset="balanced")
        new = _make_mode("code", preset="code")
        registry.register(old)
        registry.register(new)

        assert registry.get("code").preset == "code"


class TestModeRegistryList:
    """Test list_modes enumeration."""

    def test_list_modes_empty(self) -> None:
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        assert registry.list_modes() == []

    def test_list_modes_sorted(self) -> None:
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        for name in ("docs", "code", "default"):
            registry.register(_make_mode(name))

        names = [m.name for m in registry.list_modes()]
        assert names == ["code", "default", "docs"]


class TestModeRegistryBuiltins:
    """Test loading the built-in modes from disk."""

    def test_load_builtins(self) -> None:
        """Built-in directory contains default, code, docs, obsidian."""
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        registry.load_builtins()

        names = {m.name for m in registry.list_modes()}
        assert names == {"default", "code", "docs", "obsidian"}

    def test_builtin_default_mode(self) -> None:
        """The 'default' mode uses all 4 collections at weight 1.0."""
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        registry.load_builtins()

        default = registry.get("default")
        assert default.collections == {
            "code": 1.0,
            "tests": 1.0,
            "docs": 1.0,
            "text": 1.0,
        }
        assert default.llm_slot == "text"
        assert default.preset == "balanced"

    def test_builtin_code_mode(self) -> None:
        """The 'code' mode focuses on code+tests."""
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        registry.load_builtins()

        code = registry.get("code")
        assert code.collections == {"code": 0.7, "tests": 0.3}
        assert code.llm_slot == "code"
        assert code.preset == "code"
        assert code.top_k == 10

    def test_builtin_docs_mode(self) -> None:
        """The 'docs' mode targets only documentation."""
        from krag.modes.mode_registry import ModeRegistry

        registry = ModeRegistry()
        registry.load_builtins()

        docs = registry.get("docs")
        assert docs.collections == {"docs": 1.0}
        assert docs.llm_slot == "text"

    def test_user_dir_overrides_builtin(self, tmp_path: Path) -> None:
        """User modes override builtins with the same name."""
        from krag.modes.mode_registry import ModeRegistry

        user_default = tmp_path / "default.toml"
        user_default.write_text(
            dedent("""\
            [mode]
            name = "default"
            description = "User override"

            [collections]
            docs = 1.0

            [llm]
            slot = "text"

            [prompt]
            preset = "strict"
        """)
        )

        registry = ModeRegistry()
        registry.load_builtins()
        registry.load_user_modes(tmp_path)

        default = registry.get("default")
        assert default.description == "User override"
        assert default.preset == "strict"

    def test_load_user_modes_adds_custom(self, tmp_path: Path) -> None:
        """User can add entirely new modes."""
        from krag.modes.mode_registry import ModeRegistry

        custom = tmp_path / "custom.toml"
        custom.write_text(
            dedent("""\
            [mode]
            name = "custom"
            description = "A user-defined mode"

            [collections]
            code = 0.5
            docs = 0.5

            [llm]
            slot = "text"

            [prompt]
            preset = "verbose"
        """)
        )

        registry = ModeRegistry()
        registry.load_builtins()
        registry.load_user_modes(tmp_path)

        assert "custom" in {m.name for m in registry.list_modes()}
        custom_mode = registry.get("custom")
        assert custom_mode.preset == "verbose"
