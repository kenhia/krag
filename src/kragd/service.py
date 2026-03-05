"""Central service object for kragd.

Manages lifecycle of all heavyweight components (embeddings, vector store,
LLM pool, query engine) and provides the unified interface that API route
handlers delegate to.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from uuid import uuid4

from kragd.schemas import (
    CollectionStatus,
    DebugMetadata,
    DebugQueryRequest,
    DebugQueryResponse,
    HealthResponse,
    IndexRequest,
    IndexResponse,
    QdrantSearchRequest,
    QdrantSearchResponse,
    QdrantSearchResult,
    QueryRequest,
    QueryResponse,
    RetrieveRequest,
    ServiceStatus,
    SourceChunk,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from krag.models.configuration import Configuration, ModeConfiguration


class KragService:
    """Central service managing heavyweight component lifecycle.

    Must call ``await start()`` before any query/retrieve/status methods.
    Call ``await shutdown()`` for clean teardown.
    """

    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.service_config = config.service

        # Component references — populated by start()
        self.embedding_generator = None
        self.embedding_orchestrator = None
        self.vector_store = None
        self.collection_manager = None
        self.llm_pool = None
        self.query_engine = None
        self.lifecycle_manager = None
        self.mode_registry = None
        self.lexicon_store = None
        self._last_index_job: IndexResponse | None = None
        self._index_job_cache: list[IndexResponse] = []
        self._max_index_cache: int = 10

        # Indexing state — protected by _indexing_lock
        self._indexing: bool = False
        self._indexing_lock = threading.Lock()

        # SSE index event streaming (US5)
        self._index_event_subscribers: list[asyncio.Queue] = []
        self._index_subscribers_lock = threading.Lock()

        # Mode hot-reload TTL (seconds) to avoid reloading on every request
        self._mode_reload_interval: float = 5.0
        self._mode_last_reload: float = 0.0
        self._mode_lock = threading.Lock()

        # Lifecycle state
        self._started: bool = False
        self._start_time: float | None = None

    # ── guards ──────────────────────────────────

    def _require_started(self) -> None:
        """Raise ServiceNotReadyError if service is not started."""
        if not self._started:
            from krag.models.exceptions import ServiceNotReadyError

            raise ServiceNotReadyError("Service not started — call start() first")

    def _require_not_indexing(self) -> None:
        """Raise IndexingInProgressError if indexing is currently in progress."""
        if self._indexing:
            from krag.models.exceptions import IndexingInProgressError

            raise IndexingInProgressError(
                "Indexing is in progress — queries are unavailable until indexing completes. "
                "Use 'krag index-status' to check progress."
            )

    # ── SSE index event streaming (US5) ─────────

    def _broadcast_index_event(self, event: dict) -> None:
        """Push an event to all active SSE subscribers (thread-safe)."""
        with self._index_subscribers_lock:
            dead: list[asyncio.Queue] = []
            for q in self._index_event_subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._index_event_subscribers.remove(q)

    async def subscribe_index_events(self) -> AsyncGenerator[dict, None]:
        """Async generator that yields index events for an SSE client.

        If no indexing is in progress, yields a single ``index:idle``
        event and returns.  Otherwise yields events until the stream
        sees ``index:complete`` or ``index:error``.
        """
        with self._indexing_lock:
            is_indexing = self._indexing

        if not is_indexing:
            yield {"type": "index:idle", "data": {"message": "No active indexing job"}}
            return

        queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=256)
        with self._index_subscribers_lock:
            self._index_event_subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
                if event.get("type") in ("index:complete", "index:error"):
                    break
        finally:
            with self._index_subscribers_lock:
                if queue in self._index_event_subscribers:
                    self._index_event_subscribers.remove(queue)

    # ── lifecycle ───────────────────────────────

    async def start(self) -> None:
        """Initialize all heavyweight components and write PID file."""
        logger.info("══ KRAGD STARTING ══")
        self._init_embeddings()
        self._init_collection_manager()
        self._init_vector_store()
        self._init_llm_pool()
        self._init_lifecycle_manager()
        self._init_lexicon_store()
        self._init_query_engine()
        self._init_mode_registry()
        self._started = True
        self._start_time = time.monotonic()

        # Write PID file
        from kragd.pid import get_pid_path, write_pid

        self._pid_path = get_pid_path()
        write_pid(self._pid_path)
        logger.info("══ KRAGD READY ══")

    async def shutdown(self) -> None:
        """Release all resources and remove PID file. Safe to call multiple times."""
        if not self._started:
            return
        logger.info("══ KRAGD SHUTTING DOWN ══")
        # Cancel idle timer before closing pool
        if self.lifecycle_manager is not None:
            self.lifecycle_manager._cancel_timer()
        if self.llm_pool is not None:
            self.llm_pool.close()
        if self.collection_manager is not None:
            self.collection_manager.close()
        if self.vector_store is not None:
            self.vector_store.close()
        self._started = False

        # Remove PID file
        from kragd.pid import remove_pid

        if hasattr(self, "_pid_path") and self._pid_path is not None:
            remove_pid(self._pid_path)

    # ── component init (patchable in tests) ─────

    def _init_embeddings(self) -> None:
        """Load embedding models (including plugin-declared models)."""
        from krag.embeddings.generator import EmbeddingGenerator
        from krag.embeddings.orchestrator import EmbeddingOrchestrator

        self.embedding_generator = EmbeddingGenerator(
            model_name=self.config.embedding_model,
            device=self.config.embedding_device,
        )
        self.embedding_orchestrator = EmbeddingOrchestrator(
            default_model=self.config.embedding_model,
            device=self.config.embedding_device,
            additional_models=(
                {"code": self.config.embedding_code_model}
                if self.config.embedding_code_model
                else None
            ),
        )

        # Register plugin-declared embedding models (e.g. code plugin)
        if self.config.plugins is not None:
            from krag.plugins.registry import PluginRegistry

            registry = PluginRegistry(self.config.plugins)
            registry.discover_plugins()
            for meta in registry.list_plugins(filter_status="enabled"):
                handler = registry.load_plugin(meta.name)
                if handler is not None:
                    em = getattr(handler, "get_embedding_model", lambda: None)()
                    if em:
                        self.embedding_orchestrator.register_model(meta.name, em)

    def _init_vector_store(self) -> None:
        """Open legacy single-collection vector store.

        When the ``CollectionManager`` is available its shared
        ``QdrantClient`` is reused so only one file-lock is held.
        """
        from krag.storage.qdrant_impl import QdrantVectorStore

        shared_client = (
            self.collection_manager._client if self.collection_manager is not None else None
        )
        self.vector_store = QdrantVectorStore(
            collection_name=self.config.collection_name,
            vector_size=self.embedding_generator.get_dimension(),
            storage_path=str(self.config.vector_store_path),
            distance=self.config.distance_metric,
            client=shared_client,
        )

    def _init_collection_manager(self) -> None:
        """Create multi-collection manager with shared Qdrant client.

        Sets up four content-type collections (code, tests, docs, text)
        managed by a single ``QdrantClient`` to avoid local-mode lock
        conflicts.
        """
        from pathlib import Path

        from krag.routing.collection_router import CollectionRouter
        from krag.storage.collection_manager import CollectionManager

        self.collection_manager = CollectionManager(
            storage_path=Path(self.config.vector_store_path),
            vector_size=self.embedding_generator.get_dimension(),
            router=CollectionRouter(),
            distance=self.config.distance_metric,
        )

    def _init_llm_pool(self) -> None:
        """Load LLM pool (may be None if no model configured)."""
        from pathlib import Path

        from krag.synthesis.llm_pool import LLMPool

        model = self.config.llm_model
        if not model:
            self.llm_pool = None
            return

        self.llm_pool = LLMPool(
            text_model_path=Path(model),
            code_model_path=Path(self.config.llm_code_model)
            if self.config.llm_code_model
            else None,
            load_multi_llm=self.config.load_multi_llm,
            n_ctx=self.config.llm_context_size,
            n_gpu_layers=self.config.llm_n_gpu_layers,
        )

    def _init_query_engine(self) -> None:
        """Wire up the query engine."""
        from krag.orchestration.query_engine import QueryEngine

        if self.llm_pool is None:
            return

        self.query_engine = QueryEngine(
            vector_store=self.vector_store,
            embedding_generator=self.embedding_generator,
            llm_client=self.llm_pool.text_llm_client,
            top_k=self.config.top_k,
            path_aliases=self.config.path_aliases or None,
            preset_name=self.config.prompt_preset,
            system_prompt_override=self.config.prompt_system_override,
            similarity_threshold=self.config.similarity_threshold,
            embedding_orchestrator=self.embedding_orchestrator,
            lexicon_store=self.lexicon_store,
        )

    def _init_lifecycle_manager(self) -> None:
        """Wire up LLM lifecycle manager if pool is available."""
        if self.llm_pool is None:
            return

        from kragd.lifecycle import LLMLifecycleManager

        self.lifecycle_manager = LLMLifecycleManager(
            pool=self.llm_pool,
            idle_timeout=getattr(self.service_config, "idle_timeout", 300),
            primary_llm=getattr(self.service_config, "primary_llm", "text"),
        )

        # Try to set the event loop (available during lifespan startup)
        import asyncio

        try:
            self.lifecycle_manager._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    # ── helpers ─────────────────────────────────

    def _init_mode_registry(self) -> None:
        """Initialize the mode registry with builtins and optional user modes."""
        from krag.modes.mode_registry import ModeRegistry

        self.mode_registry = ModeRegistry()
        self.mode_registry.load_builtins()
        if self.config.modes_dir:
            self.mode_registry.load_user_modes(self.config.modes_dir)

    def _init_lexicon_store(self) -> None:
        """Initialize the lexicon store if a lexicon path is configured."""
        lexicon_path = self.config.lexicon_path
        if not lexicon_path:
            return

        from pathlib import Path

        from krag.lexicon.lexicon_store import LexiconStore

        self.lexicon_store = LexiconStore()
        try:
            count = self.lexicon_store.load(Path(lexicon_path))
            logger.info("Loaded lexicon with %d entries from %s", count, lexicon_path)
        except Exception:
            logger.warning("Failed to load lexicon from %s", lexicon_path, exc_info=True)
            self.lexicon_store = None

    def _resolve_mode(self, mode_name: str | None) -> ModeConfiguration | None:
        """Resolve a mode name to its ModeConfiguration, or None.

        User modes are reloaded from disk periodically (every
        ``_mode_reload_interval`` seconds) so that edits to TOML files
        take effect without restarting kragd, while avoiding redundant
        filesystem reads on every request.
        """
        if mode_name is None or self.mode_registry is None:
            return None

        # TTL-gated hot-reload: only touch disk when the interval expires
        if self.config.modes_dir:
            now = time.monotonic()
            if now - self._mode_last_reload > self._mode_reload_interval:
                if self._mode_lock.acquire(blocking=False):
                    try:
                        self.mode_registry.load_user_modes(self.config.modes_dir)
                        self._mode_last_reload = now
                    finally:
                        self._mode_lock.release()

        return self.mode_registry.get(mode_name)

    def _get_mode_infos(self) -> list:
        """Build ModeInfo list for status endpoint."""
        from kragd.schemas import ModeInfo

        if self.mode_registry is None:
            return []
        return [
            ModeInfo(
                name=m.name,
                description=m.description,
                collections=sorted(m.collections.keys()),
                llm_slot=m.llm_slot,
                preset=m.preset,
            )
            for m in self.mode_registry.list_modes()
        ]

    def _get_collection_counts(self) -> dict[str, int]:
        """Return per-collection vector counts from the CollectionManager.

        Returns an empty dict when no collection manager is configured.
        """
        if self.collection_manager is None:
            return {}
        counts: dict[str, int] = {}
        try:
            for name, stats in self.collection_manager.get_all_stats().items():
                counts[name] = int(stats.get("vectors_count", 0) or stats.get("count", 0) or 0)
        except Exception:
            logger.warning("Failed to get per-collection counts", exc_info=True)
        return counts

    def refresh_lexicon(self) -> dict[str, int | str]:
        """Reload the lexicon from disk.

        Returns:
            Dict with 'entries' count and 'status' message.

        Raises:
            RuntimeError: If no lexicon is configured.
        """
        self._require_started()

        if self.lexicon_store is None:
            from krag.models.exceptions import ResourceNotConfiguredError

            raise ResourceNotConfiguredError(
                "lexicon", "No lexicon configured — set lexicon_path in configuration"
            )

        try:
            count = self.lexicon_store.reload()
            # Update the query engine's lexicon store reference (in case it was None before)
            if self.query_engine is not None:
                self.query_engine.lexicon_store = self.lexicon_store
                if self.query_engine._lexicon_injector is None:
                    from krag.lexicon.lexicon_injector import LexiconInjector

                    self.query_engine._lexicon_injector = LexiconInjector()
            return {"entries": count, "status": "reloaded"}
        except Exception as exc:
            logger.error("Failed to reload lexicon: %s", exc, exc_info=True)
            from krag.models.exceptions import KragError

            raise KragError(f"Failed to reload lexicon: {exc}") from exc

    # ── public API ──────────────────────────────

    def query(self, request: QueryRequest) -> QueryResponse:
        """Execute a full RAG query with LLM synthesis.

        When ``request.include_debug`` is True the response contains
        populated :class:`DebugMetadata`; otherwise ``debug`` is None.
        Both paths follow the same retrieval → critic → synthesis pipeline.
        """
        self._require_started()
        self._require_not_indexing()

        if self.query_engine is None:
            from krag.models.exceptions import ResourceNotConfiguredError

            raise ResourceNotConfiguredError(
                "LLM", "No LLM model configured — cannot synthesize answers"
            )

        # Resolve mode — mode settings provide defaults, explicit params override
        mode_config = self._resolve_mode(request.mode)
        include_debug = request.include_debug

        # Determine which LLM slot will be used for lifecycle tracking
        slot = request.llm or (mode_config.llm_slot if mode_config else None) or "text"
        if self.lifecycle_manager is not None:
            self.lifecycle_manager.ensure_loaded(slot)
            self.lifecycle_manager.on_request_start(slot)

        try:
            from krag.retrieval.retriever import Retriever

            top_k = (
                request.top_k or (mode_config.top_k if mode_config else None) or self.config.top_k
            )
            threshold = (
                mode_config.similarity_threshold if mode_config else None
            ) or self.config.similarity_threshold

            # Phase 1: Retrieval (with optional timing)
            t0 = time.monotonic()
            retriever = Retriever(
                vector_store=self.vector_store,
                embedding_generator=self.embedding_generator,
                embedding_orchestrator=self.embedding_orchestrator,
                collection_manager=self.collection_manager,
            )
            results = retriever.retrieve(
                query=request.query,
                top_k=top_k,
                similarity_threshold=threshold,
            )
            retrieval_ms = (time.monotonic() - t0) * 1000

            # Collect retrieval statistics
            total_before = getattr(retriever, "_last_total_before_dedup", len(results))
            total_after = len(results)

            # Apply context relevance critic if enabled (per-request override or mode config)
            critic_scores: list[int] = []
            chunks_pre_critic = len(results)
            chunks_post_critic = len(results)

            want_critic = (
                request.critic_enabled
                if request.critic_enabled is not None
                else (mode_config.critic_enabled if mode_config else False)
            )
            if want_critic and results:
                from krag.critic.relevance_critic import RelevanceCritic

                critic_threshold = (
                    request.critic_threshold
                    if request.critic_threshold is not None
                    else (mode_config.critic_threshold if mode_config else 3)
                )
                critic_slot = self.llm_pool._slot_for(slot)
                critic_llm = critic_slot.instance
                critic = RelevanceCritic(
                    llm_client=critic_llm,
                    threshold=critic_threshold,
                    enabled=True,
                )
                scored = critic.score_chunks(request.query, results)
                critic_scores = [s.critic_score for s in scored]
                results = critic.filter_chunks(scored)
                chunks_post_critic = len(results)
                logger.info(
                    "Critic: %d/%d chunks passed (threshold %d)",
                    chunks_post_critic,
                    chunks_pre_critic,
                    critic_threshold,
                )

            # Match lexicon terms for prompt injection
            lexicon_glossary: str | None = None
            lexicon_terms_count = 0
            if self.lexicon_store is not None:
                from krag.lexicon.lexicon_injector import LexiconInjector

                matches = self.lexicon_store.match_terms(request.query)
                if matches:
                    injector = LexiconInjector()
                    selected = injector.select_top(matches)
                    lexicon_glossary = injector.format_glossary(selected)
                    lexicon_terms_count = len(selected)

            # Handle all-chunks-filtered-by-critic case (T061)
            if chunks_pre_critic > 0 and chunks_post_critic == 0:
                from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE

                logger.info("All chunks filtered by critic — returning insufficient context")

                debug = None
                if include_debug:
                    effective_llm = request.llm or (mode_config.llm_slot if mode_config else None)
                    auto_routed = effective_llm is None
                    debug = DebugMetadata(
                        llm_used="none",
                        llm_model="none",
                        route="none",
                        auto_routed=auto_routed,
                        route_reason="All chunks filtered by critic",
                        preset=request.preset
                        or (mode_config.preset if mode_config else None)
                        or self.config.prompt_preset
                        or "default",
                        mode=request.mode,
                        collections_searched=sorted(mode_config.collections.keys())
                        if mode_config
                        else None,
                        retrieval_time_ms=round(retrieval_ms, 2),
                        generation_time_ms=0.0,
                        embedding_models_used=list(
                            self.embedding_orchestrator._model_names.values()
                        )
                        if self.embedding_orchestrator is not None
                        else [self.config.embedding_model],
                        vector_spaces_searched=[],
                        total_candidates_before_dedup=total_before,
                        total_candidates_after_dedup=total_after,
                        similarity_threshold=threshold,
                        per_space_result_counts={},
                        lexicon_terms_injected=lexicon_terms_count,
                        critic_scores=critic_scores,
                        chunks_pre_critic=chunks_pre_critic,
                        chunks_post_critic=0,
                    )
                return QueryResponse(
                    answer=INSUFFICIENT_CONTEXT_PHRASE,
                    sources=[],
                    debug=debug,
                )

            # Phase 2: LLM generation with timing
            effective_llm = request.llm or (mode_config.llm_slot if mode_config else None)
            t1 = time.monotonic()
            response_text, route_name = self.llm_pool.route_and_generate(
                messages=self.query_engine.prompt_builder.build(
                    request.query, results, lexicon_glossary=lexicon_glossary
                ),
                retrieved_chunks=results,
                llm_override=effective_llm,
            )
            generation_ms = (time.monotonic() - t1) * 1000

            # Build source chunks
            sources = [
                SourceChunk(
                    chunk_id=str(getattr(s, "chunk_id", "")),
                    file_path=str(s.file_path),
                    score=s.score,
                    rank=i + 1,
                    chunk_content=s.chunk_content,
                    file_type=getattr(s, "file_type", ""),
                    language=getattr(s, "language", None),
                    function_name=getattr(s, "function_name", None),
                    class_name=getattr(s, "class_name", None),
                    start_line=getattr(s, "start_line", None),
                    end_line=getattr(s, "end_line", None),
                    collection=getattr(s, "collection", None),
                )
                for i, s in enumerate(results)
            ]

            # Build debug metadata only when requested
            debug = None
            if include_debug:
                auto_routed = effective_llm is None
                route_slot = self.llm_pool._slot_for(route_name)

                # Collect vector space info
                vector_spaces: list[str] = []
                per_space_counts: dict[str, int] = {}
                retriever_per_space = getattr(retriever, "_last_per_space_counts", None)
                if retriever_per_space:
                    vector_spaces = list(retriever_per_space.keys())
                    per_space_counts = dict(retriever_per_space)
                else:
                    if self.vector_store is not None:
                        try:
                            import warnings

                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", UserWarning)
                                qdrant_info = self.vector_store.client.get_collection(
                                    self.vector_store.collection_name
                                )
                            vectors_cfg = qdrant_info.config.params.vectors
                            if isinstance(vectors_cfg, dict):
                                vector_spaces = list(vectors_cfg.keys())
                        except Exception:
                            logger.warning(
                                "Failed to introspect vector spaces from Qdrant",
                                exc_info=True,
                            )
                    if not vector_spaces:
                        vector_spaces = ["default"]
                    for space in vector_spaces:
                        per_space_counts[space] = total_before

                debug = DebugMetadata(
                    llm_used=route_name,
                    llm_model=str(route_slot.model_path) if route_slot.model_path else "unknown",
                    route=route_name,
                    auto_routed=auto_routed,
                    route_reason=None
                    if not auto_routed
                    else "Auto-routed based on chunk composition",
                    preset=request.preset
                    or (mode_config.preset if mode_config else None)
                    or self.config.prompt_preset
                    or "default",
                    mode=request.mode,
                    collections_searched=sorted(mode_config.collections.keys())
                    if mode_config
                    else None,
                    retrieval_time_ms=round(retrieval_ms, 2),
                    generation_time_ms=round(generation_ms, 2),
                    embedding_models_used=list(self.embedding_orchestrator._model_names.values())
                    if self.embedding_orchestrator is not None
                    else [self.config.embedding_model],
                    vector_spaces_searched=vector_spaces,
                    total_candidates_before_dedup=total_before,
                    total_candidates_after_dedup=total_after,
                    similarity_threshold=threshold,
                    per_space_result_counts=per_space_counts,
                    lexicon_terms_injected=lexicon_terms_count,
                    critic_scores=critic_scores,
                    chunks_pre_critic=chunks_pre_critic,
                    chunks_post_critic=chunks_post_critic,
                )

            return QueryResponse(
                answer=response_text,
                sources=sources,
                debug=debug,
            )
        finally:
            if self.lifecycle_manager is not None:
                self.lifecycle_manager.on_request_end(slot)

    def retrieve(self, request: RetrieveRequest) -> list[SourceChunk]:
        """Retrieve chunks without LLM synthesis."""
        self._require_started()
        self._require_not_indexing()

        from krag.retrieval.retriever import Retriever

        # Resolve mode settings
        mode_config = self._resolve_mode(request.mode)

        retriever = Retriever(
            vector_store=self.vector_store,
            embedding_generator=self.embedding_generator,
            embedding_orchestrator=self.embedding_orchestrator,
            collection_manager=self.collection_manager,
        )
        top_k = request.top_k or (mode_config.top_k if mode_config else None) or self.config.top_k
        threshold = (
            mode_config.similarity_threshold if mode_config else None
        ) or self.config.similarity_threshold
        results = retriever.retrieve(
            query=request.query,
            top_k=top_k,
            similarity_threshold=threshold,
        )
        return [
            SourceChunk(
                chunk_id=str(getattr(r, "chunk_id", "")),
                file_path=str(r.file_path),
                score=r.score,
                rank=i + 1,
                chunk_content=r.chunk_content,
                file_type=getattr(r, "file_type", ""),
                collection=getattr(r, "collection", None),
                language=getattr(r, "language", None),
                function_name=getattr(r, "function_name", None),
                class_name=getattr(r, "class_name", None),
                start_line=getattr(r, "start_line", None),
                end_line=getattr(r, "end_line", None),
            )
            for i, r in enumerate(results)
        ]

    async def query_stream(self, request: QueryRequest) -> AsyncGenerator[dict, None]:
        """Stream a RAG query answer via SSE events.

        Performs the same retrieval pipeline as :meth:`query` but streams
        the LLM generation token-by-token.  Yields dicts with ``type``
        and ``data`` keys matching the SSE event contract.

        Event sequence:
            1. ``query:sources`` — retrieved chunks (sent once)
            2. ``query:token``   — one per token delta from LLM
            3. ``query:done``    — complete answer + sources
            4. ``query:error``   — on any failure (may replace 2–3)
        """
        import asyncio
        import concurrent.futures

        self._require_started()
        self._require_not_indexing()

        if self.query_engine is None:
            from krag.models.exceptions import ResourceNotConfiguredError

            raise ResourceNotConfiguredError(
                "LLM", "No LLM model configured — cannot synthesize answers"
            )

        mode_config = self._resolve_mode(request.mode)
        slot = request.llm or (mode_config.llm_slot if mode_config else None) or "text"

        if self.lifecycle_manager is not None:
            self.lifecycle_manager.ensure_loaded(slot)
            self.lifecycle_manager.on_request_start(slot)

        try:
            from krag.retrieval.retriever import Retriever

            top_k = (
                request.top_k or (mode_config.top_k if mode_config else None) or self.config.top_k
            )
            threshold = (
                mode_config.similarity_threshold if mode_config else None
            ) or self.config.similarity_threshold

            retriever = Retriever(
                vector_store=self.vector_store,
                embedding_generator=self.embedding_generator,
                embedding_orchestrator=self.embedding_orchestrator,
                collection_manager=self.collection_manager,
            )
            results = retriever.retrieve(
                query=request.query,
                top_k=top_k,
                similarity_threshold=threshold,
            )

            # Apply critic if enabled (per-request override or mode config)
            want_critic = (
                request.critic_enabled
                if request.critic_enabled is not None
                else (mode_config.critic_enabled if mode_config else False)
            )
            if want_critic and results:
                from krag.critic.relevance_critic import RelevanceCritic

                critic_threshold = (
                    request.critic_threshold
                    if request.critic_threshold is not None
                    else (mode_config.critic_threshold if mode_config else 3)
                )
                critic_slot = self.llm_pool._slot_for(slot)
                critic_llm = critic_slot.instance
                critic = RelevanceCritic(
                    llm_client=critic_llm,
                    threshold=critic_threshold,
                    enabled=True,
                )
                scored = critic.score_chunks(request.query, results)
                results = critic.filter_chunks(scored)

            # Match lexicon terms
            lexicon_glossary: str | None = None
            if self.lexicon_store is not None:
                from krag.lexicon.lexicon_injector import LexiconInjector

                matches = self.lexicon_store.match_terms(request.query)
                if matches:
                    injector = LexiconInjector()
                    selected = injector.select_top(matches)
                    lexicon_glossary = injector.format_glossary(selected)

            # Build source chunks
            sources = [
                SourceChunk(
                    chunk_id=str(getattr(s, "chunk_id", "")),
                    file_path=str(s.file_path),
                    score=s.score,
                    rank=i + 1,
                    chunk_content=s.chunk_content,
                    file_type=getattr(s, "file_type", ""),
                    language=getattr(s, "language", None),
                    function_name=getattr(s, "function_name", None),
                    class_name=getattr(s, "class_name", None),
                    start_line=getattr(s, "start_line", None),
                    end_line=getattr(s, "end_line", None),
                    collection=getattr(s, "collection", None),
                )
                for i, s in enumerate(results)
            ]

            # Yield sources event
            yield {
                "type": "query:sources",
                "data": {"sources": [s.model_dump() for s in sources]},
            }

            # Handle all-filtered case
            if not results:
                from krag.synthesis.prompt_builder import INSUFFICIENT_CONTEXT_PHRASE

                yield {
                    "type": "query:done",
                    "data": {
                        "answer": INSUFFICIENT_CONTEXT_PHRASE,
                        "sources": [s.model_dump() for s in sources],
                        "debug": None,
                    },
                }
                return

            # Build messages for LLM
            messages = self.query_engine.prompt_builder.build(
                request.query, results, lexicon_glossary=lexicon_glossary
            )
            effective_llm = request.llm or (mode_config.llm_slot if mode_config else None)

            # Stream tokens from LLM via thread-to-async bridge
            token_iter, _route = self.llm_pool.route_and_stream(
                messages=messages,
                retrieved_chunks=results,
                llm_override=effective_llm,
            )

            loop = asyncio.get_running_loop()
            token_queue: asyncio.Queue[str | None] = asyncio.Queue()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            def _consume_tokens() -> None:
                """Run in thread: iterate sync token stream, push to async queue."""
                try:
                    for token in token_iter:
                        asyncio.run_coroutine_threadsafe(token_queue.put(token), loop).result()
                finally:
                    asyncio.run_coroutine_threadsafe(token_queue.put(None), loop).result()

            future = loop.run_in_executor(executor, _consume_tokens)

            full_answer_parts: list[str] = []
            while True:
                token = await token_queue.get()
                if token is None:
                    break
                full_answer_parts.append(token)
                yield {"type": "query:token", "data": {"token": token}}

            # Wait for the thread to finish cleanly
            await asyncio.wrap_future(future)

            yield {
                "type": "query:done",
                "data": {
                    "answer": "".join(full_answer_parts),
                    "sources": [s.model_dump() for s in sources],
                    "debug": None,
                },
            }

        except Exception as exc:
            logger.error("query_stream failed: %s", exc, exc_info=True)
            yield {"type": "query:error", "data": {"error": str(exc)}}
        finally:
            if self.lifecycle_manager is not None:
                self.lifecycle_manager.on_request_end(slot)

    def debug_query(self, request: DebugQueryRequest) -> DebugQueryResponse:
        """Execute a query with full debug metadata.

        Thin wrapper around :meth:`query` with ``include_debug=True``.
        """
        query_request = QueryRequest(
            query=request.query,
            top_k=request.top_k,
            preset=request.preset,
            llm=request.llm,
            mode=request.mode,
            include_debug=True,
            critic_enabled=request.critic_enabled,
            critic_threshold=request.critic_threshold,
        )
        result = self.query(query_request)
        return DebugQueryResponse(
            answer=result.answer,
            sources=result.sources,
            debug=result.debug,
        )

    def debug_qdrant(self, request: QdrantSearchRequest) -> QdrantSearchResponse:
        """Raw vector store search bypassing Retriever (R-09).

        No dedup, boost, or RRF. Returns raw similarity scores.
        """
        self._require_started()

        if self.vector_store is None:
            from krag.models.exceptions import ResourceNotConfiguredError

            raise ResourceNotConfiguredError("vector_store", "Vector store not initialized")
        if self.embedding_generator is None:
            from krag.models.exceptions import ResourceNotConfiguredError

            raise ResourceNotConfiguredError(
                "embedding_generator", "Embedding generator not initialized"
            )

        # Generate query embedding using the appropriate model for the space
        if request.vector_space and self.embedding_orchestrator is not None:
            embeddings = self.embedding_orchestrator.embed_query(request.query)
            if request.vector_space in embeddings:
                query_vector = embeddings[request.vector_space]
            else:
                query_vector = self.embedding_generator.generate_single(request.query)
        else:
            query_vector = self.embedding_generator.generate_single(request.query)

        # Build Qdrant filter if specified
        qdrant_filter = None
        if request.filters:
            from qdrant_client.models import FieldCondition, Filter, MatchText, MatchValue

            must_conditions: list = []
            must_not_conditions: list = []
            if request.filters.file_type:
                must_conditions.append(
                    FieldCondition(
                        key="file_type",
                        match=MatchValue(value=request.filters.file_type),
                    )
                )
            if request.filters.file_path_contains:
                must_conditions.append(
                    FieldCondition(
                        key="file_path",
                        match=MatchText(text=request.filters.file_path_contains),
                    )
                )
            if request.filters.file_path_excludes:
                for pattern in request.filters.file_path_excludes:
                    must_not_conditions.append(
                        FieldCondition(
                            key="file_path",
                            match=MatchText(text=pattern),
                        )
                    )
            if must_conditions or must_not_conditions:
                qdrant_filter = Filter(
                    must=must_conditions or None,
                    must_not=must_not_conditions or None,
                )

        # Direct Qdrant search (bypass Retriever)
        # When collection_manager is available, search typed collections
        # (where data is actually stored) instead of the primary collection
        # which may be empty in multi-collection mode.

        all_points: list = []
        if self.collection_manager is not None:
            for store_obj in self.collection_manager.get_all_stores():
                coll_kwargs: dict = {
                    "collection_name": store_obj.collection_name,
                    "query": query_vector,
                    "limit": request.top_k,
                    "with_payload": request.with_payload,
                    "score_threshold": request.score_threshold,
                }
                if request.vector_space and store_obj.vector_store.is_named_vectors:
                    coll_kwargs["using"] = request.vector_space
                elif store_obj.vector_store.is_named_vectors:
                    coll_kwargs["using"] = "text"
                if qdrant_filter:
                    coll_kwargs["query_filter"] = qdrant_filter
                try:
                    raw = store_obj.vector_store.client.query_points(**coll_kwargs)
                    all_points.extend(raw.points)
                except Exception:
                    logger.debug(
                        "debug_qdrant: skipping collection '%s' (%s)",
                        store_obj.name,
                        store_obj.collection_name,
                        exc_info=True,
                    )
            # Sort by score descending across all collections, take top_k
            all_points.sort(key=lambda p: p.score, reverse=True)
            all_points = all_points[: request.top_k]
        else:
            search_kwargs: dict = {
                "collection_name": self.config.collection_name,
                "query": query_vector,
                "limit": request.top_k,
                "with_payload": request.with_payload,
                "score_threshold": request.score_threshold,
            }

            if request.vector_space:
                search_kwargs["using"] = request.vector_space
            elif self.vector_store.is_named_vectors:
                search_kwargs["using"] = "text"

            if qdrant_filter:
                search_kwargs["query_filter"] = qdrant_filter

            raw_results = self.vector_store.client.query_points(**search_kwargs)
            all_points = list(raw_results.points)

        results = []
        for point in all_points:
            payload = point.payload or {}
            results.append(
                QdrantSearchResult(
                    chunk_id=str(point.id),
                    score=point.score,
                    file_path=payload.get("file_path", ""),
                    file_type=payload.get("file_type", ""),
                    chunk_content=payload.get("chunk_content", "") if request.with_payload else "",
                    chunk_index=payload.get("chunk_index", 0),
                    start_line=payload.get("start_line"),
                    end_line=payload.get("end_line"),
                )
            )

        return QdrantSearchResponse(
            results=results,
            total_results=len(results),
            vector_space=request.vector_space,
        )

    def index(self, request: IndexRequest) -> IndexResponse:
        """Validate and start indexing in background.

        Returns immediately with a 'running' status response.
        The actual indexing runs in a background thread. Use
        GET /index/status to poll for completion.
        """
        self._require_started()

        with self._indexing_lock:
            if self._indexing:
                from krag.models.exceptions import IndexingInProgressError

                raise IndexingInProgressError(
                    "Indexing is already in progress — use 'krag index-status' to check progress"
                )
            self._indexing = True

        # Create an immediate "running" response
        job_id = str(uuid4())
        running_response = IndexResponse(
            job_id=job_id,
            status="running",
            mode=request.mode,
            files_scanned=0,
            files_processed=0,
            files_skipped=0,
            files_skipped_unchanged=0,
            files_skipped_other=0,
            files_errored=0,
            chunks_created=0,
            vectors_stored=0,
            duration_seconds=0.0,
            dry_run=request.dry_run,
            errors=[],
        )
        with self._indexing_lock:
            self._last_index_job = running_response

        # Start background thread
        thread = threading.Thread(
            target=self._run_indexing,
            args=(request, job_id),
            name="kragd-indexing",
            daemon=True,
        )
        thread.start()

        return running_response

    def _run_indexing(self, request: IndexRequest, job_id: str) -> None:
        """Execute indexing in background thread.

        Updates _last_index_job and _index_job_cache on completion.
        Clears _indexing flag when done (success or failure).
        """

        from kragd.schemas import IndexingFileError

        t0 = time.monotonic()

        from krag.orchestration.indexer import IndexingOrchestrator

        # Pause the lifecycle idle timer to prevent it from firing during
        # indexing — the LLM will be closed and reloaded, so the timer
        # must not attempt to swap/unload while that happens.
        if self.lifecycle_manager is not None:
            self.lifecycle_manager.pause()

        # Temporarily unload the LLM to free VRAM for embedding models.
        # The code embedding model may have been skipped at startup due to
        # insufficient VRAM while the LLM was loaded.
        llm_was_loaded = None  # track which LLM(s) to restore
        if self.llm_pool is not None:
            llm_was_loaded = self.llm_pool.get_active_llm()
            if llm_was_loaded:
                logger.info("Unloading LLM to free VRAM for indexing embeddings")
                self.llm_pool.close()

        # Apply request overrides (directories, file_types, exclusions) to a
        # copy of the config so the service's base config stays unchanged.
        index_config = self.config
        overrides: dict = {}
        if request.directories:
            from pathlib import Path

            overrides["directory_paths"] = [Path(d) for d in request.directories]
        if request.file_types:
            overrides["supported_file_types"] = request.file_types
        if request.exclude_patterns:
            overrides["exclusion_patterns"] = (
                list(self.config.exclusion_patterns) + request.exclude_patterns
            )
        if overrides:
            index_config = self.config.model_copy(update=overrides)

        # Build orchestrator with service's pre-loaded components,
        # sharing the existing vector store to avoid Qdrant local-mode lock conflicts
        orchestrator = IndexingOrchestrator(
            config=index_config,
            vector_store=self.vector_store,
            collection_manager=self.collection_manager,
        )

        try:
            is_full = request.mode == "full"

            # SSE progress callback — broadcasts to all SSE subscribers
            def _progress_callback(current: int, total: int, stage: str) -> None:
                self._broadcast_index_event(
                    {
                        "type": "index:progress",
                        "data": {"current": current, "total": total, "stage": stage},
                    }
                )

            if is_full:
                job = orchestrator.index_full(progress_callback=_progress_callback)
            else:
                job = orchestrator.index_incremental(progress_callback=_progress_callback)

            duration = time.monotonic() - t0

            errors = [
                IndexingFileError(
                    file_path=str(e.file_path),
                    error_type=e.error_type,
                    error_message=e.error_message,
                )
                for e in (job.error_summary or [])
            ]

            response = IndexResponse(
                job_id=job_id,
                status=job.status.value if hasattr(job.status, "value") else str(job.status),
                mode=request.mode,
                files_scanned=job.files_discovered,
                files_processed=job.files_processed,
                files_skipped=job.files_skipped,
                files_skipped_unchanged=job.files_skipped_unchanged,
                files_skipped_other=job.files_skipped_other,
                files_errored=job.files_errored,
                chunks_created=job.chunks_generated,
                vectors_stored=job.embeddings_created,
                duration_seconds=round(duration, 2),
                dry_run=request.dry_run,
                errors=errors,
                collections=self._get_collection_counts(),
            )

            with self._indexing_lock:
                self._last_index_job = response
                # Add to cache — drop oldest delivered entries if over limit
                self._index_job_cache.append(response)
                if len(self._index_job_cache) > self._max_index_cache:
                    self._index_job_cache = self._index_job_cache[-self._max_index_cache :]

            # Broadcast completion to SSE subscribers
            self._broadcast_index_event(
                {
                    "type": "index:complete",
                    "data": {
                        "job_id": job_id,
                        "status": response.status,
                        "files_processed": response.files_processed,
                        "duration_seconds": response.duration_seconds,
                    },
                }
            )
        except Exception as exc:
            logger.error("Indexing failed: %s", exc, exc_info=True)
            with self._indexing_lock:
                self._last_index_job = IndexResponse(
                    job_id=job_id,
                    status="failed",
                    mode=request.mode,
                    files_scanned=0,
                    files_processed=0,
                    files_skipped=0,
                    files_skipped_unchanged=0,
                    files_skipped_other=0,
                    files_errored=1,
                    chunks_created=0,
                    vectors_stored=0,
                    duration_seconds=round(time.monotonic() - t0, 2),
                    dry_run=request.dry_run,
                    errors=[
                        IndexingFileError(
                            file_path="<system>",
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    ],
                )
                self._index_job_cache.append(self._last_index_job)

            # Broadcast error to SSE subscribers
            self._broadcast_index_event(
                {
                    "type": "index:error",
                    "data": {
                        "job_id": job_id,
                        "error": str(exc),
                    },
                }
            )
        finally:
            orchestrator.close()

            # Reload the LLM now that indexing is done and embedding VRAM
            # can be reclaimed.
            if llm_was_loaded and self.llm_pool is not None:
                logger.info("Reloading LLM after indexing")
                try:
                    self._init_llm_pool()
                    # Re-wire query engine with fresh LLM client
                    if self.query_engine is not None and self.llm_pool is not None:
                        self.query_engine.llm_client = self.llm_pool.text_llm_client
                    # Re-wire lifecycle manager with new pool so hot-swap
                    # targets the correct LLM instances (not the old closed pool)
                    if self.lifecycle_manager is not None and self.llm_pool is not None:
                        self.lifecycle_manager._pool = self.llm_pool
                except Exception:
                    logger.warning(
                        "Failed to reload LLM after indexing — queries will be unavailable "
                        "until service restart",
                        exc_info=True,
                    )

            # Resume the lifecycle idle timer now that LLM is reloaded
            if self.lifecycle_manager is not None:
                self.lifecycle_manager.resume()

            # Always clear the indexing flag
            with self._indexing_lock:
                self._indexing = False

    def get_index_status(self) -> list[IndexResponse]:
        """Return cached indexing job results.

        Always returns a list of IndexResponse objects:
        - Empty list when no jobs have ever run
        - Single-element list for one job or active indexing
        - Multi-element list for concurrent/recent jobs

        Checks active indexing state first — returns a single-element
        list with 'running' status if indexing is in progress.
        After retrieval, marks results as delivered so they can be
        evicted when new jobs arrive.
        """
        self._require_started()

        # Check active indexing state first (US2 fix: running takes priority)
        with self._indexing_lock:
            is_indexing = self._indexing

        if is_indexing:
            return [
                IndexResponse(
                    job_id="pending",
                    status="running",
                    mode="incremental",
                    files_scanned=0,
                    files_processed=0,
                    files_skipped=0,
                    files_skipped_unchanged=0,
                    files_skipped_other=0,
                    files_errored=0,
                    chunks_created=0,
                    vectors_stored=0,
                    duration_seconds=0.0,
                    dry_run=False,
                    errors=[],
                )
            ]

        with self._indexing_lock:
            if not self._index_job_cache:
                return []

            # Return all cached results, then clear all but the most recent
            results = list(self._index_job_cache)
            # Keep only the most recent in cache
            self._index_job_cache = self._index_job_cache[-1:]

        return results

    def get_status(self) -> ServiceStatus:
        """Return service status including model info and uptime."""
        self._require_started()

        from kragd.schemas import LLMSlotStatus, VectorStoreStatus, VRAMStatus

        uptime = time.monotonic() - (self._start_time or time.monotonic())

        # Build LLM slot status
        llm_status: dict[str, LLMSlotStatus] = {}
        if self.llm_pool is not None:
            primary_llm = getattr(self.service_config, "primary_llm", "text") or "text"
            text_model = getattr(self.config, "llm_model", None)
            code_model = getattr(self.config, "llm_code_model", None)
            idle_timeout = getattr(self.service_config, "idle_timeout", None)

            # Use lifecycle manager for primary/timeout if available
            if self.lifecycle_manager is not None:
                lifecycle_status = self.lifecycle_manager.get_status()
                primary_llm = lifecycle_status.get("primary_llm") or primary_llm
                idle_timeout = lifecycle_status.get("idle_timeout_s", idle_timeout)

            if text_model:
                llm_status["text"] = LLMSlotStatus(
                    loaded=self.llm_pool._text_slot.is_loaded,
                    model=str(text_model),
                    primary=(primary_llm == "text"),
                    idle_timeout_s=None if primary_llm == "text" else idle_timeout,
                )
            if code_model:
                llm_status["code"] = LLMSlotStatus(
                    loaded=self.llm_pool._code_slot.is_loaded,
                    model=str(code_model),
                    primary=(primary_llm == "code"),
                    idle_timeout_s=None if primary_llm == "code" else idle_timeout,
                )

        # Vector store stats
        total_vectors = 0
        named_spaces: list[str] = []
        if self.vector_store is not None:
            try:
                info = self.vector_store.get_stats()
                # get_stats() returns a dict with 'count'/'vectors_count'
                total_vectors = info.get("vectors_count", 0) or info.get("count", 0) or 0
            except Exception:
                logger.warning("Failed to get vector store stats", exc_info=True)

            # Extract named vector spaces from the raw Qdrant collection config
            try:
                import warnings

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    qdrant_info = self.vector_store.client.get_collection(
                        self.vector_store.collection_name
                    )
                vectors_cfg = qdrant_info.config.params.vectors
                if isinstance(vectors_cfg, dict):
                    named_spaces = list(vectors_cfg.keys())
            except Exception:
                logger.warning(
                    "Failed to introspect named vector spaces from Qdrant",
                    exc_info=True,
                )

        # VRAM info
        vram = None
        try:
            from krag.cli.gpu import check_cuda_available

            gpu_info = check_cuda_available()
            if gpu_info.get("available"):
                vram_total = gpu_info.get("vram_total", 0)
                vram_free = gpu_info.get("vram_free", 0)
                vram = VRAMStatus(
                    total_mb=int(vram_total / 1024 / 1024) if vram_total else 0,
                    used_mb=int((vram_total - vram_free) / 1024 / 1024)
                    if vram_total and vram_free
                    else 0,
                    free_mb=int(vram_free / 1024 / 1024) if vram_free else 0,
                )
        except Exception:
            logger.debug("GPU/VRAM info unavailable", exc_info=True)

        # Per-collection stats
        collections: dict[str, CollectionStatus] = {}
        if self.collection_manager is not None:
            try:
                all_stats = self.collection_manager.get_all_stats()
                for coll_name, stats in all_stats.items():
                    vec_count = stats.get("vectors_count", 0) or stats.get("count", 0) or 0
                    coll_status = stats.get("status", "ok")
                    qdrant_name = stats.get("collection_name", coll_name)
                    collections[coll_name] = CollectionStatus(
                        collection_name=str(qdrant_name),
                        vectors_count=int(vec_count),
                        status=str(coll_status) if coll_status != "ok" else "ok",
                    )
            except Exception:
                logger.warning("Failed to get collection stats", exc_info=True)

        return ServiceStatus(
            version=_get_version(),
            uptime_seconds=uptime,
            llm=llm_status,
            embedding_models=[self.config.embedding_model],
            vector_store=VectorStoreStatus(
                collection=self.config.collection_name,
                total_vectors=total_vectors,
                named_spaces=named_spaces,
            ),
            collections=collections,
            modes=self._get_mode_infos(),
            lexicon_loaded=self.lexicon_store is not None,
            lexicon_entry_count=len(self.lexicon_store.entries) if self.lexicon_store else 0,
            vram=vram,
        )

    def get_health(self) -> HealthResponse:
        """Simple health check."""
        self._require_started()
        return HealthResponse(status="healthy", version=_get_version())


def _get_version() -> str:
    """Get krag package version."""
    try:
        from importlib.metadata import version

        return version("krag")
    except Exception:
        logger.debug("Could not determine krag package version", exc_info=True)
        return "0.0.0-dev"
