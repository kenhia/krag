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


class ServiceNotReadyError(KragError):
    """Raised when a service method is called before start()."""

    pass


class IndexingInProgressError(KragError):
    """Raised when a query is attempted while indexing is active."""

    pass


class ResourceNotConfiguredError(KragError):
    """Raised when a required resource (LLM, vector store, etc.) is not configured."""

    def __init__(self, resource: str, message: str):
        """Initialize with resource name and message.

        Args:
            resource: Name of the missing resource (e.g., "LLM", "vector_store")
            message: Human-readable error message
        """
        self.resource = resource
        super().__init__(f"{resource}: {message}")
