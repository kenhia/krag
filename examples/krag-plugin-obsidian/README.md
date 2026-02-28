# krag-plugin-obsidian

A krag file-type plugin for Obsidian vault content.

## Features

- **Path-based ownership**: Claims `.md` files only when they reside under a configured vault path. Non-vault markdown files are handled by the generic markdown plugin.
- **Mixed-content routing**: Splits notes into prose (→ `docs` collection) and fenced code blocks (→ `code` collection).
- **Virtual paths**: Stores results under `obsidian://vault-name/path` prefixes for clean attribution.
- **Custom retrieval mode**: `--mode obsidian` targets `docs` and `code` collections with vault-appropriate weights.
- **Domain lexicon**: Contributes Obsidian-specific terminology (backlink, wikilink, MOC, etc.) to improve query retrieval.

## Installation

```bash
uv pip install -e examples/krag-plugin-obsidian
```

## Configuration

Add vault paths to your `config.toml`:

```toml
[plugins.obsidian.vaults]
gratch = "~/obsidian/gratch"
work = "/data/vaults/work"
```

## Usage

```bash
# Index vault content
krag index -d ~/obsidian/gratch

# Query with obsidian mode
krag query "my notes about architecture" --mode obsidian
```

## Development

```bash
uv pip install -e "examples/krag-plugin-obsidian[dev]"
cd examples/krag-plugin-obsidian
uv run pytest
```
