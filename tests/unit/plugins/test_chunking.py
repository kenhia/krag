"""Unit tests for ChunkingStrategyResolver and CustomChunkerAdapter.

Tests strategy resolution, enum mapping, custom chunker validation,
fallback behavior, config-based overrides, and chunk_text() adapter.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from krag.extraction.chunker import TextChunker
from krag.models.text_chunk import TextChunk
from krag.plugins.chunking import ChunkingStrategyResolver, CustomChunkerAdapter
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


# ───────────────────────────────────────────────────────────
# US4: CustomChunkerAdapter Tests (T142)
# ───────────────────────────────────────────────────────────


class ChunkTextOnlyChunker:
    """Test chunker that only implements chunk_text(), not chunk()."""

    def chunk_text(self, text: str) -> list[str]:
        """Split text on double newlines."""
        return [p.strip() for p in text.split("\n\n") if p.strip()]


class ChunkTextDictChunker:
    """Test chunker whose chunk_text() returns list[dict]."""

    def chunk_text(self, text: str) -> list[dict]:
        return [{"content": line} for line in text.split("\n") if line.strip()]


class ChunkTextWithSizeChunker:
    """Test chunker with chunk_text() and size attributes."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> list[str]:
        return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]


class TestCustomChunkerAdapter:
    """Test CustomChunkerAdapter wrapping chunk_text()-only chunkers."""

    def test_adapter_wraps_chunk_text_str_output(self):
        """Adapter should convert chunk_text() str results to TextChunk objects."""
        raw_chunker = ChunkTextOnlyChunker()
        adapter = CustomChunkerAdapter(raw_chunker)

        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = adapter.chunk(text, file_path=Path("/tmp/test.txt"))

        assert len(chunks) == 3
        assert all(isinstance(c, TextChunk) for c in chunks)
        assert chunks[0].content == "Paragraph one."
        assert chunks[1].content == "Paragraph two."
        assert chunks[2].content == "Paragraph three."

    def test_adapter_wraps_chunk_text_dict_output(self):
        """Adapter should handle chunk_text() returning list[dict]."""
        raw_chunker = ChunkTextDictChunker()
        adapter = CustomChunkerAdapter(raw_chunker)

        text = "line one\nline two\nline three"
        chunks = adapter.chunk(text, file_path=Path("/tmp/test.txt"))

        assert len(chunks) == 3
        assert chunks[0].content == "line one"
        assert chunks[1].content == "line two"
        assert chunks[2].content == "line three"

    def test_adapter_sets_chunk_metadata(self):
        """Adapter should set file_path, chunk_index, and char offsets."""
        raw_chunker = ChunkTextOnlyChunker()
        adapter = CustomChunkerAdapter(raw_chunker)

        text = "First chunk.\n\nSecond chunk."
        path = Path("/data/file.log")
        chunks = adapter.chunk(text, file_path=path)

        assert chunks[0].file_path == path
        assert chunks[0].chunk_index == 0
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len("First chunk.")

        assert chunks[1].chunk_index == 1
        assert chunks[1].start_char == len("First chunk.")

    def test_adapter_skips_empty_chunks(self):
        """Adapter should skip empty strings from chunk_text()."""

        class EmptyChunker:
            def chunk_text(self, text: str) -> list[str]:
                return ["content", "", "  ", "more content"]

        adapter = CustomChunkerAdapter(EmptyChunker())
        chunks = adapter.chunk("test", file_path=Path("test.txt"))

        # Empty and whitespace-only chunks are skipped
        assert len(chunks) == 2
        assert chunks[0].content == "content"
        assert chunks[1].content == "more content"

    def test_adapter_forwards_chunk_size(self):
        """Adapter should forward chunk_size/chunk_overlap from wrapped chunker."""
        raw_chunker = ChunkTextWithSizeChunker(chunk_size=777, chunk_overlap=42)
        adapter = CustomChunkerAdapter(raw_chunker)

        assert adapter.chunk_size == 777
        assert adapter.chunk_overlap == 42

    def test_adapter_uses_defaults_when_no_size(self):
        """Adapter uses default chunk_size/overlap when wrapped chunker lacks them."""
        raw_chunker = ChunkTextOnlyChunker()
        adapter = CustomChunkerAdapter(raw_chunker)

        assert adapter.chunk_size == 1000
        assert adapter.chunk_overlap == 200

    def test_adapter_default_file_path(self):
        """Adapter should use Path('unknown') when file_path not provided."""
        raw_chunker = ChunkTextOnlyChunker()
        adapter = CustomChunkerAdapter(raw_chunker)

        chunks = adapter.chunk("Hello.\n\nWorld.")
        assert chunks[0].file_path == Path("unknown")

    def test_adapter_handles_non_str_non_dict_output(self):
        """Adapter should convert non-str/non-dict items via str()."""

        class WeirdChunker:
            def chunk_text(self, text: str) -> list:
                return [42, 3.14]

        adapter = CustomChunkerAdapter(WeirdChunker())
        chunks = adapter.chunk("test", file_path=Path("test.txt"))

        assert len(chunks) == 2
        assert chunks[0].content == "42"
        assert chunks[1].content == "3.14"

    def test_adapter_is_text_chunker_subclass(self):
        """CustomChunkerAdapter should be a TextChunker subclass."""
        raw_chunker = ChunkTextOnlyChunker()
        adapter = CustomChunkerAdapter(raw_chunker)

        assert isinstance(adapter, TextChunker)


# ───────────────────────────────────────────────────────────
# US4: Config-Based Chunking Override Tests (T142)
# ───────────────────────────────────────────────────────────


class TestChunkingOverrides:
    """Test configuration-based chunking strategy overrides."""

    def test_override_uses_config_strategy(self, caplog):
        """Config override should replace plugin's preferred strategy."""
        caplog.set_level(logging.INFO)

        resolver = ChunkingStrategyResolver(
            chunking_overrides={"logs": "default"},
        )

        # Plugin wants custom, but config says default
        custom = MockChunker()
        chunker = resolver.resolve(custom, plugin_name="logs")

        # Should use default, not the custom chunker
        assert isinstance(chunker, TextChunker)
        assert chunker is not custom
        assert any("overridden by config" in r.message for r in caplog.records)

    def test_override_not_matching_plugin_ignored(self):
        """Override for different plugin should not affect this one."""
        resolver = ChunkingStrategyResolver(
            chunking_overrides={"pdf": "default"},
        )

        custom = MockChunker()
        chunker = resolver.resolve(custom, plugin_name="logs")

        # No override for "logs", so custom chunker should be used
        assert chunker is custom

    def test_override_invalid_strategy_uses_plugin_preference(self, caplog):
        """Invalid override value should fall back to plugin's preferred strategy."""
        resolver = ChunkingStrategyResolver(
            chunking_overrides={"logs": "nonexistent_strategy"},
        )

        custom = MockChunker()
        chunker = resolver.resolve(custom, plugin_name="logs")

        # Invalid override, so use plugin's preference (the custom chunker)
        assert chunker is custom
        assert any("Invalid chunking override" in r.message for r in caplog.records)

    def test_override_semantic_strategy(self, caplog):
        """Config override to 'semantic' should use SEMANTIC (falls back to default)."""
        resolver = ChunkingStrategyResolver(
            chunking_overrides={"logs": "semantic"},
        )

        custom = MockChunker()
        chunker = resolver.resolve(custom, plugin_name="logs")

        # SEMANTIC not implemented, falls back to DEFAULT
        assert isinstance(chunker, TextChunker)

    def test_override_without_plugin_name(self):
        """Override should be ignored when plugin_name is None."""
        resolver = ChunkingStrategyResolver(
            chunking_overrides={"logs": "default"},
        )

        custom = MockChunker()
        chunker = resolver.resolve(custom, plugin_name=None)

        # No plugin_name, so override not applied
        assert chunker is custom

    def test_override_empty_dict(self):
        """Empty overrides dict should not affect behavior."""
        resolver = ChunkingStrategyResolver(chunking_overrides={})

        custom = MockChunker()
        chunker = resolver.resolve(custom, plugin_name="logs")
        assert chunker is custom

    def test_resolver_stores_overrides(self):
        """Resolver should store chunking overrides."""
        resolver = ChunkingStrategyResolver(
            chunking_overrides={"logs": "default", "csv": "semantic"},
        )

        assert resolver._chunking_overrides == {"logs": "default", "csv": "semantic"}


# ───────────────────────────────────────────────────────────
# US4: _parse_strategy_name Tests (T143)
# ───────────────────────────────────────────────────────────


class TestParseStrategyName:
    """Test _parse_strategy_name() string-to-enum conversion."""

    def test_parse_default(self):
        assert ChunkingStrategyResolver._parse_strategy_name("default") == ChunkingStrategy.DEFAULT

    def test_parse_semantic(self):
        assert (
            ChunkingStrategyResolver._parse_strategy_name("semantic") == ChunkingStrategy.SEMANTIC
        )

    def test_parse_code_aware(self):
        assert (
            ChunkingStrategyResolver._parse_strategy_name("code_aware")
            == ChunkingStrategy.CODE_AWARE
        )

    def test_parse_custom(self):
        assert ChunkingStrategyResolver._parse_strategy_name("custom") == ChunkingStrategy.CUSTOM

    def test_parse_case_insensitive(self):
        assert ChunkingStrategyResolver._parse_strategy_name("DEFAULT") == ChunkingStrategy.DEFAULT
        assert (
            ChunkingStrategyResolver._parse_strategy_name("Semantic") == ChunkingStrategy.SEMANTIC
        )

    def test_parse_strips_whitespace(self):
        assert (
            ChunkingStrategyResolver._parse_strategy_name("  default  ") == ChunkingStrategy.DEFAULT
        )

    def test_parse_invalid_returns_none(self):
        assert ChunkingStrategyResolver._parse_strategy_name("nonexistent") is None
        assert ChunkingStrategyResolver._parse_strategy_name("") is None


# ───────────────────────────────────────────────────────────
# US4: _has_chunk_text Tests (T143)
# ───────────────────────────────────────────────────────────


class TestHasChunkText:
    """Test _has_chunk_text() detection."""

    def test_detects_chunk_text_method(self):
        obj = ChunkTextOnlyChunker()
        assert ChunkingStrategyResolver._has_chunk_text(obj) is True

    def test_rejects_missing_chunk_text(self):
        assert ChunkingStrategyResolver._has_chunk_text(MockChunker()) is False

    def test_rejects_non_callable_chunk_text(self):
        class BadChunker:
            chunk_text = "not a method"

        assert ChunkingStrategyResolver._has_chunk_text(BadChunker()) is False

    def test_rejects_primitives(self):
        assert ChunkingStrategyResolver._has_chunk_text(None) is False
        assert ChunkingStrategyResolver._has_chunk_text("string") is False
        assert ChunkingStrategyResolver._has_chunk_text(42) is False


# ───────────────────────────────────────────────────────────
# US4: validate_chunker_interface Tests (T143)
# ───────────────────────────────────────────────────────────


class TestValidateChunkerInterface:
    """Test validate_chunker_interface() compliance checking."""

    def test_valid_with_chunk_method(self):
        errors = ChunkingStrategyResolver.validate_chunker_interface(MockChunker())
        assert errors == []

    def test_valid_with_chunk_text_method(self):
        errors = ChunkingStrategyResolver.validate_chunker_interface(ChunkTextOnlyChunker())
        assert errors == []

    def test_valid_with_both_methods(self):
        class BothChunker:
            def chunk(self, text, file_path=None):
                return []

            def chunk_text(self, text):
                return []

        errors = ChunkingStrategyResolver.validate_chunker_interface(BothChunker())
        assert errors == []

    def test_invalid_no_methods(self):
        errors = ChunkingStrategyResolver.validate_chunker_interface(InvalidChunker())
        assert len(errors) == 1
        assert "chunk" in errors[0].lower()

    def test_invalid_non_callable(self):
        class BadChunker:
            chunk = "not a method"

        errors = ChunkingStrategyResolver.validate_chunker_interface(BadChunker())
        assert len(errors) == 1

    def test_valid_text_chunker(self):
        chunker = TextChunker(chunk_size=500, chunk_overlap=100)
        errors = ChunkingStrategyResolver.validate_chunker_interface(chunker)
        assert errors == []


# ───────────────────────────────────────────────────────────
# US4: Resolve w/ chunk_text()-only Chunker Tests (T142, T144)
# ───────────────────────────────────────────────────────────


class TestResolveChunkTextAdapter:
    """Test resolve() wrapping chunk_text()-only chunkers in adapter."""

    def test_resolve_wraps_chunk_text_chunker(self, caplog):
        """resolve() should wrap chunk_text()-only chunker in adapter."""
        caplog.set_level(logging.INFO)

        resolver = ChunkingStrategyResolver()
        raw = ChunkTextOnlyChunker()

        result = resolver.resolve(raw, plugin_name="custom")

        assert isinstance(result, CustomChunkerAdapter)
        assert any("chunk_text()-only chunker" in r.message for r in caplog.records)

    def test_adapter_result_is_text_chunker(self):
        """Resolved adapter should be a TextChunker subclass."""
        resolver = ChunkingStrategyResolver()
        raw = ChunkTextOnlyChunker()

        result = resolver.resolve(raw, plugin_name="custom")

        assert isinstance(result, TextChunker)

    def test_adapter_produces_valid_chunks(self):
        """Resolved adapter should produce valid TextChunk objects."""
        resolver = ChunkingStrategyResolver()
        raw = ChunkTextOnlyChunker()

        chunker = resolver.resolve(raw, plugin_name="custom")
        chunks = chunker.chunk("Hello\n\nWorld", file_path=Path("/tmp/test.txt"))

        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[1].content == "World"

    def test_chunk_method_preferred_over_chunk_text(self):
        """Object with both chunk() and chunk_text() should use chunk() directly."""

        class BothChunker:
            def chunk(self, text, file_path=None, file_type=None):
                return [
                    TextChunk(
                        file_path=file_path or Path("unknown"),
                        chunk_index=0,
                        content=text,
                        start_char=0,
                        end_char=len(text),
                        token_count=len(text.split()),
                    )
                ]

            def chunk_text(self, text):
                return text.split("\n")

        resolver = ChunkingStrategyResolver()
        both = BothChunker()
        result = resolver.resolve(both, plugin_name="test")

        # Should return the original (has chunk()), not wrap in adapter
        assert result is both

    def test_fallback_when_neither_chunk_nor_chunk_text(self, caplog):
        """Object with neither method should fall back to default."""
        resolver = ChunkingStrategyResolver()
        invalid = InvalidChunker()

        result = resolver.resolve(invalid, plugin_name="test")

        assert isinstance(result, TextChunker)
        assert any("invalid chunking strategy" in r.message.lower() for r in caplog.records)
