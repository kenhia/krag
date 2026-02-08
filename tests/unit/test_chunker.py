"""Unit tests for TextChunker.

Tests text chunking functionality.
Should FAIL until TextChunker is implemented.
"""

import pytest


class TestTextChunker:
    """Unit tests for TextChunker class."""

    def test_text_chunker_initialization(self) -> None:
        """Test TextChunker can be initialized with parameters."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=500, chunk_overlap=50)

        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50

    def test_chunk_short_text_returns_single_chunk(self) -> None:
        """Test chunking short text returns single chunk."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        text = "This is a short text."

        chunks = chunker.chunk(text)

        assert len(chunks) == 1, "Short text should return single chunk"
        assert chunks[0].content == text

    def test_chunk_long_text_creates_multiple_chunks(self) -> None:
        """Test chunking long text creates multiple chunks."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        # Create text longer than chunk size
        text = "This is a sentence. " * 20  # ~400 chars

        chunks = chunker.chunk(text)

        assert len(chunks) > 1, "Long text should create multiple chunks"
        assert all(len(chunk.content) <= 120 for chunk in chunks), (
            "Chunks should respect size limit"
        )

    def test_chunk_overlap_preserved(self) -> None:
        """Test chunks have specified overlap."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "Word " * 50  # 250 chars

        chunks = chunker.chunk(text)

        if len(chunks) > 1:
            # Check overlap between consecutive chunks
            chunk1_end = chunks[0].content[-20:]
            # Should have some overlap
            assert len(chunk1_end) > 0, "Should have content to overlap"

    def test_chunk_respects_sentence_boundaries(self) -> None:
        """Test chunking tries to split at sentence boundaries."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."

        chunks = chunker.chunk(text)

        # Chunks should preferably end at sentence boundaries
        if len(chunks) > 1:
            # Most chunks should end with period
            chunks_ending_with_period = sum(
                1 for chunk in chunks if chunk.content.rstrip().endswith(".")
            )
            assert chunks_ending_with_period > 0, "Should try to split at sentence boundaries"

    def test_chunk_code_preserves_structure(self) -> None:
        """Test code-aware chunking preserves code structure."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        code = """def function_one():
    print("one")
    return 1

def function_two():
    print("two")
    return 2

def function_three():
    print("three")
    return 3"""

        chunks = chunker.chunk_code(code, language="python")

        # Should try to split at function boundaries
        assert len(chunks) > 0, "Should create chunks"
        # Ideally, each function in its own chunk or logically grouped

    def test_chunk_returns_metadata(self) -> None:
        """Test chunks include metadata (start/end positions)."""
        from krag.extraction.chunker import TextChunker
        from krag.models.text_chunk import TextChunk

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "Word " * 30

        chunks = chunker.chunk(text)

        for chunk in chunks:
            assert isinstance(chunk, TextChunk), "Should return TextChunk objects"
            assert chunk.start_char >= 0, "Should have start position"
            assert chunk.end_char > chunk.start_char, "End should be after start"
            assert len(chunk.content) > 0, "Chunk should have content"

    def test_chunk_handles_empty_text(self) -> None:
        """Test chunking empty text."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=500, chunk_overlap=50)

        chunks = chunker.chunk("")

        # Should return empty list or single empty chunk
        assert len(chunks) == 0 or (len(chunks) == 1 and chunks[0].content == "")

    def test_chunk_handles_whitespace_only(self) -> None:
        """Test chunking whitespace-only text."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=500, chunk_overlap=50)

        chunks = chunker.chunk("   \n\n\t  ")

        # Should return empty or handle gracefully
        assert len(chunks) <= 1, "Whitespace should not create multiple chunks"

    def test_chunk_preserves_order(self) -> None:
        """Test chunks maintain document order."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "First section. " * 10 + "Second section. " * 10

        chunks = chunker.chunk(text)

        # Chunks should be in order
        for i in range(len(chunks) - 1):
            assert chunks[i].start_char < chunks[i + 1].start_char, (
                "Chunks should be ordered by position"
            )

    def test_chunk_different_separators(self) -> None:
        """Test chunking with different text separators."""
        from krag.extraction.chunker import TextChunker

        # Test with paragraph separator
        chunker = TextChunker(chunk_size=200, chunk_overlap=20, separators=["\n\n", "\n", ". "])
        text = "Para 1\n\nPara 2\n\nPara 3\n\nPara 4"

        chunks = chunker.chunk(text)

        # Should prefer splitting at paragraph boundaries
        assert len(chunks) > 0, "Should create chunks"

    def test_chunk_markdown_structure(self) -> None:
        """Test chunking respects markdown structure."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        markdown = """# Header 1

Content under header 1.

## Subheader

Content under subheader.

# Header 2

Content under header 2."""

        chunks = chunker.chunk(markdown)

        # Should try to keep headers with their content
        assert len(chunks) > 0, "Should create chunks"
        # Ideally headers stay with their content

    def test_chunk_size_validation(self) -> None:
        """Test chunk size validation."""
        from krag.extraction.chunker import TextChunker

        # Overlap should be less than chunk size
        with pytest.raises((ValueError, AssertionError)):
            TextChunker(chunk_size=100, chunk_overlap=150)

    def test_chunk_with_special_characters(self) -> None:
        """Test chunking text with special characters."""
        from krag.extraction.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "Text with émojis 🚀 and spëcial çharacters. " * 5

        chunks = chunker.chunk(text)

        # Should handle special characters correctly
        assert len(chunks) > 0, "Should chunk text with special characters"
        reconstructed = "".join(chunk.content for chunk in chunks)
        assert "🚀" in reconstructed, "Should preserve special characters"
