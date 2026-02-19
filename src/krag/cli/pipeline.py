"""CLI pipeline factory — single construction point for query/eval infrastructure."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from krag.config.xdg import get_krag_config_dir

if TYPE_CHECKING:
    from krag.embeddings.generator import EmbeddingGenerator
    from krag.embeddings.orchestrator import EmbeddingOrchestrator
    from krag.models.configuration import Configuration
    from krag.orchestration.query_engine import QueryEngine
    from krag.storage.qdrant_impl import QdrantVectorStore
    from krag.synthesis.llm_client import LLMClient
    from krag.synthesis.llm_pool import LLMPool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryPipeline:
    """Immutable bundle of fully-initialised query-pipeline components."""

    config: Configuration
    embedding_generator: EmbeddingGenerator
    embedding_orchestrator: EmbeddingOrchestrator
    vector_store: QdrantVectorStore
    llm_client: LLMClient
    llm_pool: LLMPool | None
    query_engine: QueryEngine
    effective_top_k: int


def resolve_config_path(explicit_path: Path | None = None) -> Path:
    """Resolve configuration file path using XDG conventions.

    Args:
        explicit_path: User-provided path. If given, returned as-is.

    Returns:
        Path to config file (config.toml or config.yaml).

    Raises:
        FileNotFoundError: If no config file found.
    """
    if explicit_path is not None:
        if not explicit_path.exists():
            raise FileNotFoundError(f"Config file not found: {explicit_path}")
        return explicit_path

    config_dir = get_krag_config_dir()
    for name in ("config.toml", "config.yaml"):
        candidate = config_dir / name
        if candidate.exists():
            return candidate

    # Legacy fallback
    legacy = Path.home() / ".config" / "krag" / "config.toml"
    if legacy.exists():
        return legacy

    raise FileNotFoundError(
        f"No configuration found. Expected at {config_dir / 'config.toml'}\n"
        "Run 'krag init' to create one."
    )


def build_query_pipeline(
    config_path: Path | None = None,
    top_k: int | None = None,
    preset: str | None = None,
) -> QueryPipeline:
    """Build the full query pipeline from configuration.

    Args:
        config_path: Explicit path to config file. If None, uses XDG-aware
            discovery via get_krag_config_dir().
        top_k: Number of results to retrieve. If None, uses config value.
        preset: Query preset name. If None, uses default.

    Returns:
        QueryPipeline with all components initialized.

    Raises:
        FileNotFoundError: If config file not found at resolved path.
        SystemExit: If vector store path does not exist (user-friendly message).
    """
    import sys

    from krag.config.settings import ConfigManager
    from krag.embeddings.generator import EmbeddingGenerator
    from krag.embeddings.orchestrator import EmbeddingOrchestrator
    from krag.orchestration.query_engine import QueryEngine
    from krag.storage.qdrant_impl import QdrantVectorStore
    from krag.synthesis.llm_client import LLMClient
    from krag.synthesis.llm_pool import LLMPool

    # 1. Resolve config path
    resolved_path = resolve_config_path(config_path)

    # 2. Load configuration
    config_manager = ConfigManager()
    config = config_manager.load(resolved_path)

    # 3. Vector store pre-check
    if not Path(config.vector_store_path).exists():
        print(
            "Error: No indexed data found. Run 'krag index' first.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # 4. Embedding generator
    embedding_generator = EmbeddingGenerator(
        model_name=config.embedding_model,
        device=config.embedding_device,
    )

    # 5. Embedding orchestrator + plugin models
    embedding_orchestrator = EmbeddingOrchestrator(
        default_model=config.embedding_model,
        device=config.embedding_device,
    )
    if config.plugins is not None:
        from krag.plugins.registry import PluginRegistry

        _registry = PluginRegistry(config.plugins)
        _registry.discover_plugins()
        for _meta in _registry.list_plugins(filter_status="enabled"):
            _handler = _registry.load_plugin(_meta.name)
            if _handler is not None:
                _em = getattr(_handler, "get_embedding_model", lambda: None)()
                if _em:
                    embedding_orchestrator.register_model(_meta.name, _em)

    # 6. Vector store (named vectors when multi-model)
    _vs_kwargs: dict = {
        "storage_path": str(config.vector_store_path),
        "collection_name": config.collection_name,
        "vector_size": embedding_generator.get_dimension(),
    }
    if embedding_orchestrator.is_multi_model:
        _vs_kwargs["vectors_config"] = embedding_orchestrator.get_vector_config()
    vector_store = QdrantVectorStore(**_vs_kwargs)

    # 7. LLM client
    llm_client = LLMClient(
        model=config.llm_model,
        max_tokens=2000,
        n_ctx=config.llm_context_size,
        n_threads=config.llm_num_threads,
        n_gpu_layers=config.llm_n_gpu_layers,
        temperature=config.llm_temperature,
        model_cache_path=config.model_cache_path,
        top_p=config.llm_top_p,
        repeat_penalty=config.llm_repeat_penalty,
        min_p=config.llm_min_p,
    )

    # 8. LLM pool (if code model configured)
    llm_pool: LLMPool | None = None
    if config.llm_code_model:
        code_path = Path(config.llm_code_model)
        llm_pool = LLMPool(
            text_model_path=Path(str(config.llm_model)),
            code_model_path=code_path,
            load_multi_llm=config.load_multi_llm,
            n_ctx=config.llm_context_size,
            n_gpu_layers=config.llm_n_gpu_layers,
            temperature=config.llm_temperature,
            max_tokens=2000,
            top_p=config.llm_top_p,
            repeat_penalty=config.llm_repeat_penalty,
            min_p=config.llm_min_p,
        )

    # 9. Effective top_k: CLI arg > config > default (5)
    effective_top_k = top_k if top_k is not None else config.top_k

    # 10. Active preset
    active_preset = preset if preset else config.prompt_preset

    # 11. Query engine
    query_engine = QueryEngine(
        vector_store=vector_store,
        embedding_generator=embedding_generator,
        llm_client=llm_client,
        top_k=effective_top_k,
        path_aliases=config.path_aliases,
        preset_name=active_preset,
        system_prompt_override=config.prompt_system_override,
        similarity_threshold=config.similarity_threshold,
        embedding_orchestrator=embedding_orchestrator,
    )

    return QueryPipeline(
        config=config,
        embedding_generator=embedding_generator,
        embedding_orchestrator=embedding_orchestrator,
        vector_store=vector_store,
        llm_client=llm_client,
        llm_pool=llm_pool,
        query_engine=query_engine,
        effective_top_k=effective_top_k,
    )
