"""Unit tests for IndexingFailureCollector.

Tests failure recording, filtering, aggregation, and reporting.
"""

from pathlib import Path

import pytest

from krag.plugins.failures import IndexingFailureCollector, report_indexing_failure


@pytest.fixture
def collector():
    """Create a fresh IndexingFailureCollector."""
    return IndexingFailureCollector()


@pytest.fixture
def populated_collector():
    """Create a collector with some test failures."""
    collector = IndexingFailureCollector()

    # Add some core failures
    collector.record_failure(
        file_path=Path("/docs/core1.txt"),
        reason="File not found",
        plugin_name=None
    )
    collector.record_failure(
        file_path=Path("/docs/core2.txt"),
        reason="Permission denied",
        plugin_name=None,
        exception_type="PermissionError"
    )

    # Add some plugin failures
    collector.record_failure(
        file_path=Path("/docs/doc1.pdf"),
        reason="Corrupted PDF",
        plugin_name="pdf"
    )
    collector.record_failure(
        file_path=Path("/docs/doc2.pdf"),
        reason="Encrypted PDF",
        plugin_name="pdf"
    )
    collector.record_failure(
        file_path=Path("/docs/doc3.pdf"),
        reason="Invalid structure",
        plugin_name="pdf",
        exception_type="PDFStructureError"
    )

    collector.record_failure(
        file_path=Path("/docs/sheet.xlsx"),
        reason="Unsupported format version",
        plugin_name="excel"
    )

    return collector


class TestCollectorInitialization:
    """Test IndexingFailureCollector initialization."""

    def test_collector_initializes_empty(self, collector):
        """Collector should initialize with no failures."""
        assert collector.total_failures() == 0
        assert collector.get_failures() == []

    def test_collector_has_empty_failures_list(self, collector):
        """Collector should have empty failures list."""
        assert collector._failures == []


class TestFailureRecording:
    """Test recording failures."""

    def test_record_failure_adds_to_list(self, collector):
        """record_failure should add failure to internal list."""
        collector.record_failure(
            file_path=Path("/tmp/test.txt"),
            reason="Test failure"
        )

        assert collector.total_failures() == 1

    def test_record_failure_with_all_fields(self, collector):
        """record_failure should accept all optional fields."""
        collector.record_failure(
            file_path=Path("/tmp/test.pdf"),
            reason="Corrupted file",
            plugin_name="pdf",
            exception_type="CorruptionError"
        )

        failures = collector.get_failures()
        assert len(failures) == 1
        assert failures[0].file_path == Path("/tmp/test.pdf")
        assert failures[0].reason == "Corrupted file"
        assert failures[0].plugin_name == "pdf"
        assert failures[0].exception_type == "CorruptionError"

    def test_record_failure_minimal_fields(self, collector):
        """record_failure should work with minimal required fields."""
        collector.record_failure(
            file_path=Path("/tmp/test.txt"),
            reason="Error"
        )

        failures = collector.get_failures()
        assert len(failures) == 1
        assert failures[0].plugin_name is None
        assert failures[0].exception_type is None

    def test_record_multiple_failures(self, collector):
        """record_failure should accumulate multiple failures."""
        collector.record_failure(Path("/tmp/file1.txt"), "Error 1")
        collector.record_failure(Path("/tmp/file2.txt"), "Error 2")
        collector.record_failure(Path("/tmp/file3.txt"), "Error 3")

        assert collector.total_failures() == 3


class TestFailureRetrieval:
    """Test retrieving recorded failures."""

    def test_get_failures_returns_all_when_no_filter(self, populated_collector):
        """get_failures should return all failures when no filter provided."""
        failures = populated_collector.get_failures()

        assert len(failures) == 6

    def test_get_failures_returns_copy(self, collector):
        """get_failures should return a copy, not the internal list."""
        collector.record_failure(Path("/tmp/test.txt"), "Error")

        failures1 = collector.get_failures()
        failures2 = collector.get_failures()

        # Should be different objects
        assert failures1 is not failures2
        # But equal content
        assert failures1 == failures2

    def test_get_failures_filters_by_plugin(self, populated_collector):
        """get_failures should filter by plugin_name."""
        pdf_failures = populated_collector.get_failures(plugin_name="pdf")

        assert len(pdf_failures) == 3
        assert all(f.plugin_name == "pdf" for f in pdf_failures)

    def test_get_failures_filters_core_failures(self, populated_collector):
        """get_failures should filter core failures (plugin_name=None)."""
        core_failures = populated_collector.get_failures(plugin_name=None)

        # Should return all failures (including core, which have plugin_name=None)
        assert len(core_failures) == 6

    def test_get_failures_returns_empty_for_unknown_plugin(self, populated_collector):
        """get_failures should return empty list for unknown plugin."""
        failures = populated_collector.get_failures(plugin_name="nonexistent")

        assert failures == []


class TestFailureAggregation:
    """Test failure aggregation and counting."""

    def test_total_failures_returns_count(self, populated_collector):
        """total_failures should return total count of failures."""
        assert populated_collector.total_failures() == 6

    def test_total_failures_zero_when_empty(self, collector):
        """total_failures should return 0 when no failures recorded."""
        assert collector.total_failures() == 0

    def test_failures_by_plugin_groups_correctly(self, populated_collector):
        """failures_by_plugin should group failures by plugin name."""
        grouped = populated_collector.failures_by_plugin()

        assert grouped[None] == 2  # Core failures
        assert grouped["pdf"] == 3  # PDF plugin failures
        assert grouped["excel"] == 1  # Excel plugin failure

    def test_failures_by_plugin_empty_when_no_failures(self, collector):
        """failures_by_plugin should return empty dict when no failures."""
        grouped = collector.failures_by_plugin()

        assert grouped == {}

    def test_failures_by_plugin_counts_correctly(self):
        """failures_by_plugin should count multiple failures per plugin."""
        collector = IndexingFailureCollector()

        collector.record_failure(Path("/tmp/a.pdf"), "Error 1", plugin_name="pdf")
        collector.record_failure(Path("/tmp/b.pdf"), "Error 2", plugin_name="pdf")
        collector.record_failure(Path("/tmp/c.pdf"), "Error 3", plugin_name="pdf")

        grouped = collector.failures_by_plugin()

        assert grouped["pdf"] == 3


class TestCollectorClear:
    """Test clearing recorded failures."""

    def test_clear_removes_all_failures(self, populated_collector):
        """clear should remove all recorded failures."""
        assert populated_collector.total_failures() == 6

        populated_collector.clear()

        assert populated_collector.total_failures() == 0
        assert populated_collector.get_failures() == []

    def test_clear_on_empty_collector_safe(self, collector):
        """clear should be safe to call on empty collector."""
        collector.clear()

        assert collector.total_failures() == 0

    def test_can_record_after_clear(self, populated_collector):
        """Should be able to record new failures after clear."""
        populated_collector.clear()

        populated_collector.record_failure(Path("/tmp/new.txt"), "New error")

        assert populated_collector.total_failures() == 1


class TestFormatSummary:
    """Test human-readable summary formatting."""

    def test_format_summary_empty_collector(self, collector):
        """format_summary should handle empty collector."""
        summary = collector.format_summary()

        assert "No indexing failures" in summary

    def test_format_summary_includes_total(self, populated_collector):
        """format_summary should include total failure count."""
        summary = populated_collector.format_summary()

        assert "Total failures: 6" in summary

    def test_format_summary_groups_by_plugin(self, populated_collector):
        """format_summary should group failures by plugin."""
        summary = populated_collector.format_summary()

        assert "Core system: 2 failure(s)" in summary
        assert "Plugin 'pdf': 3 failure(s)" in summary
        assert "Plugin 'excel': 1 failure(s)" in summary

    def test_format_summary_includes_file_paths(self, populated_collector):
        """format_summary should list individual file paths."""
        summary = populated_collector.format_summary()

        assert "/docs/doc1.pdf" in summary
        assert "/docs/doc2.pdf" in summary
        assert "/docs/sheet.xlsx" in summary

    def test_format_summary_includes_reasons(self, populated_collector):
        """format_summary should include failure reasons."""
        summary = populated_collector.format_summary()

        assert "Corrupted PDF" in summary
        assert "Encrypted PDF" in summary
        assert "Unsupported format version" in summary

    def test_format_summary_core_failures_first(self, populated_collector):
        """format_summary should list core failures before plugin failures."""
        summary = populated_collector.format_summary()

        core_pos = summary.find("Core system")
        pdf_pos = summary.find("Plugin 'pdf'")

        assert core_pos < pdf_pos

    def test_format_summary_plugins_sorted(self):
        """format_summary should sort plugin names alphabetically."""
        collector = IndexingFailureCollector()
        collector.record_failure(Path("/tmp/z.pdf"), "Error", plugin_name="z_plugin")
        collector.record_failure(Path("/tmp/a.txt"), "Error", plugin_name="a_plugin")
        collector.record_failure(Path("/tmp/m.doc"), "Error", plugin_name="m_plugin")

        summary = collector.format_summary()

        a_pos = summary.find("Plugin 'a_plugin'")
        m_pos = summary.find("Plugin 'm_plugin'")
        z_pos = summary.find("Plugin 'z_plugin'")

        assert a_pos < m_pos < z_pos


class TestReportIndexingFailureAPI:
    """Test public report_indexing_failure API function."""

    def test_report_indexing_failure_accepts_all_params(self):
        """report_indexing_failure should accept all parameters."""
        # Should not raise exception
        report_indexing_failure(
            file_path=Path("/tmp/test.pdf"),
            reason="Test failure",
            plugin_name="test_plugin",
            exception_type="TestError"
        )

    def test_report_indexing_failure_minimal_params(self):
        """report_indexing_failure should work with minimal parameters."""
        # Should not raise exception
        report_indexing_failure(
            file_path=Path("/tmp/test.txt"),
            reason="Error"
        )

    def test_report_indexing_failure_logs_warning(self, caplog):
        """report_indexing_failure should log warning message."""
        report_indexing_failure(
            file_path=Path("/tmp/test.pdf"),
            reason="Test failure",
            plugin_name="pdf"
        )

        # Should log warning
        assert any(record.levelname == "WARNING" for record in caplog.records)
        assert any("Indexing failure reported" in record.message for record in caplog.records)

    def test_report_indexing_failure_includes_details_in_log(self, caplog):
        """report_indexing_failure should include file path and reason in log."""
        report_indexing_failure(
            file_path=Path("/docs/corrupted.pdf"),
            reason="File is corrupted",
            plugin_name="pdf"
        )

        log_messages = [record.message for record in caplog.records]
        combined_log = " ".join(log_messages)

        assert "corrupted.pdf" in combined_log
        assert "File is corrupted" in combined_log
        assert "pdf" in combined_log


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_duplicate_file_paths_allowed(self, collector):
        """Collector should allow recording same file multiple times."""
        path = Path("/tmp/test.txt")

        collector.record_failure(path, "Error 1")
        collector.record_failure(path, "Error 2")

        assert collector.total_failures() == 2

    def test_empty_reason_allowed(self, collector):
        """Collector should allow empty reason string."""
        collector.record_failure(Path("/tmp/test.txt"), "")

        assert collector.total_failures() == 1

    def test_very_long_reason(self, collector):
        """Collector should handle very long reason strings."""
        long_reason = "Error: " + "x" * 10000

        collector.record_failure(Path("/tmp/test.txt"), long_reason)

        failures = collector.get_failures()
        assert len(failures[0].reason) == len(long_reason)

    def test_special_characters_in_paths(self, collector):
        """Collector should handle special characters in file paths."""
        special_path = Path("/tmp/file with spaces & special!@#.txt")

        collector.record_failure(special_path, "Error")

        failures = collector.get_failures()
        assert failures[0].file_path == special_path

    def test_unicode_in_reason(self, collector):
        """Collector should handle unicode characters in reason."""
        unicode_reason = "File contains invalid ñ characters: 你好"

        collector.record_failure(Path("/tmp/test.txt"), unicode_reason)

        failures = collector.get_failures()
        assert failures[0].reason == unicode_reason
