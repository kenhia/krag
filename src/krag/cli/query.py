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

from krag.cli.utils import exit_with_code

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
                exit_with_code(1)

        # Validate query
        if not query or not query.strip():
            console.print("[red]Error:[/red] Query cannot be empty", style="bold")
            exit_with_code(1)

        # Initialize components
        if not Path(config.vector_store_path).exists():
            console.print(
                Panel(
                    "[yellow]No indexed data found![/yellow]\n\n"
                    "You need to index your documents first:\n"
                    "  [cyan]krag index[/cyan]",
                    title="⚠️  Storage Not Found",
                    border_style="yellow",
                )
            )
            exit_with_code(1)

        from krag.embeddings.generator import EmbeddingGenerator
        from krag.orchestration.query_engine import QueryEngine
        from krag.storage.qdrant_impl import QdrantVectorStore
        from krag.synthesis.llm_client import LLMClient

        # Initialize embedding generator first (to get dimension)
        embedding_generator = EmbeddingGenerator(
            model_name=config.embedding_model,
            device=config.embedding_device,
        )

        # Initialize vector store with embedding dimension
        vector_store = QdrantVectorStore(
            storage_path=str(config.vector_store_path),
            collection_name=config.collection_name,
            vector_size=embedding_generator.get_dimension(),
        )

        # Initialize LLM client (if synthesis is needed)
        llm_client = None
        if not no_synthesis:
            llm_client = LLMClient(
                model_path=str(config.llm_model_path),
                max_tokens=2000,
            )

        # Initialize query engine
        query_engine = QueryEngine(
            vector_store=vector_store,
            embedding_generator=embedding_generator,
            llm_client=llm_client,
            top_k=top_k,
        )

        # Execute query
        console.print(f"\n[bold]Query:[/bold] {query}\n")

        if no_synthesis:
            # Just retrieve, don't synthesize
            from krag.retrieval.retriever import Retriever

            retriever = Retriever(vector_store, embedding_generator)
            results = retriever.retrieve(query, top_k=top_k)

            console.print("[cyan]📄 Results (retrieval only):[/cyan]")
            console.print("━" * 80)

            for idx, result in enumerate(results, 1):
                console.print(f"\n{idx}. [yellow]Score: {result.score:.4f}[/yellow]")
                console.print(f"   [cyan]📁 Source:[/cyan] {result.file_path}")
                console.print(f"\n   {result.chunk_content[:500]}...")
                console.print()
        else:
            # Full query with synthesis
            response = query_engine.query(query, top_k=top_k)
            _display_full_response(response, show_sources, format)

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
