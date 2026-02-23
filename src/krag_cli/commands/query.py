"""CLI query command for krag service-backed mode.

T025: Implements `krag query` with --top-k, --preset, --llm,
--no-synthesis, --format, --debug flags.
"""

from __future__ import annotations

import typer
from rich.console import Console

from krag_cli.display import OutputFormat, display_query_response, display_retrieve_response

console = Console()


def query_command(
    query_text: str = typer.Argument(..., help="Query text"),
    top_k: int | None = typer.Option(None, "--top-k", "-k", help="Number of results"),
    preset: str | None = typer.Option(None, "--preset", "-p", help="Prompt preset"),
    mode: str | None = typer.Option(
        None, "--mode", "-m", help="Named retrieval mode (e.g. default, code, docs)"
    ),
    llm: str | None = typer.Option(
        None, "--llm", help="[Deprecated — use --mode] Force LLM slot (text/code)", hidden=True
    ),
    no_synthesis: bool = typer.Option(False, "--no-synthesis", "-n", help="Retrieve only, no LLM"),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--format", "-f", help="Output format"
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Include debug metadata"),
    show_sources: bool = typer.Option(True, "--sources/--no-sources", help="Show sources"),
    host: str | None = typer.Option(None, "--host", help="kragd host"),
    port: int | None = typer.Option(None, "--port", help="kragd port"),
) -> None:
    """Send a RAG query to kragd."""
    from krag_cli.client import KragClient
    from krag_cli.config import read_service_config

    if host is None or port is None:
        cfg_host, cfg_port = read_service_config()
        host = host or cfg_host
        port = port or cfg_port

    client = KragClient(host=host, port=port, timeout=120.0)
    try:
        # Get path aliases for display
        path_aliases = _get_path_aliases()

        if no_synthesis:
            # Retrieval only
            kwargs: dict = {}
            if top_k is not None:
                kwargs["top_k"] = top_k
            if mode is not None:
                kwargs["mode"] = mode

            sources = client.retrieve(query_text, **kwargs)
            display_retrieve_response(
                sources,
                output_format=output_format,
                path_aliases=path_aliases,
            )
        else:
            # Full RAG query
            kwargs = {}
            if top_k is not None:
                kwargs["top_k"] = top_k
            if preset is not None:
                kwargs["preset"] = preset
            if mode is not None:
                kwargs["mode"] = mode
            if llm is not None:
                kwargs["llm"] = llm
            if debug:
                kwargs["include_debug"] = True

            result = client.query(query_text, **kwargs)
            display_query_response(
                result,
                show_sources=show_sources,
                output_format=output_format,
                path_aliases=path_aliases,
            )

    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except RuntimeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        client.close()


def _get_path_aliases() -> list[str] | None:
    """Load path aliases from krag config (best-effort)."""
    try:
        from krag.config.settings import ConfigManager

        config = ConfigManager.find_and_load()
        return config.path_aliases
    except Exception:
        return None
