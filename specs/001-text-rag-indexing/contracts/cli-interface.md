# CLI Interface Contract

**Feature**: Text-Based RAG Indexing & Retrieval System  
**Interface Type**: Command Line Interface (Typer-based)  
**Version**: 1.0.0

## Overview

The krag CLI provides commands for indexing personal files and querying the indexed knowledge base. All commands follow consistent patterns for configuration, output formatting, and error handling.

---

## Global Options

Available for all commands:

```
--config PATH          Path to configuration file (default: ~/.krag/config.toml)
--verbose, -v          Enable verbose logging (INFO level)
--debug                Enable debug logging (DEBUG level)
--quiet, -q            Suppress all output except errors
--help                 Show help message and exit
```

---

## Commands

### 1. `krag init`

Initialize krag configuration and storage.

**Usage**:
```bash
krag init [OPTIONS]
```

**Options**:
```
--config-dir PATH      Directory for configuration (default: ~/.krag)
--storage-dir PATH     Directory for vector storage (default: ~/.krag/storage)
--force                Overwrite existing configuration
```

**Behavior**:
1. Create configuration directory if it doesn't exist
2. Generate default config.toml with reasonable defaults
3. Initialize empty vector store
4. Create metadata database
5. Display configuration location and next steps

**Output (Success)**:
```
✓ Configuration initialized at /home/user/.krag/config.toml
✓ Vector store created at /home/user/.krag/storage
✓ Metadata database created

Next steps:
  1. Edit /home/user/.krag/config.toml to configure directories
  2. Run 'krag index' to start indexing your files
```

**Exit Codes**:
- 0: Success
- 1: Configuration already exists (use --force to overwrite)
- 2: Permission denied creating directories

---

### 2. `krag index`

Index files from configured directories.

**Usage**:
```bash
krag index [OPTIONS]
```

**Options**:
```
--full                 Force full re-index (ignore modification times)
--incremental          Incremental update only (default behavior)
--dry-run              Show what would be indexed without processing
--max-files INT        Limit number of files to process (for testing)
--parallel             Enable parallel processing (experimental)
```

**Behavior**:
1. Load configuration
2. Discover files from configured directories
3. Apply exclusion patterns
4. Determine which files need indexing (new or modified)
5. Extract text and chunk content
6. Generate embeddings in batches
7. Store embeddings in vector database
8. Update metadata store
9. Display progress and summary

**Output (Progress)**:
```
Discovering files...
Found 1,247 files across 2 directories
Applying exclusion patterns...
524 files excluded, 723 files to process

Indexing files... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 723/723 100% 0:05:12
  - Processed: 720 files
  - Skipped: 3 files (already indexed, no changes)
  - Errors: 0 files

Generating embeddings... ━━━━━━━━━━━━━━━━━━━━━ 8,456/8,456 100% 0:02:34
  - Chunks created: 8,456
  - Embeddings generated: 8,456
  - Batch size: 32

Storing in vector database... ━━━━━━━━━━━━━━━━━━ 8,456/8,456 100% 0:00:42

✓ Indexing complete
  Total time: 8 minutes 28 seconds
  Files indexed: 720
  Chunks generated: 8,456
  Vector store size: 3.2 GB
```

**Output (Errors)**:
```
⚠ Errors encountered (3 files):
  - /path/to/corrupt.txt: UnicodeDecodeError
  - /path/to/huge.log: File exceeds size limit (512 MB > 100 MB)
  - /path/to/locked.db: Permission denied

Run with --verbose to see full error details
```

**Exit Codes**:
- 0: Success (all files processed or skipped)
- 1: Partial success (some files errored, but indexing completed)
- 2: Fatal error (configuration invalid, storage unavailable)

---

### 3. `krag query`

Query the indexed knowledge base.

**Usage**:
```bash
krag query [OPTIONS] QUERY_TEXT
```

**Arguments**:
```
QUERY_TEXT             Natural language query (required)
```

**Options**:
```
--top-k INT            Number of chunks to retrieve (default: 5)
--no-synthesis         Return retrieved chunks without LLM synthesis
--show-sources         Display source files for retrieved chunks
--format FORMAT        Output format: text, json (default: text)
```

**Behavior**:
1. Load configuration and models
2. Generate embedding for query text
3. Search vector store for top-k similar chunks
4. Retrieve chunk content and metadata
5. If synthesis enabled:
   - Construct prompt with query and retrieved chunks
   - Generate answer using local LLM
   - Stream response to stdout
6. Display sources if requested

**Output (Text Format with Synthesis)**:
```
Query: "How do I configure the authentication middleware?"

Answer:
The authentication middleware can be configured in the config.yaml file under the 
'auth' section. You need to specify the authentication method (JWT or OAuth2) and 
provide the corresponding secrets. For JWT, set the 'jwt_secret' and 'jwt_algorithm' 
parameters. The middleware will automatically validate tokens on all protected routes.

Here's an example configuration:
auth:
  method: jwt
  jwt_secret: your-secret-key
  jwt_algorithm: HS256
  token_expiry: 3600

Sources:
  - docs/configuration.md (lines 45-67)
  - src/middleware/auth.py (lines 12-34)
  - examples/config.yaml (lines 8-15)
```

**Output (JSON Format)**:
```json
{
  "query": "How do I configure the authentication middleware?",
  "answer": "The authentication middleware can be configured...",
  "sources": [
    {
      "file_path": "docs/configuration.md",
      "chunk_index": 2,
      "score": 0.87,
      "content": "# Authentication Configuration\n\nThe auth middleware..."
    },
    {
      "file_path": "src/middleware/auth.py",
      "chunk_index": 0,
      "score": 0.82,
      "content": "class AuthMiddleware:\n    \"\"\"Middleware for authentication...\""
    }
  ],
  "retrieval_time_ms": 145,
  "synthesis_time_ms": 2834,
  "total_time_ms": 2979
}
```

**Output (No Synthesis)**:
```
Query: "How do I configure the authentication middleware?"

Retrieved 5 relevant chunks:

[1] docs/configuration.md (score: 0.87)
# Authentication Configuration

The auth middleware supports JWT and OAuth2 authentication...

[2] src/middleware/auth.py (score: 0.82)
class AuthMiddleware:
    """Middleware for authentication and authorization."""
    ...

[3] examples/config.yaml (score: 0.78)
auth:
  method: jwt
  jwt_secret: your-secret-key
  ...
```

**Exit Codes**:
- 0: Success (answer generated)
- 1: No relevant results found
- 2: Error (models not loaded, vector store unavailable)

---

### 4. `krag status`

Display system status and statistics.

**Usage**:
```bash
krag status [OPTIONS]
```

**Options**:
```
--format FORMAT        Output format: text, json (default: text)
```

**Output (Text Format)**:
```
krag Status
───────────────────────────────────────────────────────

Configuration:
  Config file: /home/user/.krag/config.toml
  Storage path: /home/user/.krag/storage
  Indexed directories: 2
    - /home/user/documents
    - /mnt/nas/projects

Index Statistics:
  Total files indexed: 1,247
  Total chunks: 15,683
  Total embeddings: 15,683
  Vector store size: 4.2 GB
  Last indexed: 2026-02-03 14:32:15

Models:
  Embedding model: all-MiniLM-L6-v2 (384 dimensions)
  LLM model: mistral-7b-instruct-v0.2.Q4_K_M.gguf
  LLM context size: 2048 tokens

Recent Indexing Jobs:
  [2026-02-03 14:32:15] COMPLETED - Full index (1,247 files, 8m 28s)
  [2026-02-02 09:15:42] COMPLETED - Incremental (23 files, 0m 45s)
  [2026-02-01 16:20:11] COMPLETED - Full index (1,224 files, 8m 12s)
```

**Exit Codes**:
- 0: Success
- 2: Configuration not found or storage unavailable

---

### 5. `krag config`

Display or validate configuration.

**Usage**:
```bash
krag config [OPTIONS] [COMMAND]
```

**Commands**:
```
show                   Display current configuration
validate               Validate configuration file
edit                   Open configuration in default editor
```

**Options**:
```
--format FORMAT        Output format: text, toml, json (default: text)
```

**Output (show)**:
```toml
[directories]
paths = ["/home/user/documents", "/mnt/nas/projects"]

[exclusion]
patterns = ["node_modules", ".git", "__pycache__", "build", "dist"]

[embedding]
model = "all-MiniLM-L6-v2"
batch_size = 32
device = "cpu"

[chunking]
size = 512
overlap = 50

[retrieval]
top_k = 5

[llm]
model_path = "/home/user/.models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
n_ctx = 2048
n_threads = 4
temperature = 0.7
```

**Output (validate)**:
```
✓ Configuration is valid
✓ All directory paths exist and are readable
✓ Embedding model available
✓ LLM model file exists
✓ All settings within valid ranges
```

**Exit Codes**:
- 0: Success (configuration valid)
- 1: Configuration invalid (with error details)

---

### 6. `krag reset`

Reset vector store and metadata (destructive operation).

**Usage**:
```bash
krag reset [OPTIONS]
```

**Options**:
```
--confirm              Skip confirmation prompt
--keep-config          Reset data but keep configuration
```

**Behavior**:
1. Prompt for confirmation (unless --confirm)
2. Delete vector store contents
3. Delete metadata database
4. Optionally delete configuration (unless --keep-config)

**Output**:
```
⚠ WARNING: This will delete all indexed data!

  Vector store: /home/user/.krag/storage (4.2 GB)
  Metadata: /home/user/.krag/metadata.db
  Configuration: /home/user/.krag/config.toml (preserved with --keep-config)

Are you sure you want to continue? [y/N]: y

Deleting vector store...
Deleting metadata database...
✓ Reset complete
```

**Exit Codes**:
- 0: Success
- 1: User cancelled operation
- 2: Error during deletion

---

## Error Handling

### Common Error Patterns

**Configuration Not Found**:
```
Error: Configuration not found at /home/user/.krag/config.toml

Run 'krag init' to create a new configuration.
```

**Invalid Configuration**:
```
Error: Invalid configuration in /home/user/.krag/config.toml

  - directories.paths: At least one directory path required
  - llm.model_path: File does not exist: /path/to/missing-model.gguf

Fix the errors and try again.
```

**Storage Unavailable**:
```
Error: Cannot access vector store at /home/user/.krag/storage

  Reason: Permission denied

Check directory permissions or run with elevated privileges.
```

**Model Loading Failed**:
```
Error: Failed to load embedding model 'all-MiniLM-L6-v2'

  Reason: Network connection required for first-time download

Ensure internet connection is available for model download.
```

---

## Environment Variables

```
KRAG_CONFIG_PATH       Override default config file location
KRAG_STORAGE_PATH      Override default storage location
KRAG_LOG_LEVEL         Set logging level (DEBUG, INFO, WARNING, ERROR)
KRAG_NO_PROGRESS       Disable progress bars (useful for CI)
```

---

## Exit Code Summary

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Partial success or user cancellation |
| 2 | Fatal error (configuration, storage, models) |
| 3 | Invalid arguments or command usage |

---

## Progress Indicators

All long-running operations display:
- Progress bar with percentage
- Items processed / total items
- Elapsed time
- Estimated time remaining (when available)

Progress can be disabled with `KRAG_NO_PROGRESS=1` or `--quiet` flag.

---

## Logging

Logs written to:
- Console: Formatted output based on verbosity level
- File: `~/.krag/logs/krag.log` (rotated daily, kept for 7 days)

Log levels:
- Default: WARNING and ERROR only
- `--verbose`: INFO, WARNING, ERROR
- `--debug`: All levels including DEBUG
