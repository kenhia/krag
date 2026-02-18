"""Contract tests: ASTChunker produces valid TextChunk objects."""

from pathlib import Path

SAMPLE_PYTHON = '''
import os
from pathlib import Path

def calculate_sum(a: int, b: int) -> int:
    """Calculate sum of two numbers."""
    return a + b

class Calculator:
    """A simple calculator."""

    def __init__(self, precision: int = 2) -> None:
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        return round(a + b, self.precision)

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return round(a * b, self.precision)
'''


class TestASTChunkerContract:
    """Verify ASTChunker produces valid TextChunk objects."""

    def test_chunk_returns_list_of_text_chunks(self, tmp_path: Path) -> None:
        """chunk() must return a list of TextChunk objects."""
        from krag_plugin_code.ast_chunker import ASTChunker

        from krag.models.text_chunk import TextChunk

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SAMPLE_PYTHON)

        chunks = chunker.chunk(SAMPLE_PYTHON, file_path=file_path)
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, TextChunk)

    def test_chunks_have_valid_fields(self, tmp_path: Path) -> None:
        """Each TextChunk must have required fields populated."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SAMPLE_PYTHON)

        chunks = chunker.chunk(SAMPLE_PYTHON, file_path=file_path)
        for chunk in chunks:
            assert chunk.chunk_id  # Non-empty
            assert chunk.file_path == file_path
            assert chunk.content  # Non-empty content
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char
            assert chunk.token_count > 0

    def test_chunk_content_is_valid_code(self, tmp_path: Path) -> None:
        """Chunk content should be valid, parseable code constructs."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SAMPLE_PYTHON)

        chunks = chunker.chunk(SAMPLE_PYTHON, file_path=file_path)
        # At least one chunk should contain a function definition
        contents = [c.content for c in chunks]
        assert any("def " in c for c in contents)

    def test_get_chunk_metadata_returns_dict(self, tmp_path: Path) -> None:
        """get_chunk_metadata() must return a dict with code metadata."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SAMPLE_PYTHON)

        chunks = chunker.chunk(SAMPLE_PYTHON, file_path=file_path)
        for chunk in chunks:
            metadata = chunker.get_chunk_metadata(chunk)
            assert isinstance(metadata, dict)
            assert "language" in metadata
            assert metadata["language"] == "python"

    def test_chunk_indices_are_sequential(self, tmp_path: Path) -> None:
        """Chunk indices must be sequential starting from 0."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SAMPLE_PYTHON)

        chunks = chunker.chunk(SAMPLE_PYTHON, file_path=file_path)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))
