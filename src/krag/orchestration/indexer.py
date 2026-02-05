"""Indexing orchestration - coordinates the complete indexing pipeline."""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from krag.discovery.scanner import FileScanner
from krag.embeddings.generator import EmbeddingGenerator
from krag.extraction.chunker import TextChunker
from krag.extraction.text_extractor import TextExtractor
from krag.models.configuration import Configuration
from krag.models.file_metadata import FileMetadata
from krag.models.indexing_job import IndexingJob, JobStatus, JobType
from krag.orchestration.incremental import ChangeDetector
from krag.storage.qdrant_impl import QdrantVectorStore

logger = logging.getLogger(__name__)


class IndexingOrchestrator:
    """Orchestrates the complete indexing pipeline.

    Coordinates: file discovery → text extraction → chunking → embedding → storage
    """

    def __init__(
        self,
        directory_paths: list[Path] | Configuration | None = None,
        vector_store_path: Path | None = None,
        supported_file_types: list[str] | None = None,
        exclusion_patterns: list[str] | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        collection_name: str = "krag",
        embedding_model: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        config: Configuration | None = None,
    ):
        """Initialize indexing orchestrator.

        Args:
            directory_paths: Directories to index, or a Configuration object
            vector_store_path: Path for vector storage (None for in-memory)
            supported_file_types: File extensions to process (default: common text types)
            exclusion_patterns: Patterns to exclude
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            collection_name: Name of vector collection
            embedding_model: Sentence transformer model name
            device: Device for embeddings ('cpu', 'cuda', 'mps')
            config: Configuration object (if provided, overrides other parameters)
        """
        # Check if first argument is a Configuration object (for backward compatibility)
        if isinstance(directory_paths, Configuration):
            config = directory_paths
            directory_paths = None

        # If config is provided, use it
        if config is not None:
            self.config = config
            self.directory_paths = config.directory_paths
            self.vector_store_path = config.vector_store_path
            self.supported_file_types = config.supported_file_types
            self.exclusion_patterns = config.exclusion_patterns
            chunk_size = config.chunk_size
            chunk_overlap = config.chunk_overlap
            collection_name = config.collection_name
            embedding_model = config.embedding_model
            device = config.embedding_device
        else:
            # Build from individual parameters for backwards compatibility
            self.config = None
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

        # Initialize change detector for incremental updates
        self.change_detector = ChangeDetector(storage_path=vector_store_path or Path("."))

        # Track indexed files for incremental updates (metadata storage)
        self.indexed_files: dict[str, FileMetadata] = {}  # path -> FileMetadata

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
    ) -> IndexingJob:
        """Run complete indexing on all configured directories.

        Args:
            progress_callback: Optional callback(current, total, stage)

        Returns:
            IndexingJob with indexing statistics and status
        """
        # Create indexing job
        job = IndexingJob(
            job_id=str(uuid.uuid4()),
            job_type=JobType.FULL,
            status=JobStatus.RUNNING,
            start_time=datetime.now(),
            end_time=None,
            files_discovered=0,
            files_processed=0,
            files_skipped=0,
            files_errored=0,
            chunks_generated=0,
            embeddings_created=0,
            error_summary=[],
        )

        logger.info(f"Starting full indexing (job_id={job.job_id})")

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
        job.files_discovered = len(all_files)
        logger.info(f"Discovered {len(all_files)} files")

        if not all_files:
            logger.warning("No files found to index")
            job.status = JobStatus.COMPLETED
            job.end_time = datetime.now()
            return job

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
                    job.files_errored += 1
                    from krag.models.indexing_job import FileError

                    job.error_summary.append(
                        FileError(
                            file_path=file_metadata.file_path,
                            error_type="extraction",
                            error_message=str(e),
                        )
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

                job.chunks_generated += len(chunks)

                # Generate embeddings
                chunk_texts = [chunk.content for chunk in chunks]
                embeddings = self.embedding_generator.generate_batch(
                    chunk_texts, show_progress=False
                )
                job.embeddings_created += len(embeddings)

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

                job.files_processed += 1
                # Store file metadata for incremental updates
                self.indexed_files[str(file_metadata.file_path)] = file_metadata

            except Exception as e:
                logger.error(f"Error processing {file_metadata.file_path}: {e}")
                job.files_errored += 1
                from krag.models.indexing_job import FileError

                job.error_summary.append(
                    FileError(
                        file_path=file_metadata.file_path,
                        error_type="processing",
                        error_message=str(e),
                    )
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

            except Exception as e:
                logger.error(f"Error storing vectors: {e}")
                job.files_errored += 1
                from krag.models.indexing_job import FileError

                job.error_summary.append(
                    FileError(file_path=Path("."), error_type="storage", error_message=str(e))
                )

        job.status = JobStatus.COMPLETED
        job.end_time = datetime.now()

        logger.info(
            f"Indexing complete: {job.files_processed}/{job.files_discovered} files, "
            f"{job.chunks_generated} chunks, {job.embeddings_created} embeddings, "
            f"{job.files_errored} errors"
        )

        return job

    def index_incremental(
        self, progress_callback: Callable[[int, int, str], None] | None = None
    ) -> IndexingJob:
        """Run incremental indexing - only process new/modified files.

        Args:
            progress_callback: Optional callback(current, total, stage)

        Returns:
            IndexingJob with statistics and metadata
        """
        logger.info("Starting incremental indexing")

        job = IndexingJob(job_type=JobType.INCREMENTAL, status=JobStatus.RUNNING)

        # Stage 1: Discover all files
        scanner = FileScanner(
            directory_paths=self.directory_paths,
            supported_file_types=self.supported_file_types,
            exclusion_patterns=self.exclusion_patterns,
        )

        all_file_metadata = scanner.scan()
        job.files_discovered = len(all_file_metadata)

        # Stage 2: Categorize changes using ChangeDetector
        # Extract just the file paths for change detection
        all_file_paths = [fm.file_path for fm in all_file_metadata]
        changes_dict = self.change_detector.categorize_changes(all_file_paths, self.indexed_files)

        # Extract categorized changes
        new_changes = changes_dict["new"]
        modified_changes = changes_dict["modified"]
        deleted_changes = changes_dict["deleted"]
        unchanged_changes = changes_dict["unchanged"]

        job.files_added = len(new_changes)
        job.files_modified = len(modified_changes)
        job.files_deleted = len(deleted_changes)
        job.files_skipped = len(unchanged_changes)

        logger.info(
            f"Change detection: {job.files_added} new, {job.files_modified} modified, "
            f"{job.files_deleted} deleted, {job.files_skipped} unchanged"
        )

        # Stage 3: Handle deletions - remove from vector store
        if deleted_changes:
            logger.info(f"Removing {len(deleted_changes)} deleted files from index")
            try:
                for change in deleted_changes:
                    # Delete all vectors for this file
                    self.vector_store.delete_by_filter({"file_path": str(change.file_path)})
                    # Remove from indexed_files tracking
                    self.indexed_files.pop(str(change.file_path), None)
            except Exception as e:
                logger.error(f"Error removing deleted files: {e}")
                job.files_errored += len(deleted_changes)
                from krag.models.indexing_job import FileError

                job.error_summary.append(
                    FileError(
                        file_path=Path("."),
                        error_type="deletion",
                        error_message=f"Failed to remove deleted files: {e}",
                    )
                )

        # Stage 4: Build list of files to process (new + modified)
        # Map file paths back to their FileMetadata objects
        file_metadata_map = {str(fm.file_path): fm for fm in all_file_metadata}
        files_to_process = []

        for change in new_changes + modified_changes:
            file_path_str = str(change.file_path)
            if file_path_str in file_metadata_map:
                files_to_process.append(file_metadata_map[file_path_str])

        if not files_to_process:
            logger.info("No files to process - index is up to date")
            job.status = JobStatus.COMPLETED
            job.end_time = datetime.now()
            return job

        # Stage 5: Process new/modified files
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

                job.chunks_generated += len(chunks)

                chunk_texts = [chunk.content for chunk in chunks]
                embeddings = self.embedding_generator.generate_batch(
                    chunk_texts, show_progress=False
                )
                job.embeddings_created += len(embeddings)

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

                job.files_processed += 1
                # Store file metadata for incremental updates
                self.indexed_files[str(file_metadata.file_path)] = file_metadata

            except Exception as e:
                logger.error(f"Error processing {file_metadata.file_path}: {e}")
                job.files_errored += 1
                from krag.models.indexing_job import FileError

                job.error_summary.append(
                    FileError(
                        file_path=file_metadata.file_path,
                        error_type="processing",
                        error_message=str(e),
                    )
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

            except Exception as e:
                logger.error(f"Error storing vectors: {e}")
                job.files_errored += 1
                from krag.models.indexing_job import FileError

                job.error_summary.append(
                    FileError(file_path=Path("."), error_type="storage", error_message=str(e))
                )

        job.status = JobStatus.COMPLETED
        job.end_time = datetime.now()

        logger.info(
            f"Incremental indexing complete: {job.files_processed} processed, "
            f"{job.files_added} new, {job.files_modified} modified, "
            f"{job.files_deleted} deleted, {job.files_skipped} skipped, "
            f"{job.chunks_generated} chunks, {job.embeddings_created} embeddings"
        )

        return job
