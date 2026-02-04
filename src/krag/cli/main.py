"""Main CLI application using Typer."""

import logging

import typer
from rich.console import Console

from krag.cli.query import query_command

# Create Typer app
app = typer.Typer(
    name="krag",
    help="Personal RAG system for querying local knowledge base",
    add_completion=False,
)

# Add commands
app.command(name="query")(query_command)

# Console for rich output
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI.

    Args:
        verbose: Enable debug logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@app.callback()
def main_callback(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Configure global options for krag CLI."""
    setup_logging(verbose)


if __name__ == "__main__":
    app()
