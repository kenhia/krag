# Module Interface Contracts

**Feature**: Text-Based RAG Indexing & Retrieval System  
**Version**: 1.0.0

## Overview

This document defines the public interfaces for each module in the krag system. All interfaces use type hints and follow contract-first design principles.

---

## Discovery Module

### `FileScanner`

Discovers files from configured directories and creates FileMetadata records.

```python
class FileScanner:
    """Scans directories and generates file metadata."""
    
    def __init__(
        self,
        directory_paths: List[Path],
        exclusion_patterns: List[str],
        supported_extensions: List[str],
        max_file_size_mb: int = 100
    ):
        """Initialize scanner with configuration."""
        ...
    
    def scan(self) -> List[FileMetadata]:
        """
        Scan all configured directories and return file metadata.
        
        Returns:
            List of FileMetadata objects for discovered files
            
        Raises:
            PermissionError: If directory is not readable
            ValueError: If no directories configured
        """
        ...
    
    def scan_incremental(
        self,
        existing_metadata: Dict[Path, FileMetadata]
    ) -> Tuple[List[FileMetadata], List[Path]]:
        """
        Scan and identify changed files.
        
        Args:
            existing_metadata: Map of file path to previously indexed metadata
            
        Returns:
            Tuple of (new_or_modified_files, deleted_file_paths)
        """
        ...
```

### `FileFilter`

Applies exclusion patterns and file type filtering.

```python
class FileFilter:
    """Filters files based on patterns and criteria."""
    
    def __init__(
        self,
        exclusion_patterns: List[str],
        inclusion_patterns: Optional[List[str]] = None
    ):
        """Initialize filter with glob patterns."""
        ...
    
    def should_include(self, file_path: Path) -> bool:
        """
        Determine if file should be included based on patterns.
        
        Args:
            file_path: Path to evaluate
            
        Returns:
            True if file should be included, False otherwise
        """
        ...
```

---

## Extraction Module

### `TextExtractor`

Extracts text content from supported file types.

```python
class TextExtractor:
    """Extracts text content from various file formats."""
    
    def extract(self, file_metadata: FileMetadata) -> str:
        """
        Extract text content from file.
        
        Args:
            file_metadata: Metadata for file to extract
            
        Returns:
            Extracted text content
            
        Raises:
            UnicodeDecodeError: If file encoding cannot be determined
            PermissionError: If file is not readable
            FileTooLargeError: If file exceeds size limit
        """
        ...
    
    def detect_encoding(self, file_path: Path) -> str:
        """
        Detect file encoding.
        
        Returns:
            Encoding name (e.g., 'utf-8', 'latin-1')
        """
        ...
```

### `TextChunker`

Chunks extracted text into segments for embedding.

```python
class TextChunker:
    """Chunks text into semantic segments."""
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        respect_boundaries: bool = True
    ):
        """
        Initialize chunker with parameters.
        
        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            respect_boundaries: Whether to respect semantic boundaries
        """
        ...
    
    def chunk(
        self,
        content: str,
        file_metadata: FileMetadata
    ) -> List[TextChunk]:
        """
        Chunk text content into segments.
        
        Args:
            content: Text content to chunk
            file_metadata: Metadata for source file
            
        Returns:
            List of TextChunk objects
            
        Raises:
            ValueError: If content is empty
        """
        ...
    
    def chunk_code(
        self,
        content: str,
        language: str,
        file_metadata: FileMetadata
    ) -> List[TextChunk]:
        """
        Chunk code with language-aware boundaries.
        
        Args:
            content: Code content to chunk
            language: Programming language (e.g., 'python', 'javascript')
            file_metadata: Metadata for source file
            
        Returns:
            List of TextChunk objects respecting code structure
        """
        ...
```

---

## Embeddings Module

### `EmbeddingGenerator`

Generates vector embeddings for text chunks.

```python
class EmbeddingGenerator:
    """Generates embeddings using sentence-transformers."""
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        batch_size: int = 32
    ):
        """
        Initialize embedding generator.
        
        Args:
            model_name: HuggingFace model name
            device: Device to use ('cpu', 'cuda', 'mps')
            batch_size: Batch size for processing
        """
        ...
    
    def generate(self, chunks: List[TextChunk]) -> List[EmbeddingRecord]:
        """
        Generate embeddings for text chunks.
        
        Args:
            chunks: List of text chunks to embed
            
        Returns:
            List of EmbeddingRecord objects with vectors
            
        Raises:
            ModelNotLoadedError: If model failed to load
            TooManyTokensError: If chunk exceeds model max tokens
        """
        ...
    
    def generate_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.
        
        Args:
            text: Text to embed (typically a query)
            
        Returns:
            Embedding vector as list of floats
        """
        ...
    
    @property
    def vector_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        ...
```

---

## Storage Module

### `VectorStore` (Abstract Interface)

Abstract interface for vector storage implementations.

```python
from abc import ABC, abstractmethod

class VectorStore(ABC):
    """Abstract interface for vector storage backends."""
    
    @abstractmethod
    def upsert(self, embeddings: List[EmbeddingRecord]) -> None:
        """
        Insert or update embeddings in the store.
        
        Args:
            embeddings: List of embeddings to store
            
        Raises:
            StorageError: If upsert operation fails
        """
        ...
    
    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QueryResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters (e.g., {'file_type': 'python'})
            
        Returns:
            List of QueryResult objects sorted by similarity
        """
        ...
    
    @abstractmethod
    def delete(self, embedding_ids: List[str]) -> None:
        """
        Delete embeddings by ID.
        
        Args:
            embedding_ids: List of embedding IDs to delete
        """
        ...
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with keys: vector_count, storage_size_bytes, collection_name
        """
        ...
```

### `QdrantVectorStore`

Qdrant implementation of VectorStore.

```python
class QdrantVectorStore(VectorStore):
    """Qdrant implementation of vector storage."""
    
    def __init__(
        self,
        storage_path: Path,
        collection_name: str = "krag_embeddings",
        vector_dim: int = 384,
        distance_metric: str = "cosine"
    ):
        """
        Initialize Qdrant vector store.
        
        Args:
            storage_path: Path for Qdrant storage
            collection_name: Name of the collection
            vector_dim: Dimension of embedding vectors
            distance_metric: Distance metric ('cosine', 'dot', 'euclidean')
        """
        ...
    
    # Implements all VectorStore abstract methods
    ...
```

### `MetadataStore`

Stores file metadata and indexing job history.

```python
class MetadataStore:
    """SQLite-based metadata storage."""
    
    def __init__(self, db_path: Path):
        """Initialize metadata store with database path."""
        ...
    
    def save_file_metadata(self, metadata: FileMetadata) -> None:
        """Save or update file metadata."""
        ...
    
    def get_file_metadata(self, file_path: Path) -> Optional[FileMetadata]:
        """Retrieve file metadata by path."""
        ...
    
    def get_all_file_metadata(self) -> Dict[Path, FileMetadata]:
        """Get all file metadata as a dictionary."""
        ...
    
    def delete_file_metadata(self, file_path: Path) -> None:
        """Delete file metadata."""
        ...
    
    def save_indexing_job(self, job: IndexingJob) -> None:
        """Save indexing job record."""
        ...
    
    def get_recent_jobs(self, limit: int = 10) -> List[IndexingJob]:
        """Get recent indexing jobs."""
        ...
```

---

## Retrieval Module

### `Retriever`

Retrieves relevant chunks for queries.

```python
class Retriever:
    """Retrieves relevant chunks from vector store."""
    
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
        top_k: int = 5
    ):
        """
        Initialize retriever with dependencies.
        
        Args:
            vector_store: Vector storage implementation
            embedding_generator: Embedding generator for queries
            top_k: Default number of results to retrieve
        """
        ...
    
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QueryResult]:
        """
        Retrieve relevant chunks for query.
        
        Args:
            query: Natural language query string
            top_k: Number of results (overrides default)
            filters: Optional filters for results
            
        Returns:
            List of QueryResult objects
        """
        ...
```

---

## Synthesis Module

### `LLMClient`

Interface to local LLM for answer synthesis.

```python
class LLMClient:
    """Client for local LLM inference."""
    
    def __init__(
        self,
        model: str | Path,
        context_size: int = 2048,
        num_threads: int = 4,
        temperature: float = 0.7
    ):
        """
        Initialize LLM client.
        
        Args:
            model: HuggingFace model name (e.g., 'TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF')
                   or local path to GGUF file. HuggingFace models are auto-downloaded.
            context_size: Context window size (n_ctx)
            num_threads: Number of threads for inference
            temperature: Generation temperature
            
        Raises:
            FileNotFoundError: If local model file doesn't exist
            ModelLoadError: If model fails to load or download
        """
        ...
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        stream: bool = False
    ) -> Union[str, Iterator[str]]:
        """
        Generate text from prompt.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            stream: Whether to stream tokens
            
        Returns:
            Generated text (string or iterator if streaming)
        """
        ...
```

### `PromptBuilder`

Constructs prompts for LLM from query and context.

```python
class PromptBuilder:
    """Builds prompts for RAG queries."""
    
    def build_rag_prompt(
        self,
        query: str,
        context_chunks: List[QueryResult]
    ) -> str:
        """
        Build RAG prompt with query and retrieved context.
        
        Args:
            query: User's query
            context_chunks: Retrieved relevant chunks
            
        Returns:
            Formatted prompt string
        """
        ...
```

---

## Orchestration Module

### `IndexingOrchestrator`

Orchestrates the indexing pipeline.

```python
class IndexingOrchestrator:
    """Orchestrates the indexing pipeline."""
    
    def __init__(
        self,
        scanner: FileScanner,
        extractor: TextExtractor,
        chunker: TextChunker,
        embedding_generator: EmbeddingGenerator,
        vector_store: VectorStore,
        metadata_store: MetadataStore
    ):
        """Initialize orchestrator with pipeline components."""
        ...
    
    def index_full(self) -> IndexingJob:
        """
        Perform full indexing of all configured directories.
        
        Returns:
            IndexingJob record with results
        """
        ...
    
    def index_incremental(self) -> IndexingJob:
        """
        Perform incremental indexing (new/modified files only).
        
        Returns:
            IndexingJob record with results
        """
        ...
```

### `QueryEngine`

Orchestrates the query pipeline.

```python
class QueryEngine:
    """Orchestrates the query pipeline."""
    
    def __init__(
        self,
        retriever: Retriever,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder
    ):
        """Initialize query engine with components."""
        ...
    
    def query(
        self,
        query_text: str,
        top_k: int = 5,
        synthesize: bool = True,
        stream: bool = False
    ) -> QueryResponse:
        """
        Execute query and return response.
        
        Args:
            query_text: Natural language query
            top_k: Number of chunks to retrieve
            synthesize: Whether to synthesize answer with LLM
            stream: Whether to stream LLM response
            
        Returns:
            QueryResponse object with results
        """
        ...
```

**QueryResponse** data class:
```python
@dataclass
class QueryResponse:
    query: str
    results: List[QueryResult]
    answer: Optional[str]  # None if synthesize=False
    retrieval_time_ms: float
    synthesis_time_ms: Optional[float]
    total_time_ms: float
```

---

## Configuration Module

### `ConfigManager`

Manages configuration loading and validation.

```python
class ConfigManager:
    """Manages configuration loading and validation."""
    
    @classmethod
    def load(cls, config_path: Path) -> Configuration:
        """
        Load and validate configuration from file.
        
        Args:
            config_path: Path to config.toml file
            
        Returns:
            Validated Configuration object
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If configuration is invalid
        """
        ...
    
    @classmethod
    def create_default(cls, config_path: Path) -> Configuration:
        """
        Create default configuration file.
        
        Args:
            config_path: Where to save default config
            
        Returns:
            Default Configuration object
        """
        ...
    
    @classmethod
    def validate(cls, config: Configuration) -> List[str]:
        """
        Validate configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        ...
```

---

## Error Classes

Custom exceptions used across modules:

```python
class KragError(Exception):
    """Base exception for krag errors."""
    pass

class ConfigurationError(KragError):
    """Configuration validation or loading error."""
    pass

class StorageError(KragError):
    """Vector store or metadata store error."""
    pass

class ModelLoadError(KragError):
    """Embedding or LLM model loading error."""
    pass

class FileTooLargeError(KragError):
    """File exceeds maximum size limit."""
    pass

class TooManyTokensError(KragError):
    """Text exceeds model token limit."""
    pass
```

---

## Interface Stability

All public interfaces in this document are considered stable for v1.x releases. Breaking changes will require major version bump (v2.0.0).

Internal implementation details not documented here may change in minor/patch releases.
