"""Indexing orchestration - coordinates the complete indexing pipeline."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from krag.discovery.scanner import FileScanner
from krag.embeddings.generator import EmbeddingGenerator
from krag.extraction.chunker import TextChunker
from krag.extraction.text_extractor import TextExtractor
from krag.storage.qdrant_impl import QdrantVectorStore

logger = logging.getLogger(__name__)


class IndexingOrchestrator:
    """Orchestrates the complete indexing pipeline.

    Coordinates: file discovery → text extraction → chunking → embedding → storage
    """

    def __init__(
        self,
        directory_paths: list[Path] | None = None,
        vector_store_path: Path | None = None,
        supported_file_types: list[str] | None = None,
        exclusion_patterns: list[str] | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        collection_name: str = "krag",
        embedding_model: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        """Initialize indexing orchestrator.

        Args:
            directory_paths: Directories to index
            vector_store_path: Path for vector storage (None for in-memory)
            supported_file_types: File extensions to process (default: common text types)
            exclusion_patterns: Patterns to exclude
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            collection_name: Name of vector collection
            embedding_model: Sentence transformer model name
            device: Device for embeddings ('cpu', 'cuda', 'mps')
        """
        self.directory_paths = directory_paths or []
        self.vector_store_path = vector_store_path
        self.supported_file_types = supported_file_types
        self.exclusion_patterns = exclusion_patterns or []

        # Default supported file types
        if self.supported_file_types is None:
            self.supported_file_types = [
                ".txt",
                ".md",
                ".py",
                ".js",
                ".ts",
                ".java",
                ".cpp",
                ".c",
                ".go",
                ".rs",
                ".json",
                ".yaml",
                ".yml",
                ".toml",
                ".ini",
                ".cfg",
            ]

        # Initialize pipeline components (scanner will be created per-operation with paths)

        self.extractor = TextExtractor(max_file_size_mb=100)
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_generator = EmbeddingGenerator(model_name=embedding_model, device=device)

        # Get embedding dimension
        embedding_dim = self.embedding_generator.get_dimension()

        logger.info(f"Initializing vector store (dim={embedding_dim})")
        self.vector_store = QdrantVectorStore(
            collection_name=collection_name,
            vector_size=embedding_dim,
            storage_path=vector_store_path,
        )

        # Track indexed files for incremental updates
        self.indexed_files: dict[str, str] = {}  # path -> content_hash

    def close(self) -> None:
        """Close resources and release locks."""
        if hasattr(self, "vector_store") and self.vector_store:
            self.vector_store.close()

    def __enter__(self) -> "IndexingOrchestrator":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes resources."""
        self.close()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()

    def index_full(
        self, progress_callback: Callable[[int, int, str], None] | None = None
    ) -> dict[str, Any]:
        """Run complete indexing on all configured directories.

        Args:
            progress_callback: Optional callback(current, total, stage)

        Returns:
            Dictionary with indexing statistics
        """
        logger.info("Starting full indexing")

        stats = {
            "files_discovered": 0,
            "files_processed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "vectors_stored": 0,
            "errors": 0,
            "error_details": [],
        }

        # Stage 1: Discover files
        logger.info("Stage 1: Discovering files")
        if progress_callback:
            progress_callback(0, 100, "Discovering files")

        # Create scanner with directory paths
        scanner = FileScanner(
            directory_paths=self.directory_paths,
            supported_file_types=self.supported_file_types,
            exclusion_patterns=self.exclusion_patterns,
        )

        all_files = scanner.scan()
        stats["files_discovered"] = len(all_files)
        logger.info(f"Discovered {len(all_files)} files")

        if not all_files:
            logger.warning("No files found to index")
            return stats

        # Stage 2-5: Process each file
        all_vectors = []
        for i, file_metadata in enumerate(all_files):
            try:
                # Report progress
                if progress_callback:
                    progress_callback(i + 1, len(all_files), "Processing files")

                # Extract text
                try:
                    text = self.extractor.extract(file_metadata.file_path)
                except Exception as e:
                    logger.warning(f"Failed to extract {file_metadata.file_path}: {e}")
                    stats["errors"] += 1
                    stats["error_details"].append(
                        {
                            "file": str(file_metadata.file_path),
                            "stage": "extraction",
                            "error": str(e),
                        }
                    )
                    continue

                if not text or not text.strip():
                    logger.debug(f"Skipping empty file: {file_metadata.file_path}")
                    continue

                # Chunk text
                file_type = file_metadata.file_type or "text"
                chunks = self.chunker.chunk(
                    text, file_path=file_metadata.file_path, file_type=file_type
                )

                if not chunks:
                    logger.debug(f"No chunks created for {file_metadata.file_path}")
                    continue

                stats["chunks_created"] += len(chunks)

                # Generate embeddings
                chunk_texts = [chunk.content for chunk in chunks]
                embeddings = self.embedding_generator.generate_batch(
                    chunk_texts, show_progress=False
                )
                stats["embeddings_generated"] += len(embeddings)

                # Prepare vectors for storage
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    vector = {
                        "id": chunk.chunk_id,
                        "vector": embedding,
                        "payload": {
                            "content": chunk.content,
                            "file_path": str(chunk.file_path),
                            "file_type": file_metadata.file_type,
                            "chunk_index": chunk.chunk_index,
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                            "token_count": chunk.token_count,
                        },
                    }
                    all_vectors.append(vector)

                stats["files_processed"] += 1
                self.indexed_files[str(file_metadata.file_path)] = file_metadata.content_hash

            except Exception as e:
                logger.error(f"Error processing {file_metadata.file_path}: {e}")
                stats["errors"] += 1
                stats["error_details"].append(
                    {
                        "file": str(file_metadata.file_path),
                        "stage": "processing",
                        "error": str(e),
                    }
                )

        # Stage 6: Store vectors in batches
        if all_vectors:
            logger.info(f"Storing {len(all_vectors)} vectors")
            if progress_callback:
                progress_callback(100, 100, "Storing vectors")

            try:
                # Store in batches of 100
                batch_size = 100
                for i in range(0, len(all_vectors), batch_size):
                    batch = all_vectors[i : i + batch_size]
                    self.vector_store.upsert(batch)
                    stats["vectors_stored"] += len(batch)

            except Exception as e:
                logger.error(f"Error storing vectors: {e}")
                stats["errors"] += 1
                stats["error_details"].append({"stage": "storage", "error": str(e)})

        logger.info(
            f"Indexing complete: {stats['files_processed']}/{stats['files_discovered']} files, "
            f"{stats['chunks_created']} chunks, {stats['vectors_stored']} vectors stored, "
            f"{stats['errors']} errors"
        )

        return stats

    def index_incremental(
        self, progress_callback: Callable[[int, int, str], None] | None = None
    ) -> dict[str, Any]:
        """Run incremental indexing - only process new/modified files.

        Args:
            progress_callback: Optional callback(current, total, stage)

        Returns:
            Dictionary with indexing statistics
        """
        logger.info("Starting incremental indexing")

        stats = {
            "files_discovered": 0,
            "files_processed": 0,
            "files_skipped": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "vectors_stored": 0,
            "errors": 0,
            "error_details": [],
        }

        # Discover all files
        scanner = FileScanner(
            directory_paths=self.directory_paths,
            supported_file_types=self.supported_file_types,
            exclusion_patterns=self.exclusion_patterns,
        )

        all_files = scanner.scan()
        stats["files_discovered"] = len(all_files)

        # Filter to new/modified files
        files_to_process = []
        for file_metadata in all_files:
            file_path_str = str(file_metadata.file_path)

            # Check if file is new or modified
            if file_path_str not in self.indexed_files:
                files_to_process.append(file_metadata)
            elif self.indexed_files[file_path_str] != file_metadata.content_hash:
                files_to_process.append(file_metadata)
            else:
                stats["files_skipped"] += 1

        logger.info(
            f"Found {len(files_to_process)} new/modified files out of {len(all_files)} total"
        )

        if not files_to_process:
            logger.info("No files to process - index is up to date")
            return stats

        # Process new/modified files using same logic as full indexing
        # (simplified for now - could be refactored into a shared method)
        all_vectors = []
        for i, file_metadata in enumerate(files_to_process):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(files_to_process), "Processing files")

                text = self.extractor.extract(file_metadata.file_path)
                if not text or not text.strip():
                    continue

                file_type = file_metadata.file_type or "text"
                chunks = self.chunker.chunk(
                    text, file_path=file_metadata.file_path, file_type=file_type
                )

                if not chunks:
                    continue

                stats["chunks_created"] += len(chunks)

                chunk_texts = [chunk.content for chunk in chunks]
                embeddings = self.embedding_generator.generate_batch(
                    chunk_texts, show_progress=False
                )
                stats["embeddings_generated"] += len(embeddings)

                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    vector = {
                        "id": chunk.chunk_id,
                        "vector": embedding,
                        "payload": {
                            "content": chunk.content,
                            "file_path": str(chunk.file_path),
                            "file_type": file_metadata.file_type,
                            "chunk_index": chunk.chunk_index,
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                            "token_count": chunk.token_count,
                        },
                    }
                    all_vectors.append(vector)

                stats["files_processed"] += 1
                self.indexed_files[str(file_metadata.file_path)] = file_metadata.content_hash

            except Exception as e:
                logger.error(f"Error processing {file_metadata.file_path}: {e}")
                stats["errors"] += 1
                stats["error_details"].append(
                    {
                        "file": str(file_metadata.file_path),
                        "error": str(e),
                    }
                )

        # Store vectors
        if all_vectors:
            try:
                batch_size = 100
                for i in range(0, len(all_vectors), batch_size):
                    batch = all_vectors[i : i + batch_size]
                    self.vector_store.upsert(batch)
                    stats["vectors_stored"] += len(batch)
            except Exception as e:
                logger.error(f"Error storing vectors: {e}")
                stats["errors"] += 1

        logger.info(
            f"Incremental indexing complete: {stats['files_processed']} files processed, "
            f"{stats['files_skipped']} skipped, {stats['vectors_stored']} vectors stored"
        )

        return stats
