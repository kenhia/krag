"""Unit tests for QueryResult enriched metadata and format_source_ref().

T082: QueryResult.format_source_ref() produces structured source references.
T084: Extended fields (language, function_name, class_name, start_line, end_line).
"""

from __future__ import annotations

from pathlib import Path

from krag.models.query_result import QueryResult


def _make_result(**overrides) -> QueryResult:
    """Create a QueryResult with sensible defaults, allowing overrides."""
    defaults = {
        "chunk_id": "abc-123",
        "score": 0.9,
        "rank": 1,
        "chunk_content": "def foo(): pass",
        "file_path": Path("/src/app/main.py"),
        "chunk_index": 0,
        "file_type": ".py",
    }
    defaults.update(overrides)
    return QueryResult(**defaults)


class TestQueryResultExtendedFields:
    """T084: Extended metadata fields on QueryResult."""

    def test_language_field_optional_default_none(self) -> None:
        """T084: language field defaults to None."""
        result = _make_result()
        assert result.language is None

    def test_language_field_accepts_string(self) -> None:
        """T084: language field can be set."""
        result = _make_result(language="python")
        assert result.language == "python"

    def test_function_name_field_optional(self) -> None:
        """T084: function_name defaults to None."""
        result = _make_result()
        assert result.function_name is None

    def test_function_name_accepts_string(self) -> None:
        """T084: function_name can be set."""
        result = _make_result(function_name="_deduplicate")
        assert result.function_name == "_deduplicate"

    def test_class_name_field_optional(self) -> None:
        """T084: class_name defaults to None."""
        result = _make_result()
        assert result.class_name is None

    def test_class_name_accepts_string(self) -> None:
        """T084: class_name can be set."""
        result = _make_result(class_name="Retriever")
        assert result.class_name == "Retriever"

    def test_start_line_field_optional(self) -> None:
        """T084: start_line defaults to None."""
        result = _make_result()
        assert result.start_line is None

    def test_start_line_accepts_int(self) -> None:
        """T084: start_line can be set."""
        result = _make_result(start_line=45)
        assert result.start_line == 45

    def test_end_line_field_optional(self) -> None:
        """T084: end_line defaults to None."""
        result = _make_result()
        assert result.end_line is None

    def test_end_line_accepts_int(self) -> None:
        """T084: end_line can be set."""
        result = _make_result(end_line=68)
        assert result.end_line == 68

    def test_extended_fields_in_serialized_output(self) -> None:
        """T084: Extended fields appear in serialized model."""
        result = _make_result(
            language="python",
            function_name="retrieve",
            class_name="Retriever",
            start_line=50,
            end_line=80,
        )
        data = result.model_dump()
        assert data["language"] == "python"
        assert data["function_name"] == "retrieve"
        assert data["class_name"] == "Retriever"
        assert data["start_line"] == 50
        assert data["end_line"] == 80

    def test_backward_compatible_without_extended_fields(self) -> None:
        """T084: Existing code creating QueryResult without extended fields still works."""
        result = QueryResult(
            chunk_id="test-id",
            score=0.85,
            rank=1,
            chunk_content="some content",
            file_path=Path("/test/file.md"),
            chunk_index=0,
            file_type=".md",
        )
        assert result.language is None
        assert result.function_name is None
        assert result.class_name is None
        assert result.start_line is None
        assert result.end_line is None


class TestFormatSourceRef:
    """T082/T085: QueryResult.format_source_ref() tests."""

    def test_full_method_reference(self) -> None:
        """T082: Class.method() at file.py:L45-L68."""
        result = _make_result(
            function_name="_deduplicate",
            class_name="Retriever",
            start_line=45,
            end_line=68,
        )
        ref = result.format_source_ref()
        assert "Retriever._deduplicate()" in ref
        assert "main.py" in ref
        assert "L45" in ref
        assert "L68" in ref

    def test_standalone_function_reference(self) -> None:
        """T082: function() at file.py:L10-L20 (no class)."""
        result = _make_result(
            function_name="process_data",
            class_name=None,
            start_line=10,
            end_line=20,
        )
        ref = result.format_source_ref()
        assert "process_data()" in ref
        assert "main.py" in ref
        assert "L10" in ref
        assert "L20" in ref
        # Should NOT include "None." prefix
        assert "None." not in ref

    def test_class_only_reference(self) -> None:
        """T082: Class at file.py:L1-L100 (no function)."""
        result = _make_result(
            function_name=None,
            class_name="MyClass",
            start_line=1,
            end_line=100,
        )
        ref = result.format_source_ref()
        assert "MyClass" in ref
        assert "main.py" in ref

    def test_file_only_reference(self) -> None:
        """T082: No function or class — just file path."""
        result = _make_result(
            function_name=None,
            class_name=None,
            start_line=None,
            end_line=None,
        )
        ref = result.format_source_ref()
        assert "main.py" in ref
        # Should not crash or include "None"
        assert "None" not in ref

    def test_with_line_numbers_only(self) -> None:
        """T082: Lines but no symbol names — file.py:L5-L15."""
        result = _make_result(
            function_name=None,
            class_name=None,
            start_line=5,
            end_line=15,
        )
        ref = result.format_source_ref()
        assert "main.py" in ref
        assert "L5" in ref
        assert "L15" in ref

    def test_start_line_only_no_end(self) -> None:
        """T082: start_line without end_line — file.py:L42."""
        result = _make_result(
            start_line=42,
            end_line=None,
        )
        ref = result.format_source_ref()
        assert "L42" in ref
        # Should not include a dash or end line
        assert "L42-" not in ref or "LNone" not in ref

    def test_format_source_ref_returns_string(self) -> None:
        """T085: format_source_ref always returns a string."""
        result = _make_result()
        ref = result.format_source_ref()
        assert isinstance(ref, str)
        assert len(ref) > 0
