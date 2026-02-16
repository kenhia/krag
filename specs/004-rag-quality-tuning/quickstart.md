# Quickstart: RAG Quality Tuning

## 1. Select a Prompt Preset

Three built-in presets control how the LLM formats answers:

| Preset | Behavior |
|--------|----------|
| `strict` | Concise, source-grounded answers only |
| `balanced` | Detailed answers with numbered citations (default) |
| `verbose` | Exploratory answers with full context |

### Via CLI

```bash
krag query "What is chunking?" --preset strict
```

### Via Config (krag.toml)

```toml
[prompt]
preset = "balanced"
# system_override = "Custom system prompt text"
```

## 2. Tune Retrieval Quality

### Similarity Threshold

Filter out low-relevance chunks before they reach the LLM:

```toml
[retrieval]
top_k = 5
similarity_threshold = 0.3   # 0.0 = keep all, 1.0 = exact match only
```

Higher values → fewer but more relevant chunks. Start at `0.3` and increase if answers include irrelevant context.

### Chunk Size

Smaller chunks give more precise retrieval; larger chunks give more context:

```toml
[chunking]
chunk_size = 512
chunk_overlap = 50
```

## 3. Tune LLM Generation

```toml
[llm]
temperature = 0.2          # lower = more deterministic
top_p = 0.9                # nucleus sampling
repeat_penalty = 1.1       # discourage repetition
min_p = 0.05               # minimum token probability
```

## 4. Run Evaluation

Create a TOML file with test queries and expected checks:

```toml
# eval-tests.toml
[[queries]]
query = "What is the default chunk size?"

[[queries.checks]]
type = "substring"
value = "512"

[[queries.checks]]
type = "source_cited"
value = "defaults.py"

[[queries]]
query = "What is quantum computing?"

[[queries.checks]]
type = "no_hallucination"
```

Run the evaluation:

```bash
krag eval eval-tests.toml
```

- **JSON report** → stdout (pipe to file: `krag eval eval-tests.toml > report.json`)
- **Human summary** → stderr (always visible in terminal)
- **Exit code** 0 = all pass, 1 = any failure

### Check Types

| Type | What it checks |
|------|---------------|
| `substring` | Case-insensitive substring match in the answer |
| `source_cited` | A source path contains the given value |
| `no_hallucination` | Answer acknowledges uncertainty OR is backed by sources |

## 5. Iterate

1. Run eval → review failures
2. Adjust preset / threshold / temperature
3. Re-run eval → compare pass rates
4. Repeat until quality targets are met
