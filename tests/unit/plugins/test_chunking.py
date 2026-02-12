"""Unit tests for ChunkingStrategyResolver.

Tests strategy resolution, enum mapping, custom chunker validation, and fallback behavior.
"""

from unittest.mock import MagicMock

import pytest

from krag.extraction.chunker import TextChunker
from krag.plugins.chunking import ChunkingStrategyResolver
from krag.plugins.interfaces import ChunkingStrategy


@pytest.fixture
def resolver():
    """Create a ChunkingStrategyResolver with default settings."""
    return ChunkingStrategyResolver(default_chunk_size=1000, default_chunk_overlap=200)


@pytest.fixture
def custom_chunk_size_resolver():
    """Create a resolver with custom chunk size settings."""
    return ChunkingStrategyResolver(default_chunk_size=500, default_chunk_overlap=100)


class MockChunker:
    """Mock chunker for testing custom chunker validation."""

    def chunk(self, text: str, file_path=None):
        """Mock chunk method."""
        return []


class InvalidChunker:
    """Invalid chunker missing chunk method."""

    pass


class TestResolverInitialization:
    """Test ChunkingStrategyResolver initialization."""

    def test_resolver_initializes_with_defaults(self):
        """Resolver should initialize with provided chunk size and overlap."""
        resolver = ChunkingStrategyResolver(default_chunk_size=800, default_chunk_overlap=150)

        assert resolver._default_chunk_size == 800
        assert resolver._default_chunk_overlap == 150
        assert resolver._default_chunker is None

    def test_resolver_uses_default_parameters(self):
        """Resolver should use default parameters when not specified."""
        resolver = ChunkingStrategyResolver()

        assert resolver._default_chunk_size == 1000
        assert resolver._default_chunk_overlap == 200


class TestDefaultChunkerCreation:
    """Test default chunker creation and caching."""

    def test_get_default_chunker_creates_instance(self, resolver):
        """_get_default_chunker should create TextChunker with configured settings."""
        chunker = resolver._get_default_chunker()

        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 200

    def test_get_default_chunker_caches_instance(self, resolver):
        """_get_default_chunker should cache and reuse the same instance."""
        chunker1 = resolver._get_default_chunker()
        chunker2 = resolver._get_default_chunker()

        assert chunker1 is chunker2

    def test_get_default_chunker_respects_custom_settings(self, custom_chunk_size_resolver):
        """_get_default_chunker should use custom chunk size and overlap."""
        chunker = custom_chunk_size_resolver._get_default_chunker()

        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 100


class TestStrategyResolution:
    """Test strategy resolution to chunker instances."""

    def test_resolve_none_returns_default(self, resolver):
        """resolve should return default chunker for None strategy."""
        chunker = resolver.resolve(None, plugin_name="test_plugin")

        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 1000

    def test_resolve_none_without_plugin_name(self, resolver):
        """resolve should handle None plugin_name gracefully."""
        chunker = resolver.resolve(None)

        assert isinstance(chunker, TextChunker)

    def test_resolve_default_strategy_returns_default_chunker(self, resolver):
        """resolve should return default chunker for DEFAULT strategy."""
        chunker = resolver.resolve(ChunkingStrategy.DEFAULT, plugin_name="test_plugin")

        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 1000

    def test_resolve_semantic_strategy_falls_back_to_default(self, resolver, caplog):
        """resolve should fall back to default for SEMANTIC strategy (not implemented)."""
        chunker = resolver.resolve(ChunkingStrategy.SEMANTIC, plugin_name="test_plugin")

        assert isinstance(chunker, TextChunker)
        # Should log warning about fallback
        assert any(
            "SEMANTIC" in record.message and "not yet implemented" in record.message
            for record in caplog.records
        )

    def test_resolve_code_aware_strategy_falls_back_to_default(self, resolver, caplog):
        """resolve should fall back to default for CODE_AWARE strategy (not implemented)."""
        chunker = resolver.resolve(ChunkingStrategy.CODE_AWARE, plugin_name="test_plugin")

        assert isinstance(chunker, TextChunker)
        # Should log warning about fallback
        assert any(
            "CODE_AWARE" in record.message and "not yet implemented" in record.message
            for record in caplog.records
        )

    def test_resolve_custom_enum_without_chunker_falls_back(self, resolver, caplog):
        """resolve should fall back when CUSTOM enum provided without actual chunker."""
        chunker = resolver.resolve(ChunkingStrategy.CUSTOM, plugin_name="test_plugin")

        assert isinstance(chunker, TextChunker)
        # Should log warning about missing custom chunker
        assert any(
            "CUSTOM" in record.message and "did not provide" in record.message
            for record in caplog.records
        )

    def test_resolve_custom_chunker_returns_it(self, resolver, caplog):
        """resolve should return custom chunker if valid."""
        import logging

        caplog.set_level(logging.INFO)

        custom = MockChunker()

        chunker = resolver.resolve(custom, plugin_name="test_plugin")

        assert chunker is custom
        # Should log info about custom chunker
        assert any("provided custom chunker" in record.message for record in caplog.records)

    def test_resolve_invalid_chunker_falls_back_to_default(self, resolver, caplog):
        """resolve should fall back to default for invalid chunker objects."""
        invalid = InvalidChunker()

        chunker = resolver.resolve(invalid, plugin_name="test_plugin")

        assert isinstance(chunker, TextChunker)
        # Should log warning about invalid strategy
        assert any(
            "invalid chunking strategy" in record.message.lower() for record in caplog.records
        )

    def test_resolve_always_returns_chunker_never_none(self, resolver):
        """resolve should always return a chunker, never None."""
        # Test various invalid inputs
        result1 = resolver.resolve(None)
        result2 = resolver.resolve("invalid")
        result3 = resolver.resolve(123)
        result4 = resolver.resolve(InvalidChunker())

        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        assert result4 is not None


class TestEnumStrategyResolution:
    """Test ChunkingStrategy enum resolution."""

    def test_resolve_enum_strategy_default(self, resolver):
        """_resolve_enum_strategy should handle DEFAULT correctly."""
        chunker = resolver._resolve_enum_strategy(ChunkingStrategy.DEFAULT, "test")

        assert isinstance(chunker, TextChunker)

    def test_resolve_enum_strategy_semantic_logs_warning(self, resolver, caplog):
        """_resolve_enum_strategy should log warning for SEMANTIC."""
        resolver._resolve_enum_strategy(ChunkingStrategy.SEMANTIC, "test_plugin")

        assert any(
            "SEMANTIC" in record.message and "test_plugin" in record.message
            for record in caplog.records
        )

    def test_resolve_enum_strategy_code_aware_logs_warning(self, resolver, caplog):
        """_resolve_enum_strategy should log warning for CODE_AWARE."""
        resolver._resolve_enum_strategy(ChunkingStrategy.CODE_AWARE, "test_plugin")

        assert any(
            "CODE_AWARE" in record.message and "test_plugin" in record.message
            for record in caplog.records
        )

    def test_resolve_enum_strategy_custom_logs_warning(self, resolver, caplog):
        """_resolve_enum_strategy should log warning for CUSTOM without chunker."""
        resolver._resolve_enum_strategy(ChunkingStrategy.CUSTOM, "test_plugin")

        assert any("CUSTOM" in record.message for record in caplog.records)


class TestChunkerValidation:
    """Test custom chunker validation logic."""

    def test_is_valid_chunker_accepts_valid_chunker(self, resolver):
        """_is_valid_chunker should accept objects with callable chunk method."""
        valid = MockChunker()

        assert resolver._is_valid_chunker(valid) is True

    def test_is_valid_chunker_accepts_text_chunker(self, resolver):
        """_is_valid_chunker should accept TextChunker instances."""
        chunker = TextChunker(chunk_size=500, chunk_overlap=100)

        assert resolver._is_valid_chunker(chunker) is True

    def test_is_valid_chunker_accepts_mock_with_chunk(self, resolver):
        """_is_valid_chunker should accept MagicMock with chunk method."""
        mock = MagicMock()
        mock.chunk = MagicMock(return_value=[])

        assert resolver._is_valid_chunker(mock) is True

    def test_is_valid_chunker_rejects_missing_chunk_method(self, resolver):
        """_is_valid_chunker should reject objects without chunk method."""
        invalid = InvalidChunker()

        assert resolver._is_valid_chunker(invalid) is False

    def test_is_valid_chunker_rejects_non_callable_chunk(self, resolver):
        """_is_valid_chunker should reject objects with non-callable chunk attribute."""

        class BadChunker:
            chunk = "not a method"

        bad = BadChunker()

        assert resolver._is_valid_chunker(bad) is False

    def test_is_valid_chunker_rejects_primitives(self, resolver):
        """_is_valid_chunker should reject primitive types."""
        assert resolver._is_valid_chunker(None) is False
        assert resolver._is_valid_chunker("string") is False
        assert resolver._is_valid_chunker(123) is False
        assert resolver._is_valid_chunker([]) is False
        assert resolver._is_valid_chunker({}) is False


class TestLoggingBehavior:
    """Test logging behavior for different scenarios."""

    def test_resolve_logs_debug_for_none(self, resolver, caplog):
        """resolve should log debug message when strategy is None."""
        import logging

        caplog.set_level(logging.DEBUG)

        resolver.resolve(None, plugin_name="test_plugin")

        assert any(
            "test_plugin" in record.message and "None" in record.message
            for record in caplog.records
            if record.levelname == "DEBUG"
        )

    def test_resolve_logs_info_for_custom_chunker(self, resolver, caplog):
        """resolve should log info message when custom chunker is provided."""
        import logging

        caplog.set_level(logging.INFO)

        custom = MockChunker()
        resolver.resolve(custom, plugin_name="test_plugin")

        assert any(
            "test_plugin" in record.message and "custom chunker" in record.message
            for record in caplog.records
            if record.levelname == "INFO"
        )

    def test_resolve_logs_warning_for_invalid(self, resolver, caplog):
        """resolve should log warning for invalid strategies."""
        resolver.resolve("invalid", plugin_name="test_plugin")

        assert any(
            "invalid chunking strategy" in record.message.lower()
            for record in caplog.records
            if record.levelname == "WARNING"
        )

    def test_resolve_handles_missing_plugin_name_in_logs(self, resolver, caplog):
        """resolve should handle missing plugin_name in log messages."""
        import logging

        caplog.set_level(logging.DEBUG)

        resolver.resolve(None)

        # Should use generic "plugin" in logs
        assert any("plugin" in record.message for record in caplog.records)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_resolve_handles_unknown_enum_value(self, resolver, caplog):
        """resolve should handle unknown enum values gracefully."""

        # Create a mock enum value (simulating future additions)
        class FakeStrategy:
            pass

        fake = FakeStrategy()
        chunker = resolver.resolve(fake, plugin_name="test_plugin")

        # Should fall back to default
        assert isinstance(chunker, TextChunker)

    def test_resolve_caches_default_chunker_across_calls(self, resolver):
        """resolve should reuse cached default chunker for multiple calls."""
        chunker1 = resolver.resolve(None)
        chunker2 = resolver.resolve(ChunkingStrategy.DEFAULT)
        chunker3 = resolver.resolve(ChunkingStrategy.SEMANTIC)

        # All should return the same cached instance
        assert chunker1 is chunker2
        assert chunker2 is chunker3

    def test_resolver_thread_safety_not_guaranteed(self, resolver):
        """Note: Resolver is not thread-safe by design (single-threaded usage)."""
        # This is a documentation test - no threading in krag
        chunker = resolver.resolve(None)
        assert chunker is not None
