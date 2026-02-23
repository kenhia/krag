"""Unit tests for CollectionRouter — 8-level precedence routing.

Tests cover all routing precedence levels defined in routing/rules.py:
1. Plugin override → plugin-declared collection
2. Test directory pattern → tests
3. Test filename pattern → tests
4. Well-known doc filename → docs
5. Docs extension → docs
6. Code extension → code
7. Config/data extension → text
8. Fallback → text
"""

from __future__ import annotations

from pathlib import Path

import pytest

from krag.routing.collection_router import CollectionRouter
from krag.routing.rules import (
    COLLECTION_CODE,
    COLLECTION_DOCS,
    COLLECTION_TESTS,
    COLLECTION_TEXT,
)


class TestLevel1PluginOverride:
    """Level 1: Plugin override takes highest priority."""

    def test_plugin_override_routes_to_declared_collection(self) -> None:
        router = CollectionRouter(plugin_overrides={"my_plugin": COLLECTION_CODE})
        result = router.route(Path("anything.md"), ".md", plugin_name="my_plugin")
        assert result == COLLECTION_CODE

    def test_plugin_override_overrides_test_dir(self) -> None:
        router = CollectionRouter(plugin_overrides={"log_parser": COLLECTION_TEXT})
        result = router.route(Path("tests/log_parser/output.log"), ".log", plugin_name="log_parser")
        assert result == COLLECTION_TEXT

    def test_unknown_plugin_falls_through(self) -> None:
        router = CollectionRouter(plugin_overrides={"my_plugin": COLLECTION_CODE})
        result = router.route(Path("src/main.py"), ".py", plugin_name="other_plugin")
        assert result == COLLECTION_CODE  # falls to code extension

    def test_no_plugin_name_falls_through(self) -> None:
        router = CollectionRouter(plugin_overrides={"my_plugin": COLLECTION_CODE})
        result = router.route(Path("README.md"), ".md", plugin_name=None)
        assert result == COLLECTION_DOCS  # well-known doc


class TestLevel2TestDirectory:
    """Level 2: Test directory patterns route to tests collection."""

    @pytest.mark.parametrize(
        "path",
        [
            "tests/test_main.py",
            "test/helpers.py",
            "src/__tests__/Button.test.tsx",
            "test_utils/fixtures.py",
        ],
    )
    def test_test_dir_routes_to_tests(self, path: str) -> None:
        router = CollectionRouter()
        ext = Path(path).suffix
        result = router.route(Path(path), ext, plugin_name=None)
        assert result == COLLECTION_TESTS

    def test_test_dir_overrides_code_extension(self) -> None:
        """A .py file inside tests/ goes to tests, not code."""
        router = CollectionRouter()
        result = router.route(Path("tests/helpers/utils.py"), ".py", plugin_name=None)
        assert result == COLLECTION_TESTS

    def test_test_dir_overrides_docs_extension(self) -> None:
        """A .md file inside tests/ goes to tests, not docs (FR-005)."""
        router = CollectionRouter()
        result = router.route(Path("tests/README.md"), ".md", plugin_name=None)
        assert result == COLLECTION_TESTS

    def test_spec_dir_not_test(self) -> None:
        """spec/ and specs/ are NOT test dirs — they route via extension."""
        router = CollectionRouter()
        result = router.route(Path("specs/requirements.md"), ".md", plugin_name=None)
        assert result == COLLECTION_DOCS

    def test_specs_dir_not_test(self) -> None:
        router = CollectionRouter()
        result = router.route(Path("spec/design.md"), ".md", plugin_name=None)
        assert result == COLLECTION_DOCS


class TestLevel3TestFilename:
    """Level 3: Test filename patterns route to tests collection."""

    @pytest.mark.parametrize(
        "path",
        [
            "src/test_main.py",
            "src/main_test.py",
            "src/main_test.go",
            "src/Button.test.tsx",
            "src/Button.spec.ts",
            "src/conftest.py",
            "pytest.ini",
        ],
    )
    def test_test_filename_routes_to_tests(self, path: str) -> None:
        router = CollectionRouter()
        ext = Path(path).suffix
        result = router.route(Path(path), ext, plugin_name=None)
        assert result == COLLECTION_TESTS

    def test_setup_cfg_routes_to_tests(self) -> None:
        """setup.cfg often contains pytest config."""
        router = CollectionRouter()
        result = router.route(Path("setup.cfg"), ".cfg", plugin_name=None)
        assert result == COLLECTION_TESTS


class TestLevel4WellKnownDocs:
    """Level 4: Well-known documentation filenames route to docs."""

    @pytest.mark.parametrize(
        "filename",
        [
            "README.md",
            "CHANGELOG.md",
            "LICENSE",
            "LICENSE.txt",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "SECURITY.md",
            "AUTHORS.md",
            "MAINTAINERS.md",
            "ROADMAP.md",
        ],
    )
    def test_well_known_docs_route_to_docs(self, filename: str) -> None:
        router = CollectionRouter()
        ext = Path(filename).suffix
        result = router.route(Path(filename), ext, plugin_name=None)
        assert result == COLLECTION_DOCS

    def test_case_insensitive(self) -> None:
        """Well-known doc matching is case-insensitive."""
        router = CollectionRouter()
        result = router.route(Path("readme.md"), ".md", plugin_name=None)
        assert result == COLLECTION_DOCS

    def test_well_known_in_subdir(self) -> None:
        """Well-known doc in a subdirectory still matches."""
        router = CollectionRouter()
        result = router.route(Path("project/README.md"), ".md", plugin_name=None)
        assert result == COLLECTION_DOCS


class TestLevel5DocsExtension:
    """Level 5: Documentation file extensions route to docs."""

    @pytest.mark.parametrize(
        "path,ext",
        [
            ("docs/guide.md", ".md"),
            ("docs/api.rst", ".rst"),
            ("notes.adoc", ".adoc"),
            ("design.txt", ".txt"),
        ],
    )
    def test_docs_extensions_route_to_docs(self, path: str, ext: str) -> None:
        router = CollectionRouter()
        result = router.route(Path(path), ext, plugin_name=None)
        assert result == COLLECTION_DOCS


class TestLevel6CodeExtension:
    """Level 6: Source code extensions route to code."""

    @pytest.mark.parametrize(
        "path,ext",
        [
            ("src/main.py", ".py"),
            ("lib/index.js", ".js"),
            ("app/main.ts", ".ts"),
            ("main.go", ".go"),
            ("main.rs", ".rs"),
            ("Main.java", ".java"),
            ("widget.cpp", ".cpp"),
            ("query.sql", ".sql"),
            ("script.sh", ".sh"),
            ("module.rb", ".rb"),
            ("App.swift", ".swift"),
            ("Main.kt", ".kt"),
        ],
    )
    def test_code_extensions_route_to_code(self, path: str, ext: str) -> None:
        router = CollectionRouter()
        result = router.route(Path(path), ext, plugin_name=None)
        assert result == COLLECTION_CODE


class TestLevel7ConfigData:
    """Level 7: Config/data extensions route to text."""

    @pytest.mark.parametrize(
        "path,ext",
        [
            ("config.json", ".json"),
            ("settings.yaml", ".yaml"),
            ("app.yml", ".yml"),
            ("pyproject.toml", ".toml"),
            ("config.ini", ".ini"),
            ("app.cfg", ".cfg"),
            ("data.csv", ".csv"),
            ("settings.xml", ".xml"),
            (".env", ".env"),
        ],
    )
    def test_config_data_routes_to_text(self, path: str, ext: str) -> None:
        router = CollectionRouter()
        result = router.route(Path(path), ext, plugin_name=None)
        assert result == COLLECTION_TEXT

    def test_setup_cfg_matches_test_before_config(self) -> None:
        """setup.cfg is matched as test filename (level 3) before config/data (level 7)."""
        router = CollectionRouter()
        result = router.route(Path("setup.cfg"), ".cfg", plugin_name=None)
        assert result == COLLECTION_TESTS


class TestLevel8Fallback:
    """Level 8: Unknown extensions fall back to text."""

    @pytest.mark.parametrize(
        "path,ext",
        [
            ("Makefile", ""),
            ("Dockerfile", ""),
            ("data.parquet", ".parquet"),
            ("image.png", ".png"),
            ("archive.tar.gz", ".gz"),
        ],
    )
    def test_unknown_extensions_route_to_text(self, path: str, ext: str) -> None:
        router = CollectionRouter()
        result = router.route(Path(path), ext, plugin_name=None)
        assert result == COLLECTION_TEXT


class TestPrecedenceInteractions:
    """Verify precedence ordering when multiple rules could match."""

    def test_plugin_beats_test_dir(self) -> None:
        """Level 1 > Level 2: plugin override beats test directory."""
        router = CollectionRouter(plugin_overrides={"code_plugin": COLLECTION_CODE})
        result = router.route(Path("tests/test_main.py"), ".py", plugin_name="code_plugin")
        assert result == COLLECTION_CODE

    def test_test_dir_beats_well_known_doc(self) -> None:
        """Level 2 > Level 4: test dir beats well-known doc."""
        router = CollectionRouter()
        result = router.route(Path("tests/README.md"), ".md", plugin_name=None)
        assert result == COLLECTION_TESTS

    def test_test_dir_beats_code_extension(self) -> None:
        """Level 2 > Level 6: test dir beats code extension."""
        router = CollectionRouter()
        result = router.route(Path("tests/conftest.py"), ".py", plugin_name=None)
        assert result == COLLECTION_TESTS

    def test_test_filename_beats_code_extension(self) -> None:
        """Level 3 > Level 6: test filename beats code extension."""
        router = CollectionRouter()
        result = router.route(Path("src/test_utils.py"), ".py", plugin_name=None)
        assert result == COLLECTION_TESTS

    def test_well_known_doc_beats_docs_extension(self) -> None:
        """Level 4 > Level 5: well-known doc is a subset (both give docs)."""
        router = CollectionRouter()
        result = router.route(Path("README.md"), ".md", plugin_name=None)
        assert result == COLLECTION_DOCS

    def test_docs_extension_beats_fallback(self) -> None:
        """Level 5 > Level 8: docs extension beats fallback."""
        router = CollectionRouter()
        result = router.route(Path("notes.rst"), ".rst", plugin_name=None)
        assert result == COLLECTION_DOCS

    def test_code_extension_beats_config(self) -> None:
        """Level 6 > Level 7: code extension beats config/data."""
        router = CollectionRouter()
        result = router.route(Path("script.py"), ".py", plugin_name=None)
        assert result == COLLECTION_CODE

    def test_config_beats_fallback(self) -> None:
        """Level 7 > Level 8: config/data extension beats fallback."""
        router = CollectionRouter()
        result = router.route(Path("data.json"), ".json", plugin_name=None)
        assert result == COLLECTION_TEXT


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_extension(self) -> None:
        router = CollectionRouter()
        result = router.route(Path("Makefile"), "", plugin_name=None)
        assert result == COLLECTION_TEXT

    def test_no_plugin_overrides(self) -> None:
        router = CollectionRouter()
        result = router.route(Path("src/main.py"), ".py", plugin_name=None)
        assert result == COLLECTION_CODE

    def test_empty_plugin_overrides(self) -> None:
        router = CollectionRouter(plugin_overrides={})
        result = router.route(Path("src/main.py"), ".py", plugin_name="nonexistent")
        assert result == COLLECTION_CODE

    def test_posix_path(self) -> None:
        router = CollectionRouter()
        result = router.route(Path("src/utils/helpers.py"), ".py", plugin_name=None)
        assert result == COLLECTION_CODE

    def test_deeply_nested_test_dir(self) -> None:
        router = CollectionRouter()
        result = router.route(
            Path("packages/core/tests/unit/test_main.py"), ".py", plugin_name=None
        )
        assert result == COLLECTION_TESTS

    def test_case_sensitivity_of_extensions(self) -> None:
        """Extensions are stored lowercase in frozensets, so suffix should be compared lowercase."""
        router = CollectionRouter()
        # Path(".PY").suffix returns ".PY"
        result = router.route(Path("main.PY"), ".PY", plugin_name=None)
        # Should still route to code (case-insensitive extension matching)
        assert result == COLLECTION_CODE
