"""Eval command for krag CLI.

Runs evaluation queries from a TOML file and reports results.
JSON report → stdout, human summary → stderr.
Exit code 0 if all pass, 1 if any fail.
"""

import sys
from pathlib import Path

import typer

from krag.cli.utils import exit_with_code


def eval_command(
    eval_file: Path = typer.Argument(..., help="Path to TOML evaluation file"),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    preset: str | None = typer.Option(
        None,
        "--preset",
        "-p",
        help="Prompt preset name (strict, balanced, verbose)",
    ),
    top_k: int | None = typer.Option(
        None,
        "--top-k",
        "-k",
        help="Number of results to retrieve",
    ),
) -> None:
    """Run evaluation queries and report results.

    Loads test cases from a TOML file, runs each query through the
    RAG pipeline, and evaluates expected checks.

    JSON report → stdout (machine-parseable)
    Human summary → stderr

    Exit code: 0 = all pass, 1 = any fail.

    Example:
        krag eval tests/eval-queries.toml
        krag eval eval.toml --preset strict --top-k 10
    """
    try:
        from krag.config.settings import ConfigManager
        from krag.evaluation.loader import EvalLoadError, load_eval_file
        from krag.evaluation.reporter import format_json, format_summary, generate_report
        from krag.evaluation.runner import EvalRunner

        # Load evaluation queries
        try:
            queries = load_eval_file(eval_file)
        except EvalLoadError as e:
            print(f"Error loading eval file: {e}", file=sys.stderr)
            exit_with_code(1)

        if not queries:
            print("No queries found in eval file.", file=sys.stderr)
            exit_with_code(1)

        # Load configuration
        config_manager = ConfigManager()
        if config_path:
            config = config_manager.load(config_path)
        else:
            default_config_path = Path.home() / ".config" / "krag" / "config.toml"
            if default_config_path.exists():
                config = config_manager.load(default_config_path)
            else:
                print("No configuration found. Run 'krag init' first.", file=sys.stderr)
                exit_with_code(1)

        # Initialize pipeline components
        from krag.embeddings.generator import EmbeddingGenerator
        from krag.embeddings.orchestrator import EmbeddingOrchestrator
        from krag.orchestration.query_engine import QueryEngine
        from krag.storage.qdrant_impl import QdrantVectorStore
        from krag.synthesis.llm_client import LLMClient

        embedding_generator = EmbeddingGenerator(
            model_name=config.embedding_model,
            device=config.embedding_device,
        )

        # Build orchestrator with plugin embedding models (enables named-vector search)
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

        # Initialize vector store — use named vectors config when multi-model
        _vs_kwargs: dict = {
            "storage_path": str(config.vector_store_path),
            "collection_name": config.collection_name,
            "vector_size": embedding_generator.get_dimension(),
        }
        if embedding_orchestrator.is_multi_model:
            _vs_kwargs["vectors_config"] = embedding_orchestrator.get_vector_config()
        vector_store = QdrantVectorStore(**_vs_kwargs)

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

        active_preset = preset if preset else config.prompt_preset
        effective_top_k = top_k if top_k else config.top_k

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

        # Run evaluation
        print(f"Running {len(queries)} evaluation queries...", file=sys.stderr)
        runner = EvalRunner(query_engine=query_engine)
        results = runner.run(queries)

        # Generate report
        report = generate_report(results)

        # JSON to stdout (machine-parseable)
        print(format_json(report))

        # Summary to stderr (human-readable)
        print(format_summary(report), file=sys.stderr)

        # Exit code: 0 = all pass, 1 = any fail
        if report.failed > 0:
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        print(f"Eval failed: {e}", file=sys.stderr)
        raise typer.Exit(1) from e
