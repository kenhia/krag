# Quickstart: 007-service-architecture

**Date**: 2026-02-19
**Spec**: [spec.md](spec.md)
**Contracts**: [contracts/openapi.yaml](contracts/openapi.yaml)

---

## Prerequisites

- Python 3.11+
- `uv` for dependency management
- Existing krag configuration (`~/.config/krag/config.toml`)
- At least one LLM model downloaded
- Indexed vector store (run `krag-direct index` first if needed)

## Installation

After implementing sprint 007, install from the repo root:

```bash
uv pip install -e ".[dev]"
```

This installs three entry points:
- `kragd` — the service daemon
- `krag` — the CLI client (talks to kragd)
- `krag-direct` — the original in-process CLI (unchanged)

## Starting the Service

### Foreground (development)

```bash
kragd
```

The service starts, loads the primary LLM, and logs to stdout:

```
kragd v0.1.0 starting...
Loading configuration from ~/.config/krag/config.toml
Loading embedding model: BAAI/bge-base-en-v1.5 ✓ (1.2s)
Opening vector store: ~/.cache/krag/storage ✓
Loading primary LLM (text): qwen2.5-7b-instruct-q4_k_m.gguf ✓ (3.4s)
kragd ready at http://0.0.0.0:8742
PID file: /run/user/1000/kragd.pid
API docs: http://0.0.0.0:8742/docs
```

### Background (daemon mode)

```bash
kragd --daemon
```

### With custom host/port

```bash
kragd --host 127.0.0.1 --port 9000
```

### Development (auto-reload)

```bash
kragd --reload
```

## Using the CLI Client

Once kragd is running, use `krag` as before:

### Query

```bash
# Standard query (same as before, now uses service)
krag query "How does the plugin system work?"

# With options
krag query "What GPU functions are available?" --top-k 10 --preset concise

# Retrieval only (no LLM synthesis)
krag query "plugin architecture" --no-synthesis
```

### Indexing

```bash
# Incremental index (default)
krag index

# Full reindex
krag index --full

# Dry run
krag index --dry-run

# Specific directory
krag index --dir /home/ken/projects/myproject
```

### Debug

```bash
# Query with full debug metadata
krag debug query "How does the plugin system work?"

# Raw Qdrant search (bypass retrieval pipeline)
krag debug qdrant "plugin architecture" --space text --top-k 20

# Raw Qdrant with filters
krag debug qdrant "plugin" --filter-type code --filter-path "plugins"
```

### Service Management

```bash
# Check service status (loaded models, VRAM, uptime)
krag status

# Quick health check
krag health

# Stop the service
krag stop
```

## Direct Mode (No Service)

The original CLI is preserved as `krag-direct`:

```bash
# Works exactly like the pre-service CLI
krag-direct query "How does the plugin system work?"
krag-direct index --full
```

## Configuration

Add a `[service]` section to your existing `config.toml`:

```toml
[service]
host = "0.0.0.0"           # Bind to all interfaces (LAN access)
port = 8742                 # Default port
primary_llm = "text"        # Keep text LLM loaded permanently
idle_timeout = 300           # Unload secondary LLM after 5 min idle
log_requests = true          # Log API requests
```

All fields are optional — the service works without any `[service]` configuration using the defaults shown above.

### Remote Access

To query from another machine on your network:

1. Ensure kragd binds to `0.0.0.0` (default)
2. On the remote machine, set the server address in `config.toml`:

```toml
[service]
host = "192.168.1.100"      # IP of the machine running kragd
port = 8742
```

Or use environment variables:

```bash
KRAGD_HOST=192.168.1.100 krag query "..."
```

## API Documentation

While kragd is running, interactive API docs are available at:

- **Swagger UI**: http://0.0.0.0:8742/docs
- **ReDoc**: http://0.0.0.0:8742/redoc
- **OpenAPI JSON**: http://0.0.0.0:8742/openapi.json

## Verifying the Setup

After starting kragd, verify everything works:

```bash
# 1. Health check
krag health
# Expected: "healthy"

# 2. Status
krag status
# Expected: Shows loaded models, VRAM, vector store stats

# 3. Query
krag query "What is krag?"
# Expected: Synthesized answer with sources (< 2s for second query)

# 4. Debug
krag debug query "What is krag?"
# Expected: Answer + 10+ debug metadata fields
```

## Development Workflow

### Running Tests

```bash
# All tests (including new service tests)
uv run pytest

# Service tests only
uv run pytest tests/unit/kragd/ tests/unit/krag_cli/ tests/integration/service/

# With coverage
uv run pytest --cov=kragd --cov=krag_cli
```

### Pre-Commit Checklist

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pytest
```

All three must pass before committing.

### Testing Without a Running Service

Use FastAPI's TestClient for integration tests:

```python
from fastapi.testclient import TestClient
from kragd.app import create_app

app = create_app(config_path=test_config_path)
client = TestClient(app)

response = client.post("/query", json={"query": "test"})
assert response.status_code == 200
```
