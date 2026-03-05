"""Query command for krag CLI."""

import json
import logging
from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from krag.cli.utils import exit_with_code
from krag.config.path_reducer import PathReducer

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
    preset: str | None = typer.Option(
        None,
        "--preset",
        "-p",
        help="Prompt preset (strict, balanced, verbose, code). Overrides config file setting.",
    ),
    mode: str | None = typer.Option(
        None,
        "--mode",
        "-m",
        help="Named retrieval mode (e.g. default, code, docs). Bundles collections, LLM, preset.",
    ),
    llm: str | None = typer.Option(
        None,
        "--llm",
        help="[Deprecated — use --mode] LLM slot: 'text' or 'code'.",
        hidden=True,
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file (default: ~/.config/krag/config.toml)",
    ),
    critic: bool | None = typer.Option(
        None,
        "--critic/--no-critic",
        help="Enable/disable context relevance critic. Overrides mode default.",
    ),
    critic_threshold: int | None = typer.Option(
        None,
        "--critic-threshold",
        help="Minimum critic score (0–5). Overrides mode default.",
        min=0,
        max=5,
    ),
) -> None:
    """Query your personal knowledge base.

    Ask questions and get AI-synthesized answers from your indexed documents.

    Example:
        krag query "What are the key concepts in my notes?"
        krag query "Python async patterns" --top-k 10 --format json
    """
    try:
        from krag.cli.pipeline import build_query_pipeline

        pipeline = build_query_pipeline(
            config_path=config_path,
            top_k=top_k,
            preset=preset,
        )
        config = pipeline.config
        vector_store = pipeline.vector_store
        embedding_generator = pipeline.embedding_generator
        embedding_orchestrator = pipeline.embedding_orchestrator
        llm_pool = pipeline.llm_pool
        query_engine = pipeline.query_engine

        # ── Mode resolution ───────────────────────────────────────
        mode_config = None
        if mode:
            from krag.modes.mode_registry import ModeRegistry

            registry = ModeRegistry()
            registry.load_builtins()
            if config.modes_dir:
                registry.load_user_modes(config.modes_dir)
            mode_config = registry.get(mode)
            # Mode overrides top_k, preset, and llm slot
            top_k = mode_config.top_k
            if not preset:
                preset = mode_config.preset
            if not llm:
                llm = mode_config.llm_slot
            logger.info("Using mode '%s': preset=%s, llm=%s, top_k=%d", mode, preset, llm, top_k)

        # Wire critic: per-request override > mode config
        critic_inst = None
        want_critic = (
            critic
            if critic is not None
            else (mode_config.critic_enabled if mode_config else False)
        )
        if want_critic:
            from krag.critic.relevance_critic import RelevanceCritic

            effective_threshold = (
                critic_threshold
                if critic_threshold is not None
                else (mode_config.critic_threshold if mode_config else 3)
            )
            critic_inst = RelevanceCritic(
                llm_client=pipeline.llm_client,
                threshold=effective_threshold,
                enabled=True,
            )
            logger.info(
                "Critic enabled (threshold=%d)", effective_threshold
            )
            # Attach critic to query engine for standard path
            query_engine.critic = critic_inst

        # Override llm_pool if user explicitly requests --llm routing.
        # Close the pipeline's standalone LLM first to free VRAM.
        if llm and not llm_pool:
            from krag.synthesis.llm_pool import LLMPool

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

        # Validate query
        if not query or not query.strip():
            console.print("[red]Error:[/red] Query cannot be empty", style="bold")
            exit_with_code(1)

        # Determine prompt preset: CLI flag overrides config file
        active_preset = preset if preset else config.prompt_preset

        # Execute query
        # Log the command invocation for audit trail
        cmd_parts = ["krag", "query", f'"{query}"']
        if top_k != 5:
            cmd_parts.extend(["--top-k", str(top_k)])
        if no_synthesis:
            cmd_parts.append("--no-synthesis")
        if not show_sources:
            cmd_parts.append("--no-sources")
        if format != OutputFormat.TEXT:
            cmd_parts.extend(["--format", format])
        if config_path:
            cmd_parts.extend(["--config", str(config_path)])
        if preset:
            cmd_parts.extend(["--preset", preset])
        logger.info(f"Starting query command: {' '.join(cmd_parts)}")

        console.print(f"\n[bold]Query:[/bold] {query}\n")

        if no_synthesis:
            # Just retrieve, don't synthesize
            from krag.retrieval.retriever import Retriever

            retriever = Retriever(
                vector_store, embedding_generator, embedding_orchestrator=embedding_orchestrator
            )
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
            if llm_pool is not None:
                # Multi-LLM routing path
                from krag.retrieval.retriever import Retriever as SynthRetriever
                from krag.synthesis.prompt_builder import PromptBuilder

                retriever = SynthRetriever(
                    vector_store, embedding_generator, embedding_orchestrator=embedding_orchestrator
                )
                results = retriever.retrieve(
                    query,
                    top_k=top_k,
                    similarity_threshold=config.similarity_threshold,
                )

                # Apply critic filtering in multi-LLM path
                if critic_inst is not None and critic_inst.enabled and results:
                    scored = critic_inst.score_chunks(query, results)
                    results = critic_inst.filter_chunks(scored)

                if not results:
                    console.print(
                        Panel(
                            "No relevant results found for your query.",
                            title="💡 Answer",
                            border_style="yellow",
                        )
                    )
                    return

                # Determine route and auto-couple preset
                route = llm_pool.determine_route(results, override=llm)
                if preset:
                    active_preset = preset
                elif route == "code":
                    active_preset = "code"
                else:
                    active_preset = config.prompt_preset

                prompt_builder = PromptBuilder(
                    path_aliases=config.path_aliases,
                    preset_name=active_preset,
                    system_prompt_override=config.prompt_system_override,
                )

                # Lexicon injection for multi-LLM routing path
                lexicon_glossary = None
                if config.lexicon_path:
                    from krag.lexicon.lexicon_injector import LexiconInjector
                    from krag.lexicon.lexicon_store import LexiconStore

                    try:
                        _lex_store = LexiconStore()
                        _lex_store.load(config.lexicon_path)
                        _matches = _lex_store.match_terms(query)
                        if _matches:
                            _injector = LexiconInjector()
                            _selected = _injector.select_top(_matches)
                            lexicon_glossary = _injector.format_glossary(_selected)
                    except Exception:
                        logger.warning("Lexicon injection failed", exc_info=True)

                messages = prompt_builder.build(query, results, lexicon_glossary=lexicon_glossary)

                # Generate with spinner for potential hot-swap
                with console.status(
                    f"[bold green]Generating with {route} LLM...",
                    spinner="dots",
                ):
                    answer, llm_used = llm_pool.route_and_generate(
                        messages, results, llm_override=llm
                    )

                logger.info("Response generated by %s LLM", llm_used)

                from krag.orchestration.query_engine import QueryResponse

                response = QueryResponse(answer=answer, sources=results, query=query)
                llm_pool.close()
            else:
                response = query_engine.query(query, top_k=top_k)

            path_reducer = PathReducer(config.path_aliases)
            _display_full_response(response, show_sources, format, path_reducer)

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
    path_reducer: PathReducer,
) -> None:
    """Display complete query response with answer and sources.

    Args:
        response: QueryResponse object
        show_sources: Whether to show source information
        format: Output format
        path_reducer: Path reducer for display
    """
    if format == OutputFormat.JSON:
        output = {
            "query": response.query,
            "answer": response.answer,
            "sources": [
                {
                    "file_path": path_reducer.reduce(result.file_path),
                    "source_ref": result.format_source_ref(),
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
                source_ref = result.format_source_ref()
                output += f"### {source_ref} (score: {result.score:.3f})\n\n"
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
                source_ref = result.format_source_ref()
                console.print(
                    f"  [cyan]{result.rank}.[/cyan] {source_ref} "
                    f"[dim](score: {result.score:.3f})[/dim]"
                )
