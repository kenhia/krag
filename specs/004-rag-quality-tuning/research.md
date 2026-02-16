# Research: RAG Quality Tuning & Hallucination Reduction

**Feature**: 004-rag-quality-tuning  
**Date**: 2026-02-16  
**Status**: Complete — all NEEDS CLARIFICATION resolved

## 1. Prompt Templates & LLM Generation Settings

### 1.1 System Prompt Architecture

- **Decision**: Migrate from text completion API (`model()`) to chat completion API (`model.create_chat_completion()`) with separate `system` and `user` message roles.
- **Rationale**: Modern GGUF models embed chat templates in metadata. The current combined-string approach bypasses the model's expected chat format, actively degrading instruction following. Chat API handles stop sequences and formatting automatically per model family.
- **Alternatives considered**: Keeping text completion API (simpler code but sacrifices quality); three-message pattern with context-as-assistant (confuses small models).

### 1.2 Grounding Constraints for Small Models (3B-7B)

- **Decision**: Use short, imperative, positive constraint language. Place the grounding constraint first in the system prompt. Use ALL-CAPS emphasis on key words (ONLY, MUST). Repeat the grounding constraint after context as a reminder.
- **Rationale**: Small models have limited instruction-following capacity. Shorter prompts, primacy bias, and emphasis measurably improve compliance. Negative framing ("Do NOT use outside knowledge") is less reliable than positive ("ONLY use provided context").
- **Alternatives considered**: Few-shot examples (consumes context window); chain-of-thought phrasing (unreliable on 3B models).

### 1.3 "I Don't Know" Responses

- **Decision**: Use an explicit, exact fallback phrase in the system prompt: "I don't have enough information to answer that based on the available documents." Use the `exactly` keyword in the instruction.
- **Rationale**: Small models produce unreliable uncertainty calibration. Giving a specific phrase makes it testable via the eval harness (FR-016 check type 3) and reduces the model's decision burden.
- **Alternatives considered**: Confidence scoring (unreliable with small models); multiple fallback phrases (harder to test programmatically).

### 1.4 Source Citation

- **Decision**: Label context chunks with numbered sources (`[1] (path/to/file.md)`) and instruct the model to cite by number using parenthetical style `(1)`.
- **Rationale**: Small models handle inline numbered citations more reliably than path-based or footnote-based citations. Numbered sources reduce token waste and avoid path mangling.
- **Alternatives considered**: No citation (contradicts FR-003); verbatim path citation (models truncate/hallucinate paths); structured JSON output (harder to read).

### 1.5 Prompt Presets

- **Decision**: Three presets — `strict`, `balanced` (default), `verbose` — each bundling a system prompt string AND generation parameter defaults as a coherent unit.

| Preset | Temperature | top_p | repeat_penalty | max_tokens | Use Case |
|--------|-------------|-------|----------------|------------|----------|
| strict | 0.1 | 0.9 | 1.1 | 256 | Factual lookup, code docs |
| balanced | 0.2 | 0.9 | 1.1 | 512 | General Q&A (default) |
| verbose | 0.3 | 0.95 | 1.05 | 1024 | Exploration, summarization |

- **Rationale**: Prompt text and generation params interact — a "strict" prompt with high temperature undermines itself. Bundling ensures coherent behavior.
- **Alternatives considered**: More presets (diminishing returns); presets as prompt-only (loses coherence); per-model presets (combinatorial complexity).

### 1.6 Generation Parameters

- **Decision**: Defaults for `balanced` preset: `temperature=0.2, top_p=0.9, repeat_penalty=1.1, max_tokens=512`. Also expose `min_p=0.05` (llama.cpp-specific hallucination filter).
- **Rationale**: `temperature=0.0` produces loops on small models ~15-20% of the time. `0.1-0.2` with `repeat_penalty=1.1` is the practical sweet spot. Current default of `0.7` is too high for factual Q&A.
- **Alternatives considered**: Mirostat sampling (interacts poorly with repeat_penalty; less intuitive); temperature=0.0 without repeat_penalty (degenerate on small models).

### 1.7 Stop Sequences

- **Decision**: Use `create_chat_completion()` which handles stop sequences automatically from GGUF metadata. No manual stop sequences needed.
- **Rationale**: Current hardcoded `["User Question:", "\n\n\n"]` is fragile and format-dependent. Chat API reads model-specific EOS tokens from metadata.
- **Alternatives considered**: Manual structural stop sequences (maintenance burden); grammar-based stopping (overkill for natural language).

## 2. Similarity Score Thresholds & Retrieval

### 2.1 Score Ranges for all-MiniLM-L6-v2

Empirical cosine similarity bands:

| Score Range | Interpretation |
|-------------|---------------|
| 0.70–1.0 | High relevance — near-paraphrase or direct semantic match |
| 0.45–0.70 | Moderate relevance — topically related, likely useful |
| 0.25–0.45 | Weak relevance — tangentially related, may contain noise |
| 0.0–0.25 | Irrelevant — unrelated content |

### 2.2 Default Threshold

- **Decision**: Static threshold of 0.3 as a noise floor.
- **Rationale**: Filters bottom ~25% of the range (clearly unrelated content). MiniLM-L6-v2 is a general-purpose model that produces lower absolute scores than retrieval-specialized models — threshold above 0.5 would be too aggressive.
- **Alternatives considered**: 0.2 (too permissive); 0.4 (risks dropping moderate matches); relative/adaptive (complex, harder to debug).

### 2.3 Threshold × Top-K Interaction

- **Decision**: Filter AFTER top-k selection (limit-then-filter) in the Retriever layer. Retrieve `top_k` results from Qdrant without threshold, then apply threshold in Python.
- **Rationale**: Application-level filtering keeps logic visible in diagnostic logging ("retrieved 5, kept 3 after threshold 0.3") — essential for eval and debugging stories. Negligible performance cost at top_k=5 on local Qdrant.
- **Alternatives considered**: Qdrant-level score_threshold (loses diagnostic visibility); hybrid over-fetch (premature optimization).

### 2.4 Insufficient Context Handling

- **Decision**: Tiered approach: (1) zero chunks pass threshold → skip LLM call, return structured "insufficient context" response; (2) some but not all pass → proceed with passing chunks + log diagnostic; (3) include filtered-out count and score range in diagnostics.
- **Rationale**: Skipping the LLM call when there's no useful context saves compute and avoids the most common hallucination vector. Supports SC-002 (90% "insufficient context" on out-of-scope queries).
- **Alternatives considered**: Always call LLM and rely on prompt (less reliable); configurable strict/best-effort tied to preset (future enhancement).

### 2.5 Chunk Size Effects

- **Decision**: Current 512 chars / 50 chars overlap is acceptable but conservative. The overlap is low (10%) compared to research-optimal 50%. Consider increasing default overlap to 100 chars.
- **Rationale**: Chroma research with MiniLM-L6-v2 found best recall at 250 tokens (~700 chars) with 50% overlap. Current 512 chars is ~128-200 tokens, safely within the model's 256-token window. Overlap has more impact than size.
- **Alternatives considered**: Increase to 768/128 (closer to optimal); token-based chunking (more precise but more complex).

## 3. Evaluation Harness

### 3.1 Query Definition Format

- **Decision**: TOML format using `[[query]]` array-of-tables with nested `[[query.check]]` arrays.
- **Rationale**: Consistent with krag's all-TOML configuration. Python 3.11+ has built-in `tomllib`. TOML `[[array]]` syntax is natural for flat lists of test cases.
- **Alternatives considered**: YAML (second format to document); JSON (painful to hand-author); Python fixtures (not usable from CLI).

Required fields per query: `id` (unique, stable), `text` (query string), `check` (≥1 behavior check). Optional: `tags`, `description`.

### 3.2 Check Implementations

**Substring contains/excludes**: Case-insensitive by default with `case_sensitive` override. Plain `in` operator — no regex. Report exact check that failed.

**Source file citation**: Check `QueryResult.file_path` using suffix/substring matching (portable across environments). Check structured source data, not answer text. Report which files WERE retrieved on failure.

**Insufficient context**: Match answer text against a curated list of refusal phrases (case-insensitive). Default list: `["i don't know", "don't have enough", "insufficient context", "no relevant", "cannot answer", "not enough information", "no information available"]`. Overridable per-project.

### 3.3 Report Format

- **Decision**: Single JSON object to stdout with `metadata`, `summary`, and `results` sections. Human-readable summary table to stderr.
- **Rationale**: JSON is `jq`/`diff`-friendly for cross-run comparison. Stable query IDs as keys enable programmatic diffing.

Key report fields:
- `metadata`: timestamp, krag version, eval file, config file, config digest (SHA256), model, preset
- `summary`: total/passed/failed/pass_rate, broken down by_check_type and by_tag
- `results[]`: per-query query_id, answer, sources (with scores and chunk_preview), prompt, checks with individual pass/fail

### 3.4 Architecture Pattern

- **Decision**: Pure-Python `EvalRunner` class that the CLI thin-wraps. Same pattern as `QueryEngine` / `query_command`.
- **Rationale**: Tests import `EvalRunner` directly. CLI delegates to it. Follows krag's established architecture.

Module layout:
```
src/krag/evaluation/
    __init__.py
    runner.py       # EvalRunner class
    checks.py       # Check implementations
    report.py       # Report formatting
```

### 3.5 Pipeline Reuse

- **Decision**: Reuse `QueryEngine` directly. No isolated/parallel pipeline.
- **Rationale**: Eval should test the same code path users run. `QueryEngine.query()` returns `QueryResponse` with `.answer` and `.sources` — exactly the data needed for all check types. For determinism, recommend `temperature=0.0` in eval configs.
- **Alternatives considered**: Mock LLM for fast cycles (fine for harness unit tests, not for real eval); cached responses/replay (deferred to future).

## Summary of Key Decisions

| Area | Current State | Recommended Change |
|------|---------------|-------------------|
| LLM API | `model()` (text completion) | `model.create_chat_completion()` |
| System prompt | Combined with context | Separate `system` role message |
| Temperature | 0.7 | 0.2 (balanced default) |
| repeat_penalty | Not set (1.0) | 1.1 |
| Stop sequences | Hardcoded | Handled by chat API |
| Context formatting | `[Source: path]` | `[1] (path)` — numbered for citation |
| Presets | None | strict / balanced / verbose |
| Fallback phrase | Generic | Exact canonical phrase for eval matching |
| Similarity threshold | None | 0.3 static floor, post-retrieval filter |
| Insufficient context | Pass to LLM always | Skip LLM when 0 chunks pass threshold |
| Eval format | N/A | TOML input, JSON output |
| Eval architecture | N/A | EvalRunner wrapping QueryEngine |
