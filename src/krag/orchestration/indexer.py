"""Indexing orchestration - coordinates the complete indexing pipeline."""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from krag.discovery.scanner import FileScanner
from krag.embeddings.generator import EmbeddingGenerator
from krag.extraction.chunker import TextChunker
from krag.extraction.text_extractor import TextExtractor
from krag.models.configuration import Configuration
from krag.models.file_metadata import FileMetadata
from krag.models.indexing_job import IndexingJob, JobStatus, JobType
from krag.orchestration.incremental import ChangeDetector
from krag.plugins.chunking import ChunkingStrategyResolver
from krag.plugins.context import PluginContext
from krag.plugins.failures import IndexingFailureCollector
from krag.plugins.registry import PluginRegistry
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
            storage_path=self.vector_store_path,
        )

        # Initialize change detector for incremental updates
        self.change_detector = ChangeDetector(storage_path=self.vector_store_path or Path("."))

        # Initialize plugin system
        plugin_config = config.plugins if config is not None else None
        if plugin_config is not None:
            logger.info("Initializing plugin system")
            self.plugin_registry = PluginRegistry(plugin_config)
            self.plugin_registry.discover_plugins()
            self.plugin_registry._build_extension_map()

            # Initialize failure collector first (needed for context)
            self.failure_collector = IndexingFailureCollector()

            # Create wrapper for plugin failure reporting
            def report_plugin_failure(file_path: Path, reason: str) -> None:
                """Wrapper for plugin failure reporting."""
                self.failure_collector.record_failure(
                    file_path=file_path,
                    reason=reason,
                    plugin_name=None,  # Will be set by specific plugin calls
                )

            # Initialize plugin context with access to krag services
            self.plugin_context = PluginContext(
                embedding_generator=self.embedding_generator,
                vector_store=self.vector_store,
                chunker=self.chunker,
                logger=logging.getLogger("krag.plugins"),
                report_indexing_failure=report_plugin_failure,
            )

            # Initialize chunking strategy resolver with per-plugin overrides
            chunking_overrides = self._build_chunking_overrides(plugin_config)
            self.chunking_resolver = ChunkingStrategyResolver(
                default_chunk_size=chunk_size,
                default_chunk_overlap=chunk_overlap,
                chunking_overrides=chunking_overrides,
            )

            logger.info(
                f"Plugin system initialized: {len(self.plugin_registry.list_plugins())} plugins discovered"
            )
        else:
            # No plugin configuration - plugin system disabled
            self.plugin_registry = None
            self.plugin_context = None
            self.chunking_resolver = None
            self.failure_collector = None
            logger.debug("Plugin system disabled (no configuration provided)")

        # Track indexed files for incremental updates (metadata storage)
        self.indexed_files: dict[str, FileMetadata] = {}  # path -> FileMetadata

        # Load previously indexed files from disk
        self._load_metadata()

    def close(self) -> None:
        """Close resources and release locks."""
        if hasattr(self, "vector_store") and self.vector_store:
            self.vector_store.close()

    @staticmethod
    def _build_chunking_overrides(plugin_config: Any) -> dict[str, str]:
        """Build per-plugin chunking strategy overrides from configuration.

        Reads ``chunking_strategy`` from each plugin's settings in the config
        to allow users to override the chunking approach per plugin.

        Args:
            plugin_config: PluginConfiguration with plugin_settings

        Returns:
            dict mapping plugin name to strategy name string
        """
        overrides: dict[str, str] = {}
        if not hasattr(plugin_config, "plugin_settings"):
            return overrides

        for plugin_name, settings in plugin_config.plugin_settings.items():
            if isinstance(settings, dict) and "chunking_strategy" in settings:
                overrides[plugin_name] = str(settings["chunking_strategy"])
                logger.debug(
                    f"Chunking override for '{plugin_name}': {settings['chunking_strategy']}"
                )

        return overrides

    def __enter__(self) -> "IndexingOrchestrator":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes resources."""
        self.close()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()

    def _get_metadata_path(self) -> Path:
        """Get path to metadata persistence file.

        Returns:
            Path to metadata.json file
        """
        storage_path = self.vector_store.storage_path or Path(".")
        return storage_path / "metadata.json"

    def _load_metadata(self) -> None:
        """Load previously indexed file metadata from disk.

        Only loads metadata for files within the configured directory paths
        to avoid cross-contamination between different workspaces.
        """
        metadata_path = self._get_metadata_path()

        if not metadata_path.exists():
            logger.info("No previous metadata found, starting fresh")
            return

        try:
            import json

            with open(metadata_path) as f:
                data = json.load(f)

            # Deserialize FileMetadata objects
            from datetime import datetime

            loaded_count = 0
            for item in data:
                # Convert datetime strings back to datetime objects
                item["modification_time"] = datetime.fromisoformat(item["modification_time"])
                if item.get("last_indexed_at"):
                    item["last_indexed_at"] = datetime.fromisoformat(item["last_indexed_at"])

                # Recreate FileMetadata object
                file_path = Path(item["file_path"])

                # Only load metadata for files within our configured directories
                # This prevents cross-contamination between different workspaces
                # Get directory paths from config or from direct parameters
                dir_paths = (
                    self.config.directory_paths
                    if self.config
                    else [Path(d) for d in self.directory_paths]
                )

                is_in_workspace = any(file_path.is_relative_to(dir_path) for dir_path in dir_paths)

                if not is_in_workspace:
                    continue

                metadata = FileMetadata(
                    file_path=file_path,
                    file_size=item["file_size"],
                    modification_time=item["modification_time"],
                    file_type=item["file_type"],
                    content_hash=item.get("content_hash"),
                    last_indexed_at=item.get("last_indexed_at"),
                    chunk_count=item.get("chunk_count", 0),
                )
                self.indexed_files[str(metadata.file_path)] = metadata
                loaded_count += 1

            logger.info(f"Loaded metadata for {loaded_count} previously indexed files")

        except Exception as e:
            logger.warning(f"Failed to load metadata from {metadata_path}: {e}")
            logger.info("Starting with empty metadata state")
            self.indexed_files = {}

    def _save_metadata(self) -> None:
        """Save indexed file metadata to disk for incremental indexing."""
        metadata_path = self._get_metadata_path()

        try:
            import json

            # Ensure parent directory exists
            metadata_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize FileMetadata objects
            data = []
            for metadata in self.indexed_files.values():
                item = {
                    "file_path": str(metadata.file_path),
                    "file_size": metadata.file_size,
                    "modification_time": metadata.modification_time.isoformat(),
                    "file_type": metadata.file_type,
                    "content_hash": metadata.content_hash,
                    "last_indexed_at": (
                        metadata.last_indexed_at.isoformat() if metadata.last_indexed_at else None
                    ),
                    "chunk_count": metadata.chunk_count,
                }
                data.append(item)

            with open(metadata_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved metadata for {len(self.indexed_files)} files to {metadata_path}")

        except Exception as e:
            logger.error(f"Failed to save metadata to {metadata_path}: {e}")

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
            plugin_registry=self.plugin_registry,
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

                # T047: Check for plugin handler
                plugin_handler = None
                if self.plugin_registry is not None:
                    plugin_handler = self.plugin_registry.get_handler_for_file(
                        file_metadata.file_path, context=self.plugin_context
                    )

                # Extract text (T048: plugin-based extraction with error handling)
                text = None
                plugin_metadata = {}

                if plugin_handler is not None:
                    # Use plugin for extraction
                    try:
                        logger.debug(
                            f"Using plugin {plugin_handler.__class__.__name__} "
                            f"for {file_metadata.file_path}"
                        )

                        # T048: Plugin text extraction with try-catch
                        text = plugin_handler.extract_text(file_metadata.file_path)

                        # T049: Plugin metadata extraction with try-catch
                        try:
                            plugin_metadata = plugin_handler.extract_metadata(
                                file_metadata.file_path
                            )
                            logger.debug(
                                f"Extracted metadata from plugin: {list(plugin_metadata.keys())}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Plugin metadata extraction failed for "
                                f"{file_metadata.file_path}: {e}"
                            )
                            plugin_metadata = {}
                            # Continue processing - metadata is not essential

                    except Exception as e:
                        # T051: Plugin error handling and graceful degradation
                        logger.error(f"Plugin extraction failed for {file_metadata.file_path}: {e}")

                        # Record failure if failure collector is available
                        if self.failure_collector is not None:
                            self.failure_collector.record_failure(
                                file_path=file_metadata.file_path,
                                plugin_name=plugin_handler.__class__.__name__,
                                reason=str(e),
                                exception_type="extraction",
                            )

                        # Disable plugin on error - use handler.name for registry key
                        handler_plugin_name = getattr(
                            plugin_handler, "name", plugin_handler.__class__.__name__.lower()
                        )
                        if self.plugin_registry is not None:
                            self.plugin_registry.unload_plugin(handler_plugin_name)
                            logger.warning(
                                f"Disabled plugin '{handler_plugin_name}' due to extraction error"
                            )

                        # Fall back to default extraction
                        plugin_handler = None
                        text = None

                # If plugin extraction failed or no plugin, use default extractor
                if text is None:
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

                # T050: Integrate plugin chunking strategy selection
                if plugin_handler is not None and self.chunking_resolver is not None:
                    try:
                        # Get chunking strategy from plugin
                        chunking_strategy = plugin_handler.get_chunking_strategy()

                        # Use handler.name for config override lookup
                        handler_name = getattr(
                            plugin_handler, "name", plugin_handler.__class__.__name__
                        )

                        # Resolve to actual chunker
                        chunker = self.chunking_resolver.resolve(
                            chunking_strategy,
                            plugin_name=handler_name,
                        )

                        # Use resolved chunker
                        file_type = file_metadata.file_type or "text"
                        chunks = chunker.chunk(
                            text, file_path=file_metadata.file_path, file_type=file_type
                        )
                        logger.debug(f"Used plugin chunking strategy for {file_metadata.file_path}")
                    except Exception as e:
                        # T051: Graceful degradation on chunking error
                        logger.warning(
                            f"Plugin chunking failed for {file_metadata.file_path}: {e}, "
                            f"using default chunker"
                        )
                        # Fall back to default chunker
                        file_type = file_metadata.file_type or "text"
                        chunks = self.chunker.chunk(
                            text, file_path=file_metadata.file_path, file_type=file_type
                        )
                else:
                    # No plugin or no chunking resolver - use default chunker
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

                # Update file metadata with indexing details
                file_metadata.chunk_count = len(chunks)
                file_metadata.last_indexed_at = datetime.now()

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

        # T053: Output failure summary if there were plugin failures
        if self.failure_collector is not None and self.failure_collector.total_failures() > 0:
            failure_summary = self.failure_collector.format_summary()
            logger.warning(f"\n{failure_summary}")

        # Save metadata for incremental indexing
        self._save_metadata()

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
            plugin_registry=self.plugin_registry,
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

                # Check for plugin handler
                plugin_handler = None
                if self.plugin_registry is not None:
                    plugin_handler = self.plugin_registry.get_handler_for_file(
                        file_metadata.file_path, context=self.plugin_context
                    )

                # Extract text using plugin or default extractor
                text = None

                if plugin_handler is not None:
                    try:
                        text = plugin_handler.extract_text(file_metadata.file_path)

                        try:
                            # Extract metadata (not yet stored, but validates plugin works)
                            plugin_handler.extract_metadata(file_metadata.file_path)
                        except Exception as e:
                            logger.warning(
                                f"Plugin metadata extraction failed for "
                                f"{file_metadata.file_path}: {e}"
                            )

                    except Exception as e:
                        logger.error(f"Plugin extraction failed for {file_metadata.file_path}: {e}")

                        if self.failure_collector is not None:
                            self.failure_collector.record_failure(
                                file_path=file_metadata.file_path,
                                plugin_name=plugin_handler.__class__.__name__,
                                reason=str(e),
                                exception_type="extraction",
                            )

                        handler_plugin_name = getattr(
                            plugin_handler, "name", plugin_handler.__class__.__name__.lower()
                        )
                        if self.plugin_registry is not None:
                            self.plugin_registry.unload_plugin(handler_plugin_name)

                        plugin_handler = None
                        text = None

                if text is None:
                    text = self.extractor.extract(file_metadata.file_path)

                if not text or not text.strip():
                    continue

                # Use plugin chunking strategy if available
                if plugin_handler is not None and self.chunking_resolver is not None:
                    try:
                        chunking_strategy = plugin_handler.get_chunking_strategy()
                        chunker = self.chunking_resolver.resolve(
                            chunking_strategy,
                            plugin_name=plugin_handler.__class__.__name__,
                        )
                        file_type = file_metadata.file_type or "text"
                        chunks = chunker.chunk(
                            text, file_path=file_metadata.file_path, file_type=file_type
                        )
                    except Exception as e:
                        logger.warning(f"Plugin chunking failed for {file_metadata.file_path}: {e}")
                        file_type = file_metadata.file_type or "text"
                        chunks = self.chunker.chunk(
                            text, file_path=file_metadata.file_path, file_type=file_type
                        )
                else:
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

                # Update file metadata with indexing details
                file_metadata.chunk_count = len(chunks)
                file_metadata.last_indexed_at = datetime.now()

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

        # T053: Output failure summary if there were plugin failures
        if self.failure_collector is not None and self.failure_collector.total_failures() > 0:
            failure_summary = self.failure_collector.format_summary()
            logger.warning(f"\n{failure_summary}")

        # Save metadata for next incremental run
        self._save_metadata()

        return job
