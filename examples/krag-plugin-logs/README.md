# krag Log Files Plugin

A file type plugin for krag that provides indexing support for log files (.log) with intelligent timestamp-based chunking.

## Features

- **Log Entry Parsing**: Extracts structured log entries with timestamp detection
- **Custom Chunking**: Groups log entries by configurable time windows (default: 5 minutes)
- **Metadata Extraction**: Logs statistics (entry count, time range, log levels)
- **Flexible Formats**: Supports common log formats (syslog, application logs, etc.)

## Installation

### Development Mode

```bash
# From the plugin directory
uv pip install -e .
```

### From Source

```bash
pip install git+https://github.com/yourusername/krag-plugin-logs.git
```

### From PyPI (when published)

```bash
pip install krag-plugin-logs
```

## Usage

Once installed, the plugin is automatically discovered by krag. Log files (.log) will be indexed automatically with timestamp-based chunking:

```bash
krag index /var/log/application
```

## Supported Formats

- `.log` - Log files with timestamped entries

## Custom Chunking Strategy

This plugin demonstrates **custom chunking** by implementing a `LogFileChunker` that:

1. **Detects timestamps** in log entries (ISO 8601, common formats)
2. **Groups entries by time windows** (configurable, default 5 minutes)
3. **Preserves log entry boundaries** (never splits mid-entry)
4. **Maintains temporal coherence** for better semantic search

### Why Custom Chunking?

Log files benefit from timestamp-based chunking because:
- Related log entries (within a time window) stay together
- Debugging workflows often involve time-based queries
- Semantic search can find "what happened around timestamp X"
- Each chunk has a well-defined time range for metadata

### Example

```log
2024-02-11 10:00:15 INFO Application started
2024-02-11 10:00:20 INFO Database connected
2024-02-11 10:00:25 INFO Cache initialized
---chunk boundary (5 min window)---
2024-02-11 10:05:30 WARN Cache miss for key: user_123
2024-02-11 10:05:35 ERROR Database timeout
```

## Metadata Extraction

The plugin extracts rich metadata from log files:

- `entry_count`: Number of log entries
- `time_range_start`: Timestamp of first entry
- `time_range_end`: Timestamp of last entry
- `log_levels`: Count of each log level (INFO, WARN, ERROR, etc.)
- `source`: Log file identifier or application name

## Configuration

The plugin supports configuration through krag's plugin config:

```yaml
plugins:
  logs:
    config:
      chunk_window_minutes: 5    # Time window for chunking (default: 5)
      max_entries_per_chunk: 100 # Max entries in a chunk (default: 100)
      timestamp_formats:          # Supported timestamp formats
        - "%Y-%m-%d %H:%M:%S"
        - "%Y-%m-%dT%H:%M:%S"
```

## Development

### Running Tests

```bash
uv run pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .
```

## Architecture

This plugin demonstrates **advanced plugin architecture**:

- **Custom Chunker**: `LogFileChunker` extends `TextChunker` from krag
- **Timestamp Parsing**: Intelligent detection of various timestamp formats
- **Configurable Behavior**: Time windows and chunk sizes via config schema
- **Metadata Aggregation**: Statistics computed during text extraction

Compare with `krag-plugin-markdown` for simpler use cases with default chunking.

## License

MIT
