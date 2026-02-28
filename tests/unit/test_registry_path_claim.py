"""Tests for path-based plugin resolution in PluginRegistry (T007, T008).

T007: _resolve_by_path_claim() returns None when no plugins have has_claims_file.
T008: get_handler_for_file() two-phase resolution: path-claim first, then extension fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from krag.models.configuration import PluginConfiguration, PluginMetadata
from krag.plugins.interfaces import FileTypeHandler


def _make_config() -> PluginConfiguration:
    return PluginConfiguration(
        plugin_dir=None,
        enabled_plugins=[],
        disabled_plugins=[],
    )


class _ExtensionHandler(FileTypeHandler):
    """Handler that matches by extension only (no claims_file override)."""

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
        return [".md"]

    def extract_text(self, file_path: Path) -> str:
        return ""

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        return {}


class _ClaimingHandler(FileTypeHandler):
    """Handler that claims files under a specific path prefix."""

    def __init__(self, vault_path: Path) -> None:
        self._vault_path = vault_path.resolve()

    @property
    def name(self) -> str:
        return "obsidian"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_api_version(self) -> str:
        return "1.0"

    def supported_extensions(self) -> list[str]:
        return [".md"]

    def extract_text(self, file_path: Path) -> str:
        return ""

    def extract_metadata(self, file_path: Path) -> dict[str, Any]:
        return {}

    def claims_file(self, file_path: Path) -> bool:
        try:
            return file_path.resolve().is_relative_to(self._vault_path)
        except (ValueError, OSError):
            return False


class TestPathResolutionPerformance:
    """SC-005: Path-based resolution must add <10ms overhead per file."""

    def test_claims_file_under_10ms(self, tmp_path: Path) -> None:
        """claims_file() path-prefix check completes in <10ms per file (T079).

        Creates a handler with 5 vaults and times 1 000 calls against files
        both inside and outside vaults.  The median call must be <10ms;
        the test documents actual latency before any optimization attempt.
        """
        import time

        from krag_plugin_obsidian.handler import ObsidianFileTypeHandler

        # Create 5 vaults
        vaults: dict[str, str] = {}
        for i in range(5):
            v = tmp_path / f"vault-{i}"
            v.mkdir()
            (v / "note.md").write_text(f"Vault {i} note", encoding="utf-8")
            vaults[f"v{i}"] = str(v)

        h = ObsidianFileTypeHandler()
        h.initialize({"vaults": vaults}, context=None)

        # Build file list: half inside vaults, half outside
        files: list[Path] = []
        for i in range(5):
            v = tmp_path / f"vault-{i}"
            for j in range(100):
                files.append(v / f"note-{j}.md")
        for j in range(500):
            files.append(tmp_path / f"outside-{j}.md")

        # Time 1000 claims_file calls
        start = time.perf_counter()
        for f in files:
            h.claims_file(f)
        elapsed = time.perf_counter() - start

        per_file_ms = (elapsed / len(files)) * 1000
        # Document actual latency
        print(f"\nSC-005: claims_file per-file latency = {per_file_ms:.4f} ms")
        assert per_file_ms < 10, (
            f"Path resolution took {per_file_ms:.4f} ms/file — exceeds 10ms target"
        )

    def test_resolve_by_path_claim_under_10ms(self, tmp_path: Path) -> None:
        """_resolve_by_path_claim() completes in <10ms per file.

        Tests the full registry path-claim resolution path, not just
        the handler's claims_file().
        """
        import time

        from krag_plugin_obsidian.handler import ObsidianFileTypeHandler

        from krag.plugins.registry import PluginRegistry

        vault = tmp_path / "vault"
        vault.mkdir()

        handler = ObsidianFileTypeHandler()
        handler.initialize({"vaults": {"main": str(vault)}}, context=None)

        config = _make_config()
        registry = PluginRegistry(config)
        registry._loaded["obsidian"] = handler
        registry._discovered["obsidian"] = PluginMetadata(
            name="obsidian",
            version="1.0.0",
            entry_point="krag_plugin_obsidian:ObsidianFileTypeHandler",
            supported_extensions=[".md"],
            required_api_version="1.0",
            has_claims_file=True,
        )

        # Mix of vault and non-vault files
        files: list[Path] = []
        for i in range(500):
            files.append(vault / f"note-{i}.md")
        for i in range(500):
            files.append(tmp_path / f"outside-{i}.md")

        start = time.perf_counter()
        for f in files:
            registry._resolve_by_path_claim(f)
        elapsed = time.perf_counter() - start

        per_file_ms = (elapsed / len(files)) * 1000
        print(f"\nSC-005: _resolve_by_path_claim per-file latency = {per_file_ms:.4f} ms")
        assert per_file_ms < 10, (
            f"Registry path resolution took {per_file_ms:.4f} ms/file — exceeds 10ms target"
        )


class TestResolveByPathClaim:
    """_resolve_by_path_claim() behavior."""

    def test_returns_none_when_no_claiming_plugins(self) -> None:
        """T007: No plugins with has_claims_file → returns None."""
        from krag.plugins.registry import PluginRegistry

        registry = PluginRegistry(_make_config())

        # Populate with a non-claiming plugin
        handler = _ExtensionHandler()
        registry._loaded["markdown"] = handler
        registry._discovered["markdown"] = PluginMetadata(
            name="markdown",
            version="1.0.0",
            entry_point="krag_plugin_markdown.handler:MarkdownFileTypeHandler",
            supported_extensions=[".md"],
            required_api_version="1.0",
            has_claims_file=False,
        )

        result = registry._resolve_by_path_claim(Path("/some/file.md"))
        assert result is None

    def test_returns_none_when_no_plugins_discovered(self) -> None:
        from krag.plugins.registry import PluginRegistry

        registry = PluginRegistry(_make_config())
        result = registry._resolve_by_path_claim(Path("/some/file.md"))
        assert result is None


class TestGetHandlerForFileTwoPhase:
    """get_handler_for_file() two-phase resolution."""

    def test_path_claim_takes_priority_over_extension(self, tmp_path: Path) -> None:
        """T008: Path-claiming plugin wins over extension-based plugin for vault files."""
        from krag.plugins.registry import PluginRegistry

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        vault_file = vault_dir / "note.md"
        vault_file.write_text("# Note")

        registry = PluginRegistry(_make_config())

        # Set up extension handler
        ext_handler = _ExtensionHandler()
        registry._loaded["markdown"] = ext_handler
        registry._discovered["markdown"] = PluginMetadata(
            name="markdown",
            version="1.0.0",
            entry_point="krag_plugin_markdown.handler:MarkdownFileTypeHandler",
            supported_extensions=[".md"],
            required_api_version="1.0",
            has_claims_file=False,
        )
        registry._extension_map[".md"] = "markdown"

        # Set up claiming handler
        claiming_handler = _ClaimingHandler(vault_dir)
        registry._loaded["obsidian"] = claiming_handler
        registry._discovered["obsidian"] = PluginMetadata(
            name="obsidian",
            version="1.0.0",
            entry_point="krag_plugin_obsidian.handler:ObsidianFileTypeHandler",
            supported_extensions=[".md"],
            required_api_version="1.0",
            has_claims_file=True,
        )

        result = registry.get_handler_for_file(vault_file)
        assert result is not None
        assert result.name == "obsidian"

    def test_extension_fallback_for_non_claimed_file(self, tmp_path: Path) -> None:
        """Files not claimed by any path plugin fall through to extension."""
        from krag.plugins.registry import PluginRegistry

        non_vault_file = tmp_path / "readme.md"
        non_vault_file.write_text("# Readme")

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        registry = PluginRegistry(_make_config())

        # Extension handler
        ext_handler = _ExtensionHandler()
        registry._loaded["markdown"] = ext_handler
        registry._discovered["markdown"] = PluginMetadata(
            name="markdown",
            version="1.0.0",
            entry_point="krag_plugin_markdown.handler:MarkdownFileTypeHandler",
            supported_extensions=[".md"],
            required_api_version="1.0",
            has_claims_file=False,
        )
        registry._extension_map[".md"] = "markdown"

        # Claiming handler (vault is elsewhere)
        claiming_handler = _ClaimingHandler(vault_dir)
        registry._loaded["obsidian"] = claiming_handler
        registry._discovered["obsidian"] = PluginMetadata(
            name="obsidian",
            version="1.0.0",
            entry_point="krag_plugin_obsidian.handler:ObsidianFileTypeHandler",
            supported_extensions=[".md"],
            required_api_version="1.0",
            has_claims_file=True,
        )

        result = registry.get_handler_for_file(non_vault_file)
        assert result is not None
        assert result.name == "markdown"

    def test_returns_none_when_no_handler_matches(self, tmp_path: Path) -> None:
        """No claiming or extension handler → None."""
        from krag.plugins.registry import PluginRegistry

        registry = PluginRegistry(_make_config())
        result = registry.get_handler_for_file(tmp_path / "file.xyz")
        assert result is None
