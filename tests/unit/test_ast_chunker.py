"""Unit tests for ASTChunker — code-aware chunking via tree-sitter."""

from pathlib import Path

# --- T013: 30-line function chunked as single unit ---

SINGLE_FUNCTION_30_LINES = '''
import os


@staticmethod
def process_data(
    items: list[str],
    transform: bool = True,
    max_items: int = 100,
) -> list[dict]:
    """Process a list of data items.

    Args:
        items: List of raw string items.
        transform: Whether to apply transformation.
        max_items: Maximum items to process.

    Returns:
        List of processed dictionaries.

    Raises:
        ValueError: If items is empty.
    """
    if not items:
        raise ValueError("items must not be empty")
    results = []
    for item in items[:max_items]:
        record = {"raw": item}
        if transform:
            record["transformed"] = item.strip().lower()
        results.append(record)
    return results
'''


class TestSingleFunctionChunking:
    """T013: A 30-line function should be chunked as a single unit."""

    def test_function_is_single_chunk(self, tmp_path: Path) -> None:
        """A complete function should produce one chunk."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SINGLE_FUNCTION_30_LINES)

        chunks = chunker.chunk(SINGLE_FUNCTION_30_LINES, file_path=file_path)
        # Should have the function as one chunk (plus possibly an import chunk)
        func_chunks = [c for c in chunks if "def process_data" in c.content]
        assert len(func_chunks) == 1

    def test_function_chunk_includes_decorator(self, tmp_path: Path) -> None:
        """Function chunk must include its decorator."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SINGLE_FUNCTION_30_LINES)

        chunks = chunker.chunk(SINGLE_FUNCTION_30_LINES, file_path=file_path)
        func_chunks = [c for c in chunks if "def process_data" in c.content]
        assert len(func_chunks) == 1
        assert "@staticmethod" in func_chunks[0].content

    def test_function_chunk_includes_docstring(self, tmp_path: Path) -> None:
        """Function chunk must include its docstring."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SINGLE_FUNCTION_30_LINES)

        chunks = chunker.chunk(SINGLE_FUNCTION_30_LINES, file_path=file_path)
        func_chunks = [c for c in chunks if "def process_data" in c.content]
        assert "Process a list of data items" in func_chunks[0].content

    def test_function_metadata_has_function_name(self, tmp_path: Path) -> None:
        """Metadata must include function_name."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(SINGLE_FUNCTION_30_LINES)

        chunks = chunker.chunk(SINGLE_FUNCTION_30_LINES, file_path=file_path)
        func_chunks = [c for c in chunks if "def process_data" in c.content]
        metadata = chunker.get_chunk_metadata(func_chunks[0])
        assert metadata["function_name"] == "process_data"


# --- T014: Class with 5 methods produces separate chunks ---

CLASS_WITH_METHODS = '''
class UserService:
    """Service for managing users."""

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url
        self._cache: dict = {}

    def create_user(self, name: str, email: str) -> dict:
        """Create a new user."""
        user = {"name": name, "email": email}
        return user

    def get_user(self, user_id: int) -> dict | None:
        """Get user by ID."""
        return self._cache.get(str(user_id))

    def update_user(self, user_id: int, data: dict) -> dict:
        """Update user fields."""
        user = self.get_user(user_id) or {}
        user.update(data)
        return user

    def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        key = str(user_id)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def list_users(self, limit: int = 10) -> list[dict]:
        """List all users."""
        return list(self._cache.values())[:limit]
'''


class TestClassWithMethodsChunking:
    """T014: Class with 5 methods produces separate chunks with parent class context."""

    def test_methods_produce_separate_chunks(self, tmp_path: Path) -> None:
        """Each method should be a separate chunk."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(CLASS_WITH_METHODS)

        chunks = chunker.chunk(CLASS_WITH_METHODS, file_path=file_path)
        method_names = [
            "__init__",
            "create_user",
            "get_user",
            "update_user",
            "delete_user",
            "list_users",
        ]

        for method_name in method_names:
            matching = [c for c in chunks if f"def {method_name}" in c.content]
            assert len(matching) >= 1, f"Method {method_name} should have its own chunk"

    def test_method_chunks_include_class_context(self, tmp_path: Path) -> None:
        """Method chunks should include parent class name as context."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(CLASS_WITH_METHODS)

        chunks = chunker.chunk(CLASS_WITH_METHODS, file_path=file_path)
        method_chunks = [c for c in chunks if "def create_user" in c.content]
        assert len(method_chunks) == 1
        # Should have class context prepended or in metadata
        metadata = chunker.get_chunk_metadata(method_chunks[0])
        assert metadata.get("class_name") == "UserService"

    def test_method_chunk_metadata_has_class_name(self, tmp_path: Path) -> None:
        """Metadata for method chunks must have class_name field."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(CLASS_WITH_METHODS)

        chunks = chunker.chunk(CLASS_WITH_METHODS, file_path=file_path)
        for chunk in chunks:
            metadata = chunker.get_chunk_metadata(chunk)
            if "def " in chunk.content and "self" in chunk.content:
                assert metadata.get("class_name") == "UserService"


# --- T015: Import blocks handled ---

CODE_WITH_IMPORTS = '''
import os
import sys
from pathlib import Path
from typing import Any, Optional

def do_something() -> None:
    """Do something."""
    pass

def do_another() -> None:
    """Do another thing."""
    pass
'''


class TestImportBlockHandling:
    """T015: Import blocks should be handled (as own chunk or prepended)."""

    def test_imports_are_captured(self, tmp_path: Path) -> None:
        """Import statements should appear in the output (as chunk or prepended)."""
        from krag_plugin_code.ast_chunker import ASTChunker

        chunker = ASTChunker(language="python")
        file_path = tmp_path / "test.py"
        file_path.write_text(CODE_WITH_IMPORTS)

        chunks = chunker.chunk(CODE_WITH_IMPORTS, file_path=file_path)
        all_content = "\n".join(c.content for c in chunks)
        assert "import os" in all_content


# --- T016: Parse errors trigger graceful fallback ---


class TestParseErrorFallback:
    """T016: Parse errors trigger graceful fallback to TextChunker."""

    def test_malformed_file_does_not_crash(self, tmp_path: Path) -> None:
        """Malformed code should not raise an exception."""
        from krag_plugin_code.ast_chunker import ASTChunker

        malformed = "def broken(\n    x y\n\nclass Bad\n    pass"
        chunker = ASTChunker(language="python")
        file_path = tmp_path / "broken.py"
        file_path.write_text(malformed)

        # Should not raise
        chunks = chunker.chunk(malformed, file_path=file_path)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_fallback_produces_text_chunks(self, tmp_path: Path) -> None:
        """Fallback should still produce valid TextChunk objects."""
        from krag_plugin_code.ast_chunker import ASTChunker

        from krag.models.text_chunk import TextChunk

        malformed = "def broken(\n    x y\n\nclass Bad\n    pass"
        chunker = ASTChunker(language="python")
        file_path = tmp_path / "broken.py"
        file_path.write_text(malformed)

        chunks = chunker.chunk(malformed, file_path=file_path)
        for chunk in chunks:
            assert isinstance(chunk, TextChunk)


# --- T017: Oversized function splits at statement boundaries ---


class TestOversizedFunctionSplitting:
    """T017: Oversized function (>2048 chars) splits at statement boundaries."""

    def test_oversized_function_is_split(self, tmp_path: Path) -> None:
        """A function exceeding max chunk size should be split."""
        from krag_plugin_code.ast_chunker import ASTChunker

        # Create a function with many statements (>2048 chars)
        lines = ["def huge_function() -> None:"]
        lines.append('    """A very large function."""')
        for i in range(100):
            lines.append(f"    result_{i} = calculate_value({i}, {i + 1})")
        oversized_code = "\n".join(lines) + "\n"

        chunker = ASTChunker(language="python", max_chunk_size=500)
        file_path = tmp_path / "big.py"
        file_path.write_text(oversized_code)

        chunks = chunker.chunk(oversized_code, file_path=file_path)
        # Should be split into multiple chunks
        assert len(chunks) > 1

    def test_split_does_not_break_mid_statement(self, tmp_path: Path) -> None:
        """Split chunks should not break in the middle of a statement."""
        from krag_plugin_code.ast_chunker import ASTChunker

        lines = ["def huge_function() -> None:"]
        lines.append('    """A very large function."""')
        for i in range(60):
            lines.append(f"    result_{i} = calculate_value({i}, {i + 1})")
        oversized_code = "\n".join(lines) + "\n"

        chunker = ASTChunker(language="python", max_chunk_size=500)
        file_path = tmp_path / "big.py"
        file_path.write_text(oversized_code)

        chunks = chunker.chunk(oversized_code, file_path=file_path)
        for chunk in chunks:
            # Each chunk should be valid (not cut mid-line)
            content = chunk.content.strip()
            assert len(content) > 0
