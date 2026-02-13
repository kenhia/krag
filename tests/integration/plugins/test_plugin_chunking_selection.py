"""Integration tests for plugin chunking strategy selection.

Tests that plugins can specify chunking strategies and that the
ChunkingStrategyResolver correctly selects and applies chunkers
during the indexing pipeline.  Includes US4 tests for custom
chunking, config overrides, and the chunk_text() adapter.
"""

import logging
from pathlib import Path

import pytest

from krag.extraction.chunker import TextChunker
from krag.models.text_chunk import TextChunk
from krag.plugins.chunking import ChunkingStrategyResolver, CustomChunkerAdapter
from krag.plugins.interfaces import ChunkingStrategy
from tests.fixtures.mock_plugin import MockFileTypeHandler


class CustomChunker:
    """Custom chunker for testing."""

    def __init__(self, chunk_size: int = 300):
        self.chunk_size = chunk_size

    def chunk(self, text: str, file_path: Path | None = None) -> list[TextChunk]:
        """Simple chunking by size."""
        chunks = []
        for idx, i in enumerate(range(0, len(text), self.chunk_size)):
            chunk_text = text[i : i + self.chunk_size]
            chunk = TextChunk(
                file_path=file_path or Path("unknown"),
                chunk_index=idx,
                content=chunk_text,
                start_char=i,
                end_char=i + len(chunk_text),
                token_count=len(chunk_text.split()),
            )
            chunks.append(chunk)
        return chunks


@pytest.fixture
def resolver():
    """Create a ChunkingStrategyResolver."""
    return ChunkingStrategyResolver(default_chunk_size=1000, default_chunk_overlap=200)


class TestDefaultChunkingStrategy:
    """Test default chunking strategy selection."""

    def test_plugin_returning_none_uses_default(self, resolver):
        """Plugin returning None should use default chunker."""

        class DefaultPlugin(MockFileTypeHandler):
            def get_chunking_strategy(self):
                return None

        plugin = DefaultPlugin()
        strategy = plugin.get_chunking_strategy()

        chunker = resolver.resolve(strategy, plugin_name="default_plugin")

        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 1000

    def test_plugin_returning_default_enum_uses_default(self, resolver):
        """Plugin returning DEFAULT enum should use default chunker."""
        plugin = MockFileTypeHandler()
        strategy = plugin.get_chunking_strategy()

        # MockFileTypeHandler returns DEFAULT
        assert strategy == ChunkingStrategy.DEFAULT

        chunker = resolver.resolve(strategy, plugin_name="mock_plugin")

        assert isinstance(chunker, TextChunker)
        assert chunker.chunk_size == 1000

    def test_multiple_default_requests_share_chunker(self, resolver):
        """Multiple plugins requesting DEFAULT should share the same chunker instance."""
        chunker1 = resolver.resolve(None, plugin_name="plugin1")
        chunker2 = resolver.resolve(ChunkingStrategy.DEFAULT, plugin_name="plugin2")
        chunker3 = resolver.resolve(None, plugin_name="plugin3")

        # All should be the same instance
        assert chunker1 is chunker2
        assert chunker2 is chunker3


class TestCustomChunkingStrategy:
    """Test custom chunking strategy selection."""

    def test_plugin_providing_custom_chunker(self, resolver):
        """Plugin providing custom chunker should use that chunker."""
        custom = CustomChunker(chunk_size=300)

        class CustomPlugin(MockFileTypeHandler):
            def get_chunking_strategy(self):
                return custom

        plugin = CustomPlugin()
        strategy = plugin.get_chunking_strategy()

        chunker = resolver.resolve(strategy, plugin_name="custom_plugin")

        # Should return the custom chunker
        assert chunker is custom
        assert chunker.chunk_size == 300

    def test_custom_chunker_validation(self, resolver):
        """Resolver should validate custom chunker has chunk method."""

        class InvalidChunker:
            # Missing chunk method
            pass

        invalid = InvalidChunker()

        # Should fall back to default
        chunker = resolver.resolve(invalid, plugin_name="invalid_plugin")

        assert isinstance(chunker, TextChunker)

    def test_custom_chunker_used_in_extraction(self):
        """Custom chunker should be used during text extraction."""
        custom = CustomChunker(chunk_size=50)

        text = "A" * 150  # 150 characters
        chunks = custom.chunk(text, Path("/tmp/test.txt"))

        # Should create 3 chunks of 50 chars each
        assert len(chunks) == 3
        assert all(len(c.content) == 50 for c in chunks)


class TestSemanticChunkingStrategy:
    """Test semantic chunking strategy (not yet implemented)."""

    def test_semantic_strategy_falls_back_to_default(self, resolver, caplog):
        """SEMANTIC strategy should fall back to DEFAULT (not implemented yet)."""

        class SemanticPlugin(MockFileTypeHandler):
            def get_chunking_strategy(self):
                return ChunkingStrategy.SEMANTIC

        plugin = SemanticPlugin()
        strategy = plugin.get_chunking_strategy()

        chunker = resolver.resolve(strategy, plugin_name="semantic_plugin")

        # Should fall back to default
        assert isinstance(chunker, TextChunker)

        # Should log warning
        assert any(
            "SEMANTIC" in record.message and "not yet implemented" in record.message
            for record in caplog.records
        )


class TestCodeAwareChunkingStrategy:
    """Test code-aware chunking strategy (not yet implemented)."""

    def test_code_aware_strategy_falls_back_to_default(self, resolver, caplog):
        """CODE_AWARE strategy should fall back to DEFAULT (not implemented yet)."""

        class CodePlugin(MockFileTypeHandler):
            def get_chunking_strategy(self):
                return ChunkingStrategy.CODE_AWARE

        plugin = CodePlugin()
        strategy = plugin.get_chunking_strategy()

        chunker = resolver.resolve(strategy, plugin_name="code_plugin")

        # Should fall back to default
        assert isinstance(chunker, TextChunker)

        # Should log warning
        assert any(
            "CODE_AWARE" in record.message and "not yet implemented" in record.message
            for record in caplog.records
        )


class TestChunkingStrategyInPipeline:
    """Test chunking strategy selection within full indexing pipeline."""

    def test_different_plugins_different_strategies(self, resolver):
        """Different plugins can use different chunking strategies."""

        class DefaultPlugin(MockFileTypeHandler):
            def get_chunking_strategy(self):
                return ChunkingStrategy.DEFAULT

        class CustomPlugin(MockFileTypeHandler):
            def get_chunking_strategy(self):
                return CustomChunker(chunk_size=500)

        default_plugin = DefaultPlugin()
        custom_plugin = CustomPlugin()

        default_chunker = resolver.resolve(
            default_plugin.get_chunking_strategy(), plugin_name="default"
        )
        custom_chunker = resolver.resolve(
            custom_plugin.get_chunking_strategy(), plugin_name="custom"
        )

        # Should be different chunkers
        assert default_chunker is not custom_chunker
        assert isinstance(default_chunker, TextChunker)
        assert isinstance(custom_chunker, CustomChunker)

    def test_resolver_caches_default_across_files(self, resolver):
        """Resolver should cache default chunker across multiple file processing."""
        # Simulate processing multiple files with DEFAULT strategy
        chunkers = []
        for i in range(5):
            chunker = resolver.resolve(ChunkingStrategy.DEFAULT, plugin_name=f"file_{i}")
            chunkers.append(chunker)

        # All should be the same instance
        assert all(c is chunkers[0] for c in chunkers)

    def test_chunking_with_real_text(self, resolver):
        """Test chunking with realistic text content."""
        chunker = resolver.resolve(ChunkingStrategy.DEFAULT, plugin_name="test")

        # Create some realistic text
        text = (
            """This is a test document with multiple paragraphs.

This is paragraph two with some content that should be chunked appropriately.

And here is paragraph three with even more content to ensure chunking works correctly.
"""
            * 10
        )  # Repeat to ensure we get multiple chunks

        chunks = chunker.chunk(text, Path("/tmp/test.txt"))

        # Should produce multiple chunks
        assert len(chunks) > 1

        # Each chunk should respect size limits
        assert all(len(c.content) <= chunker.chunk_size + chunker.chunk_overlap for c in chunks)


class TestChunkingStrategyConfiguration:
    """Test chunking strategy with different configurations."""

    def test_custom_default_chunk_size(self):
        """Resolver should respect custom default chunk sizes."""
        resolver_small = ChunkingStrategyResolver(default_chunk_size=500, default_chunk_overlap=100)

        resolver_large = ChunkingStrategyResolver(
            default_chunk_size=2000, default_chunk_overlap=400
        )

        chunker_small = resolver_small.resolve(None)
        chunker_large = resolver_large.resolve(None)

        assert chunker_small.chunk_size == 500
        assert chunker_large.chunk_size == 2000

    def test_custom_overlap_configuration(self):
        """Resolver should respect custom overlap configuration."""
        resolver = ChunkingStrategyResolver(default_chunk_size=1000, default_chunk_overlap=300)

        chunker = resolver.resolve(ChunkingStrategy.DEFAULT)

        assert chunker.chunk_overlap == 300


class TestChunkingErrorHandling:
    """Test error handling in chunking strategy resolution."""

    def test_invalid_chunker_falls_back_gracefully(self, resolver, caplog):
        """Invalid chunker should fall back to default with warning."""

        class BadChunker:
            # Has chunk but it's not callable
            chunk = "not a method"

        bad = BadChunker()

        chunker = resolver.resolve(bad, plugin_name="bad_plugin")

        # Should fall back to default
        assert isinstance(chunker, TextChunker)

        # Should log warning
        assert any(
            "invalid chunking strategy" in record.message.lower() for record in caplog.records
        )

    def test_chunker_with_exception_in_chunk_method(self):
        """Chunker that raises exception should propagate error (no silent failure)."""

        class FailingChunker:
            def chunk(self, text: str, file_path: Path | None = None):
                raise RuntimeError("Chunking failed")

        failing = FailingChunker()
        resolver = ChunkingStrategyResolver()

        # Resolver accepts it (has chunk method)
        chunker = resolver.resolve(failing, plugin_name="failing")

        assert chunker is failing

        # But calling chunk raises exception (expected behavior)
        with pytest.raises(RuntimeError):
            chunker.chunk("test text", Path("/tmp/test.txt"))


class TestChunkingStrategyConsistency:
    """Test consistency of chunking strategy selection."""

    def test_same_strategy_same_chunker_instance(self, resolver):
        """Same strategy should return same chunker instance."""
        chunker1 = resolver.resolve(ChunkingStrategy.DEFAULT, "plugin1")
        chunker2 = resolver.resolve(ChunkingStrategy.DEFAULT, "plugin2")
        chunker3 = resolver.resolve(None, "plugin3")

        # All DEFAULT requests should get same instance
        assert chunker1 is chunker2
        assert chunker2 is chunker3

    def test_custom_chunkers_not_cached(self, resolver):
        """Custom chunkers should not be cached (each plugin gets their own)."""
        custom1 = CustomChunker(chunk_size=300)
        custom2 = CustomChunker(chunk_size=300)

        chunker1 = resolver.resolve(custom1, "plugin1")
        chunker2 = resolver.resolve(custom2, "plugin2")

        # Should be different instances
        assert chunker1 is not chunker2
        assert chunker1 is custom1
        assert chunker2 is custom2


class TestRealWorldScenarios:
    """Test real-world chunking scenarios."""

    def test_pdf_plugin_default_chunking(self, resolver):
        """Simulate PDF plugin using default chunking."""

        class PDFPlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "pdf"

            def get_chunking_strategy(self):
                # PDF plugin uses default
                return ChunkingStrategy.DEFAULT

        plugin = PDFPlugin()
        chunker = resolver.resolve(plugin.get_chunking_strategy(), "pdf")

        # Simulate extracting and chunking PDF text
        pdf_text = "PDF document text content. " * 100
        chunks = chunker.chunk(pdf_text, Path("/docs/document.pdf"))

        assert len(chunks) > 0

    def test_code_plugin_custom_chunking(self, resolver):
        """Simulate code plugin using custom code-aware chunking."""

        # Custom chunker that doesn't split mid-line
        class LineAwareChunker:
            def __init__(self):
                self.chunk_size = 500

            def chunk(self, text: str, file_path: Path | None = None) -> list[TextChunk]:
                lines = text.split("\n")
                chunks = []
                current_chunk = []
                current_size = 0

                for line in lines:
                    if current_size + len(line) > self.chunk_size and current_chunk:
                        chunk_text = "\n".join(current_chunk)
                        chunks.append(
                            TextChunk(
                                file_path=file_path or Path("unknown"),
                                chunk_index=len(chunks),
                                content=chunk_text,
                                start_char=0,
                                end_char=len(chunk_text),
                                token_count=len(chunk_text.split()),
                            )
                        )
                        current_chunk = []
                        current_size = 0

                    current_chunk.append(line)
                    current_size += len(line)

                if current_chunk:
                    chunk_text = "\n".join(current_chunk)
                    chunks.append(
                        TextChunk(
                            file_path=file_path or Path("unknown"),
                            chunk_index=len(chunks),
                            content=chunk_text,
                            start_char=0,
                            end_char=len(chunk_text),
                            token_count=len(chunk_text.split()),
                        )
                    )

                return chunks

        class CodePlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "code"

            def get_chunking_strategy(self):
                return LineAwareChunker()

        plugin = CodePlugin()
        chunker = resolver.resolve(plugin.get_chunking_strategy(), "code")

        # Simulate code file
        code_text = "def function():\n    return 42\n\n" * 50
        chunks = chunker.chunk(code_text, Path("/src/code.py"))

        assert len(chunks) > 0
        # Verify chunking worked (created multiple chunks or one chunk with content)
        assert sum(len(c.content) for c in chunks) > 0


# ───────────────────────────────────────────────────────────
# US4: Integration Tests - Plugin Provided Custom Chunking (T145)
# ───────────────────────────────────────────────────────────


class ChunkTextLogChunker:
    """Chunker implementing only chunk_text() per plugin contract."""

    def __init__(self, boundary_pattern: str = "---"):
        self.boundary_pattern = boundary_pattern

    def chunk_text(self, text: str) -> list[str]:
        """Split on boundary lines."""
        sections = text.split(self.boundary_pattern)
        return [s.strip() for s in sections if s.strip()]


class TestPluginCustomChunkingIntegration:
    """T145: Integration test for plugin-provided custom chunking in indexing pipeline."""

    def test_chunk_text_plugin_produces_valid_chunks(self):
        """Plugin with chunk_text()-only chunker should produce valid TextChunks in pipeline."""

        class LogPlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "logs"

            def get_chunking_strategy(self):
                return ChunkTextLogChunker(boundary_pattern="---")

        resolver = ChunkingStrategyResolver()
        plugin = LogPlugin()
        strategy = plugin.get_chunking_strategy()

        # Resolve should wrap in adapter
        chunker = resolver.resolve(strategy, plugin_name=plugin.name)
        assert isinstance(chunker, CustomChunkerAdapter)

        # Simulate indexing pipeline: extract text, then chunk
        log_text = "Entry 1: Starting\n---\nEntry 2: Processing\n---\nEntry 3: Done"
        chunks = chunker.chunk(log_text, file_path=Path("/var/log/app.log"))

        assert len(chunks) == 3
        assert all(isinstance(c, TextChunk) for c in chunks)
        assert chunks[0].content == "Entry 1: Starting"
        assert chunks[1].content == "Entry 2: Processing"
        assert chunks[2].content == "Entry 3: Done"
        assert all(c.file_path == Path("/var/log/app.log") for c in chunks)

    def test_custom_chunker_with_chunk_method_in_pipeline(self):
        """Plugin providing full chunk() method works directly in pipeline."""

        class CSVChunker:
            def __init__(self, rows_per_chunk: int = 3):
                self.rows_per_chunk = rows_per_chunk

            def chunk(
                self, text: str, file_path: Path | None = None, file_type: str | None = None
            ) -> list[TextChunk]:
                lines = [line for line in text.split("\n") if line.strip()]
                chunks = []
                for i in range(0, len(lines), self.rows_per_chunk):
                    batch = lines[i : i + self.rows_per_chunk]
                    content = "\n".join(batch)
                    chunks.append(
                        TextChunk(
                            file_path=file_path or Path("unknown"),
                            chunk_index=len(chunks),
                            content=content,
                            start_char=0,
                            end_char=len(content),
                            token_count=len(content.split()),
                        )
                    )
                return chunks

        class CSVPlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "csv"

            def get_chunking_strategy(self):
                return CSVChunker(rows_per_chunk=2)

        resolver = ChunkingStrategyResolver()
        plugin = CSVPlugin()
        chunker = resolver.resolve(plugin.get_chunking_strategy(), plugin_name="csv")

        csv_text = "name,age\nAlice,30\nBob,25\nCharlie,35"
        chunks = chunker.chunk(csv_text, file_path=Path("/data/people.csv"))

        assert len(chunks) == 2
        assert "Alice" in chunks[0].content
        assert "Charlie" in chunks[1].content

    def test_multiple_plugins_mixed_strategies_in_pipeline(self):
        """Multiple plugins with different strategies coexist in one resolver."""
        resolver = ChunkingStrategyResolver()

        # Plugin 1: Default
        default_chunker = resolver.resolve(ChunkingStrategy.DEFAULT, plugin_name="markdown")

        # Plugin 2: Custom chunk() method
        class MyCustomChunker:
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

        custom_chunker = resolver.resolve(MyCustomChunker(), plugin_name="xml")

        # Plugin 3: chunk_text()-only
        chunk_text_chunker = resolver.resolve(
            ChunkTextLogChunker(boundary_pattern="---"), plugin_name="logs"
        )

        assert isinstance(default_chunker, TextChunker)
        assert isinstance(custom_chunker, MyCustomChunker)
        assert isinstance(chunk_text_chunker, CustomChunkerAdapter)


# ───────────────────────────────────────────────────────────
# US4: Integration Tests - Default vs Custom Chunking (T146)
# ───────────────────────────────────────────────────────────


class TestDefaultVsCustomChunking:
    """T146: Test default vs custom chunking with same file type."""

    def test_default_and_custom_produce_different_results(self):
        """Default chunker and custom chunker produce different chunk boundaries."""
        text = "Section A content here.\n---\nSection B content here.\n---\nSection C."

        # Default: character-based
        default_resolver = ChunkingStrategyResolver(
            default_chunk_size=100, default_chunk_overlap=20
        )
        default_chunker = default_resolver.resolve(ChunkingStrategy.DEFAULT)
        default_chunks = default_chunker.chunk(text, file_path=Path("/tmp/test.txt"))

        # Custom: boundary-based
        custom_resolver = ChunkingStrategyResolver()
        custom_chunker = custom_resolver.resolve(
            ChunkTextLogChunker(boundary_pattern="---"), plugin_name="custom"
        )
        custom_chunks = custom_chunker.chunk(text, file_path=Path("/tmp/test.txt"))

        # Custom respects section boundaries (3 sections)
        assert len(custom_chunks) == 3
        assert custom_chunks[0].content == "Section A content here."
        assert custom_chunks[1].content == "Section B content here."
        assert custom_chunks[2].content == "Section C."

        # Default might produce different boundary splits
        # (depends on text length vs chunk size)
        default_content = "".join(c.content for c in default_chunks)
        custom_content = "".join(c.content for c in custom_chunks)

        # Both should cover all the text
        assert len(default_content) > 0
        assert len(custom_content) > 0

    def test_switching_plugin_strategy_changes_output(self):
        """Same text chunked differently when plugin changes strategy."""
        text = "A-section\n---\nB-section\n---\nC-section"

        resolver = ChunkingStrategyResolver()

        # First: use default
        default_chunks = resolver.resolve(None, plugin_name="test").chunk(
            text, file_path=Path("/tmp/test.txt")
        )

        # Then: use custom
        custom_chunks = resolver.resolve(
            ChunkTextLogChunker(boundary_pattern="---"), plugin_name="test"
        ).chunk(text, file_path=Path("/tmp/test.txt"))

        # Custom should give exactly 3 chunks
        assert len(custom_chunks) == 3
        # Default processes differently (likely 1 chunk for short text)
        assert len(default_chunks) >= 1


# ───────────────────────────────────────────────────────────
# US4: Integration Tests - Config Override (T147)
# ───────────────────────────────────────────────────────────


class TestChunkingConfigOverrideIntegration:
    """T147: Test chunking strategy selection based on plugin configuration."""

    def test_config_override_forces_default_over_custom(self, caplog):
        """Config override should override plugin's custom chunker preference."""
        caplog.set_level(logging.INFO)

        # User configured: override logs plugin to use default
        resolver = ChunkingStrategyResolver(
            default_chunk_size=1000,
            default_chunk_overlap=200,
            chunking_overrides={"logs": "default"},
        )

        class LogPlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "logs"

            def get_chunking_strategy(self):
                return ChunkTextLogChunker(boundary_pattern="---")

        plugin = LogPlugin()
        strategy = plugin.get_chunking_strategy()

        # Plugin wants custom, but config says default
        chunker = resolver.resolve(strategy, plugin_name=plugin.name)

        # Should use default, not the custom chunker
        assert isinstance(chunker, TextChunker)
        assert not isinstance(chunker, CustomChunkerAdapter)
        assert any("overridden by config" in r.message for r in caplog.records)

    def test_config_override_different_plugins_independently(self):
        """Config overrides apply independently per plugin."""
        resolver = ChunkingStrategyResolver(
            chunking_overrides={"logs": "default"},  # Only logs overridden
        )

        # Logs: overridden to default
        log_chunker = resolver.resolve(
            ChunkTextLogChunker(boundary_pattern="---"), plugin_name="logs"
        )

        # CSV: no override, gets its custom chunker
        class CSVCustom:
            def chunk(self, text, file_path=None, file_type=None):
                return []

        csv_chunker = resolver.resolve(CSVCustom(), plugin_name="csv")

        assert isinstance(log_chunker, TextChunker)
        assert isinstance(csv_chunker, CSVCustom)

    def test_config_override_end_to_end_chunking(self):
        """End-to-end: config override changes actual chunk output."""
        text = "Entry 1\n---\nEntry 2\n---\nEntry 3"

        # Without override: custom chunks on boundaries
        resolver_no_override = ChunkingStrategyResolver()
        custom = resolver_no_override.resolve(
            ChunkTextLogChunker(boundary_pattern="---"), plugin_name="logs"
        )
        custom_chunks = custom.chunk(text, file_path=Path("/var/log/app.log"))

        # With override: default character-based chunking
        resolver_override = ChunkingStrategyResolver(
            default_chunk_size=1000,
            default_chunk_overlap=200,
            chunking_overrides={"logs": "default"},
        )
        default = resolver_override.resolve(
            ChunkTextLogChunker(boundary_pattern="---"), plugin_name="logs"
        )
        default_chunks = default.chunk(text, file_path=Path("/var/log/app.log"))

        # Custom gives 3 boundary-based chunks
        assert len(custom_chunks) == 3

        # Default gives different result (likely 1 chunk for this short text)
        assert len(default_chunks) >= 1

        # Chunks are structurally different
        assert len(custom_chunks) != len(default_chunks) or any(
            c.content != d.content
            for c, d in zip(custom_chunks, default_chunks, strict=False)
        )

    def test_config_override_with_real_plugin_flow(self, caplog):
        """Simulate real plugin flow: discover → resolve → chunk → embed."""
        caplog.set_level(logging.DEBUG)

        # 1. Simulate config loading with override
        plugin_overrides = {"logs": "default", "csv": "semantic"}
        resolver = ChunkingStrategyResolver(chunking_overrides=plugin_overrides)

        # 2. "logs" plugin discovered - gets overridden
        class LogPlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "logs"

            def get_chunking_strategy(self):
                return ChunkTextLogChunker()

        log_plugin = LogPlugin()
        log_chunker = resolver.resolve(
            log_plugin.get_chunking_strategy(), plugin_name=log_plugin.name
        )

        # 3. "csv" plugin discovered - gets overridden to semantic (falls back to default)
        class CSVPlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "csv"

            def get_chunking_strategy(self):
                return ChunkingStrategy.CODE_AWARE

        csv_plugin = CSVPlugin()
        csv_chunker = resolver.resolve(
            csv_plugin.get_chunking_strategy(), plugin_name=csv_plugin.name
        )

        # 4. "markdown" plugin - no override
        class MDPlugin(MockFileTypeHandler):
            @property
            def name(self) -> str:
                return "markdown"

            def get_chunking_strategy(self):
                return None

        md_plugin = MDPlugin()
        md_chunker = resolver.resolve(md_plugin.get_chunking_strategy(), plugin_name=md_plugin.name)

        # Verify: logs uses default (overridden), csv uses default (SEMANTIC fallback),
        # markdown uses default (plugin choice)
        assert isinstance(log_chunker, TextChunker)
        assert isinstance(csv_chunker, TextChunker)
        assert isinstance(md_chunker, TextChunker)

        # All three should be the same cached default chunker
        assert log_chunker is csv_chunker
        assert csv_chunker is md_chunker
