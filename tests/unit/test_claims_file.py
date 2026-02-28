"""Tests for FileTypeHandler.claims_file() default behavior (T006).

Verifies that the base class returns False for all file paths,
ensuring backward compatibility for all existing handlers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from krag.plugins.interfaces import FileTypeHandler


class _StubHandler(FileTypeHandler):
    """Minimal concrete handler for testing the ABC default methods."""

    @property
    def name(self) -> str:
        return "stub"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_api_version(self) -> str:
        return "1.0"

    def supported_extensions(self) -> list[str]:
        return [".stub"]

    def extract_text(self, file_path: Path) -> str:
        return ""

    def extract_metadata(self, file_path: Path) -> dict:
        return {}


class TestClaimsFileDefault:
    """claims_file() on FileTypeHandler must default to False."""

    def test_returns_false_for_any_path(self) -> None:
        handler = _StubHandler()
        assert handler.claims_file(Path("/any/file.md")) is False

    def test_returns_false_for_nested_path(self) -> None:
        handler = _StubHandler()
        assert handler.claims_file(Path("/deep/nested/dir/note.md")) is False

    def test_returns_false_for_nonexistent_path(self) -> None:
        handler = _StubHandler()
        assert handler.claims_file(Path("/does/not/exist/file.txt")) is False

    @pytest.mark.parametrize(
        "path",
        [
            Path("/home/user/file.py"),
            Path("/tmp/notes/readme.md"),
            Path("relative/path.log"),
        ],
    )
    def test_returns_false_for_various_paths(self, path: Path) -> None:
        handler = _StubHandler()
        assert handler.claims_file(path) is False
