"""Unit tests for ModeLoader — T028.

Tests TOML parsing, validation, and ModeConfiguration construction.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest


class TestModeLoaderLoad:
    """Test ModeLoader.load() with valid TOML files."""

    def test_load_complete_mode(self, tmp_path: Path) -> None:
        """A fully-specified mode TOML produces the correct ModeConfiguration."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "code.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "code"
            description = "Optimized for source code queries"

            [collections]
            code = 0.7
            tests = 0.3

            [llm]
            slot = "code"

            [prompt]
            preset = "code"

            [retrieval]
            top_k = 10
            similarity_threshold = 0.15

            [critic]
            enabled = false
            threshold = 3
        """)
        )

        mode = ModeLoader.load(toml_file)

        assert mode.name == "code"
        assert mode.description == "Optimized for source code queries"
        assert mode.collections == {"code": 0.7, "tests": 0.3}
        assert mode.llm_slot == "code"
        assert mode.preset == "code"
        assert mode.top_k == 10
        assert mode.similarity_threshold == 0.15
        assert mode.critic_enabled is False
        assert mode.critic_threshold == 3

    def test_load_minimal_mode(self, tmp_path: Path) -> None:
        """A mode with only [mode].name uses all defaults."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "minimal.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "minimal"
        """)
        )

        mode = ModeLoader.load(toml_file)

        assert mode.name == "minimal"
        assert mode.description == ""
        assert mode.collections == {"code": 1.0, "tests": 1.0, "docs": 1.0, "text": 1.0}
        assert mode.llm_slot == "text"
        assert mode.preset == "balanced"
        assert mode.top_k == 5
        assert mode.similarity_threshold == 0.2
        assert mode.critic_enabled is False
        assert mode.critic_threshold == 3

    def test_load_partial_collections(self, tmp_path: Path) -> None:
        """Only specified collections appear in the result."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "docs-only.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "docs-only"

            [collections]
            docs = 1.0
        """)
        )

        mode = ModeLoader.load(toml_file)

        assert mode.collections == {"docs": 1.0}

    def test_load_name_is_lowercased(self, tmp_path: Path) -> None:
        """Mode name is normalized to lowercase."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "mixed.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "MyMode"
        """)
        )

        mode = ModeLoader.load(toml_file)
        assert mode.name == "mymode"


class TestModeLoaderValidation:
    """Test ModeLoader validation rejects invalid TOML."""

    def test_missing_mode_section(self, tmp_path: Path) -> None:
        """TOML without [mode] section raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "bad.toml"
        toml_file.write_text("[collections]\ncode = 1.0\n")

        with pytest.raises(ValueError, match="[mode]"):
            ModeLoader.load(toml_file)

    def test_missing_name_field(self, tmp_path: Path) -> None:
        """TOML without mode.name raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "noname.toml"
        toml_file.write_text("[mode]\ndescription = 'test'\n")

        with pytest.raises(ValueError, match="name"):
            ModeLoader.load(toml_file)

    def test_invalid_collection_name(self, tmp_path: Path) -> None:
        """Unknown collection name in [collections] raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "badcoll.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "bad"

            [collections]
            invalid = 1.0
        """)
        )

        with pytest.raises(ValueError, match="invalid"):
            ModeLoader.load(toml_file)

    def test_invalid_collection_weight(self, tmp_path: Path) -> None:
        """Weight outside (0.0, 1.0] raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "badweight.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "bad"

            [collections]
            code = 0.0
        """)
        )

        with pytest.raises(ValueError, match="weight"):
            ModeLoader.load(toml_file)

    def test_invalid_llm_slot(self, tmp_path: Path) -> None:
        """LLM slot not 'text' or 'code' raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "badslot.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "bad"

            [llm]
            slot = "vision"
        """)
        )

        with pytest.raises(ValueError, match="text.*code"):
            ModeLoader.load(toml_file)

    def test_invalid_preset(self, tmp_path: Path) -> None:
        """Unknown preset name raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "badpreset.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "bad"

            [prompt]
            preset = "turbo"
        """)
        )

        with pytest.raises(ValueError, match="preset"):
            ModeLoader.load(toml_file)

    def test_invalid_top_k(self, tmp_path: Path) -> None:
        """top_k < 1 raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "badtopk.toml"
        toml_file.write_text(
            dedent("""\
            [mode]
            name = "bad"

            [retrieval]
            top_k = 0
        """)
        )

        with pytest.raises(ValueError):
            ModeLoader.load(toml_file)

    def test_invalid_toml_syntax(self, tmp_path: Path) -> None:
        """Malformed TOML raises ValueError."""
        from krag.modes.mode_loader import ModeLoader

        toml_file = tmp_path / "malformed.toml"
        toml_file.write_text("this is not = [valid toml\n")

        with pytest.raises(ValueError, match="[Pp]arse|TOML|syntax"):
            ModeLoader.load(toml_file)

    def test_file_not_found(self) -> None:
        """Non-existent file raises FileNotFoundError."""
        from krag.modes.mode_loader import ModeLoader

        with pytest.raises(FileNotFoundError):
            ModeLoader.load(Path("/nonexistent/mode.toml"))


class TestModeLoaderLoadDir:
    """Test ModeLoader.load_directory() for bulk loading."""

    def test_load_directory(self, tmp_path: Path) -> None:
        """All .toml files in directory produce ModeConfigurations."""
        from krag.modes.mode_loader import ModeLoader

        for name in ("alpha", "beta"):
            (tmp_path / f"{name}.toml").write_text(f'[mode]\nname = "{name}"\n')

        modes = ModeLoader.load_directory(tmp_path)
        names = {m.name for m in modes}

        assert names == {"alpha", "beta"}

    def test_load_directory_empty(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        from krag.modes.mode_loader import ModeLoader

        modes = ModeLoader.load_directory(tmp_path)
        assert modes == []

    def test_load_directory_skips_non_toml(self, tmp_path: Path) -> None:
        """Non-.toml files are ignored."""
        from krag.modes.mode_loader import ModeLoader

        (tmp_path / "readme.md").write_text("# Modes\n")
        (tmp_path / "valid.toml").write_text('[mode]\nname = "valid"\n')

        modes = ModeLoader.load_directory(tmp_path)
        assert len(modes) == 1
        assert modes[0].name == "valid"

    def test_load_directory_skips_invalid(self, tmp_path: Path) -> None:
        """Invalid TOML files are skipped with warning, not fatal."""
        from krag.modes.mode_loader import ModeLoader

        (tmp_path / "good.toml").write_text('[mode]\nname = "good"\n')
        (tmp_path / "bad.toml").write_text("[collections]\ncode = 1.0\n")  # no [mode]

        modes = ModeLoader.load_directory(tmp_path)
        assert len(modes) == 1
        assert modes[0].name == "good"
