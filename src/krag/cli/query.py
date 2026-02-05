"""Query command for krag CLI."""

import json
import logging
from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


class OutputFormat(StrEnum):
    """Output format options."""

    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


def query_command(
    query: str = typer.Argument(..., help="Question to ask your knowledge base"),
    top_k: int = typer.Option(
        5,
        "--top-k",
        "-k",
        help="Number of relevant chunks to retrieve",
        min=1,
        max=20,
    ),
    no_synthesis: bool = typer.Option(
        False,
        "--no-synthesis",
        help="Skip LLM synthesis, only show retrieved chunks",
    ),
    show_sources: bool = typer.Option(
        True,
        "--show-sources/--no-sources",
        help="Display source file information",
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.TEXT,
        "--format",
        "-f",
        help="Output format (text, json, markdown)",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file (default: ~/.config/krag/config.toml)",
    ),
) -> None:
    """Query your personal knowledge base.

    Ask questions and get AI-synthesized answers from your indexed documents.

    Example:
        krag query "What are the key concepts in my notes?"
        krag query "Python async patterns" --top-k 10 --format json
    """
    try:
        # Load configuration
        from krag.config.settings import ConfigManager

        config_manager = ConfigManager()
        if config_path:
            config = config_manager.load(config_path)
        else:
            # Use default config path
            default_config_path = Path.home() / ".config" / "krag" / "config.toml"
            if default_config_path.exists():
                config = config_manager.load(default_config_path)
            else:
                console.print(
                    Panel(
                        "[yellow]No configuration found![/yellow]\n\n"
                        "You need to create a configuration file first:\n"
                        f"  Default location: [cyan]{default_config_path}[/cyan]\n\n"
                        "Run initialization:\n"
                        "  [cyan]krag init[/cyan]",
                        title="⚠️  Configuration Required",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

        # Validate query
        if not query or not query.strip():
            console.print("[red]Error:[/red] Query cannot be empty", style="bold")
            raise typer.Exit(1)

        # Initialize components (will be implemented with US2 - indexing)
        # For now, provide helpful error message
        if not Path(config.storage_path).exists():
            console.print(
                Panel(
                    "[yellow]No indexed data found![/yellow]\n\n"
                    "You need to index your documents first:\n"
                    "  [cyan]krag index --full[/cyan]",
                    title="⚠️  Storage Not Found",
                    border_style="yellow",
                )
            )
            raise typer.Exit(1)

        # TODO: Initialize QueryEngine when vector store is implemented
        console.print(
            Panel(
                "[yellow]Query functionality requires implementing User Story 2 (Indexing).[/yellow]\n\n"
                "The query command is ready, but needs:\n"
                "  • Vector store implementation (Qdrant)\n"
                "  • Embedding generator (sentence-transformers)\n"
                "  • Indexed documents to search\n\n"
                "Run indexing first:\n"
                "  [cyan]krag index --full[/cyan]",
                title="🚧  Implementation In Progress",
                border_style="yellow",
            )
        )

        # Placeholder for actual implementation:
        """
        from krag.orchestration.query_engine import QueryEngine
        from krag.embeddings.generator import EmbeddingGenerator
        from krag.storage.qdrant_impl import QdrantVectorStore
        from krag.synthesis.llm_client import LLMClient

        # Initialize components
        vector_store = QdrantVectorStore(...)
        embedding_generator = EmbeddingGenerator(...)
        llm_client = LLMClient(...)

        query_engine = QueryEngine(
            vector_store=vector_store,
            embedding_generator=embedding_generator,
            llm_client=llm_client,
            top_k=config.top_k,
        )

        # Execute query
        response = query_engine.query(query, top_k=top_k)

        # Format and display output
        if no_synthesis:
            _display_sources_only(response.sources, format)
        else:
            _display_full_response(response, show_sources, format)
        """

    except typer.Exit:
        # Normal exit, don't log as error
        raise
    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[red]Error:[/red] {e}", style="bold")
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        console.print(f"[red]Error:[/red] {e}", style="bold")
        raise typer.Exit(1) from e


def _display_full_response(
    response,
    show_sources: bool,
    format: OutputFormat,
) -> None:
    """Display complete query response with answer and sources.

    Args:
        response: QueryResponse object
        show_sources: Whether to show source information
        format: Output format
    """
    if format == OutputFormat.JSON:
        output = {
            "query": response.query,
            "answer": response.answer,
            "sources": [
                {
                    "file_path": str(result.file_path),
                    "chunk_content": result.chunk_content,
                    "score": result.score,
                    "rank": result.rank,
                }
                for result in response.sources
            ]
            if show_sources
            else [],
        }
        console.print(json.dumps(output, indent=2))

    elif format == OutputFormat.MARKDOWN:
        output = f"# Answer\n\n{response.answer}\n\n"
        if show_sources and response.sources:
            output += "## Sources\n\n"
            for result in response.sources:
                output += f"### {result.file_path.name} (score: {result.score:.3f})\n\n"
                output += f"```\n{result.chunk_content}\n```\n\n"
        console.print(Markdown(output))

    else:  # TEXT format
        # Display answer
        console.print(
            Panel(
                response.answer,
                title="💡 Answer",
                border_style="green",
                padding=(1, 2),
            )
        )

        # Display sources if requested
        if show_sources and response.sources:
            console.print("\n[bold]📚 Sources:[/bold]\n")
            for result in response.sources:
                console.print(
                    f"  [cyan]{result.rank}.[/cyan] {result.file_path.name} "
                    f"[dim](score: {result.score:.3f})[/dim]"
                )


def _display_sources_only(
    sources,
    format: OutputFormat,
) -> None:
    """Display only retrieved sources without synthesis.

    Args:
        sources: List of QueryResult objects
        format: Output format
    """
    if format == OutputFormat.JSON:
        output = [
            {
                "file_path": str(result.file_path),
                "chunk_content": result.chunk_content,
                "score": result.score,
                "rank": result.rank,
            }
            for result in sources
        ]
        console.print(json.dumps(output, indent=2))

    elif format == OutputFormat.MARKDOWN:
        output = "# Retrieved Chunks\n\n"
        for result in sources:
            output += f"## {result.rank}. {result.file_path.name} (score: {result.score:.3f})\n\n"
            output += f"```\n{result.chunk_content}\n```\n\n"
        console.print(Markdown(output))

    else:  # TEXT format
        table = Table(title="Retrieved Chunks", show_header=True, header_style="bold")
        table.add_column("Rank", style="cyan", width=6)
        table.add_column("File", style="green")
        table.add_column("Score", style="yellow", width=8)
        table.add_column("Content Preview", style="white", width=60)

        for result in sources:
            preview = (
                result.chunk_content[:100] + "..."
                if len(result.chunk_content) > 100
                else result.chunk_content
            )
            table.add_row(
                str(result.rank),
                result.file_path.name,
                f"{result.score:.3f}",
                preview,
            )

        console.print(table)
