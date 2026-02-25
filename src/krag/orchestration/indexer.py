"""Indexing orchestration - coordinates the complete indexing pipeline."""

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from krag.discovery.scanner import FileScanner
from krag.embeddings.orchestrator import EmbeddingOrchestrator
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

# Type alias: (collection_name, vectors) tuple for multi-collection routing
_RoutedVectors = tuple[str, list[dict[str, Any]]]


@dataclass
class FileProcessingResult:
    """Result of processing a single file through the indexing pipeline."""

    vectors: list[dict[str, Any]] = field(default_factory=list)
    chunk_count: int = 0
    embeddings_created: int = 0
    handler_name: str | None = None
    error: str | None = None
    skipped: bool = False

    @property
    def success(self) -> bool:
        """True if processing completed without error."""
        return self.error is None


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
        chunk_size: int = 384,
        chunk_overlap: int = 64,
        collection_name: str = "krag",
        embedding_model: str = "BAAI/bge-base-en-v1.5",
        device: str = "cpu",
        config: Configuration | None = None,
        vector_store: "QdrantVectorStore | None" = None,
        collection_manager: "Any | None" = None,
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
        self.embedding_orchestrator = EmbeddingOrchestrator(
            default_model=embedding_model, device=device
        )
        # Keep a reference to the default generator for backward-compat PluginContext
        self.embedding_generator = self.embedding_orchestrator._models["text"]

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

            # Create a temporary vector store placeholder for PluginContext
            # (will be replaced below once we know the full vector config)
            self.vector_store: QdrantVectorStore | None = None  # type: ignore[assignment]

            # Initialize plugin context with access to krag services
            self.plugin_context = PluginContext(
                embedding_generator=self.embedding_generator,
                vector_store=self.vector_store,  # type: ignore[arg-type]
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

            # Scan loaded plugins for additional embedding models (T049/T050)
            self._collect_plugin_embedding_models()

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

        # Initialize vector store with correct vector config
        if vector_store is not None:
            # Use injected vector store (e.g. from kragd service)
            self.vector_store = vector_store
            self._owns_vector_store = False
            logger.info("Using injected vector store (shared client)")
        else:
            self._owns_vector_store = True
            embedding_dim = self.embedding_orchestrator.dimension
            if self.embedding_orchestrator.is_multi_model:
                vectors_config = self.embedding_orchestrator.get_vector_config()
                logger.info(
                    f"Initializing vector store with named vectors: "
                    f"{list(vectors_config.keys())} (dim={embedding_dim})"
                )
                self.vector_store = QdrantVectorStore(
                    collection_name=collection_name,
                    vector_size=embedding_dim,
                    storage_path=self.vector_store_path,
                    vectors_config=vectors_config,
                    allow_recreate=True,
                )
            else:
                logger.info(f"Initializing vector store (dim={embedding_dim})")
                self.vector_store = QdrantVectorStore(
                    collection_name=collection_name,
                    vector_size=embedding_dim,
                    storage_path=self.vector_store_path,
                    allow_recreate=True,
                )

        # Update plugin context with the real vector store
        if self.plugin_context is not None:
            self.plugin_context.vector_store = self.vector_store

        # Store collection manager for multi-collection routing
        self.collection_manager = collection_manager

        # Track indexed files for incremental updates (metadata storage)
        self.indexed_files: dict[str, FileMetadata] = {}  # path -> FileMetadata

        # Load previously indexed files from disk
        self._load_metadata()

    def close(self) -> None:
        """Close resources and release locks."""
        if hasattr(self, "_owns_vector_store") and not self._owns_vector_store:
            logger.debug("Skipping vector store close (injected, not owned)")
            return
        if hasattr(self, "vector_store") and self.vector_store:
            logger.info("Closing vector store...")
            self.vector_store.close()
            logger.debug("Vector store closed")

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

    def _collect_plugin_embedding_models(self) -> None:
        """Scan loaded plugins for additional embedding models.

        Iterates through discovered plugins, loads their handlers, and registers
        any declared embedding models with the EmbeddingOrchestrator.
        """
        if self.plugin_registry is None:
            return

        seen_models: set[str] = set()
        for plugin_meta in self.plugin_registry.list_plugins(filter_status="enabled"):
            handler = self.plugin_registry.load_plugin(plugin_meta.name, self.plugin_context)
            if handler is None:
                continue

            model_name = handler.get_embedding_model()
            if model_name is None or model_name in seen_models:
                continue

            seen_models.add(model_name)
            # Derive vector_name from plugin name (e.g., "code" plugin → "code")
            vector_name = plugin_meta.name
            loaded = self.embedding_orchestrator.register_model(vector_name, model_name)
            if loaded:
                logger.info(
                    f"Plugin '{plugin_meta.name}' registered embedding model "
                    f"'{model_name}' as vector '{vector_name}'"
                )

    def __enter__(self) -> "IndexingOrchestrator":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes resources."""
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
            with open(metadata_path) as f:
                data = json.load(f)

            # Deserialize FileMetadata objects
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

    def _process_file(
        self,
        file_meta: FileMetadata,
        plugin_handler: Any | None,
    ) -> FileProcessingResult:
        """Process a single file through extraction → chunking → embedding → payload.

        Shared per-file logic used by both index_full() and index_incremental().
        Ensures consistent behaviour across indexing modes.

        Args:
            file_meta: Metadata for the file to process.
            plugin_handler: Plugin handler for this file type, or None.

        Returns:
            FileProcessingResult with vectors ready for upsert, or error info.
        """
        # 1. Reset chunker state to prevent leakage from previous files
        chunker = None
        handler_name: str | None = None

        # 2. Try plugin extraction
        text: str | None = None

        if plugin_handler is not None:
            handler_name = getattr(plugin_handler, "name", plugin_handler.__class__.__name__)
            try:
                text = plugin_handler.extract_text(file_meta.file_path)

                # Attempt metadata extraction (non-critical)
                try:
                    plugin_handler.extract_metadata(file_meta.file_path)
                except Exception as e:
                    logger.warning(
                        f"Plugin metadata extraction failed for {file_meta.file_path}: {e}"
                    )

            except Exception as e:
                logger.error(f"Plugin extraction failed for {file_meta.file_path}: {e}")

                if self.failure_collector is not None:
                    self.failure_collector.record_failure(
                        file_path=file_meta.file_path,
                        plugin_name=plugin_handler.__class__.__name__,
                        reason=str(e),
                        exception_type="extraction",
                    )

                # Disable plugin on error
                handler_plugin_name = getattr(
                    plugin_handler, "name", plugin_handler.__class__.__name__.lower()
                )
                if self.plugin_registry is not None:
                    self.plugin_registry.unload_plugin(handler_plugin_name)
                    logger.warning(
                        f"Disabled plugin '{handler_plugin_name}' due to extraction error"
                    )

                plugin_handler = None
                handler_name = None
                text = None

        # 3. Default extraction fallback
        if text is None:
            try:
                text = self.extractor.extract(file_meta.file_path)
            except Exception as e:
                logger.warning(f"Failed to extract {file_meta.file_path}: {e}")
                return FileProcessingResult(error=str(e), handler_name=handler_name)

        if not text or not text.strip():
            logger.info(f"Skipping empty file: {file_meta.file_path}")
            return FileProcessingResult(skipped=True, handler_name=handler_name)

        # 4. Chunking (plugin strategy or default)
        if plugin_handler is not None and self.chunking_resolver is not None:
            try:
                chunking_strategy = plugin_handler.get_chunking_strategy()
                chunker = self.chunking_resolver.resolve(
                    chunking_strategy,
                    plugin_name=handler_name or plugin_handler.__class__.__name__,
                )
                file_type = file_meta.file_type or "text"
                chunks = chunker.chunk(text, file_path=file_meta.file_path, file_type=file_type)
            except Exception as e:
                logger.warning(
                    f"Plugin chunking failed for {file_meta.file_path}: {e}, using default chunker"
                )
                file_type = file_meta.file_type or "text"
                chunks = self.chunker.chunk(
                    text, file_path=file_meta.file_path, file_type=file_type
                )
        else:
            file_type = file_meta.file_type or "text"
            chunks = self.chunker.chunk(text, file_path=file_meta.file_path, file_type=file_type)

        if not chunks:
            logger.info(f"Skipping file (no chunks created): {file_meta.file_path}")
            return FileProcessingResult(skipped=True, handler_name=handler_name)

        # 5. Determine vector_name based on plugin's embedding model
        vector_name = "text"
        if plugin_handler is not None:
            emb_model = plugin_handler.get_embedding_model()
            if emb_model is not None:
                resolved = self.embedding_orchestrator.get_vector_name_for_model(emb_model)
                if resolved is not None:
                    vector_name = resolved

        # 6. Generate embeddings
        embeddings = self.embedding_orchestrator.embed_chunks(chunks, vector_name=vector_name)

        # 7. Build payloads
        _active_chunker = chunker if chunker is not None else self.chunker
        _has_chunk_meta = hasattr(_active_chunker, "get_chunk_metadata")

        vectors: list[dict[str, Any]] = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            payload = {
                "content": chunk.content,
                "file_path": str(chunk.file_path),
                "file_type": file_meta.file_type,
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "token_count": chunk.token_count,
                "embedding_model": self.embedding_orchestrator._model_names.get(vector_name, ""),
            }
            if _has_chunk_meta:
                try:
                    code_meta = _active_chunker.get_chunk_metadata(chunk)
                    if code_meta:
                        payload.update(code_meta)
                except Exception:
                    pass
            vec_value: Any = (
                {vector_name: embedding}
                if self.embedding_orchestrator.is_multi_model and self.collection_manager is None
                else embedding
            )
            vectors.append(
                {
                    "id": chunk.chunk_id,
                    "vector": vec_value,
                    "payload": payload,
                }
            )

        return FileProcessingResult(
            vectors=vectors,
            chunk_count=len(chunks),
            embeddings_created=len(embeddings),
            handler_name=handler_name,
        )

    def _store_routed_vectors(
        self,
        routed_vectors: dict[str, list[dict[str, Any]]],
        job: IndexingJob,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> None:
        """Upsert vectors to per-collection stores.

        Args:
            routed_vectors: ``{collection_name: [vector_dicts]}`` mapping.
            job: Active indexing job for error tracking.
            progress_callback: Optional progress callback.
        """
        assert self.collection_manager is not None

        total = sum(len(v) for v in routed_vectors.values())
        logger.info(
            "Storing %d vectors across %d collections: %s",
            total,
            len(routed_vectors),
            {k: len(v) for k, v in routed_vectors.items()},
        )

        stored = 0
        batch_size = 100
        for collection, vectors in routed_vectors.items():
            store = self.collection_manager.get_store(collection)
            try:
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i : i + batch_size]
                    store.vector_store.upsert(batch)
                    stored += len(batch)
                    if progress_callback:
                        progress_callback(stored, total, f"Storing vectors ({collection})")
            except Exception as e:
                logger.error(f"Error storing vectors to {collection}: {e}")
                job.files_errored += 1
                from krag.models.indexing_job import FileError

                job.error_summary.append(
                    FileError(
                        file_path=Path("."),
                        error_type="storage",
                        error_message=f"Failed to store to {collection}: {e}",
                    )
                )

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
            files_skipped_unchanged=0,
            files_skipped_other=0,
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
        all_vectors: list[dict[str, Any]] = []
        # Multi-collection: group vectors by collection for routed upsert
        routed_vectors: dict[str, list[dict[str, Any]]] = {}
        for i, file_metadata in enumerate(all_files):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(all_files), "Processing files")

                # Resolve plugin handler
                plugin_handler = None
                plugin_name: str | None = None
                if self.plugin_registry is not None:
                    plugin_handler = self.plugin_registry.get_handler_for_file(
                        file_metadata.file_path, context=self.plugin_context
                    )
                    if plugin_handler is not None:
                        plugin_name = getattr(
                            plugin_handler, "name", plugin_handler.__class__.__name__
                        )

                result = self._process_file(file_metadata, plugin_handler)

                if not result.success:
                    job.files_errored += 1
                    from krag.models.indexing_job import FileError

                    job.error_summary.append(
                        FileError(
                            file_path=file_metadata.file_path,
                            error_type="extraction",
                            error_message=result.error or "Unknown error",
                        )
                    )
                    continue

                if result.skipped or not result.vectors:
                    job.files_skipped_other += 1
                    continue

                # Route vectors to the correct collection (or single store)
                if self.collection_manager is not None:
                    collection = self.collection_manager.route_file(
                        file_metadata.file_path, plugin_name=plugin_name
                    )
                    routed_vectors.setdefault(collection, []).extend(result.vectors)
                else:
                    all_vectors.extend(result.vectors)

                job.chunks_generated += result.chunk_count
                job.embeddings_created += result.embeddings_created

                # Update file metadata with indexing details
                file_metadata.chunk_count = result.chunk_count
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
        if self.collection_manager is not None and routed_vectors:
            # Multi-collection: upsert to each collection's store
            self._store_routed_vectors(routed_vectors, job, progress_callback)
        elif all_vectors:
            logger.info(f"Storing {len(all_vectors)} vectors")

            try:
                # Store in batches of 100
                batch_size = 100
                total_batches = (len(all_vectors) + batch_size - 1) // batch_size

                for batch_idx, i in enumerate(range(0, len(all_vectors), batch_size), 1):
                    batch = all_vectors[i : i + batch_size]
                    self.vector_store.upsert(batch)

                    # Update progress after each batch
                    if progress_callback:
                        vectors_stored = min(i + batch_size, len(all_vectors))
                        progress_callback(
                            vectors_stored,
                            len(all_vectors),
                            f"Storing vectors ({batch_idx}/{total_batches} batches)",
                        )

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
            f"{job.files_skipped_other} skipped (other), {job.files_errored} errors"
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
        job.files_skipped_unchanged = len(unchanged_changes)

        logger.info(
            f"Change detection: {job.files_added} new, {job.files_modified} modified, "
            f"{job.files_deleted} deleted, {job.files_skipped_unchanged} unchanged"
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

        # Stage 4b: Remove old vectors for modified files before re-indexing
        if modified_changes:
            logger.info(f"Removing old vectors for {len(modified_changes)} modified files")
            for change in modified_changes:
                try:
                    if self.collection_manager is not None:
                        # Multi-collection: delete from the routed collection
                        coll = self.collection_manager.route_file(
                            change.file_path, plugin_name=None
                        )
                        store = self.collection_manager.get_store(coll)
                        store.vector_store.delete_by_filter({"file_path": str(change.file_path)})
                    else:
                        self.vector_store.delete_by_filter({"file_path": str(change.file_path)})
                except Exception as e:
                    logger.warning(f"Failed to remove old vectors for {change.file_path}: {e}")

        # Stage 5: Process new/modified files
        all_vectors: list[dict[str, Any]] = []
        routed_vectors: dict[str, list[dict[str, Any]]] = {}
        for i, file_metadata in enumerate(files_to_process):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(files_to_process), "Processing files")

                # Resolve plugin handler
                plugin_handler = None
                plugin_name: str | None = None
                if self.plugin_registry is not None:
                    plugin_handler = self.plugin_registry.get_handler_for_file(
                        file_metadata.file_path, context=self.plugin_context
                    )
                    if plugin_handler is not None:
                        plugin_name = getattr(
                            plugin_handler, "name", plugin_handler.__class__.__name__
                        )

                result = self._process_file(file_metadata, plugin_handler)

                if not result.success:
                    job.files_errored += 1
                    from krag.models.indexing_job import FileError

                    job.error_summary.append(
                        FileError(
                            file_path=file_metadata.file_path,
                            error_type="extraction",
                            error_message=result.error or "Unknown error",
                        )
                    )
                    continue

                if result.skipped or not result.vectors:
                    job.files_skipped_other += 1
                    continue

                # Route vectors to the correct collection (or single store)
                if self.collection_manager is not None:
                    collection = self.collection_manager.route_file(
                        file_metadata.file_path, plugin_name=plugin_name
                    )
                    routed_vectors.setdefault(collection, []).extend(result.vectors)
                else:
                    all_vectors.extend(result.vectors)

                job.chunks_generated += result.chunk_count
                job.embeddings_created += result.embeddings_created

                # Update file metadata with indexing details
                file_metadata.chunk_count = result.chunk_count
                file_metadata.last_indexed_at = datetime.now()

                job.files_processed += 1
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
        if self.collection_manager is not None and routed_vectors:
            self._store_routed_vectors(routed_vectors, job, progress_callback)
        elif all_vectors:
            logger.info(f"Storing {len(all_vectors)} vectors")

            try:
                # Store in batches of 100
                batch_size = 100
                total_batches = (len(all_vectors) + batch_size - 1) // batch_size

                for batch_idx, i in enumerate(range(0, len(all_vectors), batch_size), 1):
                    batch = all_vectors[i : i + batch_size]
                    self.vector_store.upsert(batch)

                    # Update progress after each batch
                    if progress_callback:
                        vectors_stored = min(i + batch_size, len(all_vectors))
                        progress_callback(
                            vectors_stored,
                            len(all_vectors),
                            f"Storing vectors ({batch_idx}/{total_batches} batches)",
                        )

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
            f"{job.files_deleted} deleted, {job.files_skipped_unchanged} unchanged, "
            f"{job.files_skipped_other} skipped (other), "
            f"{job.chunks_generated} chunks, {job.embeddings_created} embeddings"
        )

        # T053: Output failure summary if there were plugin failures
        if self.failure_collector is not None and self.failure_collector.total_failures() > 0:
            failure_summary = self.failure_collector.format_summary()
            logger.warning(f"\n{failure_summary}")

        # Save metadata for next incremental run
        self._save_metadata()

        return job
