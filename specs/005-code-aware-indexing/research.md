# Research: Code-Aware Indexing

**Feature**: 005-code-aware-indexing  
**Date**: 2026-02-16  
**Status**: Complete

## R1: Tree-sitter AST Chunking API

### Decision
Use **py-tree-sitter v0.25+** with tree-sitter **query patterns** to extract semantic units from source files. Each grammar is a separate pip package (`tree-sitter-python`, `tree-sitter-rust`, etc.) discovered dynamically at runtime.

### Rationale
- Tree-sitter always produces a complete tree, even for syntactically invalid code — `ERROR` nodes mark broken sections while valid siblings parse correctly. This means the chunker can extract valid functions/classes from partially broken files and fall back gracefully.
- Query API (`Query` + `QueryCursor`) is the recommended approach for pattern-matching specific node types (functions, classes, decorated definitions) rather than explicit tree traversal.
- Parsing is negligible overhead: ~5–15ms for a 10k-line Python file. The bottleneck is embedding generation, not parsing.

### Alternatives Considered
- **Regex-based function extraction**: Rejected — too fragile for nested definitions, decorators, multiline signatures.
- **Python `ast` module**: Only works for Python, doesn't cover Rust/JS/etc. Tree-sitter is multi-language by design.
- **Manual tree traversal**: Works but query patterns are more concise and maintainable.

### Key Technical Details

**API sequence (v0.25+)**:
```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor

lang = Language(tspython.language())
parser = Parser(lang)
tree = parser.parse(source_bytes)

query = Query(lang, '(function_definition name: (identifier) @name) @def')
cursor = QueryCursor(query)
captures = cursor.captures(tree.root_node)  # dict[str, list[Node]]
```

**Node properties for chunk metadata**:
- `node.text` → source bytes
- `node.start_point.row` / `node.end_point.row` → 0-based line numbers
- `node.start_byte` / `node.end_byte` → byte offsets
- `node.has_error` → subtree contains ERROR nodes
- `node.child_by_field_name("name")` → function/class name node

**Python node types**:
| Construct | Node type |
|-----------|-----------|
| Function | `function_definition` |
| Class | `class_definition` |
| Decorated def | `decorated_definition` |
| Import | `import_statement`, `import_from_statement` |
| Docstring | `expression_statement` containing `string` (first child of block) |

**Dynamic grammar discovery**:
```python
import importlib, importlib.metadata
from tree_sitter import Language

def discover_grammars() -> dict[str, Language]:
    langs = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if name and name.startswith("tree-sitter-") and name != "tree-sitter":
            lang_name = name.replace("tree-sitter-", "").replace("-", "_")
            try:
                mod = importlib.import_module(f"tree_sitter_{lang_name}")
                langs[lang_name] = Language(mod.language())
            except (ImportError, AttributeError):
                pass
    return langs
```

**Error handling**: Tree-sitter always produces a tree. Use `root.has_error` to detect problems, skip `ERROR` nodes during chunking, extract valid siblings normally.

---

## R2: Qdrant Multi-Vector Architecture

### Decision
Use **Qdrant named vectors** in a single collection with **Reciprocal Rank Fusion (RRF)** for result merging. Not separate collections. Not min-max normalization.

### Rationale
- Qdrant recommends "use a single collection" for multi-modal embeddings. Named vectors (`"text"`, `"code"`) store different embedding model outputs per point.
- Points that only have one embedding model (e.g., `.md` files only have `"text"`) simply omit the other vector — Qdrant handles sparse named vectors per point.
- `query_batch_points` searches both vector spaces in a **single network call**, returning separate result lists.
- **RRF is more appropriate than min-max normalization** for cross-model score merging. Scores from different embedding models are in different semantic spaces — a 0.8 from model A doesn't mean the same as 0.8 from model B. RRF uses rank positions (which are comparable) rather than raw scores.

### Alternatives Considered
- **Separate collections per model**: More isolation for independent rebuild/delete, but requires manual merge and no shared payload index. Rejected for v1 — can migrate later if needed.
- **Payload filtering in single collection**: Can't support different vector spaces or per-model search. Rejected.
- **Min-max normalization** (from spec): Scales scores to [0,1] per model per query. Simpler to implement but less robust — a model that returns uniformly high scores will have its weakest results boosted to the same range as another model's best. RRF avoids this by using rank position only.

### Key Technical Details

**Collection creation**:
```python
client.create_collection(
    collection_name="krag_embeddings",
    vectors_config={
        "text": VectorParams(size=768, distance=Distance.COSINE),
        "code": VectorParams(size=768, distance=Distance.COSINE),
    },
)
```

**Upsert with selective named vectors**:
```python
PointStruct(
    id=hash_id,
    vector={"code": code_embedding},  # omit "text" for code-only files
    payload={"file_path": "...", "content": "...", "model": "code"},
)
```

**Batch search (single call)**:
```python
responses = client.query_batch_points(
    collection_name="krag_embeddings",
    requests=[
        QueryRequest(query=text_vector, using="text", limit=10, with_payload=True),
        QueryRequest(query=code_vector, using="code", limit=10, with_payload=True),
    ],
)
text_results = responses[0].points
code_results = responses[1].points
```

**RRF merge**:
```python
def reciprocal_rank_fusion(result_lists: list[list], k: int = 60, limit: int = 10):
    scores: dict[str, float] = {}
    point_map: dict[str, object] = {}
    for results in result_lists:
        for rank, point in enumerate(results):
            pid = str(point.id)
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
            point_map[pid] = point
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [point_map[pid] for pid, _ in ranked[:limit]]
```

**Cosine score range**: Qdrant normalizes vectors at insertion, so cosine scores are typically in [0, 1]. But for merging, use RRF (rank-based) not raw scores.

### Spec Update Required
FR-014 currently says "min-max normalization per model per query." Based on this research, recommend changing to **RRF** (rank-based fusion). RRF is:
- More robust to score distribution differences between models
- Used by Qdrant internally for their own multi-vector fusion
- Parameter-free besides the constant `k=60` (standard default)

---

## R3: VRAM Detection

### Decision
Use **`torch.cuda.mem_get_info()`** instead of pynvml. Use GGUF file size + KV cache estimate + 500MB overhead as model VRAM estimate, with 20% safety margin.

### Rationale
- `torch` is already installed as a transitive dependency of `sentence-transformers`. No new dependency needed.
- `torch.cuda.mem_get_info()` reports **post-context-init** free VRAM, which is more accurate for allocation decisions than pynvml (which reports raw driver-level values).
- pynvml is **not** a transitive dependency of llama-cpp-python (contrary to the spec's assumption). Adding it would be an unnecessary new dependency.
- Existing `gpu.py` already uses `torch.cuda.*` for GPU detection — using the same library is consistent.

### Alternatives Considered
- **pynvml / nvidia-ml-py**: Would require adding a new explicit dependency. Reports raw driver-level VRAM (same as nvidia-smi), which doesn't account for CUDA context overhead. Rejected.
- **`torch.cuda.get_device_properties().total_memory - memory_allocated()`**: Currently used in `gpu.py` but `memory_allocated()` only tracks PyTorch's own allocations, not other processes. `mem_get_info()` queries the driver for system-wide free VRAM. Recommend fixing existing code as well.

### Key Technical Details

**VRAM query**:
```python
import torch

def get_free_vram(device: int = 0) -> int | None:
    """Return free VRAM in bytes, or None if no GPU."""
    if not torch.cuda.is_available():
        return None
    free, total = torch.cuda.mem_get_info(device)
    return free
```

**Model VRAM estimate**:
$$\text{VRAM}_\text{needed} \approx \text{file\_size} + (n\_ctx \times 2\text{ MB}) + 500\text{ MB overhead}$$

**Safety margin**: Use 20% of free VRAM as safety margin (accounts for VRAM fragmentation, desktop compositor, other processes).

```python
def can_fit_model(model_path: str, n_ctx: int = 4096) -> bool:
    free = get_free_vram()
    if free is None:
        return False
    needed = os.path.getsize(model_path) + (n_ctx * 2 * 1024**2) + (500 * 1024**2)
    return free * 0.80 >= needed
```

### Spec Update Required
- FR-016: Change "via pynvml" to "via `torch.cuda.mem_get_info()`"
- Dependencies: Remove pynvml from explicit dependency list
- Clarification Q3: Note that the implementation uses torch instead of pynvml

---

## R4: LLM Hot-Swap with llama-cpp-python

### Decision
Use `Llama.close()` for deterministic VRAM release, with a `threading.Lock` for thread safety. Follow the built-in `LlamaProxy` pattern from `llama_cpp/server/model.py`. No progress callback via the high-level API — use `verbose=True` for loading feedback, plus manual timing.

### Rationale
- `Llama.close()` (added v0.2.79) calls `llama_model_free()` which immediately releases CUDA memory. No need for `torch.cuda.empty_cache()` — llama.cpp uses its own CUDA allocator, not PyTorch's.
- `del model` also calls `close()` via `__del__`, but CPython's GC doesn't guarantee prompt invocation. Always call `.close()` explicitly.
- Chat template auto-detection works for both Phi-3 and Qwen2.5-Coder (both embed `tokenizer.chat_template` in GGUF metadata). No `chat_format=` parameter needed.
- Two `Llama` instances can coexist in VRAM simultaneously (no CUDA context conflicts). But for our 16GB GPU, Phi-3 (~8.5GB) + Qwen2.5-Coder (~5.4GB) = ~13.9GB + KV caches ≈ ~15GB leaves almost no headroom. Hot-swap is the default strategy.

### Alternatives Considered
- **Rely on `del model` + GC**: Unreliable for prompt VRAM release. Rejected.
- **Use `gc.collect()` + `torch.cuda.empty_cache()`**: Unnecessary — llama.cpp doesn't use PyTorch's CUDA allocator. Added `gc.collect()` as belt-and-suspenders for reference cycles only.
- **Progress callback via low-level API**: `llama_model_params.progress_callback` exists in C API but isn't exposed in the high-level `Llama()` constructor. Too much complexity for the load-time feedback need. Use `verbose=True` + manual timing instead.

### Key Technical Details

**Hot-swap pattern** (from built-in `LlamaProxy`):
```python
def swap_model(current: Llama | None, new_path: str, **kwargs) -> Llama:
    if current is not None:
        current.close()      # deterministic VRAM release
        del current
        gc.collect()         # belt-and-suspenders for ref cycles
    return Llama(model_path=new_path, n_gpu_layers=-1, **kwargs)
```

**Load times** (NVMe SSD → VRAM):
| Model | Size | Load Time |
|-------|------|-----------|
| Phi-3-medium Q5_K_M | ~8.5 GB | ~3–6 seconds |
| Qwen2.5-Coder-7B Q5_K_M | ~5.4 GB | ~2–4 seconds |

**Thread safety**: `Llama` is NOT thread-safe. Use `threading.Lock` to guard all access (swap + generate). The built-in server uses an async double-lock pattern.

```python
class LLMPool:
    def __init__(self):
        self._lock = threading.Lock()
        self._model: Llama | None = None

    def swap(self, model_path: str, **kwargs):
        with self._lock:
            if self._model is not None:
                self._model.close()
                self._model = None
            self._model = Llama(model_path=model_path, n_gpu_layers=-1, **kwargs)

    def generate(self, messages: list[dict], **kwargs) -> str:
        with self._lock:
            return self._model.create_chat_completion(messages=messages, **kwargs)
```

**Chat format**: Auto-detected from GGUF metadata. No explicit `chat_format=` needed for Phi-3 or Qwen2.5-Coder.

**Concurrent models**: Possible if VRAM permits (`load_multi_llm = true`). No CUDA context conflicts. krag checks VRAM before attempting concurrent load.

---

## R5: Score Merging Strategy — Spec Deviation

### Decision
Use **Reciprocal Rank Fusion (RRF)** instead of the min-max normalization specified in the spec.

### Rationale
The spec (FR-014, clarification Q2) specifies "min-max normalization per model per query." Research shows this is suboptimal for cross-model score merging:

1. **Scores from different models are in different semantic spaces** — a model that consistently returns high scores will have its weakest results inflated to the same range as another model's best results after min-max normalization.
2. **RRF uses rank positions** which are inherently comparable across models — rank 1 from model A and rank 1 from model B both represent "this model's best match."
3. **Qdrant uses RRF internally** for their own multi-vector fusion (implemented in `qdrant_fastembed.py`).
4. **RRF is parameter-free** except for the constant `k=60` (standard default from the original RRF paper).

### Spec Impact
- FR-014: Update from "normalize scores using min-max normalization per model per query" to "merge results using Reciprocal Rank Fusion (RRF)"
- Edge case "Multi-model score merging": Update rationale from "raw scores are not directly comparable; use min-max" to "raw scores are not directly comparable; use rank-based fusion (RRF)"
- Clarification Q2: Note the deviation and reason

---

## R6: VRAM Detection — Spec Deviation

### Decision
Use `torch.cuda.mem_get_info()` instead of pynvml.

### Rationale
pynvml is NOT a transitive dependency of llama-cpp-python (spec assumed it was). torch IS available (via sentence-transformers) and provides more accurate post-context-init VRAM information.

### Spec Impact
- FR-016: Change "via `pynvml`" to "via `torch.cuda.mem_get_info()`"
- Dependencies: Remove "pynvml" from dependency list
- Clarification Q3: Note the implementation approach change

---

## R7: Plugin Embedding Model Declaration

### Decision
Extend `FileTypeHandler` ABC with an optional `embedding_model` property that plugins can override to declare their preferred embedding model. Plugins that don't override it return `None` (use system default).

### Rationale
- Follows existing pattern: `get_chunking_strategy()` is already an optional method that returns `None` by default.
- No breaking change to the plugin API — existing plugins are unaffected (property returns `None`).
- The `EmbeddingOrchestrator` reads each plugin's `embedding_model` during indexing to route files to the correct embedder.

### Alternatives Considered
- **Plugin configuration section in TOML**: Already possible via `plugin_settings` in `PluginConfiguration`, but embedding model is a fundamental plugin property, not a user configuration. Keep in code.
- **Separate embedding plugin interface**: Over-engineering for a single optional property. Rejected.

### Key Technical Details
```python
class FileTypeHandler(ABC):
    # ... existing interface ...

    def get_embedding_model(self) -> str | None:
        """Return the preferred embedding model name/path, or None for system default."""
        return None
```
