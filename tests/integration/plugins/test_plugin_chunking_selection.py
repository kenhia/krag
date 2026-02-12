"""Integration tests for plugin chunking strategy selection.

Tests that plugins can specify chunking strategies and that the
ChunkingStrategyResolver correctly selects and applies chunkers
during the indexing pipeline.
"""

from pathlib import Path

import pytest

from krag.extraction.chunker import TextChunker
from krag.models.text_chunk import TextChunk
from krag.plugins.chunking import ChunkingStrategyResolver
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
