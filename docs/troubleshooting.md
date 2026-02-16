# Troubleshooting

Common issues and solutions for krag and its plugin system.

## Plugin Issues

### Plugin Not Found After Installation

**Symptom**: `krag plugin list` doesn't show a recently installed plugin.

**Causes & Solutions**:

1. **Wrong Python environment**: The plugin was installed in a different Python environment than krag.
   ```bash
   # Check which Python krag uses
   which krag
   
   # Install in the correct environment
   uv pip install krag-plugin-markdown
   ```

2. **Missing entry point**: The plugin package doesn't register the `krag.plugins` entry point correctly.
   - Check the plugin's `pyproject.toml` has:
     ```toml
     [project.entry-points."krag.plugins"]
     plugin_name = "package.module:HandlerClass"
     ```
   - After fixing, reinstall: `uv pip install -e ./plugin-dir`

3. **Import error during discovery**: The plugin fails to import silently.
   - Run `krag plugin validate` for detailed error output
   - Check for missing dependencies: `uv pip install <missing-package>`

### Plugin Load Error

**Symptom**: `krag plugin list` shows the plugin with a load error.

**Common errors**:

| Error | Cause | Fix |
|-------|-------|-----|
| `No module named 'xyz'` | Missing dependency | `uv pip install xyz` |
| `API version incompatible` | Plugin needs newer/older krag | Update plugin or krag |
| `Not a FileTypeHandler subclass` | Wrong entry point target | Fix `pyproject.toml` entry point |
| `Invalid configuration` | Bad settings in config.toml | Check `[plugins.<name>]` section |

### Plugin Disabled During Indexing

**Symptom**: Plugin works initially but gets disabled mid-run.

**Cause**: The plugin raised an unhandled exception during `extract_text()` or `extract_metadata()`.

**Solutions**:
1. Check indexing output for the specific error message
2. Review the failure-to-index summary at the end of the run
3. File a bug with the plugin maintainer
4. Try updating the plugin: `uv pip install --upgrade <plugin-package>`

### File Extension Conflict

**Symptom**: Wrong plugin handles a file type.

**Solution**: Control plugin priority via the `enabled` list order in `config.toml`:
```toml
[plugins]
# First listed plugin wins for shared extensions
enabled = ["preferred_plugin", "other_plugin"]
```

## Configuration Issues

### Configuration File Not Found

**Symptom**: `No configuration file found` error.

**Solution**: Initialize krag configuration:
```bash
krag init
```

Default location: `~/.config/krag/config.toml`

### Invalid Configuration

**Symptom**: Validation errors when running krag commands.

**Solutions**:
```bash
# Validate configuration
krag config validate

# Show current configuration
krag config show

# Edit configuration
krag config edit
```

**Common config errors**:
- `directory_paths must not be empty` — Add at least one directory to index
- `All paths must be absolute` — Use full paths like `/home/user/docs`, not `~/docs`
- `chunk_overlap must be less than chunk_size` — Reduce overlap or increase chunk size
- Plugin listed in both `enabled` and `disabled` — Remove from one list

### Legacy Configuration Migration

If you have a YAML config from an older version:
```bash
krag migrate
```

This converts `config.yaml` to `config.toml` format.

## Indexing Issues

### No Files Found

**Symptom**: `Discovered 0 files` during indexing.

**Causes**:
1. **Directory doesn't exist**: Check paths in `config.toml`
2. **File types not supported**: Add extensions to `supported_file_types` or install appropriate plugins
3. **Exclusion patterns too broad**: Review `exclusion_patterns` in config
4. **Permission denied**: Check file/directory permissions

### Indexing Failures

**Symptom**: Some files fail to index.

**Solutions**:
1. Check the failure summary at the end of indexing output
2. Run with verbose logging: `krag index --verbose`
3. Common causes:
   - File encoding issues (non-UTF-8 without Latin-1 fallback)
   - Corrupted files
   - Files exceeding `max_file_size_mb` limit
   - Plugin extraction errors

## Performance Issues

### Slow Indexing

**Possible improvements**:
1. Use incremental indexing: `krag index --incremental`
2. Reduce chunk overlap: Lower `chunk_overlap` in config
3. Use GPU for embeddings: Set `embedding_device = "cuda"` or `"mps"`
4. Increase batch size: Raise `embedding_batch_size` (uses more memory)
5. Exclude large directories: Add patterns to `exclusion_patterns`

### High Memory Usage

**Solutions**:
1. Reduce `embedding_batch_size` (default: 32)
2. Use a smaller embedding model
3. Index fewer directories at once

## Getting Help

1. Check this troubleshooting guide
2. Run `krag --help` for command documentation
3. Run `krag plugin validate` for plugin diagnostics
4. Review logs in `~/.local/state/krag/logs/`
5. File an issue on the project repository

## Quality Tuning

### Prompt Presets

krag includes three built-in prompt presets that control how the LLM generates answers:

| Preset | Temperature | Max Tokens | Description |
|--------|-------------|------------|-------------|
| `strict` | 0.1 | 256 | Concise, source-grounded answers only |
| `balanced` | 0.2 | 512 | Detailed answers with citations (default) |
| `verbose` | 0.3 | 1024 | Exploratory answers with full context |

**Config file** (`~/.config/krag/config.toml`):

```toml
[prompt]
preset = "strict"
# system_override = "Custom system prompt..."
```

**CLI override** (takes precedence over config):

```bash
krag query "What is RAG?" --preset strict
```

### Similarity Threshold

Controls the minimum relevance score for retrieved chunks. Chunks below this threshold are filtered out before reaching the LLM.

```toml
[retrieval]
similarity_threshold = 0.3  # default; range 0.0–1.0
```

- **Lower values** (0.1–0.2): Include more context, may add noise
- **Default** (0.3): Good balance for most use cases
- **Higher values** (0.5+): Only highly relevant chunks, may miss useful context

### LLM Parameters

Fine-tune generation behavior:

```toml
[llm]
temperature = 0.2         # Lower = more deterministic
top_p = 0.9               # Nucleus sampling threshold
repeat_penalty = 1.1      # Penalize repeated tokens
min_p = 0.05              # Minimum probability threshold
```

### Evaluation Workflow

Run a suite of test queries to measure answer quality:

```bash
# Create an evaluation file (TOML format)
cat > eval-queries.toml << 'EOF'
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
EOF

# Run evaluation
krag eval eval-queries.toml

# With specific preset
krag eval eval-queries.toml --preset strict
```

**Check types**:

| Type | Description |
|------|-------------|
| `substring` | Answer must contain the specified text (case-insensitive) |
| `source_cited` | At least one retrieved source path must contain the value |
| `no_hallucination` | Answer either acknowledges insufficient context or has sources |

The eval command outputs JSON to stdout and a human summary to stderr. Exit code is 0 if all checks pass, 1 if any fail.

### Debugging Queries

Enable DEBUG logging to see the full pipeline state:

```bash
krag query "test query" --log-level DEBUG
```

This reveals:
- Each retrieved chunk with score and source file
- Threshold filtering results
- Complete chat messages sent to the LLM
- Generation parameter values
