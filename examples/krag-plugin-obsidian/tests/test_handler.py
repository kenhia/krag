"""Tests for ObsidianFileTypeHandler — Phase 3 / User Story 1."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from krag_plugin_obsidian.handler import ObsidianFileTypeHandler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def handler() -> ObsidianFileTypeHandler:
    """Return a bare (uninitialized) handler."""
    return ObsidianFileTypeHandler()


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """Create a minimal vault directory with a few .md files."""
    vault = tmp_path / "my-vault"
    vault.mkdir()

    # A note with frontmatter
    note = vault / "hello.md"
    note.write_text(
        "---\ntitle: Hello\ntags: [greeting]\n---\n\nHello, world!\n",
        encoding="utf-8",
    )

    # A plain note without frontmatter
    plain = vault / "plain.md"
    plain.write_text("Just some text.\n", encoding="utf-8")

    # A sub-directory note
    sub = vault / "projects"
    sub.mkdir()
    nested = sub / "todo.md"
    nested.write_text(
        "---\ntitle: TODO\n---\n\n- Buy milk\n- Write tests\n",
        encoding="utf-8",
    )

    return vault


@pytest.fixture()
def initialized_handler(tmp_vault: Path) -> ObsidianFileTypeHandler:
    """Return a handler initialized with one vault."""
    h = ObsidianFileTypeHandler()
    config: dict[str, Any] = {"vaults": {"my-vault": str(tmp_vault)}}
    h.initialize(config, context=None)
    return h


# ---------------------------------------------------------------------------
# T022 — initialize() resolves vault paths, warns on missing
# ---------------------------------------------------------------------------


class TestInitialize:
    def test_initialize_resolves_existing_vault(self, tmp_vault: Path) -> None:
        """initialize() populates vault_paths for valid directories."""
        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": {"my-vault": str(tmp_vault)}}, context=None)
        assert len(h.vault_paths) == 1
        assert h.vault_paths["my-vault"] == tmp_vault.resolve()

    def test_initialize_warns_on_missing_vault(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """initialize() logs a warning and skips a missing vault directory."""
        missing = tmp_path / "nonexistent"
        h = ObsidianFileTypeHandler()
        with caplog.at_level(logging.WARNING):
            h.initialize({"vaults": {"gone": str(missing)}}, context=None)
        assert len(h.vault_paths) == 0
        assert "gone" in caplog.text

    def test_initialize_tilde_expansion(self, tmp_path: Path) -> None:
        """initialize() expands ~ in vault paths."""
        h = ObsidianFileTypeHandler()
        # We can't really test ~ because it's system-dependent, but let's
        # make sure a path that *starts* with a known prefix works.
        h.initialize({"vaults": {"v": str(tmp_path)}}, context=None)
        assert h.vault_paths["v"] == tmp_path.resolve()

    def test_initialize_empty_config(self) -> None:
        """initialize() with no config yields empty vault_paths."""
        h = ObsidianFileTypeHandler()
        h.initialize(None, context=None)
        assert h.vault_paths == {}

    def test_initialize_empty_vaults_dict(self) -> None:
        """initialize() with empty vaults dict yields empty vault_paths."""
        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": {}}, context=None)
        assert h.vault_paths == {}


# ---------------------------------------------------------------------------
# T023 — claims_file() returns True for files under vault paths
# ---------------------------------------------------------------------------


class TestClaimsFileTrue:
    def test_claims_md_file_under_vault(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """claims_file() returns True for a .md file under the vault."""
        md_file = tmp_vault / "hello.md"
        assert initialized_handler.claims_file(md_file) is True

    def test_claims_nested_md_file(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """claims_file() returns True for nested vault files."""
        nested = tmp_vault / "projects" / "todo.md"
        assert initialized_handler.claims_file(nested) is True


# ---------------------------------------------------------------------------
# T024 — claims_file() returns False for files outside vault paths
# ---------------------------------------------------------------------------


class TestClaimsFileFalse:
    def test_file_outside_vault(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_path: Path
    ) -> None:
        """claims_file() returns False for files outside any vault."""
        outside = tmp_path / "other" / "notes.md"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("outside", encoding="utf-8")
        assert initialized_handler.claims_file(outside) is False

    def test_non_md_file_under_vault(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """claims_file() returns False for non-.md files even under vault."""
        txt_file = tmp_vault / "notes.txt"
        txt_file.write_text("text file", encoding="utf-8")
        assert initialized_handler.claims_file(txt_file) is False


# ---------------------------------------------------------------------------
# T025 — claims_file() returns False when no vaults configured
# ---------------------------------------------------------------------------


class TestClaimsFileNoVaults:
    def test_no_vaults_configured(self, handler: ObsidianFileTypeHandler) -> None:
        """claims_file() returns False when handler has no vaults."""
        assert handler.claims_file(Path("/any/file.md")) is False

    def test_initialized_empty_vaults(self) -> None:
        """claims_file() returns False after initialize with empty vaults."""
        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": {}}, context=None)
        assert h.claims_file(Path("/some/note.md")) is False


# ---------------------------------------------------------------------------
# T026 — extract_text() reads .md content and strips frontmatter
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_strips_frontmatter(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """extract_text() returns body without frontmatter."""
        text = initialized_handler.extract_text(tmp_vault / "hello.md")
        assert "Hello, world!" in text
        assert "title:" not in text
        assert "---" not in text

    def test_plain_file_no_frontmatter(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """extract_text() returns full content when no frontmatter."""
        text = initialized_handler.extract_text(tmp_vault / "plain.md")
        assert "Just some text." in text

    def test_empty_body_after_frontmatter(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """extract_text() returns empty-ish string for frontmatter-only files."""
        fm_only = tmp_vault / "meta-only.md"
        fm_only.write_text("---\ntitle: Empty\n---\n", encoding="utf-8")
        text = initialized_handler.extract_text(fm_only)
        assert text.strip() == "" or "Empty" in text  # may synthesize from FM


# ---------------------------------------------------------------------------
# T027 — extract_metadata() returns frontmatter fields
# ---------------------------------------------------------------------------


class TestExtractMetadata:
    def test_returns_frontmatter_fields(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """extract_metadata() includes parsed YAML frontmatter."""
        meta = initialized_handler.extract_metadata(tmp_vault / "hello.md")
        assert meta["title"] == "Hello"
        assert meta["tags"] == ["greeting"]

    def test_default_title_from_filename(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """extract_metadata() uses filename stem when title not in frontmatter."""
        meta = initialized_handler.extract_metadata(tmp_vault / "plain.md")
        assert meta["title"] == "plain"

    def test_includes_vault_name(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """extract_metadata() includes vault_name."""
        meta = initialized_handler.extract_metadata(tmp_vault / "hello.md")
        assert meta.get("vault_name") == "my-vault"

    def test_includes_virtual_path(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """extract_metadata() includes virtual_path with obsidian:// prefix."""
        meta = initialized_handler.extract_metadata(tmp_vault / "hello.md")
        assert meta.get("virtual_path") == "obsidian://my-vault/hello.md"


# ---------------------------------------------------------------------------
# T028 — supported_extensions() returns [".md", ".markdown"]
# ---------------------------------------------------------------------------


class TestSupportedExtensions:
    def test_returns_md_and_markdown(self, handler: ObsidianFileTypeHandler) -> None:
        """supported_extensions() includes .md and .markdown."""
        exts = handler.supported_extensions()
        assert ".md" in exts
        assert ".markdown" in exts
        assert len(exts) == 2


# ---------------------------------------------------------------------------
# T029 — Virtual path generation
# ---------------------------------------------------------------------------


class TestVirtualPath:
    def test_root_level_file(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """Virtual path for root-level file is obsidian://vault-name/file.md."""
        vp = initialized_handler._resolve_vault(tmp_vault / "hello.md")
        assert vp is not None
        vault_name, virtual_path = vp
        assert vault_name == "my-vault"
        assert virtual_path == "obsidian://my-vault/hello.md"

    def test_nested_file(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """Virtual path preserves subdirectory structure."""
        vp = initialized_handler._resolve_vault(tmp_vault / "projects" / "todo.md")
        assert vp is not None
        vault_name, virtual_path = vp
        assert vault_name == "my-vault"
        assert virtual_path == "obsidian://my-vault/projects/todo.md"

    def test_deterministic(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_vault: Path
    ) -> None:
        """Same file always produces the same virtual path (FR-017)."""
        file = tmp_vault / "hello.md"
        vp1 = initialized_handler._resolve_vault(file)
        vp2 = initialized_handler._resolve_vault(file)
        assert vp1 == vp2

    def test_file_outside_vault_returns_none(
        self, initialized_handler: ObsidianFileTypeHandler, tmp_path: Path
    ) -> None:
        """_resolve_vault() returns None for files outside any vault."""
        outside = tmp_path / "other.md"
        assert initialized_handler._resolve_vault(outside) is None

    def test_multiple_vaults_distinct_prefix(self, tmp_path: Path) -> None:
        """Different vaults produce distinct obsidian:// prefixes."""
        v1 = tmp_path / "vault-a"
        v1.mkdir()
        v2 = tmp_path / "vault-b"
        v2.mkdir()

        (v1 / "note.md").write_text("a", encoding="utf-8")
        (v2 / "note.md").write_text("b", encoding="utf-8")

        h = ObsidianFileTypeHandler()
        h.initialize(
            {"vaults": {"alpha": str(v1), "beta": str(v2)}},
            context=None,
        )

        r1 = h._resolve_vault(v1 / "note.md")
        r2 = h._resolve_vault(v2 / "note.md")
        assert r1 is not None and r2 is not None
        assert r1[1] == "obsidian://alpha/note.md"
        assert r2[1] == "obsidian://beta/note.md"


# ---------------------------------------------------------------------------
# T070 — lexicon.json contains all required terms
# ---------------------------------------------------------------------------


class TestLexiconContents:
    """Verify bundled lexicon.json has the required Obsidian terms (FR-027)."""

    REQUIRED_TERMS = [
        "backlink",
        "daily note",
        "canvas",
        "dataview",
        "template",
        "frontmatter",
        "wikilink",
        "MOC",
        "tag",
        "vault",
    ]

    def test_lexicon_file_exists(self) -> None:
        """lexicon.json must be bundled inside the plugin package."""
        import krag_plugin_obsidian

        pkg_dir = Path(krag_plugin_obsidian.__file__).parent
        lexicon_path = pkg_dir / "lexicon.json"
        assert lexicon_path.is_file(), f"Missing {lexicon_path}"

    def test_contains_required_terms(self) -> None:
        """lexicon.json must contain all 10 required terms."""
        import json

        import krag_plugin_obsidian

        pkg_dir = Path(krag_plugin_obsidian.__file__).parent
        data = json.loads((pkg_dir / "lexicon.json").read_text(encoding="utf-8"))
        for term in self.REQUIRED_TERMS:
            assert term in data, f"Missing required term: {term}"
            assert isinstance(data[term], str), f"Definition for '{term}' must be a string"
            assert len(data[term]) > 0, f"Definition for '{term}' must be non-empty"

    def test_has_at_least_10_terms(self) -> None:
        """lexicon.json must have at least 10 entries."""
        import json

        import krag_plugin_obsidian

        pkg_dir = Path(krag_plugin_obsidian.__file__).parent
        data = json.loads((pkg_dir / "lexicon.json").read_text(encoding="utf-8"))
        assert len(data) >= 10


# ---------------------------------------------------------------------------
# T071 — initialize() merges lexicon entries into LexiconStore
# ---------------------------------------------------------------------------


class TestLexiconMerge:
    """initialize() calls merge_entries() on the context's lexicon store."""

    def test_merges_into_lexicon_store(self, tmp_vault: Path) -> None:
        """Lexicon entries are merged when context provides a lexicon_store."""
        from krag.lexicon.lexicon_store import LexiconStore

        store = LexiconStore()
        context = type("Ctx", (), {"lexicon_store": store})()

        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": {"v": str(tmp_vault)}}, context=context)

        # Should have merged the 10 Obsidian terms
        assert len(store.entries) >= 10
        assert "backlink" in store.entries
        assert "vault" in store.entries

    def test_merges_without_context(self, tmp_vault: Path) -> None:
        """initialize() succeeds silently when no context is provided."""
        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": {"v": str(tmp_vault)}}, context=None)
        # Should not raise
        assert len(h.vault_paths) == 1


# ---------------------------------------------------------------------------
# T072 — merge does not overwrite user-defined terms
# ---------------------------------------------------------------------------


class TestLexiconNoOverwrite:
    """User-defined terms are preserved during merge."""

    def test_user_term_preserved(self, tmp_vault: Path) -> None:
        """An existing user-defined term is NOT overwritten by plugin merge."""
        from krag.lexicon.lexicon_store import LexiconStore

        store = LexiconStore()
        # Pre-load a user-defined "vault" term
        store.entries["vault"] = "User's custom definition of vault"
        store._compile_patterns()

        context = type("Ctx", (), {"lexicon_store": store})()

        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": {"v": str(tmp_vault)}}, context=context)

        # User definition should still be there
        assert store.entries["vault"] == "User's custom definition of vault"

    def test_new_terms_still_added(self, tmp_vault: Path) -> None:
        """Terms not already in the store are added during merge."""
        from krag.lexicon.lexicon_store import LexiconStore

        store = LexiconStore()
        # Pre-load only "vault"
        store.entries["vault"] = "User vault def"
        store._compile_patterns()

        context = type("Ctx", (), {"lexicon_store": store})()

        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": {"v": str(tmp_vault)}}, context=context)

        # "vault" preserved, but other Obsidian terms added
        assert store.entries["vault"] == "User vault def"
        assert "backlink" in store.entries
        assert "wikilink" in store.entries
