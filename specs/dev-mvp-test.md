# MVP Testing Guide

**Date**: 2026-02-04  
**Purpose**: Manual testing of KRAG MVP (User Stories 1 & 2)  
**Status**: Phase 4 Complete - Ready for End-to-End Testing

## Overview

This guide walks through testing the complete MVP functionality:
- **User Story 1**: Query personal knowledge base with natural language
- **User Story 2**: Index local and network storage locations

## Prerequisites

- Python 3.11+ with uv installed
- Git repository cloned and dependencies installed
- Access to test directories:
  - `/home/ken` (local storage)
  - `/gratch/KUB1/home/ken` (network storage)

## Test Workflow

### Step 1: Initialize Configuration

Create a fresh configuration for testing:

```bash
cd /home/ken/src/krag

# Remove any existing config and storage
rm -rf ~/.config/krag/

# Initialize new configuration
uv run python -m krag.cli init

# Expected output:
# Created configuration at /home/ken/.config/krag/config.yaml
# Default Settings:
#   Directories: [PosixPath('/home/ken/Documents')]
#   Embedding model: sentence-transformers/all-MiniLM-L6-v2
#   Vector store: /home/ken/.config/krag/storage
#   LLM model: /home/ken/.config/krag/models/model.gguf
```

**Verify**: Configuration file created at `~/.config/krag/config.yaml`

### Step 2: Customize Configuration (Optional)

Edit the configuration to adjust settings:

```bash
# View current configuration
uv run python -m krag.cli config show

# Edit configuration (opens in editor)
uv run python -m krag.cli config edit

# Validate configuration
uv run python -m krag.cli config validate
```

**Suggested Edits** (in `~/.config/krag/config.yaml`):
```toml
# Adjust file types if needed
supported_file_types = [
    ".txt", ".md", ".py", ".js", ".ts", 
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".rs", ".go", ".rb", ".php",
    ".json", ".yaml", ".yml", ".toml"
]

# Add exclusion patterns for large/unnecessary directories
exclusion_patterns = [
    "**/node_modules/**",
    "**/.git/**",
    "**/build/**",
    "**/__pycache__/**",
    "**/.venv/**",
    "**/venv/**",
    "**/dist/**",
    "**/target/**",
    "**/.cache/**",
    "**/tmp/**",
    "**/temp/**"
]
```

### Step 3: Dry Run - Preview Indexing

Test file discovery without actually indexing:

```bash
# Dry run for local home directory
uv run python -m krag.cli index \
    --dir /home/ken \
    --dry-run

# Expected output:
# - Count of discovered files by type
# - Table showing file extensions and counts
# - No actual indexing performed
```

```bash
# Dry run for network storage (if accessible)
uv run python -m krag.cli index \
    --dir /gratch/KUB1/home/ken \
    --dry-run
```

**Verify**: 
- File counts seem reasonable
- Unexpected file types not included
- No errors about missing directories

### Step 4: Index Local Directory

Index your local home directory:

```bash
# Index /home/ken with progress tracking
uv run python -m krag.cli index \
    --dir /home/ken

# This will:
# 1. Discover all supported files
# 2. Extract text content
# 3. Chunk into manageable pieces
# 4. Generate embeddings (384-dimensional vectors)
# 5. Store in Qdrant vector database
```

**Expected Output**:
```
Initializing indexing pipeline...
Directories: /home/ken
Vector store: /home/ken/.krag/storage
Mode: Full reindex

[Progress bar showing file processing]

============================================================
Indexing Complete!
============================================================

 Files discovered      XXX
 Files processed       XXX
 Chunks created        XXX
 Embeddings generated  XXX
 Vectors stored        XXX
```

**Time Estimate**: 
- Small home dir (~1000 files): 5-10 minutes
- Medium home dir (~5000 files): 20-30 minutes
- Large home dir (~10000 files): 30-60 minutes

**Note**: Initial run downloads the embedding model (~90MB) which may take a few minutes.

### Step 5: Check Indexing Status

Verify the index was created successfully:

```bash
uv run python -m krag.cli status

# Expected output:
#                  KRAG System Status
# ┌─────────────────┬────────────────────────────────────────┐
# │ Configuration   │ /home/ken/.config/krag/config.yaml     │
# │ Directories     │ /home/ken/Documents                    │
# │ Embedding Model │ sentence-transformers/all-MiniLM-L6-v2 │
# │ Vector Store    │ /home/ken/.config/krag/storage         │
# │ Collection      │ krag_embeddings                        │
# │ Indexed Vectors │ XXXX                                   │
# │ Status          │ green                                  │
# └─────────────────┴────────────────────────────────────────┘
```

**Verify**:
- Indexed Vectors count > 0
- Status is "green"
- Vector Store path exists

### Step 6: Index Network Storage

Add network storage to the index:

```bash
# Check if network path is accessible
ls /gratch/KUB1/home/ken

# If accessible, index it
uv run python -m krag.cli index \
    --dir /gratch/KUB1/home/ken

# Note: If the path is not accessible or doesn't exist, 
# the command will fail gracefully with an error message
```

**Alternative - Index Multiple Directories at Once**:
```bash
uv run python -m krag.cli index \
    --dir /home/ken \
    --dir /gratch/KUB1/home/ken
```

### Step 7: Verify Combined Index

Check that both locations are indexed:

```bash
uv run python -m krag.cli status

# Should show increased vector count
```

### Step 8: Test Queries

Now test retrieval by querying the indexed content:

#### Query 1: Code Search
```bash
# Find Python functions or code patterns
uv run python -m krag.cli query \
    "Python function for vector similarity" \
    --config ~/.krag/config.yaml \
    --no-synthesis \
    --show-sources \
    --top-k 5
```

#### Query 2: Documentation Search
```bash
# Find documentation or explanations
uv run python -m krag.cli query \
    "How to configure embeddings" \
    --config ~/.krag/config.yaml \
    --no-synthesis \
    --show-sources
```

#### Query 3: Configuration Search
```bash
# Find configuration files or settings
uv run python -m krag.cli query \
    "database configuration settings" \
    --config ~/.krag/config.yaml \
    --no-synthesis \
    --show-sources
```

#### Query 4: Project-Specific Search
```bash
# Search for project-specific content
uv run python -m krag.cli query \
    "RAG system architecture" \
    --config ~/.krag/config.yaml \
    --show-sources
```

**Expected Output Format**:
```
Query: "your search query"

📄 Results (retrieval only):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Score: 0.XXXX
   📁 Source: /path/to/file.ext
   
   [Relevant excerpt from the file...]

2. Score: 0.XXXX
   📁 Source: /path/to/another-file.ext
   
   [Another relevant excerpt...]
```

### Step 9: Advanced Testing

#### Test Incremental Indexing

After modifying some files, test incremental updates:

```bash
# Make some changes to indexed files
echo "# New content" >> /home/ken/test-doc.md

# Run incremental update
uv run python -m krag.cli index \
    --dir /home/ken \
    --incremental

# Expected: Only changed files are re-processed
```

#### Test File Type Filtering

Index only specific file types:

```bash
# Index only Python files
uv run python -m krag.cli index \
    --dir /home/ken/src \
    --type .py \
    --dry-run
```

#### Test Exclusion Patterns

Exclude specific directories:

```bash
# Index but exclude node_modules and build directories
uv run python -m krag.cli index \
    --dir /home/ken/projects \
    --exclude "**/node_modules/**" \
    --exclude "**/build/**" \
    --dry-run
```

## Verification Checklist

- [ ] Configuration initialized successfully
- [ ] Dry-run shows expected file counts
- [ ] Local directory indexed without errors
- [ ] Network directory indexed (if accessible)
- [ ] Status command shows correct vector count
- [ ] Queries return relevant results
- [ ] Query results include file paths
- [ ] Query scores are reasonable (0.0-1.0 range)
- [ ] Incremental indexing works (optional)
- [ ] File filtering works as expected (optional)

## Troubleshooting

### Issue: "Configuration not found"
```bash
# Solution: Initialize configuration
uv run python -m krag.cli init
```

### Issue: "Directory does not exist"
```bash
# Verify the path exists
ls -la /path/to/directory

# Check for typos in path
# Ensure network paths are mounted
```

### Issue: Slow indexing
```bash
# Check file count first with dry-run
uv run python -m krag.cli index --dir /path --dry-run

# Consider excluding large unnecessary directories
uv run python -m krag.cli index \
    --dir /path \
    --exclude "**/node_modules/**" \
    --exclude "**/.git/**"
```

### Issue: No query results
```bash
# 1. Verify vectors were stored
uv run python -m krag.cli status

# 2. Check vector store exists
ls -la ~/.config/krag/storage

# 3. Try a broader query
# 4. Verify the config path in query command
```

### Issue: Query command config mismatch
```bash
# Query command needs explicit config path
uv run python -m krag.cli query "search" \
    --config ~/.krag/config.yaml \
    --no-synthesis \
    --show-sources
```

## Performance Metrics

Track these metrics during testing:

| Metric | Target | Actual |
|--------|--------|--------|
| Files indexed | N/A | ___ |
| Indexing time | ~10 min per 1000 files | ___ |
| Vectors created | ~1-3 per file | ___ |
| Query response time | < 5 seconds | ___ |
| Query relevance | Top result relevant | ✓/✗ |
| Storage size | ~1MB per 1000 files | ___ |

## Test Results Summary

**Date**: _______________  
**Tester**: _______________

### Indexing Results

- **Local directory** (`/home/ken`):
  - Files discovered: ___
  - Files processed: ___
  - Chunks created: ___
  - Vectors stored: ___
  - Indexing time: ___
  - Errors: ___

- **Network directory** (`/gratch/KUB1/home/ken`):
  - Files discovered: ___
  - Files processed: ___
  - Chunks created: ___
  - Vectors stored: ___
  - Indexing time: ___
  - Errors: ___

### Query Results

| Query | Top Result Relevant? | Response Time | Notes |
|-------|---------------------|---------------|-------|
| "Python function for vector similarity" | ✓/✗ | ___ sec | |
| "How to configure embeddings" | ✓/✗ | ___ sec | |
| "database configuration settings" | ✓/✗ | ___ sec | |
| "RAG system architecture" | ✓/✗ | ___ sec | |

### Issues Encountered

1. _______________________________________________
2. _______________________________________________
3. _______________________________________________

### Overall Assessment

- [ ] MVP meets acceptance criteria
- [ ] Ready for further development
- [ ] Issues need resolution before proceeding

**Notes**: 
_______________________________________________
_______________________________________________
_______________________________________________

## Next Steps

After successful MVP testing:

1. **Document findings** in this file
2. **Report issues** in GitHub issues or project tracker
3. **Consider Phase 5**: Incremental re-indexing optimization
4. **Plan enhancements**: Based on real-world usage patterns

## Reference Commands

Quick reference for common operations:

```bash
# Initialize
uv run python -m krag.cli init

# Check status
uv run python -m krag.cli status

# Index (dry-run)
uv run python -m krag.cli index --dir /path --dry-run

# Index (full)
uv run python -m krag.cli index --dir /path

# Index (incremental)
uv run python -m krag.cli index --dir /path --incremental

# Query
uv run python -m krag.cli query "search text" \
    --config ~/.krag/config.yaml \
    --no-synthesis \
    --show-sources

# Config management
uv run python -m krag.cli config show
uv run python -m krag.cli config validate
uv run python -m krag.cli config edit
```

---

**For Questions or Issues**: Check the main README.md or project documentation
