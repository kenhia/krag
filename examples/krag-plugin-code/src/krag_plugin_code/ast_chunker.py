"""AST-based code chunker using tree-sitter.

Parses source code into semantic units (functions, methods, classes)
and produces TextChunk objects with code-specific metadata.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tree_sitter import Node, Parser

from krag.models.text_chunk import TextChunk

from krag_plugin_code.languages import get_grammar_for_language

logger = logging.getLogger(__name__)

# Default max chunk size in characters for code files
DEFAULT_CODE_CHUNK_SIZE = 2048


@dataclass(frozen=True)
class SemanticUnit:
    """A parsed code construct from tree-sitter.

    Intermediate representation — never stored, only used during chunking.
    """

    node_type: str  # "function_definition", "class_definition", etc.
    name: str | None  # Function/class name, or None for import blocks
    source_text: str  # Full source text of this unit
    start_line: int  # 0-based (raw tree-sitter)
    end_line: int  # 0-based (raw tree-sitter)
    start_byte: int  # Byte offset in source file
    end_byte: int  # Byte offset in source file
    parent_class: str | None  # Parent class name for methods
    decorators: list[str] = field(default_factory=list)  # Decorator strings
    has_error: bool = False  # True if subtree contains ERROR nodes
    children: list[SemanticUnit] = field(default_factory=list)  # Methods for classes


class ASTChunker:
    """Tree-sitter AST-based code chunker.

    Chunks source code into semantic units — complete functions, methods,
    and classes. Falls back to text-based chunking on parse errors.
    """

    def __init__(
        self,
        language: str = "python",
        max_chunk_size: int = DEFAULT_CODE_CHUNK_SIZE,
    ) -> None:
        """Initialize the AST chunker.

        Args:
            language: Language name for tree-sitter grammar.
            max_chunk_size: Maximum chunk size in characters.
        """
        self.language = language
        self.max_chunk_size = max_chunk_size
        self._grammar = get_grammar_for_language(language)
        self._parser: Parser | None = None
        self._chunk_metadata: dict[str, dict[str, Any]] = {}

        if self._grammar is not None:
            self._parser = Parser(self._grammar)

    def chunk(
        self,
        text: str,
        file_path: Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Chunk source code into semantic units.

        Each chunk is a complete semantic unit when possible. Oversized units
        are split at statement boundaries. Falls back to text-based chunking
        if tree-sitter can't parse.

        Args:
            text: Source code as string.
            file_path: Path to source file (for metadata).
            metadata: File-level metadata from extract_metadata().

        Returns:
            List of TextChunk objects.
        """
        if file_path is None:
            file_path = Path("unknown")

        # Clear metadata for this chunking run
        self._chunk_metadata = {}

        if self._parser is None or self._grammar is None:
            logger.warning(
                "No tree-sitter grammar for %s, falling back to text chunking",
                self.language,
            )
            return self._fallback_chunk(text, file_path)

        try:
            source_bytes = text.encode("utf-8")
            tree = self._parser.parse(source_bytes)
            root = tree.root_node

            # Check for severe parse errors
            if root.has_error:
                logger.warning(
                    "Parse errors in %s, attempting partial extraction",
                    file_path,
                )

            # Extract semantic units from the AST
            units = self._extract_semantic_units(root, source_bytes)

            if not units:
                logger.warning(
                    "No semantic units found in %s, falling back to text chunking",
                    file_path,
                )
                return self._fallback_chunk(text, file_path)

            # Convert units to TextChunks
            chunks = self._units_to_chunks(units, file_path, text)
            return chunks

        except Exception as e:
            logger.warning(
                "AST chunking failed for %s: %s, falling back to text chunking",
                file_path,
                e,
            )
            return self._fallback_chunk(text, file_path)

    def get_chunk_metadata(self, chunk: TextChunk) -> dict[str, Any]:
        """Return code-specific metadata for a chunk.

        Called by the indexer after chunking to get metadata for the vector payload.

        Args:
            chunk: A TextChunk produced by this chunker.

        Returns:
            Dict with code metadata fields.
        """
        return self._chunk_metadata.get(
            chunk.chunk_id,
            {"language": self.language},
        )

    def _extract_semantic_units(self, root: Node, source_bytes: bytes) -> list[SemanticUnit]:
        """Extract semantic units from the AST root node.

        Uses tree-sitter queries when available, falls back to tree traversal.

        Args:
            root: Root AST node.
            source_bytes: Raw source code bytes.

        Returns:
            List of SemanticUnit objects.
        """
        units: list[SemanticUnit] = []
        processed_ranges: set[tuple[int, int]] = set()

        # Walk top-level children
        for child in root.children:
            child_units = self._process_node(child, source_bytes, parent_class=None)
            for unit in child_units:
                range_key = (unit.start_byte, unit.end_byte)
                if range_key not in processed_ranges:
                    units.append(unit)
                    processed_ranges.add(range_key)

        return units

    def _process_node(
        self,
        node: Node,
        source_bytes: bytes,
        parent_class: str | None = None,
    ) -> list[SemanticUnit]:
        """Process a single AST node into semantic units.

        Args:
            node: AST node to process.
            source_bytes: Raw source code bytes.
            parent_class: Parent class name (for methods).

        Returns:
            List of SemanticUnit objects.
        """
        units: list[SemanticUnit] = []
        node_type = node.type

        # Python: decorated definitions wrap the actual definition
        if node_type == "decorated_definition":
            # Extract decorators
            decorators: list[str] = []
            inner_def = None
            for child in node.children:
                if child.type == "decorator":
                    dec_text = source_bytes[child.start_byte : child.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    decorators.append(dec_text)
                elif child.type in (
                    "function_definition",
                    "class_definition",
                ):
                    inner_def = child

            if inner_def is not None:
                # Process the inner definition, but use the decorated_definition's
                # byte range so we capture decorators
                inner_units = self._process_node(inner_def, source_bytes, parent_class)
                for u in inner_units:
                    # Replace with the full decorated source text
                    full_text = source_bytes[node.start_byte : node.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    decorated_unit = SemanticUnit(
                        node_type=u.node_type,
                        name=u.name,
                        source_text=full_text,
                        start_line=node.start_point[0],
                        end_line=node.end_point[0],
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                        parent_class=u.parent_class,
                        decorators=decorators,
                        has_error=node.has_error,
                        children=u.children,
                    )
                    units.append(decorated_unit)
            return units

        # Function definitions (Python + Rust)
        if node_type in (
            "function_definition",
            "function_item",
        ):
            name = self._get_name(node, source_bytes)
            source_text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            unit = SemanticUnit(
                node_type=node_type,
                name=name,
                source_text=source_text,
                start_line=node.start_point[0],
                end_line=node.end_point[0],
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                parent_class=parent_class,
                has_error=node.has_error,
            )
            units.append(unit)
            return units

        # Class definitions (Python)
        if node_type == "class_definition":
            class_name = self._get_name(node, source_bytes)
            # Extract methods as children
            method_units: list[SemanticUnit] = []
            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.children:
                    child_units = self._process_node(child, source_bytes, parent_class=class_name)
                    method_units.extend(child_units)

            # Each method becomes its own chunk with class context
            # The class definition itself (without methods) isn't extracted
            # separately — the methods carry the class context
            if method_units:
                units.extend(method_units)
            else:
                # Class with no methods — chunk the whole thing
                source_text = source_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                unit = SemanticUnit(
                    node_type=node_type,
                    name=class_name,
                    source_text=source_text,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    parent_class=parent_class,
                    has_error=node.has_error,
                )
                units.append(unit)
            return units

        # Rust struct/impl/enum/trait
        if node_type in ("struct_item", "enum_item", "trait_item"):
            name = self._get_name(node, source_bytes)
            source_text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            unit = SemanticUnit(
                node_type=node_type,
                name=name,
                source_text=source_text,
                start_line=node.start_point[0],
                end_line=node.end_point[0],
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                parent_class=parent_class,
                has_error=node.has_error,
            )
            units.append(unit)
            return units

        if node_type == "impl_item":
            # Extract impl block methods
            impl_name = None
            for child in node.children:
                if child.type == "type_identifier":
                    impl_name = source_bytes[child.start_byte : child.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    break

            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.children:
                    child_units = self._process_node(child, source_bytes, parent_class=impl_name)
                    units.extend(child_units)
            else:
                # Impl with no body — chunk the whole thing
                source_text = source_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                unit = SemanticUnit(
                    node_type=node_type,
                    name=impl_name,
                    source_text=source_text,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    parent_class=parent_class,
                    has_error=node.has_error,
                )
                units.append(unit)
            return units

        # Import statements — group consecutive imports
        if node_type in (
            "import_statement",
            "import_from_statement",
            "use_declaration",
        ):
            source_text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            unit = SemanticUnit(
                node_type="import",
                name=None,
                source_text=source_text,
                start_line=node.start_point[0],
                end_line=node.end_point[0],
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                parent_class=None,
                has_error=node.has_error,
            )
            units.append(unit)
            return units

        # Skip comments, expression statements (module-level), etc.
        # They'll be captured if they're part of a larger construct

        return units

    def _get_name(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract the name from a definition node.

        Args:
            node: AST node (function_definition, class_definition, etc.).
            source_bytes: Raw source bytes.

        Returns:
            Name string, or None if not found.
        """
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return source_bytes[name_node.start_byte : name_node.end_byte].decode(
                "utf-8", errors="replace"
            )
        return None

    def _units_to_chunks(
        self,
        units: list[SemanticUnit],
        file_path: Path,
        full_text: str,
    ) -> list[TextChunk]:
        """Convert semantic units to TextChunk objects.

        Prepends class context for methods and handles oversized units.

        Args:
            units: Semantic units extracted from AST.
            file_path: Source file path.
            full_text: Full source text.

        Returns:
            List of TextChunk objects.
        """
        chunks: list[TextChunk] = []

        # Group consecutive imports into a single chunk
        import_lines: list[str] = []
        import_start_byte = 0
        import_end_byte = 0

        non_import_units: list[SemanticUnit] = []
        for unit in units:
            if unit.node_type == "import":
                if not import_lines:
                    import_start_byte = unit.start_byte
                import_lines.append(unit.source_text)
                import_end_byte = unit.end_byte
            else:
                non_import_units.append(unit)

        # Create import chunk if any
        if import_lines:
            import_text = "\n".join(import_lines)
            chunk_id = str(uuid.uuid4())
            import_chunk = TextChunk(
                chunk_id=chunk_id,
                file_path=file_path,
                chunk_index=len(chunks),
                content=import_text,
                start_char=import_start_byte,
                end_char=import_end_byte,
                token_count=max(1, len(import_text.split())),
                created_at=datetime.now(timezone.utc),
            )
            chunks.append(import_chunk)
            self._chunk_metadata[chunk_id] = {
                "language": self.language,
                "function_name": None,
                "class_name": None,
                "start_line": None,
                "end_line": None,
                "node_type": "import",
                "has_decorators": False,
            }

        # Process non-import units
        for unit in non_import_units:
            # Prepend class context for methods
            content = unit.source_text
            if unit.parent_class:
                content = f"# Class: {unit.parent_class}\n{content}"

            # Check if oversized
            if len(content) > self.max_chunk_size:
                sub_chunks = self._split_oversized_unit(unit, content, file_path, len(chunks))
                chunks.extend(sub_chunks)
            else:
                chunk_id = str(uuid.uuid4())
                chunk = TextChunk(
                    chunk_id=chunk_id,
                    file_path=file_path,
                    chunk_index=len(chunks),
                    content=content,
                    start_char=unit.start_byte,
                    end_char=unit.end_byte,
                    token_count=max(1, len(content.split())),
                    created_at=datetime.now(timezone.utc),
                )
                chunks.append(chunk)
                self._chunk_metadata[chunk_id] = {
                    "language": self.language,
                    "function_name": unit.name
                    if unit.node_type in ("function_definition", "function_item")
                    else None,
                    "class_name": unit.parent_class,
                    "start_line": unit.start_line + 1,  # Convert to 1-based
                    "end_line": unit.end_line + 1,
                    "node_type": unit.node_type,
                    "has_decorators": len(unit.decorators) > 0,
                }

        # Re-index chunk_index to be sequential
        for i, chunk in enumerate(chunks):
            if chunk.chunk_index != i:
                # Create a new TextChunk with correct index
                new_chunk = TextChunk(
                    chunk_id=chunk.chunk_id,
                    file_path=chunk.file_path,
                    chunk_index=i,
                    content=chunk.content,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    token_count=chunk.token_count,
                    created_at=chunk.created_at,
                )
                chunks[i] = new_chunk

        return chunks

    def _split_oversized_unit(
        self,
        unit: SemanticUnit,
        content: str,
        file_path: Path,
        start_index: int,
    ) -> list[TextChunk]:
        """Split an oversized semantic unit at statement boundaries.

        Args:
            unit: The oversized semantic unit.
            content: The content text (possibly with class context prepended).
            file_path: Source file path.
            start_index: Starting chunk index.

        Returns:
            List of TextChunk objects for the split unit.
        """
        chunks: list[TextChunk] = []
        lines = content.split("\n")

        current_lines: list[str] = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            if current_size + line_size > self.max_chunk_size and current_lines:
                # Emit current chunk
                chunk_content = "\n".join(current_lines)
                chunk_id = str(uuid.uuid4())
                chunk = TextChunk(
                    chunk_id=chunk_id,
                    file_path=file_path,
                    chunk_index=start_index + len(chunks),
                    content=chunk_content,
                    start_char=unit.start_byte,
                    end_char=unit.end_byte,
                    token_count=max(1, len(chunk_content.split())),
                    created_at=datetime.now(timezone.utc),
                )
                chunks.append(chunk)
                self._chunk_metadata[chunk_id] = {
                    "language": self.language,
                    "function_name": unit.name
                    if unit.node_type in ("function_definition", "function_item")
                    else None,
                    "class_name": unit.parent_class,
                    "start_line": unit.start_line + 1,
                    "end_line": unit.end_line + 1,
                    "node_type": unit.node_type,
                    "has_decorators": len(unit.decorators) > 0,
                }
                current_lines = []
                current_size = 0

            current_lines.append(line)
            current_size += line_size

        # Emit remaining lines
        if current_lines:
            chunk_content = "\n".join(current_lines)
            chunk_id = str(uuid.uuid4())
            chunk = TextChunk(
                chunk_id=chunk_id,
                file_path=file_path,
                chunk_index=start_index + len(chunks),
                content=chunk_content,
                start_char=unit.start_byte,
                end_char=unit.end_byte,
                token_count=max(1, len(chunk_content.split())),
                created_at=datetime.now(timezone.utc),
            )
            chunks.append(chunk)
            self._chunk_metadata[chunk_id] = {
                "language": self.language,
                "function_name": unit.name
                if unit.node_type in ("function_definition", "function_item")
                else None,
                "class_name": unit.parent_class,
                "start_line": unit.start_line + 1,
                "end_line": unit.end_line + 1,
                "node_type": unit.node_type,
                "has_decorators": len(unit.decorators) > 0,
            }

        return chunks

    def _fallback_chunk(self, text: str, file_path: Path) -> list[TextChunk]:
        """Fallback to simple text-based chunking.

        Used when tree-sitter parsing fails or no grammar is available.

        Args:
            text: Source code text.
            file_path: Source file path.

        Returns:
            List of TextChunk objects.
        """
        logger.info("Using text-based fallback chunking for %s", file_path)
        chunks: list[TextChunk] = []
        chunk_size = self.max_chunk_size
        overlap = min(200, chunk_size // 4)

        start = 0
        index = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            content = text[start:end]

            chunk_id = str(uuid.uuid4())
            chunk = TextChunk(
                chunk_id=chunk_id,
                file_path=file_path,
                chunk_index=index,
                content=content,
                start_char=start,
                end_char=end,
                token_count=max(1, len(content.split())),
                created_at=datetime.now(timezone.utc),
            )
            chunks.append(chunk)
            self._chunk_metadata[chunk_id] = {
                "language": self.language,
                "function_name": None,
                "class_name": None,
                "start_line": None,
                "end_line": None,
                "node_type": "text_fallback",
                "has_decorators": False,
            }

            start += chunk_size - overlap
            index += 1

        return chunks
