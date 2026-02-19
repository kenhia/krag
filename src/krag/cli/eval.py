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
    llm: str | None = typer.Option(
        None,
        "--llm",
        help="LLM to use: 'text' (general) or 'code' (code-specialized). "
        "Per-query 'llm' field in the TOML file takes precedence.",
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
        from krag.cli.pipeline import build_query_pipeline
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

        # Build the full pipeline (config loading, embedding, vector store, LLM)
        pipeline = build_query_pipeline(
            config_path=config_path,
            top_k=top_k,
            preset=preset,
        )

        # If --llm is specified but no pool exists, try to create one.
        # Close the pipeline's standalone LLM first to free VRAM before
        # the pool loads its own copy of the text model.
        llm_pool = pipeline.llm_pool
        if llm and not llm_pool:
            from krag.synthesis.llm_pool import LLMPool

            config = pipeline.config
            code_path = Path(config.llm_code_model) if config.llm_code_model else None
            pipeline.llm_client.close()
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

        # Run evaluation
        print(f"Running {len(queries)} evaluation queries...", file=sys.stderr)
        runner = EvalRunner(
            query_engine=pipeline.query_engine,
            llm_pool=llm_pool,
            llm_override=llm,
        )
        results = runner.run(queries)

        # Generate report
        report = generate_report(results)

        # Clean up LLM pool if we used one
        if llm_pool is not None:
            llm_pool.close()

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
