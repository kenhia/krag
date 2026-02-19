# Contract: Log Management CLI

**Module**: `src/krag/cli/log.py`
**Parent**: `krag log` subcommand group in `cli/main.py`

## Commands

### `krag log rotate`

```python
def rotate() -> None:
    """Archive the current log file and start fresh.

    Behavior:
        - Shifts existing backups: krag.log.4 → krag.log.5, ..., krag.log → krag.log.1
        - Creates new empty krag.log
        - If no log file exists, creates parent dirs + empty file
        - Maximum 5 backup files (consistent with RotatingFileHandler config)

    Output:
        - Prints path of archived log file on success
        - Prints "No log file to rotate" if file doesn't exist
    """
```

### `krag log clear`

```python
def clear() -> None:
    """Truncate the current log file to zero bytes.

    Behavior:
        - Opens log file in write mode (truncates)
        - If no log file exists, no-op with message
        - Safe for concurrent access on POSIX (truncate is atomic)

    Output:
        - Prints "Log cleared: {path}" on success
        - Prints "No log file found" if file doesn't exist
    """
```

### `krag log path`

```python
def path() -> None:
    """Print the absolute path to the current log file.

    Behavior:
        - Resolves via get_krag_state_dir() / "logs" / "krag.log"
        - Prints path regardless of whether file exists
        - Appends "(exists)" or "(not found)" suffix

    Output:
        - e.g., "/home/user/.local/state/krag/logs/krag.log (exists)"
    """
```

## Log Path Resolution

Reuses existing `get_krag_state_dir()` from `krag.config.xdg`:

```python
def get_log_file_path() -> Path:
    """Return the canonical log file path."""
    return get_krag_state_dir() / "logs" / "krag.log"
```
