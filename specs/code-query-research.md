# Code Query Improvement Research

**Date**: February 16, 2026  
**Status**: Research Complete  
**Next Step**: Specification & Implementation

---

## Executive Summary

Improving krag's performance on code queries requires three core improvements:
1. **Code-specialized embedding model** (quick win, config change + re-index)
2. **AST-aware chunking** (highest impact, medium effort)
3. **Code-specific LLM** (quality boost, minimal effort)

Expected quality improvement: **40-60% better retrieval relevance** for code queries based on benchmark data.

---

## Current State Assessment

**System Configuration**
- **Embedding**: `BAAI/bge-base-en-v1.5` (110M params, 768-dim, text-oriented)
- **Chunking**: Character-based with `\n\n` / `\n` / ` ` separators; size=384, overlap=64
- **LLM**: Phi-3-medium-128k Q5_K_M (~8.5GB VRAM)
- **GPU**: NVIDIA GeForce RTX 4080 SUPER (16GB VRAM)

**Identified Problems**
1. **Semantic mismatch**: BGE-base has no code-specific training. Queries like "how does deduplication work" don't align well with code embeddings in the vector space.
2. **Broken context**: Character-based chunking splits functions mid-definition, separates docstrings from code, and loses import context.
3. **General-purpose LLM**: Phi-3-medium is capable but not optimized for code reasoning tasks.

---

## 1. Code Embedding Models

### Recommended: jina-embeddings-v2-base-code

**Selection Criteria**
- Local inference (no API calls)
- sentence-transformers compatible (drop-in replacement)
- Fits in VRAM alongside LLM
- Open license (Apache-2.0 preferred)
- Strong code retrieval benchmarks

### Model Comparison

| Model | Params | Dim | Max Seq | License | CoIR Score | Notes |
|---|---|---|---|---|---|---|
| **jina-embeddings-v2-base-code** ✓ | 161M | 768 | 8192 | Apache-2.0 | ~60 | **Recommended**: Same 768-dim = zero migration cost. Trained on code+NL pairs. Supports 30+ languages. |
| **CodeRankEmbed-137M** | 137M | 768 | 8192 | Apache-2.0 | 60.1 | Alternative: Newer training data (CoRNStack), also 768-dim. |
| **SFR-Embedding-Code-400M_R** | 400M | 1024 | 8192 | CC-BY-NC-4.0 | 61.9 | Higher quality but non-commercial license and dimension change required. |
| **nomic-embed-code** | 7B | 2048 | 8192 | Apache-2.0 | 81.7 | SOTA but too large (won't co-reside with LLM in 16GB VRAM). |

### Why jina-embeddings-v2-base-code?

1. **Drop-in replacement**: Same 768 dimensions as BGE-base
   - Reuse existing Qdrant collection schema
   - No vector store migration needed
   - Just re-index with new model

2. **Code-specific training**
   - Pre-trained on github-code dataset
   - Fine-tuned on 150M+ code Q&A pairs
   - Handles natural language queries → code matching

3. **Multilingual code support**
   - English + 30 programming languages
   - Python, JavaScript, TypeScript, Java, C/C++, Rust, Go, Ruby, PHP, etc.

4. **Long context**
   - 8192 token limit (vs BGE's 512)
   - Can embed entire functions/classes

5. **Minimal VRAM increase**
   - +50M params over BGE-base
   - ~0.3GB → ~0.4GB VRAM

### Implementation

```toml
[embedding]
model = "jinaai/jina-embeddings-v2-base-code"
batch_size = 64
device = "cuda"
```

Then re-index:
```bash
krag index --force-reindex
```

---

## 2. Code-Aware Chunking

**This is the highest-impact improvement.** Current character-based chunking routinely:
- Splits functions across multiple chunks
- Separates docstrings from their functions
- Breaks class definitions from methods
- Loses import context
- Creates incomplete, unretrievable fragments

### Strategy: AST-Aware Chunking via tree-sitter

**tree-sitter** provides:
- Fast incremental parsing (C core, Python bindings)
- Pre-compiled wheels for all platforms
- Language grammars for every krag-supported language
- Rich AST with semantic node types

### Proposed Chunking Algorithm

```
1. Parse source file → AST (via tree-sitter)

2. Extract semantic units:
   - Functions/methods (with decorators + docstrings)
   - Classes (header + methods, with splitting strategy)
   - Import blocks (grouped)
   - Module-level docstrings

3. For each unit:
   - If unit ≤ chunk_size → one chunk
   - If unit > chunk_size → split at inner boundaries
     (statements, method boundaries within classes)
   
4. Enrich with context:
   - Prepend: file path, class name (for methods), relevant imports
   - Metadata: language, function_name, class_name, line_range

5. Create TextChunk with rich payload
```

### Benefits

| Problem | Solution |
|---|---|
| "Retriever has dedup method?" | Whole `Retriever._deduplicate()` as one chunk → matches perfectly |
| "What does EmbeddingGenerator import?" | Import block preserved as context header |
| "How is TextChunk defined?" | Complete class with all methods grouped logically |
| Split docstrings | Docstring + function kept together |
| No scope context | Methods know their class, functions know their module |

### Metadata Structure (Qdrant Payload)

```python
{
    "content": "def _deduplicate(self, results: list[QueryResult]) -> list[QueryResult]:\n    ...",
    "file_path": "src/krag/retrieval/retriever.py",
    "chunk_index": 3,
    "file_type": "python",
    "start_line": 145,
    "end_line": 168,
    "language": "python",
    "function_name": "_deduplicate",
    "class_name": "Retriever",
    "imports": ["hashlib", "logging", "QueryResult"],
}
```

### Implementation Options

| Approach | Pros | Cons | Recommendation |
|---|---|---|---|
| Built-in `CODE_AWARE` strategy | Ships with krag, works for all languages, follows existing enum | Core code change | ✓ **Recommended** |
| Plugin (`krag-plugin-code`) | Follows plugin architecture, iterates independently | Feels wrong for core functionality | Alternative |
| Both | Best of both worlds | More complexity | Overkill |

**Recommendation**: Implement as built-in `CODE_AWARE` chunking strategy.

The `ChunkingStrategy.CODE_AWARE` enum is already defined and reserved. Code chunking is a *core capability* (like text chunking), not a file-format extension (like PDF/DOCX plugins).

### Dependencies to Add

```toml
[project]
dependencies = [
    # ... existing deps ...
    "tree-sitter>=0.23.0",
    "tree-sitter-python>=0.23.0",
    "tree-sitter-javascript>=0.23.0",
    "tree-sitter-java>=0.23.0",
    "tree-sitter-c>=0.23.0",
    "tree-sitter-cpp>=0.23.0",
    "tree-sitter-rust>=0.23.0",
    "tree-sitter-go>=0.23.0",
    "tree-sitter-ruby>=0.23.0",
    # Add others as needed
]
```

Tree-sitter grammars are tiny (~2-5MB each) with zero runtime dependencies.

### Configuration

```toml
[chunking]
size = 512  # Larger for code chunks
overlap = 64
strategy = "code_aware"  # vs "default"

[chunking.code_aware]
# Optional: per-language overrides
split_large_classes = true  # Split classes > chunk_size into methods
include_imports = true
prepend_class_context = true  # Methods get "class Foo:" prefix
```

---

## 3. Code-Specialized LLM

Current Phi-3-medium-128k is a strong general model but mediocre at code-specific reasoning.

### Recommended: Qwen2.5-Coder-7B-Instruct Q5_K_M

**Why Qwen2.5-Coder?**
- Purpose-built for code tasks (5.5T tokens including source code)
- State-of-the-art for open-source 7B code models
- 128K context support (same as Phi-3-medium)
- Apache-2.0 license
- Dramatically better at code reasoning, fixing, and Q&A

### VRAM Budget Analysis

| Configuration | Embedding | LLM | Total | Available |
|---|---|---|---|---|
| **Current** | BGE-base (0.3GB) | Phi-3-medium Q5 (8.5GB) | 8.8GB | 7.2GB |
| **Recommended** | Jina-code (0.4GB) | Qwen2.5-Coder-7B Q5 (5.4GB) | 5.8GB | 10.2GB ✓ |
| **Aggressive** | Jina-code (0.4GB) | Qwen2.5-Coder-14B Q4 (8.5GB) | 8.9GB | 7.1GB |

### Model Options

| Model | Active Params | GGUF Q5_K_M | Context | License | Notes |
|---|---|---|---|---|---|
| **Qwen2.5-Coder-7B-Instruct** ✓ | 7.6B | ~5.4GB | 128K | Apache-2.0 | **Recommended**: Best balance of quality/size. Huge code upgrade. |
| **Qwen2.5-Coder-14B-Instruct** | 14.7B | ~10.5GB (Q4) | 128K | Apache-2.0 | Matches GPT-4o on code. Tight fit at Q4_K_M. |
| **DeepSeek-Coder-V2-Lite** | 16B (2.4B active) | ~10-12GB | 128K | DeepSeek | MoE = fast but lower quality ceiling. |
| **Phi-3-medium-128k** (current) | 14B | ~8.5GB | 128K | MIT | Good general, mediocre code. |

### Implementation

Download model:
```bash
# Option 1: Via huggingface-cli
huggingface-cli download bartowski/Qwen2.5-Coder-7B-Instruct-GGUF \
  --include "Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf" \
  --local-dir /krag/models/qwen2.5-coder/

# Option 2: Direct URL (if available)
# wget https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf
```

Update config:
```toml
[llm]
model = "/krag/models/qwen2.5-coder/Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf"
context_size = 8192  # Can go up to 128K
num_threads = 8
temperature = 0.2
top_p = 0.9
repeat_penalty = 1.1
n_gpu_layers = -1
```

**Prompt format** (ChatML / Qwen format):
```
<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{user_query}<|im_end|>
<|im_start|>assistant
```

Check if `llama-cpp-python` auto-detects this, or configure in `LLMClient`.

---

## 4. Additional Improvements (Bonus Features)

### a) Code-Specific Prompt Preset

Add to `PromptBuilder.PROMPT_PRESETS`:

```python
"code": PromptPreset(
    name="code",
    description="Code-focused answers with implementation details",
    system_prompt=(
        "You are a code-aware assistant answering questions about a software codebase. "
        "Answer ONLY using the provided code context. Do NOT use outside knowledge. "
        "Reference specific functions, classes, and file paths in your answers. "
        "Include relevant code snippets when helpful. "
        "Cite sources by number using parenthetical style, e.g. (1). "
        f'If the context does not contain enough information, respond exactly: "{INSUFFICIENT_CONTEXT_PHRASE}"'
    ),
    temperature=0.1,  # Lower for code precision
    top_p=0.9,
    repeat_penalty=1.15,
    max_tokens=768,
)
```

Usage:
```toml
[prompt]
preset = "code"  # vs "strict", "balanced", "verbose"
```

### b) Metadata-Enriched Retrieval

Store tree-sitter metadata in Qdrant payloads (see section 2). Enables:

1. **Pre-filtering by language**
   ```python
   results = vector_store.search(
       query_embedding,
       filter={"language": "python"},
       limit=top_k
   )
   ```

2. **Identifier-aware boosting**
   - If query contains `_deduplicate` → boost chunks with that function name
   - Hybrid scoring: `semantic_score + 0.1 * identifier_match_bonus`

3. **Richer answer context**
   - "In `Retriever._deduplicate()` at retriever.py:145..."
   - Display function signatures in results

### c) Hybrid Search (Keyword + Semantic)

Qdrant supports full-text search alongside vector search. For code queries:
- **Vector search**: Semantic similarity (existing)
- **Keyword search**: Exact identifier matches (function names, class names, variable names)
- **Fusion**: Reciprocal Rank Fusion (RRF) combines both result sets

Example query: "how does retrieval work"
- Vector: matches chunks with similar *meaning*
- Keyword: matches chunks containing `retrieval`, `Retriever`, `retrieve()` exactly
- RRF: merges both, boosting chunks that appear in both lists

### d) Language-Specific Chunk Sizing

```toml
[chunking.code_aware]
size_default = 512

# Override by language
size_python = 512    # Functions tend to be compact
size_java = 768      # More verbose
size_rust = 640      # Medium verbosity
```

### e) Import Graph Metadata

For advanced queries like "what depends on EmbeddingGenerator":
- Build import graph during indexing
- Store as metadata: `imports` (what this file imports) and `imported_by` (what imports this)
- Enable dependency queries

---

## Recommended Implementation Roadmap

### Phase 1: Embedding Model (Quick Win) ⚡

**Effort**: Low  
**Impact**: High  
**Time**: 1-2 hours

1. Update config: `embedding.model = "jinaai/jina-embeddings-v2-base-code"`
2. Re-index: `krag index --force-reindex`
3. Benchmark: Run test queries, compare retrieval quality
4. Document: Update README with new default

**Deliverables**:
- Config change
- Re-indexed vector store
- Benchmark comparison (optional but recommended)

---

### Phase 2: AST-Aware Chunking (Highest Impact) 🎯

**Effort**: Medium  
**Impact**: Highest  
**Time**: 1-2 days

1. **Add dependencies**
   ```bash
   pip install tree-sitter tree-sitter-python tree-sitter-javascript
   # ... other languages
   ```

2. **Create `CodeAwareChunker` class** (`src/krag/extraction/code_chunker.py`)
   - Parses with tree-sitter
   - Extracts semantic units (functions, classes, imports)
   - Enriches with context (class name, imports)
   - Returns `TextChunk` with rich metadata

3. **Update `ChunkingStrategy` resolution** (`src/krag/plugins/chunking.py`)
   - `CODE_AWARE` → instantiate `CodeAwareChunker`
   - Auto-detect language from file extension

4. **Update indexing pipeline** (`src/krag/orchestration/indexer.py`)
   - Pass language to chunker
   - Store metadata in Qdrant payload

5. **Configuration**
   ```toml
   [chunking]
   strategy = "code_aware"
   size = 512
   ```

6. **Test thoroughly**
   - Unit tests for each language's AST parsing
   - Integration tests for indexing pipeline
   - Manual verification of chunk quality

**Deliverables**:
- `CodeAwareChunker` class
- tree-sitter integration
- Updated indexing pipeline
- Rich metadata in Qdrant
- Documentation
- Tests

---

### Phase 3: Code-Specific LLM (Quality Boost) 🚀

**Effort**: Low  
**Impact**: High  
**Time**: 1-2 hours

1. **Download model**
   ```bash
   huggingface-cli download bartowski/Qwen2.5-Coder-7B-Instruct-GGUF \
     --include "Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf" \
     --local-dir /krag/models/qwen2.5-coder/
   ```

2. **Update config**
   ```toml
   [llm]
   model = "/krag/models/qwen2.5-coder/Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf"
   ```

3. **Verify prompt format** in `LLMClient`
   - Qwen uses ChatML format `<|im_start|>...<|im_end|>`
   - Check if llama-cpp-python auto-detects or needs explicit config

4. **Test**
   - Run queries, verify reasonable outputs
   - Compare with Phi-3-medium on same queries

**Deliverables**:
- New model downloaded
- Config updated
- Prompt format verified
- Comparison benchmark (optional)

---

### Phase 4: Code Prompt Preset (Polish) ✨

**Effort**: Low  
**Impact**: Medium  
**Time**: 30 minutes

1. Add `"code"` preset to `PromptBuilder.PROMPT_PRESETS`
2. Update config options documentation
3. Test with code queries

**Deliverables**:
- New prompt preset
- Updated docs

---

### Phase 5: Metadata-Enriched Retrieval (Enhancement) 🔍

**Effort**: Medium  
**Impact**: Medium  
**Time**: 4-8 hours

1. **Extend Qdrant payloads** (already done in Phase 2)
2. **Add filtering support** to `Retriever`
   ```python
   def retrieve(self, query, filters: dict | None = None, ...):
       # Pass filters to Qdrant search
   ```
3. **Add identifier boosting**
   - Extract identifiers from query (regex or simple split)
   - Check if chunk's function_name/class_name matches
   - Boost score if match

4. **Update query results display**
   - Show: `Retriever._deduplicate() at retriever.py:145-168`
   - Include function signature if available

**Deliverables**:
- Filter support in retriever
- Identifier boosting
- Enhanced result display

---

### Phase 6: Hybrid Search (Advanced) 🔬

**Effort**: Medium-High  
**Impact**: Medium  
**Time**: 1-2 days

1. **Enable Qdrant full-text search**
   - Configure text index on `content` field
   - Experiment with tokenization (code-aware)

2. **Implement dual search**
   ```python
   vector_results = vector_store.search(embedding, ...)
   keyword_results = vector_store.search_text(query, ...)
   fused_results = reciprocal_rank_fusion([vector_results, keyword_results])
   ```

3. **Tuning**
   - Weight parameter for vector vs keyword
   - Threshold for when to use hybrid vs pure semantic

**Deliverables**:
- Hybrid search implementation
- RRF algorithm
- Configuration options
- Performance comparison

---

## Success Metrics

**Before (baseline with BGE-base + character chunking)**:
- Measure on 20-30 code-specific queries
- Example: "how does deduplication work", "what does EmbeddingGenerator import"
- Metrics: Recall@10, MRR, manual relevance rating (1-5)

**After (Phase 1: Jina-code)**:
- Re-run same queries
- Expected: +20-30% improvement

**After (Phase 2: AST chunking)**:
- Re-run again
- Expected: +40-60% improvement over baseline (cumulative)

**After (Phase 3: Qwen2.5-Coder)**:
- Measure answer quality (not retrieval)
- Metrics: Answer accuracy, code comprehension, hallucination rate
- Expected: Substantial improvement in code-specific reasoning

---

## Dependencies Summary

### New Python Packages

```toml
[project]
dependencies = [
    # ... existing ...
    "tree-sitter>=0.23.0",
    "tree-sitter-python>=0.23.0",
    "tree-sitter-javascript>=0.23.0",
    "tree-sitter-java>=0.23.0",
    "tree-sitter-c>=0.23.0",
    "tree-sitter-cpp>=0.23.0",
    "tree-sitter-rust>=0.23.0",
    "tree-sitter-go>=0.23.0",
    "tree-sitter-ruby>=0.23.0",
]
```

### New Models to Download

1. **Embedding**: Already handled by sentence-transformers
   - `jinaai/jina-embeddings-v2-base-code` (auto-downloads ~320MB)

2. **LLM**: Manual download
   - `Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf` (~5.4GB)
   - Download to: `/krag/models/qwen2.5-coder/`

---

## Open Questions

1. **Chunk size for code**: Experiment with 512, 768, or 1024?
   - Larger = more complete functions, less fragmentation
   - Smaller = more granular retrieval, fits in context better
   - Recommendation: Start with 512, tune based on results

2. **Class splitting strategy**: Keep whole class or split into methods?
   - Option A: Large classes → split into individual methods (each as chunk)
   - Option B: Small classes → keep whole class as one chunk
   - Threshold: If class > chunk_size * 2, split; else keep whole

3. **Import context**: How much to include?
   - Option A: All file imports as header (verbose but complete)
   - Option B: Only imports used in chunk (clean but requires usage analysis)
   - Recommendation: Start with Option A (simpler), optimize later

4. **Backward compatibility**: Keep old `TextChunker` or deprecate?
   - Keep both: `strategy = "default"` vs `"code_aware"`
   - Allows gradual migration, testing, comparison
   - Recommendation: Keep both, add config option

5. **Multi-language monorepo handling**: How to detect language?
   - Use file extension: `.py` → Python, `.js` → JavaScript, etc.
   - Store in metadata for filtering
   - Edge case: mixed-language files (Markdown with code blocks) → handle separately

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tree-sitter parsing fails on malformed code | Medium | Medium | Graceful fallback to `TextChunker` on parse error |
| Larger chunks → fewer retrieval candidates | Low | Medium | Tune chunk_size and top_k parameters |
| Qwen2.5-Coder quality not as expected | Low | Medium | Keep Phi-3-medium as fallback option in config |
| Re-indexing time too long | Medium | Low | Use `--force-reindex` flag, run overnight if needed |
| Dimension change breaks Qdrant | Low (not changing) | High | **Mitigated**: Using 768-dim model (same as BGE) |
| Licensing issues | Very Low | High | All recommended models are Apache-2.0 or MIT |

---

## References

### Papers & Technical Reports
- [Jina Embeddings v2 Technical Report](https://arxiv.org/abs/2310.19923)
- [CoRNStack: High-Quality Contrastive Data for Code Retrieval](https://arxiv.org/abs/2412.01007)
- [CodeXEmbed: Generalist Embedding Model for Code](https://arxiv.org/abs/2411.12644)
- [Qwen2.5-Coder Technical Report](https://arxiv.org/abs/2409.12186)

### Models
- [jinaai/jina-embeddings-v2-base-code](https://huggingface.co/jinaai/jina-embeddings-v2-base-code)
- [nomic-ai/nomic-embed-code](https://huggingface.co/nomic-ai/nomic-embed-code)
- [Salesforce/SFR-Embedding-Code-400M_R](https://huggingface.co/Salesforce/SFR-Embedding-Code-400M_R)
- [Qwen/Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)
- [bartowski/Qwen2.5-Coder-7B-Instruct-GGUF](https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF)

### Tools & Libraries
- [tree-sitter](https://tree-sitter.github.io/) - Incremental parsing library
- [py-tree-sitter](https://github.com/tree-sitter/py-tree-sitter) - Python bindings

### Benchmarks
- [CodeSearchNet](https://github.com/github/CodeSearchNet) - Code search evaluation
- [CoIR](https://github.com/CoIR-team/coir) - Code Information Retrieval benchmark
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) - Massive Text Embedding Benchmark

---

## Appendix: Hardware Specifications

**Target System**: NVIDIA GeForce RTX 4080 SUPER
- **VRAM**: 16,376 MiB (16GB)
- **Compute Capability**: 8.9
- **CUDA Cores**: 10,240
- **Tensor Cores**: Yes (4th gen)
- **Memory Bandwidth**: 736 GB/s

**VRAM Allocation Strategy**:
- Embedding model: ~0.4GB (Jina-code)
- LLM: ~5.4GB (Qwen2.5-Coder-7B Q5_K_M)
- KV cache: ~2-3GB (for 8K context)
- Overhead: ~1GB
- **Total**: ~9GB used, ~7GB free

This leaves room for:
- Larger context sizes (up to ~32K tokens)
- Running other CUDA applications concurrently
- Future model size increases

---

## Conclusion

The three-phase approach (embedding → chunking → LLM) provides incremental, measurable improvements:

1. **Phase 1** (embedding swap): Quick win, 20-30% better retrieval
2. **Phase 2** (AST chunking): Transformative, 40-60% cumulative improvement
3. **Phase 3** (code LLM): Better synthesis and reasoning on retrieved code

All three phases are **independent** and can be implemented in any order or in parallel. However, Phase 2 (chunking) delivers the single largest quality improvement and should be prioritized.

**Total estimated effort**: 2-3 days for Phases 1-3, plus 1-2 days for optional enhancements (Phases 4-6).

**Expected outcome**: krag becomes genuinely capable at answering code-specific questions, with retrieval quality approaching or exceeding commercial RAG solutions for code.
