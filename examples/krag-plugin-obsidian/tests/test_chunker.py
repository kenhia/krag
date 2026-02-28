"""Tests for ObsidianChunker — Phase 4 / User Story 2 (Mixed-Content Routing)."""

from __future__ import annotations

from pathlib import Path

import pytest


from krag_plugin_obsidian.chunker import ObsidianChunker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VAULT_NAME = "test-vault"
VIRTUAL_PREFIX = "obsidian://test-vault/notes/example.md"
FILE_PATH = Path("/tmp/vault/notes/example.md")


@pytest.fixture()
def chunker() -> ObsidianChunker:
    """Return a chunker with a test vault."""
    return ObsidianChunker(vault_name=VAULT_NAME, virtual_path=VIRTUAL_PREFIX)


# ---------------------------------------------------------------------------
# T040 — prose-only note produces docs-targeted chunks
# ---------------------------------------------------------------------------


class TestProseOnly:
    def test_prose_only_chunks_target_docs(self, chunker: ObsidianChunker) -> None:
        """Prose-only note should produce chunks with target_collection='docs'."""
        text = "This is a simple note.\n\nIt has two paragraphs."
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        assert len(chunks) >= 1
        for chunk in chunks:
            meta = chunker.get_chunk_metadata(chunk)
            assert meta["target_collection"] == "docs"
            assert meta["content_type"] == "prose"

    def test_prose_content_preserved(self, chunker: ObsidianChunker) -> None:
        """Prose content is preserved in chunk text."""
        text = "Hello, world!"
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        assert any("Hello, world!" in c.content for c in chunks)


# ---------------------------------------------------------------------------
# T041 — fenced code block with language goes to code collection
# ---------------------------------------------------------------------------


class TestFencedCodeWithLanguage:
    def test_code_block_with_language_targets_code(self, chunker: ObsidianChunker) -> None:
        """Fenced code block with a language tag targets the code collection."""
        text = (
            "Some prose before.\n\n"
            "```python\n"
            "def hello():\n"
            "    print('hi')\n"
            "```\n\n"
            "Some prose after."
        )
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        assert len(chunks) >= 2  # at least prose + code

        code_chunks = [c for c in chunks if chunker.get_chunk_metadata(c)["content_type"] == "code"]
        assert len(code_chunks) >= 1
        meta = chunker.get_chunk_metadata(code_chunks[0])
        assert meta["target_collection"] == "code"
        assert "def hello()" in code_chunks[0].content

    def test_prose_around_code_targets_docs(self, chunker: ObsidianChunker) -> None:
        """Prose surrounding a code block still targets docs."""
        text = "Intro paragraph.\n\n```python\ncode()\n```\n\nConclusion paragraph."
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        prose_chunks = [
            c for c in chunks if chunker.get_chunk_metadata(c)["content_type"] == "prose"
        ]
        assert len(prose_chunks) >= 1
        for pc in prose_chunks:
            assert chunker.get_chunk_metadata(pc)["target_collection"] == "docs"


# ---------------------------------------------------------------------------
# T042 — fenced code block without language → docs (FR-012)
# ---------------------------------------------------------------------------


class TestFencedCodeNoLanguage:
    def test_untagged_code_block_targets_docs(self, chunker: ObsidianChunker) -> None:
        """Code block without language tag is treated as prose → docs (FR-012)."""
        text = "Some text.\n\n```\nno language here\n```\n\nMore text."
        chunks = chunker.chunk(text, file_path=FILE_PATH)

        # Find the chunk containing the untagged code
        untagged = [c for c in chunks if "no language here" in c.content]
        assert len(untagged) == 1
        meta = chunker.get_chunk_metadata(untagged[0])
        assert meta["target_collection"] == "docs"


# ---------------------------------------------------------------------------
# T043 — multiple code blocks with different languages
# ---------------------------------------------------------------------------


class TestMultipleCodeBlocks:
    def test_multiple_languages_each_in_own_chunk(self, chunker: ObsidianChunker) -> None:
        """Multiple code blocks produce separate chunks with correct languages."""
        text = (
            "Intro.\n\n"
            "```python\nprint('py')\n```\n\n"
            "Middle.\n\n"
            "```javascript\nconsole.log('js')\n```\n\n"
            "End."
        )
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        code_chunks = [c for c in chunks if chunker.get_chunk_metadata(c)["content_type"] == "code"]
        assert len(code_chunks) == 2

        langs = {chunker.get_chunk_metadata(c)["language"] for c in code_chunks}
        assert langs == {"python", "javascript"}

        for cc in code_chunks:
            assert chunker.get_chunk_metadata(cc)["target_collection"] == "code"


# ---------------------------------------------------------------------------
# T044 — language identifier preserved in chunk metadata
# ---------------------------------------------------------------------------


class TestLanguagePreserved:
    def test_language_in_metadata(self, chunker: ObsidianChunker) -> None:
        """Language identifier is available in chunk metadata."""
        text = "```rust\nfn main() {}\n```"
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        assert len(chunks) >= 1
        meta = chunker.get_chunk_metadata(chunks[0])
        assert meta["language"] == "rust"

    def test_prose_has_no_language(self, chunker: ObsidianChunker) -> None:
        """Prose chunks have language=None."""
        text = "Just prose."
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        meta = chunker.get_chunk_metadata(chunks[0])
        assert meta.get("language") is None


# ---------------------------------------------------------------------------
# T045 — get_chunk_metadata returns target_collection and content_type
# ---------------------------------------------------------------------------


class TestChunkMetadata:
    def test_metadata_keys_present(self, chunker: ObsidianChunker) -> None:
        """get_chunk_metadata() always returns target_collection, content_type, vault_name."""
        text = "Hello."
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        meta = chunker.get_chunk_metadata(chunks[0])
        assert "target_collection" in meta
        assert "content_type" in meta
        assert "vault_name" in meta
        assert meta["vault_name"] == VAULT_NAME

    def test_code_chunk_metadata_complete(self, chunker: ObsidianChunker) -> None:
        """Code chunks include language in metadata."""
        text = "```go\npackage main\n```"
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        meta = chunker.get_chunk_metadata(chunks[0])
        assert meta == {
            "target_collection": "code",
            "content_type": "code",
            "language": "go",
            "vault_name": VAULT_NAME,
        }


# ---------------------------------------------------------------------------
# T046 — nested/varying backtick fence lengths
# ---------------------------------------------------------------------------


class TestVaryingFenceLengths:
    def test_four_backtick_fence(self, chunker: ObsidianChunker) -> None:
        """Four-backtick fences are correctly parsed."""
        text = "````python\ncode()\n````"
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        code_chunks = [c for c in chunks if chunker.get_chunk_metadata(c)["content_type"] == "code"]
        assert len(code_chunks) == 1
        assert "code()" in code_chunks[0].content

    def test_nested_triple_inside_quad(self, chunker: ObsidianChunker) -> None:
        """Triple backticks inside a quad-fence are treated as content, not delimiters."""
        text = "````markdown\n```python\ninner_code()\n```\n````"
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        code_chunks = [c for c in chunks if chunker.get_chunk_metadata(c)["content_type"] == "code"]
        # Should be ONE code chunk containing the nested fence as content
        assert len(code_chunks) == 1
        assert "```python" in code_chunks[0].content
        assert "inner_code()" in code_chunks[0].content


# ---------------------------------------------------------------------------
# T047 — empty note and zero-content handling
# ---------------------------------------------------------------------------


class TestEmptyContent:
    def test_empty_string(self, chunker: ObsidianChunker) -> None:
        """Empty string produces no chunks."""
        chunks = chunker.chunk("", file_path=FILE_PATH)
        assert chunks == []

    def test_whitespace_only(self, chunker: ObsidianChunker) -> None:
        """Whitespace-only string produces no chunks."""
        chunks = chunker.chunk("   \n\n  \n", file_path=FILE_PATH)
        assert chunks == []

    def test_empty_code_block(self, chunker: ObsidianChunker) -> None:
        """Empty code block is skipped."""
        text = "Some text.\n\n```python\n```\n\nMore text."
        chunks = chunker.chunk(text, file_path=FILE_PATH)
        # Empty code block should be skipped; only prose remains
        for c in chunks:
            meta = chunker.get_chunk_metadata(c)
            assert meta["content_type"] == "prose"
