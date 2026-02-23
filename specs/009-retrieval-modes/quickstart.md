# Quickstart: Sprint 009 Implementation

**Branch**: `009-retrieval-modes`

This guide provides the recommended implementation order with step-by-step instructions for each story. Stories are ordered by dependency — each builds on the one before it.

---

## Implementation Order

| Step | Story | Covers | Depends On |
|------|-------|--------|------------|
| 1 | Lifecycle Timer Fix | FR-001 – FR-003 | — |
| 2 | Multi-Collection Qdrant | FR-004 – FR-011 | Step 1 (stable lifecycle) |
| 3 | Mode System | FR-012 – FR-020 | Step 2 (collections to target) |
| 4 | Domain Lexicon | FR-021 – FR-028 | Step 3 (modes reference lexicon config) |
| 5 | Context Critic | FR-029 – FR-036 | Step 3 (modes reference critic config) |

Steps 4 and 5 are independent of each other and can be developed in either order.

---

## Step 1: Lifecycle Timer Fix

**Files to modify**: `src/kragd/lifecycle.py`, `src/kragd/service.py`
**Tests to create**: `tests/unit/kragd/test_lifecycle.py` (extend existing)

### 1.1 Add pause/resume to LLMLifecycleManager

In `src/kragd/lifecycle.py`:

```python
# Add to LLMLifecycleManager class
_paused: bool = False

def pause(self) -> None:
    """Cancel the idle timer to prevent firing during indexing."""
    self._paused = True
    if self._idle_task is not None:
        self._loop.call_soon_threadsafe(self._idle_task.cancel)
        log.info("Lifecycle idle timer paused for indexing")

def resume(self, slot: str = "secondary") -> None:
    """Re-schedule the idle timer after indexing completes."""
    self._paused = False
    self._loop.call_soon_threadsafe(self._schedule_idle_timeout)
    log.info("Lifecycle idle timer resumed after indexing")
```

### 1.2 Add defense-in-depth check

In `_unload_after_timeout()`, add an early return:

```python
async def _unload_after_timeout(self) -> None:
    await asyncio.sleep(self._timeout_seconds)
    if self._paused:
        log.debug("Idle timer fired but lifecycle is paused — skipping unload")
        return
    # ... existing unload logic
```

### 1.3 Wire into indexing flow

In `src/kragd/service.py` `_run_indexing()`:

```python
def _run_indexing(self, ...):
    self._lifecycle.pause()          # Before llm_pool.close()
    try:
        # ... existing indexing code ...
    finally:
        self._init_llm_pool()        # Existing reload
        self._lifecycle.resume()     # After LLM reload
```

### 1.4 Write tests

- Test that `pause()` cancels the timer task
- Test that `resume()` re-schedules the timer
- Test that `_unload_after_timeout()` returns early when paused
- Test full cycle: pause → wait > timeout → resume → timer fires normally

### 1.5 Verify

```bash
uv run ruff format src/kragd/lifecycle.py src/kragd/service.py
uv run ruff check src/kragd/ --fix
uv run pytest tests/unit/kragd/test_lifecycle.py -v
```

---

## Step 2: Multi-Collection Qdrant

**New files**: `src/krag/storage/collection_manager.py`, `src/krag/routing/` (package)
**Files to modify**: `src/krag/storage/qdrant_impl.py`, `src/krag/orchestration/indexer.py`, `src/krag/retrieval/retriever.py`, `src/krag/models/configuration.py`
**Tests to create**: `tests/unit/test_collection_router.py`, `tests/unit/test_collection_manager.py`, `tests/integration/test_multi_collection_indexing.py`

### 2.1 Create routing package

```python
# src/krag/routing/__init__.py
from .collection_router import CollectionRouter

# src/krag/routing/rules.py — consolidate constants
COLLECTION_CODE = "krag_code"
COLLECTION_TESTS = "krag_tests"
COLLECTION_DOCS = "krag_docs"
COLLECTION_TEXT = "krag_text"
ALL_COLLECTIONS = [COLLECTION_CODE, COLLECTION_TESTS, COLLECTION_DOCS, COLLECTION_TEXT]

CODE_EXTENSIONS = {".py", ".ts", ".js", ".rs", ".go", ".java", ".c", ".cpp", ".h", ...}
DOC_EXTENSIONS = {".md", ".rst", ".adoc", ".txt"}
TEST_DIRS = {"tests", "test", "__tests__", "spec"}
TEST_PATTERNS = [re.compile(r"^test_"), re.compile(r"_test\.\w+$"), ...]
# ... 8-level precedence rules
```

### 2.2 Implement CollectionRouter

`src/krag/routing/collection_router.py`:

```python
class CollectionRouter:
    def route(self, file_path: Path, plugin_override: str | None = None) -> str:
        """Return the collection name for a file, applying 8-level precedence."""
```

### 2.3 Create CollectionManager

`src/krag/storage/collection_manager.py`:

```python
class CollectionManager:
    """Owns the shared QdrantClient and creates per-collection QdrantVectorStore wrappers."""
    
    def __init__(self, storage_path: Path):
        self._client = QdrantClient(path=str(storage_path))
        self._stores: dict[str, QdrantVectorStore] = {}
    
    def get_store(self, collection: str) -> QdrantVectorStore: ...
    def ensure_collections(self) -> None: ...
```

### 2.4 Modify QdrantVectorStore

Refactor `__init__` to accept an optional pre-created `QdrantClient`. When provided, skip creating a new client.

### 2.5 Wire into indexer and retriever

- `indexer.py`: Use `CollectionRouter` to decide target collection, call the right `QdrantVectorStore`.
- `retriever.py`: Accept list of target collections, query each, merge via weighted RRF.

### 2.6 Write tests and verify

```bash
uv run pytest tests/unit/test_collection_router.py tests/unit/test_collection_manager.py -v
uv run pytest tests/integration/test_multi_collection_indexing.py -v
```

---

## Step 3: Mode System

**New files**: `src/krag/modes/` (package), `src/krag_cli/commands/modes.py`, `src/krag/cli/modes.py`, `src/kragd/routers/query.py` (modify)
**Files to modify**: `src/krag/orchestration/query_engine.py`, `src/krag/models/configuration.py`, `src/krag_cli/commands/query.py`, `src/krag/cli/query.py`
**Tests to create**: `tests/unit/test_mode_loader.py`, `tests/unit/test_mode_registry.py`, `tests/integration/test_mode_query.py`, `tests/contract/test_mode_contract.py`

### 3.1 Create mode loader and registry

```python
# src/krag/modes/mode_loader.py
class ModeLoader:
    def load(self, path: Path) -> ModeConfiguration: ...
    def validate(self, config: ModeConfiguration) -> list[str]: ...

# src/krag/modes/mode_registry.py
class ModeRegistry:
    def __init__(self):
        self._modes: dict[str, ModeConfiguration] = {}
    
    def register(self, name: str, config: ModeConfiguration) -> None: ...
    def get(self, name: str) -> ModeConfiguration: ...
    def list_modes(self) -> list[ModeConfiguration]: ...
    def load_builtins(self) -> None: ...
    def load_user_modes(self, directory: Path) -> None: ...
```

### 3.2 Add built-in mode TOML files

Copy from `contracts/mode-schema.toml` examples → `src/krag/modes/builtin/{default,code,docs}.toml`.

### 3.3 Add ModeConfiguration to models

```python
# In src/krag/models/configuration.py
class ModeConfiguration(BaseModel):
    name: str
    description: str = ""
    collections: dict[str, float]   # collection_name → weight
    llm_slot: str = "text"          # "text" or "code"
    preset: str = "balanced"
    top_k: int = 5
    similarity_threshold: float = 0.2
    critic_enabled: bool = False
    critic_threshold: int = 3
```

### 3.4 Wire into query engine

In `query_engine.py`, resolve mode at query time → extract collections, LLM slot, preset, and params → pass to retriever and prompt builder.

### 3.5 Add --mode CLI flag

- `krag_cli/commands/query.py`: Add `--mode` option, deprecate `--llm` with warning.
- `krag/cli/query.py`: Same for krag-direct.
- `kragd/routers/query.py`: Add `mode` field to request schema.

### 3.6 Add modes list/show commands

- `krag_cli/commands/modes.py`: `krag modes list` (Rich table), `krag modes show <name>`.
- `krag/cli/modes.py`: Same for krag-direct.

### 3.7 Write tests and verify

```bash
uv run pytest tests/unit/test_mode_loader.py tests/unit/test_mode_registry.py -v
uv run pytest tests/integration/test_mode_query.py -v
uv run pytest tests/contract/test_mode_contract.py -v
```

---

## Step 4: Domain Lexicon

**New files**: `src/krag/lexicon/` (package), `src/krag_cli/commands/lexicon.py`, `src/kragd/routers/lexicon.py`
**Files to modify**: `src/krag/synthesis/prompt_builder.py`, `src/krag/models/configuration.py`
**Tests to create**: `tests/unit/test_lexicon_store.py`, `tests/unit/test_lexicon_injector.py`, `tests/integration/test_lexicon_injection.py`, `tests/contract/test_lexicon_contract.py`

### 4.1 Create lexicon store

```python
# src/krag/lexicon/lexicon_store.py
class LexiconStore:
    def __init__(self):
        self._entries: dict[str, str] = {}
        self._patterns: list[tuple[re.Pattern, str, str]] = []  # (compiled, term, definition)
    
    def load(self, path: Path) -> int: ...        # Returns entry count
    def reload(self) -> int: ...                   # Reloads from same path
    def match(self, text: str) -> list[LexiconMatch]: ...  # Case-insensitive word-boundary
```

Validation against `contracts/lexicon-schema.json` at load time.

### 4.2 Create lexicon injector

```python
# src/krag/lexicon/lexicon_injector.py
class LexiconInjector:
    MAX_ENTRIES = 10
    MAX_CHARS = 1500
    
    def select(self, query: str, store: LexiconStore) -> list[LexiconMatch]: ...
    def format_for_prompt(self, matches: list[LexiconMatch]) -> str: ...
```

### 4.3 Inject into prompt builder

In `src/krag/synthesis/prompt_builder.py`, add an injection point in `build_system_prompt()` that appends matched lexicon entries as a "Project Terminology" section.

### 4.4 Add refresh endpoint and CLI

- `src/kragd/routers/lexicon.py`: `POST /lexicon/refresh`.
- `src/krag_cli/commands/lexicon.py`: `krag lexicon refresh`.

### 4.5 Write tests and verify

```bash
uv run pytest tests/unit/test_lexicon_store.py tests/unit/test_lexicon_injector.py -v
uv run pytest tests/integration/test_lexicon_injection.py -v
```

---

## Step 5: Context Critic

**New files**: `src/krag/critic/` (package)
**Files to modify**: `src/krag/orchestration/query_engine.py`, `src/krag/models/configuration.py`
**Tests to create**: `tests/unit/test_relevance_critic.py`, `tests/integration/test_critic_filtering.py`, `tests/contract/test_critic_contract.py`

### 5.1 Create relevance critic

```python
# src/krag/critic/relevance_critic.py
class RelevanceCritic:
    SCORE_REGEX = re.compile(r'\b([0-5])\b')
    MIN_CHUNK_LENGTH = 50
    
    async def score_chunks(
        self, query: str, chunks: list[TextChunk], llm_client: LLMClient
    ) -> list[ScoredChunk]: ...
    
    def filter(
        self, scored: list[ScoredChunk], threshold: int = 3
    ) -> list[ScoredChunk]: ...
```

Each chunk is scored individually with a constrained prompt (`temp=0.0`, `max_tokens=4`). Chunks < 50 chars bypass scoring. Parse failures → fail-open (include chunk, score = -1).

### 5.2 Wire into query engine

In `query_engine.py`, after retrieval and before prompt construction:

```python
if mode.critic_enabled:
    scored = await critic.score_chunks(query, chunks, llm_client)
    chunks = critic.filter(scored, threshold=mode.critic_threshold)
    if not chunks:
        return insufficient_context_response()
```

Add critic metadata to debug output.

### 5.3 Write tests and verify

```bash
uv run pytest tests/unit/test_relevance_critic.py -v
uv run pytest tests/integration/test_critic_filtering.py -v
uv run pytest tests/contract/test_critic_contract.py -v
```

---

## Final Verification

After all steps are implemented:

```bash
# Format and lint
uv run ruff format src/ tests/
uv run ruff check src/ tests/ --fix

# Full test suite
uv run pytest --tb=short

# Type checking
uv run mypy src/

# Coverage
uv run pytest --cov=src --cov-report=html
```

### Smoke Test

```bash
# Index a mixed project
krag-direct index /path/to/mixed-project

# Verify collection routing
krag-direct query --mode code --debug "How does retry work?"
krag-direct query --mode docs --debug "What is the architecture?"

# Check modes
krag-direct modes list

# Test lexicon (if configured)
krag-direct lexicon refresh
krag-direct query "What is kragd?" --debug
```
