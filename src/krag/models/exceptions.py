"""Custom exception classes for krag."""


class KragError(Exception):
    """Base exception for all krag errors."""

    pass


class ConfigurationError(KragError):
    """Configuration-related errors."""

    pass


class StorageError(KragError):
    """Storage operation errors."""

    pass


class ModelLoadError(KragError):
    """Error loading embedding or LLM models."""

    pass


class IndexingError(KragError):
    """Error during indexing operation."""

    pass


class QueryError(KragError):
    """Error during query operation."""

    pass


class FileProcessingError(KragError):
    """Error processing individual file."""

    def __init__(self, file_path: str, message: str):
        """Initialize with file path and message.

        Args:
            file_path: Path to file that caused error
            message: Error message
        """
        self.file_path = file_path
        super().__init__(f"{file_path}: {message}")
