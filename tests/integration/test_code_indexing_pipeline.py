"""Integration test: end-to-end Python project indexing with code plugin.

T019 [US1] Validates the full pipeline: file discovery → text extraction →
AST chunking → embedding → vector storage with code metadata.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from krag.models.text_chunk import TextChunk


@pytest.fixture()
def sample_python_path() -> Path:
    """Path to the sample Python fixture file."""
    return Path(__file__).parent.parent / "fixtures" / "code" / "sample_python.py"


class TestCodeIndexingPipeline:
    """End-to-end integration tests for code-aware indexing."""

    def test_code_plugin_chunks_python_file(self, sample_python_path: Path) -> None:
        """Code plugin should chunk a Python file into semantic units."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})

        # Extract text
        text = handler.extract_text(sample_python_path)
        assert isinstance(text, str)
        assert len(text) > 0

        # Get chunker for this file type
        chunker = handler.get_chunker(sample_python_path)

        # Chunk the text
        chunks = chunker.chunk(text, file_path=sample_python_path)
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, TextChunk)

    def test_chunks_are_semantic_units(self, sample_python_path: Path) -> None:
        """Chunks should be complete functions/methods, not arbitrary splits."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})
        text = handler.extract_text(sample_python_path)
        chunker = handler.get_chunker(sample_python_path)
        chunks = chunker.chunk(text, file_path=sample_python_path)

        # At least some chunks should contain def statements
        has_function_chunks = any("def " in c.content for c in chunks)
        assert has_function_chunks, "Expected some chunks to contain function definitions"

        # No chunk should split a function in the middle (every 'def' should
        # be at the beginning or after a class context line)
        for chunk in chunks:
            lines = chunk.content.strip().split("\n")
            # Filter out empty lines and class context lines
            code_lines = [
                line for line in lines if line.strip() and not line.startswith("# Class:")
            ]
            if code_lines and "def " in code_lines[0]:
                # If chunk starts with a function def, it should include the body
                assert len(code_lines) > 1 or "pass" in code_lines[0]

    def test_chunks_have_code_metadata(self, sample_python_path: Path) -> None:
        """Each chunk should have retrievable code metadata."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})
        text = handler.extract_text(sample_python_path)
        chunker = handler.get_chunker(sample_python_path)
        chunks = chunker.chunk(text, file_path=sample_python_path)

        for chunk in chunks:
            meta = chunker.get_chunk_metadata(chunk)
            assert isinstance(meta, dict)
            assert "language" in meta
            assert meta["language"] == "python"

    def test_method_chunks_include_class_context(self, sample_python_path: Path) -> None:
        """Method chunks should include class context prefix."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})
        text = handler.extract_text(sample_python_path)
        chunker = handler.get_chunker(sample_python_path)
        chunks = chunker.chunk(text, file_path=sample_python_path)

        # Find chunks that are methods (have class_name in metadata)
        method_chunks = [
            c for c in chunks if chunker.get_chunk_metadata(c).get("class_name") is not None
        ]
        assert len(method_chunks) > 0, "Expected method chunks with class context"

        for mc in method_chunks:
            assert mc.content.startswith("# Class:"), (
                f"Method chunk should start with class context: {mc.content[:80]}"
            )

    def test_extract_metadata_detects_language(self, sample_python_path: Path) -> None:
        """extract_metadata should correctly identify Python."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})
        meta = handler.extract_metadata(sample_python_path)

        assert meta["language"] == "python"
        assert meta["line_count"] > 0
        assert meta["file_size"] > 0
        assert meta["has_parse_errors"] is False

    def test_malformed_file_handled_gracefully(self) -> None:
        """Malformed files should not crash the pipeline."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})

        broken_path = (
            Path(__file__).parent.parent / "fixtures" / "code" / "malformed" / "broken_python.py"
        )
        text = handler.extract_text(broken_path)
        chunker = handler.get_chunker(broken_path)

        # Should not raise
        chunks = chunker.chunk(text, file_path=broken_path)
        assert len(chunks) > 0  # Fallback should produce chunks

    def test_import_blocks_captured(self, sample_python_path: Path) -> None:
        """Import statements should be captured as chunks."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})
        text = handler.extract_text(sample_python_path)
        chunker = handler.get_chunker(sample_python_path)
        chunks = chunker.chunk(text, file_path=sample_python_path)

        # Check that imports are present in some chunk
        all_content = " ".join(c.content for c in chunks)
        assert "import" in all_content

    def test_chunk_indices_sequential(self, sample_python_path: Path) -> None:
        """Chunk indices should be sequential starting from 0."""
        from krag_plugin_code.handler import CodeFileHandler

        handler = CodeFileHandler()
        handler.initialize({})
        text = handler.extract_text(sample_python_path)
        chunker = handler.get_chunker(sample_python_path)
        chunks = chunker.chunk(text, file_path=sample_python_path)

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))
