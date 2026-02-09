"""Plugin system for file type handlers.

This package provides a plugin architecture for extending krag with custom file type
handlers. Plugins can extract text from specialized file formats (PDF, DOCX, etc.)
and integrate seamlessly into the indexing pipeline.

Key Components:
    - FileTypeHandler: Abstract base class for file type plugins
    - PluginRegistry: Manages plugin discovery, loading, and lifecycle
    - PluginContext: Provides plugins with access to krag services
    - ChunkingStrategy: Defines available chunking approaches

Example Usage:
    >>> from krag.plugins import FileTypeHandler, PluginRegistry
    >>> registry = PluginRegistry(config)
    >>> handler = registry.get_handler_for_extension('.pdf')
    >>> text = handler.extract_text(Path('/docs/manual.pdf'))
"""

from krag.models.configuration import PluginConfiguration, PluginMetadata
from krag.plugins.context import PluginContext
from krag.plugins.exceptions import (
    PluginAPIVersionError,
    PluginConfigurationError,
    PluginDependencyError,
    PluginDisabledError,
    PluginError,
    PluginExtractionError,
    PluginLoadError,
    PluginNotFoundError,
)
from krag.plugins.failures import IndexingFailureCollector
from krag.plugins.interfaces import ChunkingStrategy, FileTypeHandler
from krag.plugins.loader import PluginLoader
from krag.plugins.registry import PLUGIN_API_VERSION, PluginRegistry

__all__ = [
    "FileTypeHandler",
    "ChunkingStrategy",
    "PluginMetadata",
    "PluginConfiguration",
    "PluginContext",
    "PluginRegistry",
    "PluginLoader",
    "IndexingFailureCollector",
    "PLUGIN_API_VERSION",
    "PluginError",
    "PluginExtractionError",
    "PluginConfigurationError",
    "PluginDisabledError",
    "PluginNotFoundError",
    "PluginLoadError",
    "PluginAPIVersionError",
    "PluginDependencyError",
]
