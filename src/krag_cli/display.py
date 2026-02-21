"""Rich display formatting for query results.

T024: Provides consistent Rich output matching the existing krag CLI style.
Supports TEXT, JSON, and MARKDOWN output formats.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from krag.config.path_reducer import PathReducer

console = Console()


class OutputFormat(str, Enum):  # noqa: UP042
    """Output format for CLI display.

    Inherits from str for Typer compatibility.
    """

    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


def display_query_response(
    result: dict[str, Any],
    *,
    show_sources: bool = True,
    output_format: OutputFormat = OutputFormat.TEXT,
    path_aliases: list[str] | None = None,
) -> None:
    """Display a query response with answer and sources.

    Args:
        result: Raw query response dict from KragClient.
        show_sources: Whether to show source information.
        output_format: Output format (text, json, markdown).
        path_aliases: Path alias strings for PathReducer.
    """
    answer = result.get("answer", "")
    sources = result.get("sources", []) if show_sources else []
    debug = result.get("debug")

    if output_format == OutputFormat.JSON:
        _display_json(result, sources, show_sources, path_aliases)
    elif output_format == OutputFormat.MARKDOWN:
        _display_markdown(answer, sources, path_aliases)
    else:
        _display_text(answer, sources, path_aliases)

    if debug:
        _display_debug(debug)


def display_retrieve_response(
    sources: list[dict[str, Any]],
    *,
    output_format: OutputFormat = OutputFormat.TEXT,
    path_aliases: list[str] | None = None,
) -> None:
    """Display retrieval-only results (no LLM synthesis).

    Args:
        sources: List of source chunk dicts from KragClient.
        output_format: Output format (text, json, markdown).
        path_aliases: Path alias strings for PathReducer.
    """
    reducer = PathReducer(path_aliases)

    if output_format == OutputFormat.JSON:
        output = {
            "sources": [
                {
                    "file_path": reducer.reduce(s.get("file_path", "")),
                    "source_ref": _format_source_ref(s),
                    "chunk_content": s.get("chunk_content", ""),
                    "score": s.get("score", 0.0),
                    "rank": s.get("rank", 0),
                }
                for s in sources
            ]
        }
        console.print(json.dumps(output, indent=2))
        return

    if output_format == OutputFormat.MARKDOWN:
        output = "# Results (retrieval only)\n\n"
        for s in sources:
            ref = _format_source_ref(s)
            score = s.get("score", 0.0)
            content = s.get("chunk_content", "")
            output += f"### {ref} (score: {score:.3f})\n\n```\n{content}\n```\n\n"
        console.print(Markdown(output))
        return

    # TEXT format
    console.print("[cyan]Results (retrieval only):[/cyan]")
    console.print("━" * 80)

    for s in sources:
        rank = s.get("rank", 0)
        score = s.get("score", 0.0)
        file_path = reducer.reduce(s.get("file_path", ""))
        content = s.get("chunk_content", "")

        console.print(f"\n{rank}. [yellow]Score: {score:.4f}[/yellow]")
        console.print(f"   [cyan]Source:[/cyan] {file_path}")
        preview = content[:500] + "..." if len(content) > 500 else content
        console.print(f"\n   {preview}")
        console.print()


# ── Private helpers ──────────────────────────────


def _display_text(
    answer: str,
    sources: list[dict[str, Any]],
    path_aliases: list[str] | None,
) -> None:
    """Display TEXT format output with Rich Panel."""
    reducer = PathReducer(path_aliases)

    console.print()
    console.print(
        Panel(
            answer,
            title="Answer",
            border_style="green",
            padding=(1, 2),
        )
    )

    if sources:
        console.print("\n[bold]Sources:[/bold]\n")
        for s in sources:
            rank = s.get("rank", 0)
            score = s.get("score", 0.0)
            ref = _format_source_ref(s)
            file_path = reducer.reduce(s.get("file_path", ""))

            if ref != file_path:
                # We have a meaningful source ref (function/class info)
                console.print(f"  [cyan]{rank}.[/cyan] {ref} [dim](score: {score:.3f})[/dim]")
            else:
                console.print(f"  [cyan]{rank}.[/cyan] {file_path} [dim](score: {score:.3f})[/dim]")
    console.print()


def _display_json(
    result: dict[str, Any],
    sources: list[dict[str, Any]],
    show_sources: bool,
    path_aliases: list[str] | None,
) -> None:
    """Display JSON format output."""
    reducer = PathReducer(path_aliases)

    output = {
        "answer": result.get("answer", ""),
        "sources": [
            {
                "file_path": reducer.reduce(s.get("file_path", "")),
                "source_ref": _format_source_ref(s),
                "chunk_content": s.get("chunk_content", ""),
                "score": s.get("score", 0.0),
                "rank": s.get("rank", 0),
            }
            for s in sources
        ]
        if show_sources
        else [],
    }

    if result.get("debug"):
        output["debug"] = result["debug"]

    console.print(json.dumps(output, indent=2))


def _display_markdown(
    answer: str,
    sources: list[dict[str, Any]],
    path_aliases: list[str] | None,
) -> None:
    """Display Markdown format output."""
    output = f"# Answer\n\n{answer}\n\n"

    if sources:
        output += "## Sources\n\n"
        for s in sources:
            ref = _format_source_ref(s)
            score = s.get("score", 0.0)
            content = s.get("chunk_content", "")
            output += f"### {ref} (score: {score:.3f})\n\n```\n{content}\n```\n\n"

    console.print(Markdown(output))


def _display_debug(debug: dict[str, Any]) -> None:
    """Display debug metadata."""
    console.print()
    console.print("[bold]Debug:[/bold]")
    for key, value in debug.items():
        console.print(f"  {key}: {value}")


def _format_source_ref(source: dict[str, Any]) -> str:
    """Format a source reference string from a source chunk dict.

    Mirrors QueryResult.format_source_ref() but works with raw dicts.
    """
    from pathlib import Path

    file_path = source.get("file_path", "")
    filename = Path(file_path).name if file_path else "unknown"

    class_name = source.get("class_name")
    function_name = source.get("function_name")
    start_line = source.get("start_line")
    end_line = source.get("end_line")

    # Build symbol part
    if class_name and function_name:
        symbol = f"{class_name}.{function_name}()"
    elif function_name:
        symbol = f"{function_name}()"
    elif class_name:
        symbol = class_name
    else:
        symbol = None

    # Build line part
    if start_line is not None and end_line is not None:
        line_ref = f":L{start_line}-L{end_line}"
    elif start_line is not None:
        line_ref = f":L{start_line}"
    else:
        line_ref = ""

    file_ref = f"{filename}{line_ref}"

    if symbol:
        return f"{symbol} at {file_ref}"
    return file_ref
