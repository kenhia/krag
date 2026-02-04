"""Text extraction from various file formats."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extracts text content from files with encoding detection.

    Handles various text formats and encoding detection.
    """

    def __init__(
        self,
        max_file_size_mb: int = 100,
        normalize_whitespace: bool = True,
        preserve_formatting: bool = False,
    ):
        """Initialize text extractor.

        Args:
            max_file_size_mb: Maximum file size to process in MB
            normalize_whitespace: Whether to normalize whitespace (default: True)
            preserve_formatting: Whether to preserve exact formatting (default: False)
        """
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.normalize_whitespace = normalize_whitespace
        self.preserve_formatting = preserve_formatting
        logger.debug(
            f"TextExtractor initialized with max_file_size={max_file_size_mb}MB, "
            f"normalize_whitespace={normalize_whitespace}, "
            f"preserve_formatting={preserve_formatting}"
        )

    def extract(self, file_path: Path) -> str:
        """Extract text content from file.

        Args:
            file_path: Path to file

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is too large or binary
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size_bytes:
            raise ValueError(
                f"File too large: {file_size} bytes (exceeds max file size: {self.max_file_size_bytes} bytes)"
            )

        # Handle empty files
        if file_size == 0:
            return ""

        # Detect encoding and read
        encoding = self.detect_encoding(file_path)

        try:
            with open(file_path, encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode file as text: {e}") from e

        # Apply whitespace normalization if requested and not preserve_formatting
        if self.normalize_whitespace and not self.preserve_formatting:
            # Normalize whitespace for non-code files
            if file_path.suffix not in {".py", ".js", ".java", ".cpp", ".c", ".go", ".rs"}:
                # Strip excess whitespace but preserve structure
                lines = content.split("\n")
                lines = [line.rstrip() for line in lines]  # Remove trailing whitespace
                content = "\n".join(lines)
                # Remove excessive blank lines (more than 2 consecutive)
                while "\n\n\n\n" in content:
                    content = content.replace("\n\n\n\n", "\n\n\n")

        return content

    def detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding.

        Args:
            file_path: Path to file

        Returns:
            Detected encoding name
        """
        # Try UTF-8 first (most common)
        try:
            with open(file_path, encoding="utf-8") as f:
                f.read()
            return "utf-8"
        except UnicodeDecodeError:
            pass

        # Try Latin-1 (ISO-8859-1) as fallback
        try:
            with open(file_path, encoding="latin-1") as f:
                f.read()
            return "latin-1"
        except UnicodeDecodeError:
            pass

        # If all fail, default to UTF-8 with error handling
        return "utf-8"
