"""Text chunking with overlap and structure preservation."""

import logging
from pathlib import Path
from uuid import uuid4

from krag.models.text_chunk import TextChunk

logger = logging.getLogger(__name__)


class TextChunker:
    """Chunks text into overlapping segments with structure awareness.

    Uses character-based splitting with sentence boundary awareness.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ):
        """Initialize text chunker.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            separators: Custom separators for splitting (optional)

        Raises:
            ValueError: If chunk_size <= chunk_overlap
        """
        if chunk_size <= chunk_overlap:
            raise ValueError("chunk_size must be greater than chunk_overlap")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.custom_separators = separators
        logger.debug(
            f"TextChunker initialized with chunk_size={chunk_size}, "
            f"overlap={chunk_overlap}, "
            f"custom_separators={separators is not None}"
        )

    def chunk(
        self,
        text: str,
        file_path: Path | None = None,
        file_type: str | None = None,
    ) -> list[TextChunk]:
        """Chunk text into overlapping segments.

        Args:
            text: Text content to chunk
            file_path: Source file path (optional, for metadata)
            file_type: File type (for structure awareness, optional)

        Returns:
            List of TextChunk objects
        """
        # Handle empty or whitespace-only text
        if not text or not text.strip():
            return []

        # Use defaults if not provided
        if file_path is None:
            file_path = Path("unknown.txt")
        if file_type is None:
            file_type = "text"

        # Use custom separators if provided, otherwise determine by file type
        if self.custom_separators is not None:
            separators = self.custom_separators
        elif file_type in {"python", "javascript", "java", "cpp", "c", "go", "rust"}:
            # Code: respect line structure
            separators = ["\n\n", "\n", " "]
        elif file_type == "markdown":
            # Markdown: respect headers and paragraphs
            separators = ["\n## ", "\n# ", "\n\n", "\n", " "]
        else:
            # General text: sentence and paragraph boundaries
            separators = ["\n\n", ". ", "! ", "? ", "\n", " "]

        chunks = self._split_text_recursive(text, separators)

        # Create TextChunk objects with metadata
        text_chunks = []
        for i, chunk_content in enumerate(chunks):
            # Find actual position in original text
            start_char = text.find(chunk_content)
            if start_char == -1:
                # Fallback: estimate position
                start_char = sum(len(c) for c in chunks[:i])

            end_char = start_char + len(chunk_content)

            # Calculate token count (simple approximation)
            token_count = len(chunk_content.split())

            text_chunk = TextChunk(
                chunk_id=str(uuid4()),
                file_path=file_path,
                chunk_index=i,
                start_char=start_char,
                end_char=end_char,
                content=chunk_content,
                token_count=token_count,
            )
            text_chunks.append(text_chunk)

        logger.debug(f"Created {len(text_chunks)} chunks from {file_path}")
        return text_chunks

    def chunk_code(
        self,
        code: str,
        language: str = "python",
        file_path: Path | None = None,
    ) -> list[TextChunk]:
        """Chunk code with language-aware structure preservation.

        Args:
            code: Code content to chunk
            language: Programming language
            file_path: Source file path (optional)

        Returns:
            List of TextChunk objects
        """
        # Map language to file_type
        file_type_map = {
            "python": "python",
            "javascript": "javascript",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "go": "go",
            "rust": "rust",
        }
        file_type = file_type_map.get(language, "code")

        return self.chunk(code, file_path=file_path, file_type=file_type)

    def _split_text_recursive(
        self,
        text: str,
        separators: list[str],
    ) -> list[str]:
        """Recursively split text using multiple separators.

        Args:
            text: Text to split
            separators: List of separators to try (in order)

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # If text is short enough, return as single chunk
        if len(text) <= self.chunk_size:
            return [text]

        # Try each separator
        for separator in separators:
            if separator in text:
                splits = text.split(separator)
                chunks = []
                current_chunk = ""

                for split in splits:
                    # Add separator back (except for first split)
                    if current_chunk:
                        test_chunk = current_chunk + separator + split
                    else:
                        test_chunk = split

                    if len(test_chunk) <= self.chunk_size:
                        current_chunk = test_chunk
                    else:
                        # Current chunk is full, save it
                        if current_chunk:
                            chunks.append(current_chunk)

                        # If split itself is too large, recurse with next separators
                        if len(split) > self.chunk_size:
                            if len(separators) > 1:
                                sub_chunks = self._split_text_recursive(
                                    split,
                                    separators[1:],
                                )
                                chunks.extend(sub_chunks)
                            else:
                                # Force split by chunk_size
                                chunks.extend(self._force_split(split))
                        else:
                            current_chunk = split

                # Add final chunk
                if current_chunk:
                    chunks.append(current_chunk)

                # Add overlap between chunks
                return self._add_overlap(chunks)

        # No separator found, force split
        return self._force_split(text)

    def _force_split(self, text: str) -> list[str]:
        """Force split text by chunk_size when no good separator found.

        Args:
            text: Text to split

        Returns:
            List of chunks
        """
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i : i + self.chunk_size]
            if chunk:
                chunks.append(chunk)
        return chunks

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        """Add overlap between consecutive chunks.

        Args:
            chunks: List of chunks without overlap

        Returns:
            List of chunks with overlap added
        """
        if len(chunks) <= 1 or self.chunk_overlap == 0:
            return chunks

        overlapped = []
        for i in range(len(chunks)):
            if i == 0:
                # First chunk: no prefix overlap
                overlapped.append(chunks[i])
            else:
                # Add overlap from previous chunk
                prev_chunk = chunks[i - 1]
                overlap = prev_chunk[-self.chunk_overlap :]
                overlapped.append(overlap + chunks[i])

        return overlapped
