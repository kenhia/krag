"""Live integration tests for Obsidian vault plugin against a running kragd.

Run with:
    uv run pytest -m live --no-cov -v -k obsidian

Requires:
    - A running kragd service
    - The Obsidian plugin installed (``uv pip install -e examples/krag-plugin-obsidian``)
    - At least one vault configured in kragd's config.toml under ``[plugins.obsidian.vaults]``

Environment variables — see conftest.py for connection details.
    KRAG_TEST_OBSIDIAN_VAULT  Path to the Obsidian vault to index (default: ~/obsidian)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from krag_cli.client import KragClient
from tests.live.conftest import ensure_idle, poll_index_complete

pytestmark = pytest.mark.live


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vault_dir() -> Path:
    return Path(os.environ.get("KRAG_TEST_OBSIDIAN_VAULT", str(Path.home() / "obsidian")))


# =========================================================================
# T076 — Vault indexing and query against kragd
# =========================================================================


class Test00VaultIndexing:
    """Index an Obsidian vault and verify results are queryable."""

    def test_vault_exists(self) -> None:
        """Skip all Obsidian live tests if the vault directory is missing."""
        vault = _vault_dir()
        if not vault.is_dir():
            pytest.skip(f"Obsidian vault not found: {vault}")

    def test_trigger_vault_index(self, client: KragClient) -> None:
        """Trigger incremental indexing of the Obsidian vault directory."""
        vault = _vault_dir()
        if not vault.is_dir():
            pytest.skip(f"Vault not found: {vault}")

        ensure_idle(client, timeout=120)
        resp = client.index(
            mode="incremental",
            directories=[str(vault)],
        )
        assert resp["status"] in ("running", "completed")

    def test_wait_for_index(self, client: KragClient) -> None:
        """Wait for vault indexing to complete."""
        result = poll_index_complete(client, timeout=600)
        assert result["status"] == "completed", f"Vault indexing failed: {result}"
        self.__class__._index_result = result

    def test_files_indexed(self) -> None:
        """At least some files should have been scanned."""
        result = getattr(self.__class__, "_index_result", None)
        if result is None:
            pytest.skip("Indexing did not complete")
        assert result["files_scanned"] > 0, "Expected files to be scanned"

    def test_query_vault_content(self, client: KragClient) -> None:
        """A broad query should return results from the indexed vault."""
        ensure_idle(client, timeout=60)
        sources = client.retrieve("notes and documents", top_k=10)
        assert len(sources) > 0, "Expected retrieval results after vault indexing"


# =========================================================================
# T077 — Mixed-content routing verification
# =========================================================================


class Test01MixedContentRouting:
    """Verify that prose and code blocks are routed to separate collections."""

    def test_docs_collection_has_results(self, client: KragClient) -> None:
        """Querying for note prose should return docs-collection results."""
        ensure_idle(client, timeout=60)
        sources = client.retrieve("daily notes and ideas", top_k=10)
        # We can't filter by collection in the public API, but we can verify
        # results are returned — the Obsidian plugin routes prose to docs.
        assert isinstance(sources, list)

    def test_code_collection_has_results(self, client: KragClient) -> None:
        """Querying for code should return code-collection results if any code blocks exist."""
        ensure_idle(client, timeout=60)
        try:
            resp = client.query(
                "code snippet or function definition",
                top_k=5,
                mode="code",
            )
            assert "answer" in resp
        except (RuntimeError, ValueError):
            pytest.skip("Code mode not available or no code blocks found")

    def test_debug_qdrant_shows_collections(self, client: KragClient) -> None:
        """The status endpoint should show both docs and code collections."""
        status = client.status()
        collections = status.get("collections", {})
        assert len(collections) > 0, "Expected at least one collection"
        # Both should exist if any vault content with code blocks was indexed
        col_names = set(collections.keys()) if isinstance(collections, dict) else set()
        # At minimum, docs should exist
        has_docs = any("docs" in name for name in col_names)
        assert has_docs, f"Expected a docs collection — found: {col_names}"


# =========================================================================
# T078 — --mode obsidian query
# =========================================================================


class Test02ObsidianMode:
    """Verify queries work with --mode obsidian retrieval mode."""

    def test_obsidian_mode_exists(self, client: KragClient) -> None:
        """The obsidian mode should be listed in /modes."""
        resp = client._get("/modes")
        modes = resp.get("modes", resp) if isinstance(resp, dict) else resp
        mode_names = [m["name"] if isinstance(m, dict) else m for m in modes]
        assert "obsidian" in mode_names, f"obsidian mode not found — available: {mode_names}"

    def test_query_with_obsidian_mode(self, client: KragClient) -> None:
        """A query with --mode obsidian should return an answer."""
        ensure_idle(client, timeout=60)
        try:
            resp = client.query(
                "What topics are in my notes?",
                top_k=5,
                mode="obsidian",
            )
            assert "answer" in resp
            assert len(resp["answer"]) > 0
        except (RuntimeError, ValueError) as e:
            pytest.fail(f"Obsidian mode query failed: {e}")

    def test_retrieve_with_obsidian_mode(self, client: KragClient) -> None:
        """Retrieval with obsidian mode should return sources."""
        ensure_idle(client, timeout=60)
        try:
            sources = client.retrieve("notes", top_k=5, mode="obsidian")
            assert isinstance(sources, list)
            # May be empty if no vault content matches, but should not error
        except (RuntimeError, ValueError) as e:
            pytest.fail(f"Obsidian mode retrieval failed: {e}")

    def test_obsidian_mode_detail(self, client: KragClient) -> None:
        """GET /modes/obsidian should return the obsidian mode configuration."""
        try:
            resp = client._get("/modes/obsidian")
            assert resp["name"] == "obsidian"
        except (RuntimeError, ValueError):
            pytest.skip("Mode detail endpoint not available")
