"""CLI debug commands (debug query and debug qdrant).

T040/T044: `krag debug query "..."` and `krag debug qdrant "..."` subcommands.
"""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

debug_app = typer.Typer(
    name="debug",
    help="Debug commands for query analysis and raw vector search.",
    no_args_is_help=True,
)


@debug_app.command(name="query")
def debug_query_command(
    query: str = typer.Argument(..., help="Query text"),
    top_k: int | None = typer.Option(None, "--top-k", "-k", help="Number of results"),
    preset: str | None = typer.Option(None, "--preset", "-p", help="Prompt preset name"),
    mode: str | None = typer.Option(
        None, "--mode", "-m", help="Named retrieval mode (e.g. default, code, docs)"
    ),
    llm: str | None = typer.Option(None, "--llm", help="Force LLM: text or code"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Execute a query with full debug metadata.

    Shows answer, sources, and 14 debug fields including timings,
    routing decision, candidates, and vector spaces.
    """
    from krag_cli.main import _get_client

    client = _get_client(host, port, timeout=120.0)
    try:
        payload: dict[str, Any] = {"query": query}
        if top_k is not None:
            payload["top_k"] = top_k
        if preset is not None:
            payload["preset"] = preset
        if mode is not None:
            payload["mode"] = mode
        if llm is not None:
            payload["llm"] = llm

        result = client.post("/debug/query", json=payload)

        if output_json:
            console.print(json.dumps(result, indent=2))
            return

        # Display answer
        answer = result.get("answer", "")
        console.print(Panel(answer, title="[bold]Answer[/bold]", border_style="green"))

        # Display sources
        sources = result.get("sources", [])
        if sources:
            console.print(f"\n[bold]Sources[/bold] ({len(sources)} chunks):")
            for i, src in enumerate(sources, 1):
                path = src.get("file_path", "")
                score = src.get("score", 0)
                lines = ""
                if src.get("start_line"):
                    lines = f" L{src['start_line']}"
                    if src.get("end_line"):
                        lines += f"-{src['end_line']}"
                console.print(f"  {i}. {path}{lines} (score: {score:.3f})")

        # Display debug metadata
        debug = result.get("debug", {})
        if debug:
            _display_debug_panel(debug)

    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except RuntimeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


@debug_app.command(name="qdrant")
def debug_qdrant_command(
    query: str = typer.Argument(..., help="Query text"),
    space: str | None = typer.Option(None, "--space", "-s", help="Vector space name"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results"),
    threshold: float | None = typer.Option(
        None, "--threshold", "-t", help="Minimum similarity score"
    ),
    filter_type: str | None = typer.Option(None, "--filter-type", help="Filter by file_type"),
    filter_path: str | None = typer.Option(
        None, "--filter-path", help="Include only paths containing this substring"
    ),
    exclude_path: list[str] | None = typer.Option(
        None, "--exclude-path", "-x", help="Exclude paths containing this substring (repeatable)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    no_payload: bool = typer.Option(False, "--no-payload", help="Exclude chunk content"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Raw vector store search bypassing Retriever.

    Returns raw similarity scores without dedup, boost, or RRF.
    Useful for debugging retrieval quality and vector space content.
    """
    from krag_cli.main import _get_client

    client = _get_client(host, port, timeout=60.0)
    try:
        payload: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "with_payload": not no_payload,
        }
        if space is not None:
            payload["vector_space"] = space
        if threshold is not None:
            payload["score_threshold"] = threshold

        filters: dict[str, str] = {}
        if filter_type is not None:
            filters["file_type"] = filter_type
        if filter_path is not None:
            filters["file_path_contains"] = filter_path
        if exclude_path:
            filters["file_path_excludes"] = list(exclude_path)
        if filters:
            payload["filters"] = filters

        result = client.post("/debug/qdrant", json=payload)

        if output_json:
            console.print(json.dumps(result, indent=2))
            return

        # Display as Rich table
        total = result.get("total_results", 0)
        v_space = result.get("vector_space")
        title = f"Raw Qdrant Search ({total} results"
        if v_space:
            title += f", space: {v_space}"
        title += ")"

        table = Table(title=title)
        table.add_column("#", style="dim", width=4)
        table.add_column("Score", justify="right", width=8)
        table.add_column("File", style="cyan")
        table.add_column("Type", width=6)
        table.add_column("Lines", width=10)

        for i, r in enumerate(result.get("results", []), 1):
            lines = ""
            if r.get("start_line"):
                lines = f"{r['start_line']}"
                if r.get("end_line"):
                    lines += f"-{r['end_line']}"
            table.add_row(
                str(i),
                f"{r['score']:.4f}",
                r.get("file_path", ""),
                r.get("file_type", ""),
                lines,
            )

        console.print(table)

    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


def _display_debug_panel(debug: dict[str, Any]) -> None:
    """Display debug metadata in a Rich panel."""
    table = Table(title="Debug Metadata", show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    # Core routing info
    table.add_row("LLM Used", debug.get("llm_used", ""))
    table.add_row("LLM Model", debug.get("llm_model", ""))
    table.add_row("Route", debug.get("route", ""))
    table.add_row("Auto-Routed", str(debug.get("auto_routed", "")))
    if debug.get("route_reason"):
        table.add_row("Route Reason", debug["route_reason"])
    table.add_row("Preset", debug.get("preset", ""))

    # Timing
    retrieval_ms = debug.get("retrieval_time_ms", 0)
    generation_ms = debug.get("generation_time_ms", 0)
    table.add_row("Retrieval Time", f"{retrieval_ms:.1f} ms")
    table.add_row("Generation Time", f"{generation_ms:.1f} ms")
    table.add_row("Total Time", f"{retrieval_ms + generation_ms:.1f} ms")

    # Retrieval stats
    table.add_row("Embedding Models", ", ".join(debug.get("embedding_models_used", [])))
    table.add_row("Vector Spaces", ", ".join(debug.get("vector_spaces_searched", [])))
    table.add_row("Candidates (pre-dedup)", str(debug.get("total_candidates_before_dedup", "")))
    table.add_row("Candidates (post-dedup)", str(debug.get("total_candidates_after_dedup", "")))
    table.add_row("Similarity Threshold", str(debug.get("similarity_threshold", "")))

    # Per-space counts
    per_space = debug.get("per_space_result_counts", {})
    if per_space:
        counts = ", ".join(f"{k}: {v}" for k, v in per_space.items())
        table.add_row("Per-Space Counts", counts)

    console.print(table)
