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

        # Run evaluation
        print(f"Running {len(queries)} evaluation queries...", file=sys.stderr)
        runner = EvalRunner(query_engine=pipeline.query_engine)
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
