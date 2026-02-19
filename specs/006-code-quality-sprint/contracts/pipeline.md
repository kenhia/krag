# Contract: CLI Pipeline Factory

**Module**: `src/krag/cli/pipeline.py`
**Consumers**: `cli/query.py`, `cli/eval.py`

## Functions

### `build_query_pipeline`

Constructs the full query/eval infrastructure from config. Single point of construction for all shared components.

```python
def build_query_pipeline(
    config_path: Path | None = None,
    top_k: int | None = None,
    preset: str | None = None,
) -> QueryPipeline:
    """Build the full query pipeline from configuration.

    Args:
        config_path: Explicit path to config file. If None, uses XDG-aware
            discovery via get_krag_config_dir().
        top_k: Number of results to retrieve. If None, uses config value.
        preset: Query preset name. If None, uses default.

    Returns:
        QueryPipeline with all components initialized.

    Raises:
        FileNotFoundError: If config file not found at resolved path.
        SystemExit: If vector store path does not exist (user-friendly message).
    """
```

**Behavior**:
1. Resolve config path via `get_krag_config_dir()` (XDG-aware)
2. Load and validate `Configuration` from TOML
3. Check vector store path exists → user-friendly error if not
4. Create `EmbeddingGenerator` from config
5. Create `EmbeddingOrchestrator`, register plugin embedding models
6. Create `QdrantVectorStore` with embedding config
7. Create `LLMClient` from config
8. Create `LLMPool` if multiple models configured, else `None`
9. Resolve `effective_top_k`: CLI arg > config > default (5)
10. Create `QueryEngine` with all components
11. Return frozen `QueryPipeline` dataclass

### `resolve_config_path`

```python
def resolve_config_path(explicit_path: Path | None = None) -> Path:
    """Resolve configuration file path using XDG conventions.

    Args:
        explicit_path: User-provided path. If given, returned as-is.

    Returns:
        Path to config file (config.toml or config.yaml).

    Raises:
        FileNotFoundError: If no config file found.
    """
```

## QueryPipeline Dataclass

```python
@dataclass(frozen=True)
class QueryPipeline:
    config: Configuration
    embedding_generator: EmbeddingGenerator
    embedding_orchestrator: EmbeddingOrchestrator
    vector_store: QdrantVectorStore
    llm_client: LLMClient
    llm_pool: LLMPool | None
    query_engine: QueryEngine
```
