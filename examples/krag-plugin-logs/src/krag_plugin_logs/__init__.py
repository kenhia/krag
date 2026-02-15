"""krag plugin for indexing log files with timestamp-based chunking.

This plugin provides support for indexing log files (.log) with a custom chunking
strategy that groups log entries by time windows for better temporal coherence.
"""

from krag_plugin_logs.handler import LogFileHandler

__version__ = "1.0.0"
__all__ = ["LogFileHandler"]
