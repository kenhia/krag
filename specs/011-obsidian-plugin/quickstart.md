# Quickstart: 011-obsidian-plugin

**Branch**: `011-obsidian-plugin` | **Date**: 2026-02-27

## Prerequisites

- krag installed and working (`krag --version`)
- At least one Obsidian vault on disk (a directory with `.md` files)
- Python 3.11+

## 1. Install the Plugin

```bash
cd examples/krag-plugin-obsidian
uv pip install -e .
```

Verify discovery:
```bash
krag plugins list
# Should show: obsidian (1.0.0) - Obsidian vault content handler
```

## 2. Configure Vault Paths

Add to your `config.toml`:

```toml
[plugins.obsidian.vaults]
my-vault = "~/obsidian/my-vault"
```

Replace the path with your actual vault location. You can add multiple vaults:

```toml
[plugins.obsidian.vaults]
personal = "~/obsidian/personal"
work = "/data/vaults/work"
```

## 3. Index Your Vault

```bash
krag index -d ~/obsidian/my-vault
```

Expected output:
```
Discovered 142 files
Processing files... [========] 142/142
Obsidian plugin handled 138 .md files
  → docs collection: 412 prose chunks
  → code collection: 47 code block chunks
Generic handlers: 4 non-.md files → text collection
Indexing complete (job_id=...)
```

## 4. Query Vault Content

```bash
# Default mode
krag query "meeting notes from last week"

# Obsidian-optimized mode (targets docs + code with tuned weights)
krag query "my project architecture notes" --mode obsidian
```

Results show virtual paths:
```
[0.87] obsidian://my-vault/projects/architecture.md (chunk 2)
  "The system uses a three-tier architecture with..."

[0.82] obsidian://my-vault/meetings/2026-02-20.md (chunk 1)
  "Discussed the new API design..."
```

## 5. Verify Mixed-Content Routing

For a note containing fenced code blocks:

```bash
# Check docs collection
krag retrieve "explain the algorithm" --mode docs
# → Should find prose from vault notes

# Check code collection  
krag retrieve "python function" --mode code
# → Should find fenced code blocks from vault notes
```

Via debug endpoint (if kragd is running):
```bash
curl http://localhost:8000/debug/qdrant | jq '.collections'
# Shows krag_docs and krag_code with vault-sourced chunks
```

## 6. Key Behaviors

| Scenario | What Happens |
|----------|-------------|
| `.md` file inside vault path | Handled by Obsidian plugin |
| `.md` file outside vault path | Handled by generic markdown plugin |
| Fenced code block with language tag | Routed to `code` collection |
| Fenced code block without language tag | Treated as prose → `docs` collection |
| Vault path doesn't exist | Warning logged, vault skipped |
| No vaults configured | Plugin active but claims no files |

## 7. Troubleshooting

**Plugin not appearing in `krag plugins list`**:
- Ensure you ran `uv pip install -e .` from the plugin directory
- Check that the `krag.plugins` entry point is in `pyproject.toml`

**Files not being claimed by Obsidian plugin**:
- Verify vault path in config matches the indexed directory
- Check `krag index` log for "Plugin 'obsidian' claims file by path" messages
- Ensure vault path exists on disk

**No results from `--mode obsidian`**:
- Verify the mode is available: `krag modes list`
- Ensure vault content was indexed (check `krag status`)
