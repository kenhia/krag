# Contract: Obsidian Retrieval Mode

**Scope**: `src/krag/modes/builtin/obsidian.toml`

## Mode Definition

```toml
[mode]
name = "obsidian"
description = "Optimized for Obsidian vault content queries"

[collections]
docs = 1.0
code = 0.7

[llm]
slot = "text"

[prompt]
preset = "balanced"

[retrieval]
top_k = 8
similarity_threshold = 0.15

[critic]
enabled = true
threshold = 3
```

## Requirement Traceability

| Field | Value | Requirement |
|-------|-------|-------------|
| `collections.docs` | 1.0 | FR-023: targets docs |
| `collections.code` | 0.7 | FR-023: targets code with lower weight |
| `collections.tests` | (absent) | FR-023: excludes tests |
| `collections.text` | (absent) | FR-023: excludes text |
| `critic.enabled` | true | FR-024: critic enabled |
| `critic.threshold` | 3 | FR-024: threshold 3 |
| `prompt.preset` | "balanced" | FR-025: balanced preset |

## Loading Behavior

The `ModeLoader.load_directory()` method in `src/krag/modes/mode_loader.py` automatically picks up all `.toml` files from the builtin directory. No code changes required — just adding the file makes the mode available.

## Usage

```bash
krag query "my notes about project architecture" --mode obsidian
```
