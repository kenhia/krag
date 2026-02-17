# Data Model: RAG Quality Tuning & Hallucination Reduction

**Feature**: 004-rag-quality-tuning  
**Date**: 2026-02-16

## New Entities

### PromptPreset

Represents a named prompt configuration combining system prompt text and generation parameters.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | str | Yes | Preset identifier: "strict", "balanced", "verbose" |
| system_prompt | str | Yes | System prompt text sent as the `system` role message |
| temperature | float | Yes | Sampling temperature (0.0–2.0) |
| top_p | float | Yes | Nucleus sampling cutoff (0.0–1.0) |
| repeat_penalty | float | Yes | Repetition penalty multiplier (≥1.0) |
| max_tokens | int | Yes | Maximum tokens to generate |
| description | str | No | Human-readable description of the preset's purpose |

**Validation rules**:
- `name` must be one of the built-in names or a user-defined identifier (alphanumeric + hyphens)
- `temperature` must be in [0.0, 2.0]
- `top_p` must be in [0.0, 1.0]
- `repeat_penalty` must be ≥ 1.0
- `max_tokens` must be > 0

**Built-in instances**:

| Preset | temperature | top_p | repeat_penalty | max_tokens |
|--------|-------------|-------|----------------|------------|
| strict | 0.1 | 0.9 | 1.1 | 256 |
| balanced | 0.2 | 0.9 | 1.1 | 512 |
| verbose | 0.3 | 0.95 | 1.05 | 1024 |

### EvalQuery

A test case definition for the evaluation harness.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str | Yes | Unique, stable identifier for cross-run comparison |
| text | str | Yes | The query string to execute against the knowledge base |
| checks | list[EvalCheck] | Yes (≥1) | One or more behavior checks to validate |
| tags | list[str] | No | Categorization for filtering/grouping in reports |
| description | str | No | Human note explaining what the query tests |

**Validation rules**:
- `id` must be unique within an evaluation file
- `text` must be non-empty
- `checks` must contain at least one check

### EvalCheck

A single behavior check within an evaluation query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | str | Yes | Check type: "contains", "excludes", "source_file", "insufficient_context" |
| value | str | Conditional | Required for "contains", "excludes", "source_file"; not used for "insufficient_context" |
| case_sensitive | bool | No | Default: false. Only applies to "contains" and "excludes" |

**Validation rules**:
- `type` must be one of the four allowed values
- `value` is required when `type` is "contains", "excludes", or "source_file"
- `value` must not be provided when `type` is "insufficient_context"

### EvalResult

Result of running a single evaluation query.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query_id | str | Yes | References EvalQuery.id |
| query_text | str | Yes | The query that was executed |
| tags | list[str] | No | Copied from EvalQuery |
| passed | bool | Yes | True if ALL checks passed |
| duration_seconds | float | Yes | Wall-clock time for this query |
| answer | str | Yes | Generated answer text |
| sources | list[SourceInfo] | Yes | Retrieved chunks with scores |
| prompt | str | Yes | Complete prompt sent to LLM |
| checks | list[CheckResult] | Yes | Per-check pass/fail results |

### SourceInfo

Metadata about a retrieved source chunk (for eval reports).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file_path | str | Yes | Source file path (reduced) |
| score | float | Yes | Cosine similarity score |
| rank | int | Yes | Retrieval rank (1-based) |
| chunk_preview | str | Yes | First ~200 chars of chunk content |

### CheckResult

Result of a single behavior check.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | str | Yes | Check type that was evaluated |
| value | str | No | The value that was checked for (if applicable) |
| passed | bool | Yes | Whether this check passed |
| message | str | No | Diagnostic message on failure |

### EvalReport

Aggregate evaluation results.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| metadata | ReportMetadata | Yes | Run context information |
| summary | ReportSummary | Yes | Aggregate pass/fail statistics |
| results | list[EvalResult] | Yes | Per-query detailed results |

### ReportMetadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timestamp | str (ISO 8601) | Yes | When the evaluation was run |
| krag_version | str | Yes | krag package version |
| eval_file | str | Yes | Path to the evaluation definition file |
| config_file | str | Yes | Path to the krag config used |
| config_digest | str | Yes | SHA256 of config file |
| duration_seconds | float | Yes | Total evaluation time |
| model | str | Yes | LLM model identifier |
| prompt_preset | str | Yes | Prompt preset used |

### ReportSummary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| total | int | Yes | Total number of queries |
| passed | int | Yes | Number passed (all checks) |
| failed | int | Yes | Number failed (any check) |
| pass_rate | float | Yes | passed / total |
| by_check_type | dict[str, TypeSummary] | Yes | Pass rate broken down by check type |
| by_tag | dict[str, TagSummary] | No | Pass rate broken down by tag |

### TypeSummary / TagSummary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| total | int | Yes | Number of checks/queries in this group |
| passed | int | Yes | Number passed |
| failed | int | Yes | Number failed |
| pass_rate | float | Yes | passed / total |

## Modified Entities

### Configuration (existing)

New fields to add:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| similarity_threshold | float | 0.3 | Minimum cosine similarity score for chunk inclusion |
| llm_top_p | float | 0.9 | Nucleus sampling cutoff |
| llm_repeat_penalty | float | 1.1 | Repetition penalty |
| llm_min_p | float | 0.05 | Minimum p filter (llama.cpp specific) |
| prompt_preset | str | "balanced" | Active prompt preset name |
| prompt_system_override | str | None | Custom system prompt override (replaces preset's system prompt) |

**Validation rules**:
- `similarity_threshold` must be in [0.0, 1.0]
- `llm_top_p` must be in [0.0, 1.0]
- `llm_repeat_penalty` must be ≥ 1.0
- `llm_min_p` must be in [0.0, 1.0]
- `prompt_preset` must be one of the built-in preset names or match a user-defined preset
- All new fields have backward-compatible defaults (existing configs continue to work)

### TOML Configuration Sections

New/updated sections in the config file:

```toml
[retrieval]
top_k = 5
similarity_threshold = 0.3

[llm]
model = "microsoft/Phi-3-mini-4k-instruct-gguf"
temperature = 0.2        # Now defaults to 0.2 instead of 0.7
top_p = 0.9
repeat_penalty = 1.1
min_p = 0.05
max_tokens = 512
context_size = 2048

[prompt]
preset = "balanced"       # NEW section
system_override = ""      # Optional: replaces preset system prompt
```

## Entity Relationships

```
Configuration 1──1 PromptPreset (selected by name)
EvalQuery 1──* EvalCheck
EvalResult 1──1 EvalQuery (by id reference)
EvalResult 1──* SourceInfo
EvalResult 1──* CheckResult
EvalReport 1──1 ReportMetadata
EvalReport 1──1 ReportSummary
EvalReport 1──* EvalResult
```

## State Transitions

### Evaluation Query Lifecycle

```
LOADED (from TOML) → EXECUTING (query sent to pipeline) → CHECKED (behavior checks applied) → REPORTED (included in output)
```

No persistent state — evaluation is a stateless batch operation.
