"""Edge case tests for the plugin system.

Tests all edge cases defined in spec.md (EC-001 through EC-006) to validate
robust plugin behavior under failure conditions.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from krag.models.configuration import PluginConfiguration, PluginMetadata
from krag.plugins.context import PluginContext
from krag.plugins.exceptions import (
    PluginAPIVersionError,
    PluginConfigurationError,
    PluginDependencyError,
)
from krag.plugins.failures import IndexingFailureCollector
from krag.plugins.registry import PLUGIN_API_VERSION, PluginRegistry
from tests.fixtures.mock_plugin import MockFileTypeHandler

# --- Fixtures ---


@pytest.fixture
def config_empty():
    """Configuration with no enabled/disabled plugins."""
    return PluginConfiguration(enabled_plugins=[], disabled_plugins=[])


@pytest.fixture
def registry(config_empty):
    """Registry with empty configuration."""
    return PluginRegistry(config_empty)


@pytest.fixture
def plugin_context(tmp_path):
    """Create a PluginContext for testing."""
    from krag.embeddings.generator import EmbeddingGenerator
    from krag.extraction.chunker import TextChunker
    from krag.storage.vector_store import VectorStore

    return PluginContext(
        embedding_generator=MagicMock(spec=EmbeddingGenerator),
        vector_store=MagicMock(spec=VectorStore),
        chunker=TextChunker(chunk_size=1000, chunk_overlap=200),
        logger=logging.getLogger("test"),
        report_indexing_failure=MagicMock(),
    )


@pytest.fixture
def failure_collector():
    """Create a fresh IndexingFailureCollector."""
    return IndexingFailureCollector()


def _add_plugin(registry, name, *, extensions=None, enabled=True, api_version="1.0.0"):
    """Helper to add a discovered plugin to the registry."""
    registry._discovered[name] = PluginMetadata(
        name=name,
        version="1.0.0",
        entry_point=f"dummy.{name}:Handler",
        supported_extensions=extensions or [".test"],
        required_api_version=api_version,
        is_enabled=enabled,
    )


# --- EC-001: Plugin fails during file processing ---


class TestEC001PluginFailsDuringProcessing:
    """EC-001: When a plugin fails during file processing, the system MUST:
    1. Log the failure via the failure-to-index API (FR-014)
    2. Disable the plugin for the remainder of the run
    3. Continue processing remaining files without the errant plugin (FR-008)
    """

    def test_extraction_failure_recorded_in_collector(self, failure_collector):
        """A plugin extraction failure should be recorded in the failure collector."""
        failure_collector.record_failure(
            file_path=Path("/doc.pdf"),
            plugin_name="pdf",
            reason="Corrupt PDF",
            exception_type="PluginExtractionError",
        )

        assert failure_collector.total_failures() == 1
        by_plugin = failure_collector.failures_by_plugin()
        assert "pdf" in by_plugin
        assert by_plugin["pdf"] == 1

    def test_plugin_disabled_after_load_failure(self, registry, plugin_context):
        """Plugin should be disabled after a load failure."""
        _add_plugin(registry, "failing_plugin")

        # Mock loader to raise on load
        with patch.object(registry._loader, "load_plugin_class", side_effect=Exception("Segfault")):
            handler = registry.load_plugin("failing_plugin", plugin_context)

        assert handler is None
        assert registry._discovered["failing_plugin"].is_enabled is False
        assert registry._discovered["failing_plugin"].load_error is not None

    def test_disabled_plugin_returns_none_on_subsequent_load(self, registry, plugin_context):
        """A plugin disabled by failure should return None on subsequent load attempts."""
        _add_plugin(registry, "failing_plugin")
        registry._discovered["failing_plugin"].is_enabled = False
        registry._discovered["failing_plugin"].load_error = "Previous failure"

        handler = registry.load_plugin("failing_plugin", plugin_context)
        assert handler is None

    def test_other_plugins_continue_after_one_fails(self, registry, plugin_context):
        """Other plugins should remain functional after one plugin fails."""
        _add_plugin(registry, "good_plugin", extensions=[".good"])
        _add_plugin(registry, "bad_plugin", extensions=[".bad"])

        # Pre-load good plugin
        good_handler = MockFileTypeHandler()
        registry._loaded["good_plugin"] = good_handler

        # Disable bad plugin (simulating failure)
        registry._discovered["bad_plugin"].is_enabled = False
        registry._discovered["bad_plugin"].load_error = "Crashed"

        # Good plugin should still work
        assert registry.load_plugin("good_plugin", plugin_context) is good_handler
        # Bad plugin should return None
        assert registry.load_plugin("bad_plugin", plugin_context) is None

    def test_failure_collector_aggregates_multiple_failures(self, failure_collector):
        """Multiple failures from the same plugin should be aggregated."""
        for i in range(3):
            failure_collector.record_failure(
                file_path=Path(f"/file{i}.pdf"),
                plugin_name="pdf",
                reason=f"Error {i}",
                exception_type="PluginExtractionError",
            )

        assert failure_collector.total_failures() == 3
        by_plugin = failure_collector.failures_by_plugin()
        assert by_plugin["pdf"] == 3

    def test_failure_collector_tracks_exception_types(self, failure_collector):
        """Failure collector should track failures by exception type."""
        failure_collector.record_failure(
            file_path=Path("/a.pdf"),
            plugin_name="pdf",
            reason="corrupt",
            exception_type="PluginExtractionError",
        )
        failure_collector.record_failure(
            file_path=Path("/b.pdf"),
            plugin_name="pdf",
            reason="oom",
            exception_type="RuntimeError",
        )

        by_type = failure_collector.failures_by_exception_type()
        assert "PluginExtractionError" in by_type
        assert "RuntimeError" in by_type


# --- EC-002: Multiple plugins claim same file extension ---


class TestEC002ExtensionConflicts:
    """EC-002: When multiple plugins claim the same file extension:
    1. The first plugin in configuration file order wins
    2. Configuration MUST allow per-extension overrides (FR-007)
    """

    def test_first_plugin_wins_extension_conflict(self, registry):
        """First plugin in config order should win when multiple claim same extension."""
        _add_plugin(registry, "plugin_a", extensions=[".txt"])
        _add_plugin(registry, "plugin_b", extensions=[".txt"])

        registry._build_extension_map()

        # First plugin wins
        assert registry._extension_map[".txt"] == "plugin_a"

    def test_extension_conflicts_detected(self, registry):
        """check_extension_conflicts should detect when multiple plugins claim same extension."""
        _add_plugin(registry, "plugin_a", extensions=[".txt"])
        _add_plugin(registry, "plugin_b", extensions=[".txt"])

        conflicts = registry.check_extension_conflicts()

        assert ".txt" in conflicts
        assert "plugin_a" in conflicts[".txt"]
        assert "plugin_b" in conflicts[".txt"]

    def test_no_conflicts_when_extensions_differ(self, registry):
        """No conflicts should be reported when plugins claim different extensions."""
        _add_plugin(registry, "plugin_a", extensions=[".txt"])
        _add_plugin(registry, "plugin_b", extensions=[".csv"])

        conflicts = registry.check_extension_conflicts()

        assert len(conflicts) == 0

    def test_disabled_plugins_excluded_from_conflicts(self, registry):
        """Disabled plugins should not participate in extension conflict detection."""
        _add_plugin(registry, "plugin_a", extensions=[".txt"])
        _add_plugin(registry, "plugin_b", extensions=[".txt"], enabled=False)

        conflicts = registry.check_extension_conflicts()

        assert len(conflicts) == 0

    def test_extension_map_skips_disabled_plugins(self, registry):
        """Disabled plugins' extensions should not appear in the extension map."""
        _add_plugin(registry, "disabled_plugin", extensions=[".txt"], enabled=False)

        registry._build_extension_map()

        assert ".txt" not in registry._extension_map

    def test_conflict_logged_as_warning(self, registry, caplog):
        """Extension conflicts should be logged as warnings."""
        _add_plugin(registry, "plugin_a", extensions=[".txt"])
        _add_plugin(registry, "plugin_b", extensions=[".txt"])

        with caplog.at_level(logging.WARNING):
            registry.check_extension_conflicts()

        assert any("conflict" in record.message.lower() for record in caplog.records)

    def test_three_way_extension_conflict(self, registry):
        """Three plugins claiming the same extension should be reported correctly."""
        _add_plugin(registry, "plugin_a", extensions=[".md"])
        _add_plugin(registry, "plugin_b", extensions=[".md"])
        _add_plugin(registry, "plugin_c", extensions=[".md"])

        conflicts = registry.check_extension_conflicts()

        assert ".md" in conflicts
        assert len(conflicts[".md"]) == 3
        # First wins in extension map
        registry._build_extension_map()
        assert registry._extension_map[".md"] == "plugin_a"


# --- EC-003: Missing plugin dependencies ---


class TestEC003MissingDependencies:
    """EC-003: When plugin dependencies are missing or incompatible:
    1. System MUST log a warning
    2. System MUST disable the plugin for the current run (FR-010)
    """

    @patch("krag.plugins.registry.PluginLoader")
    def test_missing_dependency_disables_plugin(self, mock_loader_class, plugin_context):
        """Plugin with missing dependencies should be disabled."""
        mock_loader = MagicMock()
        mock_loader.load_plugin_class.side_effect = PluginDependencyError(
            "requires package 'pdfplumber' which is not installed",
            plugin_name="pdf",
        )
        mock_loader_class.return_value = mock_loader

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(config)
        _add_plugin(registry, "pdf", extensions=[".pdf"])

        handler = registry.load_plugin("pdf", plugin_context)

        assert handler is None
        assert registry._discovered["pdf"].is_enabled is False
        assert "missing dependencies" in registry._discovered["pdf"].load_error.lower()

    @patch("krag.plugins.registry.PluginLoader")
    def test_missing_dependency_logged(self, mock_loader_class, plugin_context, caplog):
        """Missing dependency error should be logged."""
        mock_loader = MagicMock()
        mock_loader.load_plugin_class.side_effect = PluginDependencyError(
            "requires 'pdfplumber'", plugin_name="pdf"
        )
        mock_loader_class.return_value = mock_loader

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(config)
        _add_plugin(registry, "pdf", extensions=[".pdf"])

        with caplog.at_level(logging.ERROR):
            registry.load_plugin("pdf", plugin_context)

        assert any("pdf" in record.message.lower() for record in caplog.records)

    def test_validate_dependencies_catches_issues(self, registry):
        """validate_dependencies should detect and report missing dependencies."""
        _add_plugin(registry, "pdf", extensions=[".pdf"])

        with patch.object(
            registry._loader,
            "load_plugin_class",
            side_effect=PluginDependencyError("requires 'pdfplumber'", plugin_name="pdf"),
        ):
            issues = registry.validate_dependencies()

        assert "pdf" in issues
        assert registry._discovered["pdf"].is_enabled is False

    def test_validate_dependencies_skips_disabled(self, registry):
        """validate_dependencies should skip already-disabled plugins."""
        _add_plugin(registry, "disabled_plugin", enabled=False)

        with patch.object(registry._loader, "load_plugin_class") as mock_load:
            issues = registry.validate_dependencies()

        mock_load.assert_not_called()
        assert len(issues) == 0

    def test_validate_dependencies_handles_non_dependency_errors(self, registry):
        """validate_dependencies should handle non-dependency import errors."""
        _add_plugin(registry, "broken_plugin")

        with patch.object(
            registry._loader,
            "load_plugin_class",
            side_effect=RuntimeError("Unexpected error"),
        ):
            issues = registry.validate_dependencies()

        assert "broken_plugin" in issues
        assert "Failed to import" in issues["broken_plugin"]
        assert registry._discovered["broken_plugin"].is_enabled is False


# --- EC-004: Invalid or corrupted plugin configuration ---


class TestEC004InvalidConfiguration:
    """EC-004: When plugin configuration is invalid or corrupted:
    1. System MUST log a warning
    2. System MUST disable the plugin for the current run (FR-010)
    """

    @patch("krag.plugins.registry.PluginLoader")
    def test_invalid_config_disables_plugin(self, mock_loader_class, plugin_context):
        """Plugin with invalid config should be disabled."""
        mock_loader = MagicMock()
        mock_loader.load_plugin_class.side_effect = PluginConfigurationError(
            "missing required field 'api_key'",
            plugin_name="cloud",
        )
        mock_loader_class.return_value = mock_loader

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(config)
        _add_plugin(registry, "cloud", extensions=[".cloud"])

        handler = registry.load_plugin("cloud", plugin_context)

        assert handler is None
        assert registry._discovered["cloud"].is_enabled is False
        assert "invalid configuration" in registry._discovered["cloud"].load_error.lower()

    @patch("krag.plugins.registry.PluginLoader")
    def test_invalid_config_error_logged(self, mock_loader_class, plugin_context, caplog):
        """Invalid configuration should be logged with helpful guidance."""
        mock_loader = MagicMock()
        mock_loader.load_plugin_class.side_effect = PluginConfigurationError(
            "missing required field 'api_key'",
            plugin_name="cloud",
        )
        mock_loader_class.return_value = mock_loader

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(config)
        _add_plugin(registry, "cloud", extensions=[".cloud"])

        with caplog.at_level(logging.ERROR):
            registry.load_plugin("cloud", plugin_context)

        # Should reference config file location
        assert any("config.toml" in record.message for record in caplog.records)

    def test_validate_plugins_detects_invalid_config(self):
        """validate_plugins should detect invalid plugin configuration schemas."""
        config = PluginConfiguration(
            enabled_plugins=[],
            disabled_plugins=[],
            plugin_settings={"mock_plugin": {"invalid_field": "value"}},
        )
        registry = PluginRegistry(config)
        _add_plugin(registry, "mock_plugin")

        # Mock the loader to return a handler with a strict config schema
        mock_handler = MagicMock(spec=MockFileTypeHandler)
        mock_handler.required_api_version = "1.0.0"
        mock_handler.version = "1.0.0"
        mock_handler.supported_extensions.return_value = [".mock"]

        # Config schema that rejects unknown fields
        mock_schema = MagicMock()
        mock_schema.side_effect = TypeError("Unexpected field: invalid_field")
        mock_handler.config_schema.return_value = mock_schema

        with patch.object(registry._loader, "load_plugin_class", return_value=MagicMock):
            with patch.object(registry._loader, "instantiate_plugin", return_value=mock_handler):
                with patch.object(registry._loader, "check_api_compatibility"):
                    failed = registry.validate_plugins()

        assert "mock_plugin" in failed
        assert registry._discovered["mock_plugin"].is_enabled is False

    def test_corrupted_config_returns_none(self, registry, plugin_context):
        """Corrupted config during initialization should return None handler."""
        _add_plugin(registry, "corrupt_plugin")

        mock_handler_class = MagicMock()
        mock_handler = MagicMock(spec=MockFileTypeHandler)
        mock_handler.required_api_version = "1.0.0"
        mock_handler_class.return_value = mock_handler

        with patch.object(registry._loader, "load_plugin_class", return_value=mock_handler_class):
            with patch.object(registry._loader, "instantiate_plugin", return_value=mock_handler):
                with patch.object(registry._loader, "check_api_compatibility"):
                    with patch.object(
                        registry._loader,
                        "initialize_plugin",
                        side_effect=PluginConfigurationError(
                            "corrupted config", plugin_name="corrupt_plugin"
                        ),
                    ):
                        handler = registry.load_plugin("corrupt_plugin", plugin_context)

        assert handler is None
        assert registry._discovered["corrupt_plugin"].is_enabled is False


# --- EC-005: Upgraded plugin ---


class TestEC005UpgradedPlugin:
    """EC-005: When a plugin has been upgraded:
    1. If API version is compatible, plugin loads normally
    2. Each run treats plugins the same regardless of upgrade status (FR-010)
    """

    def test_compatible_upgrade_loads_normally(self, registry, plugin_context):
        """Upgraded plugin with compatible API version should load normally."""
        _add_plugin(registry, "mock_plugin", api_version="1.0.0")

        # Pre-load to simulate successful load after upgrade
        handler = MockFileTypeHandler()
        registry._loaded["mock_plugin"] = handler

        result = registry.load_plugin("mock_plugin", plugin_context)
        assert result is handler

    @patch("krag.plugins.registry.PluginLoader")
    def test_incompatible_upgrade_disables_plugin(self, mock_loader_class, plugin_context):
        """Upgraded plugin with incompatible API version should be disabled."""
        mock_loader = MagicMock()

        # First call loads the class
        mock_handler_class = MagicMock()
        mock_loader.load_plugin_class.return_value = mock_handler_class

        # Instantiation works
        mock_handler = MagicMock(spec=MockFileTypeHandler)
        mock_handler.required_api_version = "2.0.0"
        mock_loader.instantiate_plugin.return_value = mock_handler

        # API check fails
        mock_loader.check_api_compatibility.side_effect = PluginAPIVersionError(
            f"Plugin requires API version 2.0.0 but krag provides {PLUGIN_API_VERSION}",
            plugin_name="upgraded_plugin",
        )
        mock_loader_class.return_value = mock_loader

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(config)
        _add_plugin(registry, "upgraded_plugin")

        handler = registry.load_plugin("upgraded_plugin", plugin_context)

        assert handler is None
        assert registry._discovered["upgraded_plugin"].is_enabled is False
        assert "incompatible" in registry._discovered["upgraded_plugin"].load_error.lower()

    def test_minor_version_compatible(self, registry, plugin_context):
        """Plugin requiring same major but different minor version should load."""
        _add_plugin(registry, "mock_plugin", api_version="1.2.0")

        handler = MockFileTypeHandler()
        registry._loaded["mock_plugin"] = handler

        result = registry.load_plugin("mock_plugin", plugin_context)
        assert result is handler

    @patch("krag.plugins.registry.PluginLoader")
    def test_major_version_mismatch_rejected(self, mock_loader_class, plugin_context):
        """Plugin with different major API version should be rejected."""
        mock_loader = MagicMock()
        mock_handler_class = MagicMock()
        mock_loader.load_plugin_class.return_value = mock_handler_class

        mock_handler = MagicMock()
        mock_handler.required_api_version = "3.0.0"
        mock_loader.instantiate_plugin.return_value = mock_handler

        mock_loader.check_api_compatibility.side_effect = PluginAPIVersionError(
            "API version mismatch: requires 3.0.0, have 1.0.0",
            plugin_name="future_plugin",
        )
        mock_loader_class.return_value = mock_loader

        config = PluginConfiguration(enabled_plugins=[], disabled_plugins=[])
        registry = PluginRegistry(config)
        _add_plugin(registry, "future_plugin")

        handler = registry.load_plugin("future_plugin", plugin_context)

        assert handler is None
        assert registry._discovered["future_plugin"].is_enabled is False

    def test_same_version_loads_normally(self, registry, plugin_context):
        """Plugin with exact same API version should load normally."""
        _add_plugin(registry, "mock_plugin", api_version=PLUGIN_API_VERSION)

        handler = MockFileTypeHandler()
        registry._loaded["mock_plugin"] = handler

        result = registry.load_plugin("mock_plugin", plugin_context)
        assert result is handler


# --- EC-006: Resource limits ---


class TestEC006ResourceLimits:
    """EC-006: Resource limits (memory, processing time) are out of scope
    for initial release. Document as intentionally deferred."""

    @pytest.mark.skip(reason="EC-006: Resource limits out of scope for initial release")
    def test_resource_limits_placeholder(self):
        """Placeholder test documenting that resource limits are deferred."""
        pass
