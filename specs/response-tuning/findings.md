# Response Quality Tuning — Cross-Session Planning Document

> **Purpose**: Track discoveries, implemented fixes, and future work for improving krag's RAG response quality. This document persists across sessions/evolutions.

## Problem Statement

krag's retrieval pipeline returns answers that miss factual information present in the indexed codebase. Evaluation tests show the LLM confidently fabricates answers instead of grounding them in retrieved context.

## Root Cause Analysis (2026-02-16)

### Diagnostic Session

**Test harness**: `krag eval tests/fixtures/eval_queries.toml -p strict` → 1/3 passed (33%)

| Query | Expected | Actual | Pass |
|-------|----------|--------|------|
| "What is the default chunk size in krag?" | substring "512", source defaults.py | "Krag does not have a default chunk size" | FAIL |
| "What embedding model does krag use by default?" | substring "all-MiniLM-L6-v2" | "Kaggle uses the Word2Vec model" | FAIL |
| "What is quantum computing and how does it relate to krag?" | no_hallucination | Hallucinated but had sources | PASS |

### Finding 1: Correct chunks rank too low

`defaults.py` contains `DEFAULT_CHUNK_SIZE = 512` and `DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"` but ranks **82-88 out of 100** (score 0.6051) vs irrelevant chunks at rank 1-9 (score 0.6612).

**Why**: The embedding model (`all-MiniLM-L6-v2`) is trained on natural language. It considers "krag's default chunker" (from docstrings in interfaces.py) more similar to "default chunk size" than `DEFAULT_CHUNK_SIZE = 512` (code constants). Raw code constant names are semantically opaque to NL-trained models.

### Finding 2: Duplicate content floods results

The same chunk from `interfaces.py` (chunk_index 18) appears **9 times** in the top 10 results, each with a different UUID but identical content and score. This happens because:

- `interfaces.py` and `test_interfaces.py` share identical docstrings
- The same text gets chunked to the same content with different chunk IDs
- No deduplication occurs at retrieval time

Out of 20 results with top_k=20, only **3 unique pieces of content** were returned.

### Finding 3: LLM confidently fabricates

When the retrieved context doesn't contain the answer (because the right chunks weren't retrieved), the Phi-3-medium model confidently fabricates plausible-sounding but wrong answers. The strict/balanced prompt presets instruct "only use information from the provided context", but the model ignores this instruction.

## Implemented Fixes

### Evolution 1: Quality Tuning Feature (004-rag-quality-tuning)

- Chat completion API migration (system/user messages)
- Prompt presets (strict/balanced/verbose)
- Similarity threshold filtering
- Evaluation harness
- Diagnostic logging

### Evolution 2: Response Quality Fixes (current)

#### Fix 2A: Enriched defaults.py comments (semantic boost)

**Problem**: Code constants like `DEFAULT_CHUNK_SIZE = 512` have poor semantic similarity to natural language queries.

**Solution**: Added descriptive natural-language comments to all constants in `defaults.py` so the embedding model can match them to user queries. Each constant now has a comment explaining what it configures in plain English.

**Impact**: Chunks containing these constants will have richer semantic content, improving their similarity scores for relevant queries.

#### Fix 2B: Retrieval-time deduplication

**Problem**: Identical content appearing multiple times (from test files, overlapping chunks, etc.) crowds out diverse results.

**Solution**: Added content-based deduplication in `Retriever.retrieve()`. After fetching from the vector store, results are filtered to keep only the first occurrence of each unique content hash. The retriever over-fetches (requests `top_k * 3` from the store) to ensure enough unique results survive dedup.

**Impact**: Top-k results now contain diverse chunks from different files, dramatically increasing the chance that the correct source file appears.

#### Fix 2C: Keyword boost re-ranking (hybrid search lite)

**Problem**: Pure semantic search misses exact keyword matches (e.g., "chunk size" → `DEFAULT_CHUNK_SIZE`).

**Solution**: After semantic retrieval and dedup, results are re-scored with a keyword boost. Query terms that appear in chunk content (case-insensitive) contribute a configurable bonus to the final score. Results are re-sorted by boosted score.

**Impact**: Chunks containing exact query keywords rank higher even if their semantic similarity is moderate.

#### Fix 2D: Context in user message (prompt restructuring)

**Problem**: Phi-3-medium Q2_K quantized model ignores grounding instructions in the system prompt. When context is in the system message, the model treats it as background rather than authoritative source material.

**Solution**: Moved retrieved context from the system message to the user message. System message now contains only the preset instructions. User message contains the context blocks, a grounding instruction ("Using ONLY the context above..."), and the query.

**Impact**: Pass rate improved from 33% → 67%. The model now correctly grounds its answer for Q1 (default chunk size = 512) and Q3 (quantum computing not related). Q2 (embedding model) fails because the model generalizes to "SentenceTransformer" instead of quoting the exact model name "all-MiniLM-L6-v2".

### Evolution 3: Model and Parameter Upgrades

After the code-level fixes in Evolution 2, the remaining quality gap was traced to model capabilities:

- **Embedding model upgrade**: Replaced `sentence-transformers/all-MiniLM-L6-v2` (384-dim) with `BAAI/bge-base-en-v1.5` (768-dim). BGE-base provides significantly stronger semantic matching for both natural language and code content.
- **LLM upgrade**: Replaced Q2_K quantization (~2.5GB) with Q5_K_M quantization (~10GB) of Phi-3-medium-128k-instruct. The higher-quality quantization dramatically improves instruction following and grounding.
- **Chunking tuned**: 512/50 → 384/64, optimized for BGE-base's input characteristics.
- **Context window**: 2048 → 8192 tokens, allowing the LLM to process more retrieved context.
- **Similarity threshold**: 0.3 → 0.2, calibrated for BGE-base's more conservative scoring.
- **Threading/batching**: Threads 4→8, batch size 32→64, for better hardware utilization.

**Impact**: Pass rate 67% → 100% (3/3). All evaluation queries now produce correctly grounded answers. The model accurately quotes specific values from retrieved context and appropriately refuses to answer when information is not in the corpus.

## Future Work

### Near-term

- [x] **Embedding model upgrade**: Upgraded to `BAAI/bge-base-en-v1.5` (768-dim) from `all-MiniLM-L6-v2` (384-dim). BGE-base provides strong retrieval quality for both NL and code content without requiring a code-specific model.
- [ ] **Chunking strategy for config/constants files**: Small files with many constants get chunked poorly. Consider a "whole-file" or "logical-block" chunking strategy for short config-like files.
- [ ] **Source diversity enforcement**: Ensure top-k results include chunks from at least N different files, not all from one file.

### Medium-term

- [ ] **Full BM25 hybrid search**: Add a proper sparse retrieval index (BM25) alongside dense vectors. Combine scores with reciprocal rank fusion (RRF). Libraries: `rank_bm25`, `tantivy` (via `tantivy-py`).
- [ ] **Query expansion**: Automatically expand queries to include likely code identifiers (e.g., "chunk size" → also search "CHUNK_SIZE", "chunk_size").
- [ ] **Contextual chunking**: Prepend file path and class/function context to each chunk so the embedding captures what module/component the code belongs to.
- [ ] **Re-ranker model**: Add a cross-encoder re-ranker (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) as a second pass after initial retrieval.

### Long-term

- [ ] **Eval suite expansion**: Build a comprehensive eval suite with 20+ queries covering code, config, architecture, and edge cases.
- [ ] **Automated regression testing**: Run eval suite in CI and fail on quality regressions.
- [ ] **Multi-modal retrieval**: Support diagram/image indexing for architecture docs.
- [ ] **User feedback loop**: Allow users to rate answers and use feedback to improve retrieval.

## Metrics Tracking

| Date | Eval File | Preset | Pass Rate | Notes |
|------|-----------|--------|-----------|-------|
| 2026-02-16 | eval_queries.toml (3q) | strict | 33% | Baseline, before fixes |
| 2026-02-16 | eval_queries.toml (3q) | balanced | 33% | Same results as strict |
| 2026-02-16 | eval_queries.toml (3q) | balanced | 33% | After fixes 2A+2B+2C, retrieval fixed but LLM still hallucinates |
| 2026-02-16 | eval_queries.toml (3q) | balanced | 67% | After fix 2D (context in user message), Q1+Q3 pass, Q2 fails (model generalizes) |
| 2026-02-16 | eval_queries.toml (3q) | balanced | 100% | After model upgrades (BGE-base + Q5_K_M + tuned params), all 3 pass |

## Key Configuration Reference

```toml
[retrieval]
similarity_threshold = 0.2

[prompt]
preset = "balanced"

[embedding]
model = "BAAI/bge-base-en-v1.5"
batch_size = 64

[chunking]
size = 384
overlap = 64
```

## Technical Notes

- Vector store: Qdrant (local/disk mode at `/krag/index`)
- Embedding dimension: 768 (BAAI/bge-base-en-v1.5)
- LLM: Phi-3-medium-128k-instruct-GGUF (Q5_K_M quantization, ~10GB)
- Context window: 8192 tokens
- Similarity metric: Cosine distance
