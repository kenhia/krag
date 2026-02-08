# Contract: Plugin Chunking Strategy Selection

**Version**: 1.0.0  
**Status**: Draft  
**Purpose**: Defines how plugins specify and integrate chunking strategies

---

## Overview

Plugins can choose one of three approaches for text chunking:

1. **Use krag's default chunker** - Return `None` or `ChunkingStrategy.DEFAULT`
2. **Select a specific krag chunker** - Return `ChunkingStrategy` enum value
3. **Provide custom chunker** - Return `TextChunker` subclass instance

This design accommodates future expansion of native chunking strategies while allowing plugin-specific customization.

---

## ChunkingStrategy Enum

```python
from enum import Enum

class ChunkingStrategy(Enum):
    """Available built-in chunking strategies in krag"""
    
    DEFAULT = "default"
    """
    Current TextChunker behavior:
    - Fixed character-based chunks with overlap
    - No semantic boundary detection
    - Use for general text content
    """
    
    SEMANTIC = "semantic"
    """
    Future: Semantic boundary detection:
    - Respects sentence/paragraph boundaries
    - Preserves context at chunk edges
    - Use for narrative content, articles
    
    Status: NOT YET IMPLEMENTED (returns DEFAULT for now)
    """
    
    CODE_AWARE = "code_aware"
    """
    Future: Code structure-aware chunking:
    - Chunks at function/class boundaries
    - Preserves syntactic units
    - Use for source code files
    
    Status: NOT YET IMPLEMENTED (returns DEFAULT for now)
    """
    
    CUSTOM = "custom"
    """
    Plugin provides custom TextChunker implementation.
    When returning ChunkingStrategy.CUSTOM, plugin MUST also
    provide a TextChunker instance via get_custom_chunker().
    """
```

---

## FileTypeHandler Chunking Methods

### Required Method

```python
@abstractmethod
def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
    """
    Return preferred chunking strategy for this plugin's file types.
    
    Returns:
        ChunkingStrategy | TextChunker | None:
            - None: Use DEFAULT strategy (most common)
            - ChunkingStrategy.DEFAULT: Explicit default
            - ChunkingStrategy.SEMANTIC: Request semantic chunker (future)
            - ChunkingStrategy.CODE_AWARE: Request code-aware chunker (future)
            - TextChunker instance: Custom chunking implementation
            
    Examples:
        # Use krag's default chunker (Option 1)
        return None
        
        # Use krag's default chunker (Option 2, explicit)
        return ChunkingStrategy.DEFAULT
        
        # Request future semantic chunker
        return ChunkingStrategy.SEMANTIC
        
        # Provide custom chunker
        return LogFileChunker(boundary_pattern=r'^\\[\\d{4}-\\d{2}-\\d{2}')
    """
```

### Optional Method (for CUSTOM strategy)

```python
def get_custom_chunker(self) -> TextChunker | None:
    """
    Provide custom chunker implementation (optional).
    
    Returns:
        TextChunker | None: Custom chunker or None
        
    Notes:
        - Only called if get_chunking_strategy() returns ChunkingStrategy.CUSTOM
        - Can return None to fall back to DEFAULT
        - Prefer returning chunker directly from get_chunking_strategy()
        
    Example:
        return MyCustomChunker(settings=self.config)
    """
    return None
```

---

## TextChunker Interface (for Custom Chunkers)

Plugins providing custom chunking must implement this interface:

```python
class TextChunker(ABC):
    """Base class for text chunking strategies"""
    
    @abstractmethod
    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into chunks.
        
        Args:
            text (str): Text to chunk
            
        Returns:
            list[str]: List of text chunks
            
        Constraints:
            - Chunks should not be empty strings
            - Chunks should preserve meaningful boundaries when possible
            - Should handle empty input gracefully (return [] or [''])
            
        Example:
            >>> chunker.chunk_text("Line 1\\nLine 2\\nLine 3")
            ["Line 1\\nLine 2", "Line 2\\nLine 3"]
        """
    
    @property
    def chunk_size(self) -> int | None:
        """
        Target chunk size in characters (optional).
        
        Returns:
            int | None: Target size or None if not applicable
            
        Notes:
            - Used for progress estimation
            - Not enforced strictly
        """
        return None
    
    @property
    def chunk_overlap(self) -> int | None:
        """
        Overlap between chunks in characters (optional).
        
        Returns:
            int | None: Overlap size or None if not applicable
            
        Notes:
            - Used for progress estimation
            - Not enforced strictly
        """
        return None
```

---

## Integration Flow

### 1. Plugin Specifies Strategy

```python
class PDFFileTypeHandler(FileTypeHandler):
    def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
        # PDFs work well with default chunking
        return None
```

### 2. Indexer Requests Strategy

```python
# In indexing orchestrator
handler = plugin_registry.get_handler_for_extension(".pdf")
chunking_strategy = handler.get_chunking_strategy()
```

### 3. Indexer Resolves Chunker

```python
# Resolve actual chunker to use
if chunking_strategy is None or chunking_strategy == ChunkingStrategy.DEFAULT:
    chunker = self.default_chunker  # Existing TextChunker
    
elif isinstance(chunking_strategy, ChunkingStrategy):
    if chunking_strategy == ChunkingStrategy.SEMANTIC:
        # Future: chunker = self.semantic_chunker
        chunker = self.default_chunker  # Fallback for now
        
    elif chunking_strategy == ChunkingStrategy.CODE_AWARE:
        # Future: chunker = self.code_aware_chunker
        chunker = self.default_chunker  # Fallback for now
        
    elif chunking_strategy == ChunkingStrategy.CUSTOM:
        # Get custom chunker from plugin
        custom_chunker = handler.get_custom_chunker()
        chunker = custom_chunker if custom_chunker else self.default_chunker
        
elif hasattr(chunking_strategy, 'chunk_text'):
    # Plugin provided TextChunker instance directly
    chunker = chunking_strategy
    
else:
    # Invalid return value, log warning and use default
    logger.warning(f"Invalid chunking strategy from {handler.name}, using default")
    chunker = self.default_chunker
```

### 4. Indexer Applies Chunking

```python
# Extract text via plugin
text = handler.extract_text(file_path)

# Chunk using resolved chunker
chunks = chunker.chunk_text(text)

# Continue with embedding generation...
```

---

## Example Implementations

### Example 1: Use Default Chunking (Simplest)

```python
class MarkdownHandler(FileTypeHandler):
    def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
        # Markdown works fine with default chunking
        return None
```

### Example 2: Request Future Semantic Chunking

```python
class ArticleHandler(FileTypeHandler):
    def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
        # Request semantic chunking when available
        # Falls back to DEFAULT until implemented
        return ChunkingStrategy.SEMANTIC
```

### Example 3: Provide Custom Chunking

```python
class LogFileChunker(TextChunker):
    """Chunk log files by timestamp boundaries"""
    
    def __init__(self, timestamp_pattern: str = r'^\[\d{4}-\d{2}-\d{2}'):
        self.pattern = re.compile(timestamp_pattern, re.MULTILINE)
    
    def chunk_text(self, text: str) -> list[str]:
        # Find all log entry starts
        matches = list(self.pattern.finditer(text))
        
        if not matches:
            # No timestamps found, use single chunk
            return [text] if text else []
        
        chunks = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunks.append(text[start:end].strip())
        
        return chunks
    
    @property
    def chunk_size(self) -> int | None:
        return None  # Variable size
    
    @property
    def chunk_overlap(self) -> int | None:
        return 0  # No overlap

class LogFileHandler(FileTypeHandler):
    def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
        # Provide custom log file chunker
        return LogFileChunker()
```

### Example 4: Configuration-Based Chunking

```python
class CodeFileHandler(FileTypeHandler):
    def __init__(self):
        self.use_custom_chunking = False
    
    def initialize(self, config: dict[str, Any]) -> None:
        self.use_custom_chunking = config.get("code_aware_chunking", False)
    
    def get_chunking_strategy(self) -> ChunkingStrategy | TextChunker | None:
        if self.use_custom_chunking:
            # Request code-aware chunking (future)
            return ChunkingStrategy.CODE_AWARE
        else:
            # Use default for now
            return None
```

---

## Contract Tests

### Test 1: Strategy Return Types

```python
def test_chunking_strategy_valid_types(handler: FileTypeHandler):
    """Verify get_chunking_strategy returns valid type"""
    strategy = handler.get_chunking_strategy()
    
    assert (
        strategy is None or
        isinstance(strategy, ChunkingStrategy) or
        hasattr(strategy, 'chunk_text')
    ), f"Invalid chunking strategy type: {type(strategy)}"
```

### Test 2: Custom Chunker Implementation

```python
def test_custom_chunker_implements_interface(custom_chunker: TextChunker):
    """Verify custom chunker implements required methods"""
    assert hasattr(custom_chunker, 'chunk_text')
    assert callable(custom_chunker.chunk_text)
    
    # Test actual chunking
    chunks = custom_chunker.chunk_text("Sample text for testing")
    assert isinstance(chunks, list)
    assert all(isinstance(chunk, str) for chunk in chunks)
```

### Test 3: Default Chunking Integration

```python
def test_default_chunking_integration(handler: FileTypeHandler, test_file: Path):
    """Verify handler returning None uses default chunker"""
    strategy = handler.get_chunking_strategy()
    
    if strategy is None:
        # Should integrate with default TextChunker
        default_chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        text = handler.extract_text(test_file)
        chunks = default_chunker.chunk_text(text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
```

### Test 4: Custom Chunking Integration

```python
def test_custom_chunking_integration(handler: FileTypeHandler, test_file: Path):
    """Verify custom chunker integrates correctly"""
    strategy = handler.get_chunking_strategy()
    
    if isinstance(strategy, TextChunker):
        text = handler.extract_text(test_file)
        chunks = strategy.chunk_text(text)
        
        assert isinstance(chunks, list)
        assert all(isinstance(chunk, str) for chunk in chunks)
        # Chunks should not be empty unless text is empty
        if text:
            assert len(chunks) > 0
```

### Test 5: Fallback Behavior

```python
def test_invalid_strategy_fallback():
    """Verify invalid strategy falls back gracefully"""
    # Mock handler returning invalid strategy
    class BadHandler(FileTypeHandler):
        def get_chunking_strategy(self):
            return "invalid"  # Wrong type
    
    handler = BadHandler()
    strategy = handler.get_chunking_strategy()
    
    # Indexer should detect and handle this gracefully
    if not (strategy is None or 
            isinstance(strategy, ChunkingStrategy) or
            hasattr(strategy, 'chunk_text')):
        # Should fall back to default - this is tested in indexer
        pass
```

---

## Future Expansion

### Adding New Base Chunking Strategies

When adding a new built-in chunking strategy to krag:

1. Add enum value to `ChunkingStrategy`
2. Implement chunker class in `krag.extraction`
3. Update chunking resolution logic in indexer
4. Update plugin API documentation
5. Increment plugin API minor version

### Example: Adding SEMANTIC Strategy

```python
# 1. Add to enum
class ChunkingStrategy(Enum):
    # ...existing...
    SEMANTIC = "semantic"

# 2. Implement chunker
class SemanticTextChunker(TextChunker):
    def chunk_text(self, text: str) -> list[str]:
        # Implement semantic boundary detection
        pass

# 3. Update indexer resolution
if chunking_strategy == ChunkingStrategy.SEMANTIC:
    chunker = SemanticTextChunker()

# 4. Document in plugin guide

# 5. Bump API version to 1.1.0
```

Existing plugins automatically benefit from new strategies if they requested them.

---

## Performance Requirements

Custom chunkers SHOULD:
- Complete chunking in <1 second for typical files (<100KB)
- Handle large files (>10MB) without excessive memory usage
- Be deterministic (same input → same output)
- Not modify input text

---

## Error Handling

Custom chunkers SHOULD:
- Return empty list for empty input (not raise)
- Handle encoding issues gracefully
- Not raise on unexpected input formats
- Log warnings for unusual inputs

If custom chunker raises exception:
- Indexer logs error
- Falls back to default chunker
- Continues processing
