"""Unit tests for domain exception classes and hierarchy (US8).

T008: Validates that:
- All new domain exceptions inherit from KragError
- Each exception class can be instantiated with a message
- LexiconValidationError and EvalLoadError are part of KragError hierarchy
- isinstance checks work correctly for exception dispatch
"""

from __future__ import annotations


class TestExceptionHierarchy:
    """All domain exceptions must inherit from KragError."""

    def test_service_not_ready_error_inherits_krag_error(self) -> None:
        from krag.models.exceptions import KragError, ServiceNotReadyError

        exc = ServiceNotReadyError("Service not started — call start() first")
        assert isinstance(exc, KragError)
        assert isinstance(exc, ServiceNotReadyError)
        assert str(exc) == "Service not started — call start() first"

    def test_indexing_in_progress_error_inherits_krag_error(self) -> None:
        from krag.models.exceptions import IndexingInProgressError, KragError

        exc = IndexingInProgressError("Indexing is in progress")
        assert isinstance(exc, KragError)
        assert isinstance(exc, IndexingInProgressError)
        assert "Indexing is in progress" in str(exc)

    def test_resource_not_configured_error_inherits_krag_error(self) -> None:
        from krag.models.exceptions import KragError, ResourceNotConfiguredError

        exc = ResourceNotConfiguredError("LLM", "No LLM model configured")
        assert isinstance(exc, KragError)
        assert isinstance(exc, ResourceNotConfiguredError)
        assert exc.resource == "LLM"
        assert "No LLM model configured" in str(exc)

    def test_resource_not_configured_error_str_format(self) -> None:
        from krag.models.exceptions import ResourceNotConfiguredError

        exc = ResourceNotConfiguredError("vector_store", "Vector store not initialized")
        assert "vector_store" in str(exc)
        assert "Vector store not initialized" in str(exc)

    def test_lexicon_validation_error_inherits_krag_error(self) -> None:
        from krag.lexicon.lexicon_store import LexiconValidationError
        from krag.models.exceptions import KragError

        exc = LexiconValidationError("bad lexicon")
        assert isinstance(exc, KragError)

    def test_eval_load_error_inherits_krag_error(self) -> None:
        from krag.evaluation.loader import EvalLoadError
        from krag.models.exceptions import KragError

        exc = EvalLoadError("bad eval file")
        assert isinstance(exc, KragError)


class TestExceptionDispatch:
    """Exception handler should dispatch correctly via isinstance."""

    def test_service_not_ready_is_not_indexing_in_progress(self) -> None:
        from krag.models.exceptions import IndexingInProgressError, ServiceNotReadyError

        exc = ServiceNotReadyError("not started")
        assert not isinstance(exc, IndexingInProgressError)

    def test_indexing_in_progress_is_not_service_not_ready(self) -> None:
        from krag.models.exceptions import IndexingInProgressError, ServiceNotReadyError

        exc = IndexingInProgressError("indexing active")
        assert not isinstance(exc, ServiceNotReadyError)

    def test_resource_not_configured_is_not_service_not_ready(self) -> None:
        from krag.models.exceptions import ResourceNotConfiguredError, ServiceNotReadyError

        exc = ResourceNotConfiguredError("LLM", "no LLM")
        assert not isinstance(exc, ServiceNotReadyError)

    def test_all_domain_exceptions_catchable_as_krag_error(self) -> None:
        from krag.models.exceptions import (
            IndexingInProgressError,
            KragError,
            ResourceNotConfiguredError,
            ServiceNotReadyError,
        )

        exceptions = [
            ServiceNotReadyError("not started"),
            IndexingInProgressError("indexing"),
            ResourceNotConfiguredError("LLM", "missing"),
        ]
        for exc in exceptions:
            assert isinstance(exc, KragError), f"{type(exc).__name__} is not a KragError"

    def test_existing_exceptions_still_catchable(self) -> None:
        """Existing exception types must not be broken by the new additions."""
        from krag.models.exceptions import (
            ConfigurationError,
            FileProcessingError,
            IndexingError,
            KragError,
            ModelLoadError,
            QueryError,
            StorageError,
        )

        for cls in [
            ConfigurationError,
            StorageError,
            ModelLoadError,
            IndexingError,
            QueryError,
        ]:
            assert issubclass(cls, KragError)

        fp_exc = FileProcessingError("/foo.py", "bad file")
        assert isinstance(fp_exc, KragError)
