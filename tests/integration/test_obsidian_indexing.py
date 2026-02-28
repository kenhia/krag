"""Integration tests for Obsidian plugin — path-based ownership and virtual paths.

Phase 5 (US3): Vault .md files claimed by Obsidian plugin; non-vault .md by
markdown plugin.  Two-phase resolution: path-claim first, extension fallback.

Phase 6 (US4): Virtual paths are deterministic and appear correctly in
metadata and chunk payloads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from krag_plugin_obsidian.handler import ObsidianFileTypeHandler

from krag.models.configuration import PluginConfiguration, PluginMetadata
from krag.plugins.interfaces import FileTypeHandler
from krag.plugins.registry import PluginRegistry

# ---------------------------------------------------------------------------
# Helpers — lightweight mock "markdown" plugin for extension fallback
# ---------------------------------------------------------------------------


class _StubMarkdownHandler(FileTypeHandler):
    """Minimal markdown handler for testing — does NOT override claims_file."""

    @property
    def name(self) -> str:
        return "markdown"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_api_version(self) -> str:
        return "1.0"

    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown"]

    def extract_text(self, file_path: Path) -> str:  # pragma: no cover
        return file_path.read_text(encoding="utf-8")

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:  # pragma: no cover
        return {"handler": "markdown"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """Create a vault directory with a couple of notes."""
    vault = tmp_path / "my-vault"
    vault.mkdir()
    (vault / "note-a.md").write_text("# Note A\n\nVault content.", encoding="utf-8")
    sub = vault / "sub"
    sub.mkdir()
    (sub / "deep.md").write_text("# Deep\n\nNested note.", encoding="utf-8")
    return vault


@pytest.fixture()
def non_vault_dir(tmp_path: Path) -> Path:
    """Create a directory outside any vault with .md files."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "readme.md").write_text("# README\n\nGeneric markdown.", encoding="utf-8")
    (d / "notes.markdown").write_text("More notes.", encoding="utf-8")
    return d


@pytest.fixture()
def obsidian_handler(tmp_vault: Path) -> ObsidianFileTypeHandler:
    """Return an Obsidian handler initialised with one vault."""
    h = ObsidianFileTypeHandler()
    h.initialize({"vaults": {"my-vault": str(tmp_vault)}}, context=None)
    return h


@pytest.fixture()
def markdown_handler() -> _StubMarkdownHandler:
    """Return a stub markdown handler (extension-based only)."""
    return _StubMarkdownHandler()


@pytest.fixture()
def registry(
    obsidian_handler: ObsidianFileTypeHandler,
    markdown_handler: _StubMarkdownHandler,
) -> PluginRegistry:
    """Build a PluginRegistry with both obsidian and markdown plugins injected.

    Uses internal attributes to avoid requiring real entry-point discovery.
    """
    config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
    reg = PluginRegistry(config)

    # Markdown first — wins the extension map for .md/.markdown (Phase 2 fallback).
    # This mirrors real discovery order: the base markdown plugin is installed
    # before the Obsidian add-on.
    reg._discovered["markdown"] = PluginMetadata(
        name="markdown",
        version="1.0.0",
        entry_point="krag_plugin_markdown:MarkdownFileTypeHandler",
        supported_extensions=[".md", ".markdown"],
        required_api_version="1.0",
        is_enabled=True,
        has_claims_file=False,
    )
    reg._loaded["markdown"] = markdown_handler

    # Obsidian second — has_claims_file=True so Phase 1 (path-claim) runs
    # before extension fallback.  Extension map conflict is expected and
    # harmless because obsidian uses claims_file(), not the extension map.
    reg._discovered["obsidian"] = PluginMetadata(
        name="obsidian",
        version="1.0.0",
        entry_point="krag_plugin_obsidian:ObsidianFileTypeHandler",
        supported_extensions=[".md", ".markdown"],
        required_api_version="1.0",
        is_enabled=True,
        has_claims_file=True,
    )
    reg._loaded["obsidian"] = obsidian_handler

    # Build extension map so Phase 2 resolution works
    reg._build_extension_map()

    return reg


# =========================================================================
# Phase 5 / US3 — Path-Based Plugin Ownership
# =========================================================================


# ---------------------------------------------------------------------------
# T053 — vault .md handled by Obsidian, non-vault .md by markdown
# ---------------------------------------------------------------------------


class TestVaultVsNonVaultOwnership:
    """Vault .md files are handled by Obsidian; non-vault .md by markdown."""

    def test_vault_md_claimed_by_obsidian(
        self,
        registry: PluginRegistry,
        tmp_vault: Path,
    ) -> None:
        """A .md file under the vault is handled by the Obsidian plugin."""
        handler = registry.get_handler_for_file(tmp_vault / "note-a.md")
        assert handler is not None
        assert handler.name == "obsidian"

    def test_non_vault_md_handled_by_markdown(
        self,
        registry: PluginRegistry,
        non_vault_dir: Path,
    ) -> None:
        """A .md file outside any vault falls back to the markdown plugin."""
        handler = registry.get_handler_for_file(non_vault_dir / "readme.md")
        assert handler is not None
        assert handler.name == "markdown"

    def test_vault_nested_md_claimed_by_obsidian(
        self,
        registry: PluginRegistry,
        tmp_vault: Path,
    ) -> None:
        """Nested vault files are also claimed by Obsidian."""
        handler = registry.get_handler_for_file(tmp_vault / "sub" / "deep.md")
        assert handler is not None
        assert handler.name == "obsidian"

    def test_non_md_under_vault_not_claimed(
        self,
        registry: PluginRegistry,
        tmp_vault: Path,
    ) -> None:
        """Non-.md files under the vault are NOT claimed by Obsidian."""
        txt = tmp_vault / "data.txt"
        txt.write_text("plain text", encoding="utf-8")
        handler = registry.get_handler_for_file(txt)
        # Obsidian doesn't claim it; no txt handler exists → None
        assert handler is None or handler.name != "obsidian"


# ---------------------------------------------------------------------------
# T054 — no vaults configured → all .md handled by markdown
# ---------------------------------------------------------------------------


class TestNoVaultsConfigured:
    """When no vaults are configured, markdown handles all .md files."""

    def test_no_vaults_all_md_by_markdown(
        self,
        markdown_handler: _StubMarkdownHandler,
        non_vault_dir: Path,
    ) -> None:
        """With no Obsidian vaults, .md files go to the markdown plugin."""
        # Create registry with obsidian having no vaults
        empty_obsidian = ObsidianFileTypeHandler()
        empty_obsidian.initialize({"vaults": {}}, context=None)

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        reg = PluginRegistry(config)

        # Markdown first — wins extension map
        reg._discovered["markdown"] = PluginMetadata(
            name="markdown",
            version="1.0.0",
            entry_point="krag_plugin_markdown:MarkdownFileTypeHandler",
            supported_extensions=[".md", ".markdown"],
            required_api_version="1.0",
            is_enabled=True,
            has_claims_file=False,
        )
        reg._loaded["markdown"] = markdown_handler

        reg._discovered["obsidian"] = PluginMetadata(
            name="obsidian",
            version="1.0.0",
            entry_point="krag_plugin_obsidian:ObsidianFileTypeHandler",
            supported_extensions=[".md", ".markdown"],
            required_api_version="1.0",
            is_enabled=True,
            has_claims_file=True,
        )
        reg._loaded["obsidian"] = empty_obsidian
        reg._build_extension_map()

        handler = reg.get_handler_for_file(non_vault_dir / "readme.md")
        assert handler is not None
        assert handler.name == "markdown"


# ---------------------------------------------------------------------------
# T055 — two vaults configured → correct virtual path prefix per vault
# ---------------------------------------------------------------------------


class TestTwoVaultsVirtualPaths:
    """Two configured vaults produce the correct obsidian:// prefix each."""

    def test_two_vaults_correct_prefixes(self, tmp_path: Path) -> None:
        """Each vault's files get distinct obsidian:// virtual path prefixes."""
        v1 = tmp_path / "vault-alpha"
        v1.mkdir()
        (v1 / "alpha.md").write_text("Alpha note.", encoding="utf-8")

        v2 = tmp_path / "vault-beta"
        v2.mkdir()
        (v2 / "beta.md").write_text("Beta note.", encoding="utf-8")

        h = ObsidianFileTypeHandler()
        h.initialize(
            {"vaults": {"alpha": str(v1), "beta": str(v2)}},
            context=None,
        )

        meta_a = h.extract_metadata(v1 / "alpha.md")
        meta_b = h.extract_metadata(v2 / "beta.md")

        assert meta_a["vault_name"] == "alpha"
        assert meta_a["virtual_path"] == "obsidian://alpha/alpha.md"
        assert meta_b["vault_name"] == "beta"
        assert meta_b["virtual_path"] == "obsidian://beta/beta.md"

    def test_two_vaults_registry_resolution(self, tmp_path: Path) -> None:
        """Registry resolves files from both vaults to the Obsidian plugin."""
        v1 = tmp_path / "vault-alpha"
        v1.mkdir()
        (v1 / "a.md").write_text("A.", encoding="utf-8")

        v2 = tmp_path / "vault-beta"
        v2.mkdir()
        (v2 / "b.md").write_text("B.", encoding="utf-8")

        h = ObsidianFileTypeHandler()
        h.initialize(
            {"vaults": {"alpha": str(v1), "beta": str(v2)}},
            context=None,
        )

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        reg = PluginRegistry(config)
        reg._discovered["obsidian"] = PluginMetadata(
            name="obsidian",
            version="1.0.0",
            entry_point="krag_plugin_obsidian:ObsidianFileTypeHandler",
            supported_extensions=[".md", ".markdown"],
            required_api_version="1.0",
            is_enabled=True,
            has_claims_file=True,
        )
        reg._loaded["obsidian"] = h
        reg._build_extension_map()

        assert reg.get_handler_for_file(v1 / "a.md") is not None
        assert reg.get_handler_for_file(v1 / "a.md").name == "obsidian"
        assert reg.get_handler_for_file(v2 / "b.md") is not None
        assert reg.get_handler_for_file(v2 / "b.md").name == "obsidian"


# ---------------------------------------------------------------------------
# T056 — overlapping vault paths → first vault in config order wins
# ---------------------------------------------------------------------------


class TestOverlappingVaultPaths:
    """When vault paths overlap, the first vault in config order claims the file."""

    def test_overlapping_first_wins(self, tmp_path: Path) -> None:
        """Nested vault paths: first config entry whose path matches wins."""
        outer = tmp_path / "outer"
        outer.mkdir()
        inner = outer / "inner"
        inner.mkdir()
        (inner / "note.md").write_text("Inner note.", encoding="utf-8")

        h = ObsidianFileTypeHandler()
        # "parent" vault covers outer/; "child" vault covers outer/inner/
        # Dicts preserve insertion order in Python 3.7+, so parent is checked first
        h.initialize(
            {"vaults": {"parent": str(outer), "child": str(inner)}},
            context=None,
        )

        meta = h.extract_metadata(inner / "note.md")
        # The parent vault matches first → virtual path uses parent prefix
        assert meta["vault_name"] == "parent"
        assert meta["virtual_path"] == "obsidian://parent/inner/note.md"


# =========================================================================
# Phase 5 / US3 — T057: End-to-end pipeline claims_file priority
# =========================================================================


class TestPipelineClaimsFilePriority:
    """Verify the two-phase resolution works end-to-end."""

    def test_claims_file_takes_priority_over_extension(
        self,
        registry: PluginRegistry,
        tmp_vault: Path,
    ) -> None:
        """Path-claiming (Phase 1) beats extension lookup (Phase 2)."""
        vault_file = tmp_vault / "note-a.md"
        handler = registry.get_handler_for_file(vault_file)
        assert handler is not None
        assert handler.name == "obsidian"

        # Verify that extension-based lookup would also work, but the key
        # point is that get_handler_for_file chose obsidian via claims_file.
        assert handler.name == "obsidian"

    def test_markdown_extension_fallback_outside_vault(
        self,
        registry: PluginRegistry,
        non_vault_dir: Path,
    ) -> None:
        """Non-vault .md falls through path-claim to extension fallback."""
        handler = registry.get_handler_for_file(non_vault_dir / "readme.md")
        assert handler is not None
        assert handler.name == "markdown"


# =========================================================================
# Phase 5 / US3 — T058: Handler edge cases
# =========================================================================


class TestHandlerEdgeCases:
    """Edge case handling: zero-byte files, binary files, permission errors."""

    def test_zero_byte_file(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """Zero-byte .md file returns empty text without error."""
        empty = tmp_vault / "empty.md"
        empty.write_text("", encoding="utf-8")
        text = obsidian_handler.extract_text(empty)
        assert text == ""

    def test_binary_file_under_vault(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """Binary file with .md extension raises UnicodeDecodeError."""
        binary = tmp_vault / "binary.md"
        binary.write_bytes(b"\x80\x81\x82\x83\xff\xfe")
        with pytest.raises(UnicodeDecodeError):
            obsidian_handler.extract_text(binary)

    def test_missing_file(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """Missing file raises FileNotFoundError."""
        missing = tmp_vault / "ghost.md"
        with pytest.raises(FileNotFoundError):
            obsidian_handler.extract_text(missing)

    def test_whitespace_only_file(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """Whitespace-only file returns empty string after strip."""
        ws = tmp_vault / "whitespace.md"
        ws.write_text("   \n\n   \n", encoding="utf-8")
        text = obsidian_handler.extract_text(ws)
        assert text == ""

    def test_frontmatter_only_file(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """File with only frontmatter returns empty body."""
        fm = tmp_vault / "meta-only.md"
        fm.write_text("---\ntitle: Empty\n---\n", encoding="utf-8")
        text = obsidian_handler.extract_text(fm)
        assert text.strip() == ""


# =========================================================================
# Phase 6 / US4 — Virtual Path Display
# =========================================================================


# ---------------------------------------------------------------------------
# T060 — virtual path determinism
# ---------------------------------------------------------------------------


class TestVirtualPathDeterminism:
    """Same file always produces the same virtual path (FR-017)."""

    def test_deterministic_across_calls(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """Multiple extract_metadata calls return identical virtual paths."""
        f = tmp_vault / "note-a.md"
        meta1 = obsidian_handler.extract_metadata(f)
        meta2 = obsidian_handler.extract_metadata(f)
        assert meta1["virtual_path"] == meta2["virtual_path"]

    def test_deterministic_after_reinit(
        self,
        tmp_vault: Path,
    ) -> None:
        """Virtual path is the same after re-initialising the handler."""
        f = tmp_vault / "note-a.md"

        h1 = ObsidianFileTypeHandler()
        h1.initialize({"vaults": {"my-vault": str(tmp_vault)}}, context=None)
        vp1 = h1.extract_metadata(f)["virtual_path"]

        h2 = ObsidianFileTypeHandler()
        h2.initialize({"vaults": {"my-vault": str(tmp_vault)}}, context=None)
        vp2 = h2.extract_metadata(f)["virtual_path"]

        assert vp1 == vp2


# ---------------------------------------------------------------------------
# T061 — multiple vaults produce distinct obsidian:// prefixes
# ---------------------------------------------------------------------------


class TestMultipleVaultsDistinctPrefixes:
    """Different vaults produce different obsidian:// prefixes."""

    def test_distinct_prefixes(self, tmp_path: Path) -> None:
        """Two vaults with the same filename produce different virtual paths."""
        v1 = tmp_path / "vault-gratch"
        v1.mkdir()
        (v1 / "note.md").write_text("Gratch note.", encoding="utf-8")

        v2 = tmp_path / "vault-work"
        v2.mkdir()
        (v2 / "note.md").write_text("Work note.", encoding="utf-8")

        h = ObsidianFileTypeHandler()
        h.initialize(
            {"vaults": {"gratch": str(v1), "work": str(v2)}},
            context=None,
        )

        m1 = h.extract_metadata(v1 / "note.md")
        m2 = h.extract_metadata(v2 / "note.md")

        assert m1["virtual_path"] == "obsidian://gratch/note.md"
        assert m2["virtual_path"] == "obsidian://work/note.md"
        assert m1["virtual_path"] != m2["virtual_path"]


# ---------------------------------------------------------------------------
# T062 — virtual paths appear correctly in chunk metadata
# ---------------------------------------------------------------------------


class TestVirtualPathInChunkPayload:
    """Verify virtual paths flow into chunk metadata via the chunker."""

    def test_chunk_metadata_includes_vault_name(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """Chunk metadata includes vault_name from the handler."""
        f = tmp_vault / "note-a.md"
        text = obsidian_handler.extract_text(f)
        chunker = obsidian_handler.get_chunking_strategy()
        assert chunker is not None

        chunks = chunker.chunk(text, file_path=f)
        assert len(chunks) >= 1
        for chunk in chunks:
            meta = chunker.get_chunk_metadata(chunk)
            assert meta["vault_name"] == "my-vault"
            assert "target_collection" in meta

    def test_virtual_path_in_extract_metadata(
        self,
        obsidian_handler: ObsidianFileTypeHandler,
        tmp_vault: Path,
    ) -> None:
        """extract_metadata() includes obsidian:// virtual path."""
        f = tmp_vault / "note-a.md"
        meta = obsidian_handler.extract_metadata(f)
        assert meta["virtual_path"].startswith("obsidian://")
        assert "my-vault" in meta["virtual_path"]
        assert "note-a.md" in meta["virtual_path"]
